"""Small process-safe transport worker; network calls happen outside DB transactions."""
from __future__ import annotations

import threading
from collections.abc import Callable
from sqlalchemy.orm import Session, sessionmaker
from app.services.sync_transport_service import SyncTransportService

class SyncTransportWorker:
    def __init__(self, session_factory: sessionmaker, *, peer_device_uuid, channel: str,
                 publisher_device_uuid, publisher_generation_uuid, publisher_clinic_uuid,
                 sender: Callable[[list[dict]], None], batch_size: int = 100,
                 after_claim: Callable[[list[dict]], None] | None = None,
                 before_send: Callable[[list[dict]], None] | None = None,
                 proof_capability_negotiator: Callable[[], str] | None = None,
                 proof_sender: Callable[[list[dict]], None] | None = None,
                 pending_proof_loader: Callable[[], list[dict]] | None = None,
                 after_application_business_commit: Callable[[object], None] | None = None,
                 before_medical_visit_business_apply: Callable[[object], None] | None = None):
        self.session_factory = session_factory
        self.peer_device_uuid = peer_device_uuid
        self.channel = channel
        self.publisher_device_uuid = publisher_device_uuid
        self.publisher_generation_uuid = publisher_generation_uuid
        self.publisher_clinic_uuid = publisher_clinic_uuid
        self.sender = sender
        self.batch_size = batch_size
        self.after_claim = after_claim
        self.before_send = before_send
        self.proof_capability_negotiator = proof_capability_negotiator
        self.proof_sender = proof_sender
        self.pending_proof_loader = pending_proof_loader
        self.application_enabled = False
        self.after_application_business_commit = after_application_business_commit
        self.before_medical_visit_business_apply = before_medical_visit_business_apply
        self._stop = threading.Event()
        self.service = SyncTransportService()

    def run_once(self) -> int:
        with self.session_factory() as db:  # claim commits before sender is called
            events = self.service.claim_batch(db, peer_device_uuid=self.peer_device_uuid,
                                              channel=self.channel, limit=self.batch_size,
                                              publisher_device_uuid=self.publisher_device_uuid,
                                              publisher_generation_uuid=self.publisher_generation_uuid,
                                              publisher_clinic_uuid=self.publisher_clinic_uuid)
        if not events:
            if self.pending_proof_loader is not None and self.proof_sender is not None:
                pending = self.pending_proof_loader()
                decision = self.proof_capability_negotiator() if self.proof_capability_negotiator is not None else "negotiation_failed"
                print(f"worker proof_capability_decision={decision}", flush=True)
                if pending and decision == "supported":
                    self.proof_sender(pending)
            return 0
        if self.after_claim is not None:
            self.after_claim(events)
        try:
            if self.proof_capability_negotiator is not None:
                decision = self.proof_capability_negotiator()
                print(f"worker proof_capability_decision={decision}", flush=True)
                if decision == "supported" and self.proof_sender is not None:
                    self.proof_sender(events)
            if self.before_send is not None:
                self.before_send(events)
            self.sender(events)
        except Exception as exc:
            permanent = exc.__class__.__name__ in {"ConflictException", "ForbiddenException", "UnauthorizedException"} or getattr(getattr(exc, "response", None), "status_code", 0) in {400, 401, 403, 409, 422}
            detail = getattr(getattr(exc, "__cause__", None), "detail", None) or getattr(exc, "detail", None)
            structured_code = detail.get("details", {}).get("error_code") if isinstance(detail, dict) else None
            is_revoked = "RELAY_AUTHORIZATION_REVOKED" in str(exc) or structured_code == "SYNC_RELAY_NOT_AUTHORIZED"
            configuration = structured_code in {'SYNC_DEVICE_NOT_FOUND', 'SYNC_DEVICE_AUTH_REQUIRED', 'SYNC_DEVICE_AUTH_INVALID'}
            classification = 'RELAY_AUTHORIZATION_REVOKED' if is_revoked else ('TRANSPORT_CONFIGURATION' if configuration else ('TRANSPORT_PERMANENT' if permanent else 'NETWORK_TEMPORARY'))
            print(f"worker stage=classify exception_type={type(exc).__name__} cause_type={type(exc.__cause__).__name__ if exc.__cause__ else 'none'} structured_code={structured_code or 'none'} classification={classification}", flush=True)
            with self.session_factory() as db:
                for event in events:
                    self.service.record_failure(db, event_uuid=event["event_uuid"],
                                                peer_device_uuid=self.peer_device_uuid,
                                                channel=self.channel, error_code=("RELAY_AUTHORIZATION_REVOKED" if is_revoked else ("TRANSPORT_CONFIGURATION" if configuration else ("TRANSPORT_PERMANENT" if permanent else "NETWORK_TEMPORARY"))),
                                                error_message=type(exc).__name__, permanent=(permanent or is_revoked))
            return 0
        # The sender owns the HTTP ACK. Do not acknowledge locally a second time;
        # the source API is the single writer of delivery state.
        return len(events)

    def stop(self) -> None:
        self._stop.set()

    def run_application_once(self, *, limit: int = 1, event_uuid=None) -> int:
        """Run the receiver-side durable inbox consumer from the worker entry point."""
        with self.session_factory() as db:
            result = self.service.apply_inbox_once(db, limit=limit, event_uuid=event_uuid, after_business_commit=self.after_application_business_commit, before_business_apply=self.before_medical_visit_business_apply)
        return int(result.get("applied", 0))

    def run_forever(self, interval_seconds: float = 1.0) -> None:
        while not self._stop.is_set():
            if self.application_enabled:
                self.run_application_once(limit=self.batch_size)
            self.run_once()
            self._stop.wait(interval_seconds)
