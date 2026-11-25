"""Durable stage-four event transport. It never applies inbox payloads to business tables."""
from __future__ import annotations

import hashlib
import json
import logging
import inspect
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select, update, text, func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.exceptions import ConflictException, ForbiddenException, NotFoundException
from app.models.sync_change import SyncChange
from app.models.sync_device import SyncDevice
from app.models.sync_transport import SyncEventDelivery, SyncEventInbox, SyncTransportEvent, SyncRelayAuthorization, SyncTransportAttempt, SyncTransportCursor, SyncPublicationCounter, SyncEventPublication, SyncPublicationReceipt
from app.services.sync_journal import payload_sha256

TRANSPORT_SCHEMA_VERSION = 1
CHANNEL_MOBILE = "mobile_server"
CHANNEL_CENTRAL = "central_server"
DELIVERY_LEASE_SECONDS = 30


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _event_hash(event: dict[str, Any]) -> str:
    body = {
        "event_uuid": str(event["event_uuid"]), "source_clinic_uuid": str(event["source_clinic_uuid"]),
        "source_device_uuid": str(event["source_device_uuid"]), "source_generation_uuid": str(event["source_generation_uuid"]),
        "source_sequence": int(event["source_sequence"]), "entity_type": event["entity_type"],
        "entity_uuid": str(event["entity_uuid"]), "revision_uuid": str(event["revision_uuid"]) if event.get("revision_uuid") else None,
        "parent_revision_uuid": str(event["parent_revision_uuid"]) if event.get("parent_revision_uuid") else None,
        "operation": event["operation"], "schema_version": int(event["schema_version"]), "payload": event["payload"],
    }
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()


class SyncTransportService:
    def _authorize_medical_visit_inbox(self, db: Session, row: SyncEventInbox):
        """Validate business delegation immediately before the first visit write."""
        from app.models.local_revision import LocalRevision
        prior = db.scalar(select(LocalRevision).where(
            LocalRevision.entity_type == "medical_visits",
            LocalRevision.entity_uuid == row.entity_uuid,
            LocalRevision.revision_uuid == row.revision_uuid,
        ))
        if prior is not None:
            return {"status": "already_applied", "revision_uuid": str(prior.revision_uuid)}
        from app.models.origin_proof_transport import OriginProofTransportReceipt
        receipt = db.scalar(select(OriginProofTransportReceipt).where(
            OriginProofTransportReceipt.event_uuid == row.event_uuid,
        ).order_by(OriginProofTransportReceipt.id.desc()))
        if receipt is None:
            raise ValueError("BUSINESS_AUTHORIZATION_EVIDENCE_MISSING")
        proof = dict(receipt.proof or {})
        delegation_ref = proof.get("authorization_reference")
        if not delegation_ref:
            raise ValueError("BUSINESS_DELEGATION_REFERENCE_MISSING")
        from app.models.proof_trust import ProofDelegation, ProofTrustedKey
        delegation = db.scalar(select(ProofDelegation).where(
            ProofDelegation.delegation_uuid == uuid.UUID(str(delegation_ref))
        ).execution_options(populate_existing=True).with_for_update())
        if delegation is None or delegation.state != "active":
            raise ValueError("DELEGATION_REVOKED")
        from app.services.proof_verification_service import (
            validate_required_fields, verify_binding, verify_delegation_scope,
            verify_key_scope, verify_signature,
        )
        if validate_required_fields(proof) != "valid":
            raise ValueError("BUSINESS_PROOF_INVALID")
        if verify_binding(proof, event_uuid=row.event_uuid,
                content_sha256=row.content_sha256, clinic_uuid=row.source_clinic_uuid,
                entity_type=row.entity_type, entity_uuid=row.entity_uuid,
                revision_uuid=row.revision_uuid, operation=row.operation) != "valid":
            raise ValueError("BUSINESS_PROOF_EVENT_BINDING_INVALID")
        key = db.get(ProofTrustedKey, proof.get("signing_key_id"))
        if key is None or verify_signature(proof, key.public_key) != "valid":
            raise ValueError("BUSINESS_PROOF_SIGNATURE_INVALID")
        origin_service = uuid.UUID(str(proof.get("origin_service_uuid")))
        origin_device = uuid.UUID(str(proof.get("origin_device_uuid")))
        if verify_key_scope(proof, key, clinic_uuid=row.source_clinic_uuid,
                origin_service_uuid=origin_service, origin_device_uuid=origin_device) != "valid":
            raise ValueError("BUSINESS_PROOF_KEY_SCOPE_INVALID")
        if verify_delegation_scope(proof, delegation,
                clinic_uuid=row.source_clinic_uuid, origin_service_uuid=origin_service,
                user_uuid=uuid.UUID(str(proof.get("origin_user_uuid"))),
                entity_type=row.entity_type, operation=row.operation,
                policy_version=proof.get("authorization_policy_version")) != "valid":
            raise ValueError("BUSINESS_DELEGATION_SCOPE_INVALID")
        return {"status": "authorized", "delegation_uuid": str(delegation.delegation_uuid)}

    def claim_inbox_application(self, db: Session, *, limit: int = 1, lease_seconds: int = 30, event_uuid: uuid.UUID | None = None) -> list[SyncEventInbox]:
        """Claim durable received events; the claim commits before business work."""
        now = _now()
        # Missing evidence is reconsidered only when a receipt for the exact
        # event has arrived. Revoked delegations remain blocked permanently.
        from app.models.origin_proof_transport import OriginProofTransportReceipt
        recoverable = select(OriginProofTransportReceipt.id).where(
            OriginProofTransportReceipt.event_uuid == SyncEventInbox.event_uuid
        ).exists()
        db.execute(update(SyncEventInbox).where(
            SyncEventInbox.status == "blocked_authorization",
            SyncEventInbox.application_error_code == "BUSINESS_AUTHORIZATION_EVIDENCE_MISSING",
            recoverable,
        ).values(status="received_waiting_application", application_error_code=None, application_error_message=None))
        db.flush()
        criteria = [
            (SyncEventInbox.status == "received_waiting_application") |
            ((SyncEventInbox.status == "applying") & (SyncEventInbox.application_lease_expires_at < now)),
        ]
        if event_uuid is not None: criteria.append(SyncEventInbox.event_uuid == event_uuid)
        rows = db.scalars(select(SyncEventInbox).where(*criteria).order_by(SyncEventInbox.received_at).with_for_update(skip_locked=True).limit(limit)).all()
        for row in rows:
            row.status = "applying"
            row.application_attempt_count = int(row.application_attempt_count or 0) + 1
            row.application_lease_uuid = uuid.uuid4()
            row.application_lease_expires_at = now + timedelta(seconds=lease_seconds)
        db.commit()
        return rows

    def apply_inbox_once(self, db: Session, *, limit: int = 1, lease_seconds: int = 30, event_uuid: uuid.UUID | None = None, after_business_commit=None, before_business_apply=None) -> dict[str, int]:
        """Apply claimed inbox rows through the shared internal entity appliers.

        Receipt/ACK remains independent: a received row is durable before this
        consumer runs. A failed application returns the row to the durable
        waiting state and never acknowledges the sender.
        """
        from types import SimpleNamespace
        from app.services.entity_application_service import apply_worker_entity, apply_worker_update_entity, apply_medical_visit_entity, apply_medical_visit_update_entity
        claimed = self.claim_inbox_application(db, limit=limit, lease_seconds=lease_seconds, event_uuid=event_uuid)
        applied = failed = 0
        for row in claimed:
            try:
                event = SimpleNamespace(event_uuid=row.event_uuid, source_clinic_uuid=row.source_clinic_uuid,
                    source_device_uuid=row.source_device_uuid, source_generation_uuid=row.source_generation_uuid,
                    source_sequence=row.source_sequence, entity_type=row.entity_type, entity_uuid=row.entity_uuid,
                    revision_uuid=row.revision_uuid, parent_revision_uuid=row.parent_revision_uuid,
                    operation=row.operation, schema_version=row.schema_version, content_sha256=row.content_sha256,
                    payload=row.payload, operation_uuid=(row.payload or {}).get("operation_uuid"),
                    base_version=(row.payload or {}).get("base_version"))
                if row.entity_type == "workers" and row.operation in ("insert", "create"):
                    apply_worker_entity(db, event)
                elif row.entity_type == "workers" and row.operation == "update":
                    apply_worker_update_entity(db, event)
                elif row.entity_type == "medical_visits" and row.operation in ("insert", "create"):
                    apply_medical_visit_entity(db, event)
                elif row.entity_type == "medical_visits" and row.operation == "update":
                    self._authorize_medical_visit_inbox(db, row)
                    if before_business_apply is not None:
                        before_business_apply(row)
                    apply_medical_visit_update_entity(db, event)
                else:
                    raise ValueError("INBOX_ENTITY_OPERATION_UNSUPPORTED")
                # Application primitives own their business commit. Ensure no
                # implicit ORM transaction remains while the test/recovery hook
                # coordinates the separate inbox-finalization commit.
                if db.in_transaction():
                    db.commit()
                if after_business_commit is not None:
                    after_business_commit(row)
                with db.begin():
                    current = db.scalar(select(SyncEventInbox).where(SyncEventInbox.id == row.id).with_for_update())
                    if current is None or current.application_lease_uuid != row.application_lease_uuid:
                        raise ConflictException("INBOX_APPLICATION_LEASE_LOST")
                    current.status = "applied"; current.applied_at = _now(); current.application_lease_uuid = None; current.application_lease_expires_at = None; current.application_error_code = None; current.application_error_message = None
                applied += 1
            except Exception as exc:
                db.rollback()
                with db.begin():
                    current = db.scalar(select(SyncEventInbox).where(SyncEventInbox.id == row.id).with_for_update())
                    # A stale owner must never overwrite a newer owner's
                    # applied result or lease. Only the owner holding the
                    # exact lease may return its row to retryable state.
                    if current is not None and current.status == "applying" and current.application_lease_uuid == row.application_lease_uuid:
                        reason = str(exc)
                        permanent_auth = reason in {"DELEGATION_REVOKED", "BUSINESS_AUTHORIZATION_EVIDENCE_MISSING", "BUSINESS_DELEGATION_REFERENCE_MISSING", "BUSINESS_PROOF_INVALID", "BUSINESS_PROOF_EVENT_BINDING_INVALID", "BUSINESS_PROOF_SIGNATURE_INVALID", "BUSINESS_PROOF_KEY_SCOPE_INVALID", "BUSINESS_DELEGATION_SCOPE_INVALID"}
                        current.status = "blocked_authorization" if permanent_auth else "received_waiting_application"; current.application_lease_uuid = None; current.application_lease_expires_at = None; current.application_error_code = reason if permanent_auth else type(exc).__name__; current.application_error_message = reason[:500]
                failed += 1
        return {"claimed": len(claimed), "applied": applied, "failed": failed}
    def claim_proof_batch(self, db, *, peer_device_uuid, channel, limit=100):
        from app.models.origin_proof_delivery import OriginProofDelivery
        from app.models.origin_proof import OriginProof
        from datetime import timedelta
        now=_now(); rows=db.scalars(select(OriginProofDelivery).where(OriginProofDelivery.peer_device_uuid==peer_device_uuid,OriginProofDelivery.channel==channel,OriginProofDelivery.status.in_(("pending","leased")),(OriginProofDelivery.lease_expires_at.is_(None)) | (OriginProofDelivery.lease_expires_at < now)).with_for_update(skip_locked=True).limit(limit)).all()
        out=[]
        for row in rows:
            proof=db.get(OriginProof,row.proof_uuid)
            if proof is None: continue
            row.status='leased'; row.attempt_count += 1; row.lease_token=uuid.uuid4(); row.lease_expires_at=now+timedelta(seconds=int(__import__('os').environ.get('PROOF_DELIVERY_LEASE_SECONDS','60')))
            out.append((row,proof))
        db.commit(); return out

    def acknowledge_proof_delivery(self, db, *, delivery_id, peer_device_uuid, channel, lease_token):
        from app.models.origin_proof_delivery import OriginProofDelivery
        row=db.scalar(select(OriginProofDelivery).where(OriginProofDelivery.id==delivery_id,OriginProofDelivery.peer_device_uuid==peer_device_uuid,OriginProofDelivery.channel==channel).with_for_update())
        if row is None or row.lease_token != lease_token or row.status != 'leased' or not row.lease_expires_at or row.lease_expires_at < _now():
            raise ConflictException('PROOF_DELIVERY_LEASE_INVALID')
        row.status='delivered'; row.delivered_at=_now(); row.lease_token=None; row.lease_expires_at=None; db.commit(); return row
    def relay_inbox_once(self, db: Session, *, carrier_device_uuid: uuid.UUID,
                         publisher_device_uuid: uuid.UUID, publisher_generation_uuid: uuid.UUID,
                         destination_device_uuid: uuid.UUID, channel: str, limit: int = 100,
                         _after_publish=None) -> dict[str, int]:
        """Durably promote verified inbox events into the local publisher stream.

        This is an explicit background operation; it never creates SyncChange or
        applies medical data. Authorization is evaluated per event and denied
        events remain in the inbox for a later authorized run.
        """
        # `limit` is a limit on eligible relay work, not on the oldest inbox
        # rows.  An unauthorized old event must remain durable but must not
        # starve a later authorized event.  We therefore scan the ordered
        # candidate set and stop after `limit` successful relay attempts.
        authorized_scope = select(SyncRelayAuthorization.id).where(
            SyncRelayAuthorization.carrier_device_uuid == carrier_device_uuid,
            SyncRelayAuthorization.origin_device_uuid == SyncTransportEvent.source_device_uuid,
            SyncRelayAuthorization.origin_generation_uuid == SyncTransportEvent.source_generation_uuid,
            SyncRelayAuthorization.destination_device_uuid == destination_device_uuid,
            SyncRelayAuthorization.channel == channel,
            SyncRelayAuthorization.is_active.is_(True),
        ).exists()
        completed_delivery = select(SyncEventDelivery.id).where(
            SyncEventDelivery.event_uuid == SyncTransportEvent.event_uuid,
            SyncEventDelivery.peer_device_uuid == destination_device_uuid,
            SyncEventDelivery.channel == channel,
            SyncEventDelivery.status.in_(("pending", "leased", "delivered")),
        ).exists()
        rows = db.scalars(select(SyncTransportEvent).where(
            SyncTransportEvent.origin_kind == "inbox", authorized_scope, ~completed_delivery
        ).order_by(SyncTransportEvent.id.asc()).with_for_update(skip_locked=True)).all()
        log = logging.getLogger("sync.transport.relay")
        log.info("relay_candidates destination=%s channel=%s count=%s limit=%s", destination_device_uuid, channel, len(rows), limit)
        published = 0
        completed = 0
        for event in rows:
            if completed >= limit:
                break
            try:
                result = self.publish_relay_event(db, event_uuid=event.event_uuid,
                    carrier_device_uuid=carrier_device_uuid,
                    publisher_device_uuid=publisher_device_uuid,
                    publisher_generation_uuid=publisher_generation_uuid,
                    destination_device_uuid=destination_device_uuid, channel=channel)
                if result.get("published"): published += 1
                if _after_publish is not None:
                    _after_publish(event.event_uuid, result.get("publish_sequence"))
                queued = self.queue_for_peer(db, peer_device_uuid=destination_device_uuid,
                    channel=channel, source_clinic_uuid=event.source_clinic_uuid,
                    source_generation_uuid=event.source_generation_uuid,
                    source_device_uuid=event.source_device_uuid, limit=1)
                log.info("relay_queued event=%s publication=%s queued=%s has_more=%s", event.event_uuid, result.get("publish_sequence"), queued.get("queued"), queued.get("has_more"))
                completed += 1
            except ForbiddenException:
                db.rollback()
                continue
        return {"published": published}
    def resume_relay_delivery(self, db: Session, *, event_uuid: uuid.UUID, peer_device_uuid: uuid.UUID,
                              channel: str, publisher_device_uuid: uuid.UUID, publisher_generation_uuid: uuid.UUID,
                              publisher_clinic_uuid: uuid.UUID) -> None:
        """Explicitly requeue only authorization-denied deliveries after scope is restored."""
        self.authorize_relay(db, carrier_device_uuid=peer_device_uuid,
                             origin_device_uuid=publisher_device_uuid,
                             origin_generation_uuid=publisher_generation_uuid,
                             destination_device_uuid=peer_device_uuid, channel=channel)
        dq = select(SyncEventDelivery).where(
            SyncEventDelivery.event_uuid == event_uuid, SyncEventDelivery.peer_device_uuid == peer_device_uuid,
            SyncEventDelivery.channel == channel)
        if publisher_device_uuid is not None:
            dq = dq.where(SyncEventDelivery.publisher_device_uuid == publisher_device_uuid, SyncEventDelivery.publisher_generation_uuid == publisher_generation_uuid, SyncEventDelivery.clinic_uuid == publisher_clinic_uuid)
        delivery = db.scalar(dq.with_for_update())
        if delivery is None: raise NotFoundException("SYNC_DELIVERY_NOT_FOUND")
        if delivery.last_error_code != "RELAY_AUTHORIZATION_REVOKED":
            raise ConflictException("SYNC_DELIVERY_NOT_RESUMABLE")
        delivery.status = "pending"; delivery.last_error_code = None; delivery.last_error_message = None
        delivery.available_at = _now(); delivery.lease_token = None; delivery.lease_expires_at = None
        db.commit()
    def authorize_relay(self, db: Session, *, carrier_device_uuid: uuid.UUID, origin_device_uuid: uuid.UUID,
                        origin_generation_uuid: uuid.UUID, destination_device_uuid: uuid.UUID, channel: str) -> None:
        """Default-deny relay scope; receipt of an inbox event grants no relay right."""
        log = logging.getLogger("sync.transport.authorization")
        predicates = [
            SyncRelayAuthorization.carrier_device_uuid == carrier_device_uuid,
            SyncRelayAuthorization.origin_device_uuid == origin_device_uuid,
            SyncRelayAuthorization.origin_generation_uuid == origin_generation_uuid,
            SyncRelayAuthorization.destination_device_uuid == destination_device_uuid,
            SyncRelayAuthorization.channel == channel,
            SyncRelayAuthorization.is_active.is_(True),
        ]
        count = db.scalar(select(func.count()).select_from(SyncRelayAuthorization).where(*predicates))
        caller = inspect.stack()[1].function
        log.info("authorize_relay_result caller=%s carrier=%s origin=%s generation=%s destination=%s channel=%s matches=%s", caller, carrier_device_uuid, origin_device_uuid, origin_generation_uuid, destination_device_uuid, channel, count)
        allowed = db.scalar(select(SyncRelayAuthorization.id).where(*predicates))
        if allowed is None:
            raise ForbiddenException("SYNC_RELAY_NOT_AUTHORIZED", {"error_code": "SYNC_RELAY_NOT_AUTHORIZED"})

    def publish_relay_event(self, db: Session, *, event_uuid: uuid.UUID, carrier_device_uuid: uuid.UUID,
                            publisher_device_uuid: uuid.UUID, publisher_generation_uuid: uuid.UUID,
                            destination_device_uuid: uuid.UUID, channel: str) -> dict[str, Any]:
        """Publish a verified inbox event only under an explicit relay scope.

        The event's origin fields remain immutable. Publication identity is carried
        separately; application tables and SyncChange are never touched.
        """
        event = db.scalar(select(SyncTransportEvent).where(SyncTransportEvent.event_uuid == event_uuid).with_for_update())
        if event is None:
            raise NotFoundException("SYNC_TRANSPORT_EVENT_NOT_FOUND")
        self.authorize_relay(db, carrier_device_uuid=carrier_device_uuid,
                             origin_device_uuid=event.source_device_uuid,
                             origin_generation_uuid=event.source_generation_uuid,
                             destination_device_uuid=destination_device_uuid, channel=channel)
        existing = db.scalar(select(SyncEventPublication).where(
            SyncEventPublication.event_uuid == event_uuid,
            SyncEventPublication.channel == channel,
            SyncEventPublication.publisher_device_uuid == publisher_device_uuid,
            SyncEventPublication.publisher_generation_uuid == publisher_generation_uuid).with_for_update())
        if existing:
            db.commit(); return {"published": 0, "duplicate": True, "publish_sequence": existing.publish_sequence}
        counter = db.scalar(select(SyncPublicationCounter).where(
            SyncPublicationCounter.clinic_uuid == event.source_clinic_uuid,
            SyncPublicationCounter.publisher_device_uuid == publisher_device_uuid,
            SyncPublicationCounter.publisher_generation_uuid == publisher_generation_uuid,
            SyncPublicationCounter.channel == channel).with_for_update())
        if counter is None:
            db.add(SyncPublicationCounter(source_device_uuid=event.source_device_uuid, source_generation_uuid=event.source_generation_uuid, clinic_uuid=event.source_clinic_uuid, publisher_device_uuid=publisher_device_uuid, publisher_generation_uuid=publisher_generation_uuid, channel=channel, next_sequence=1)); db.flush()
            counter = db.scalar(select(SyncPublicationCounter).where(SyncPublicationCounter.clinic_uuid == event.source_clinic_uuid, SyncPublicationCounter.publisher_device_uuid == publisher_device_uuid, SyncPublicationCounter.publisher_generation_uuid == publisher_generation_uuid, SyncPublicationCounter.channel == channel).with_for_update())
        seq = counter.next_sequence; counter.next_sequence += 1
        db.add(SyncEventPublication(event_uuid=event_uuid, source_device_uuid=event.source_device_uuid,
            source_generation_uuid=event.source_generation_uuid, channel=channel, publish_sequence=seq,
            published_at=_now(), publisher_device_uuid=publisher_device_uuid, publisher_generation_uuid=publisher_generation_uuid))
        db.commit(); return {"published": 1, "duplicate": False, "publish_sequence": seq}

    def publish_committed(self, db: Session, *, channel: str, limit: int = 100, _fail_before_commit: bool = False,
                          source_device_uuid: uuid.UUID | None = None,
                          source_generation_uuid: uuid.UUID | None = None,
                          source_clinic_uuid: uuid.UUID | None = None,
                          publisher_device_uuid: uuid.UUID | None = None,
                          publisher_generation_uuid: uuid.UUID | None = None) -> dict[str, Any]:
        """Assign channel-local positions only to already committed SyncChange rows.

        The counter row is locked for the short database transaction. A duplicate
        event is ignored by the unique constraint, so concurrent publishers cannot
        allocate two positions for one event.
        """
        if limit < 1 or limit > 1000:
            raise ConflictException("SYNC_BATCH_LIMIT_INVALID")
        publisher_device_uuid = publisher_device_uuid or source_device_uuid
        publisher_generation_uuid = publisher_generation_uuid or source_generation_uuid
        if publisher_device_uuid is None or publisher_generation_uuid is None or source_clinic_uuid is None:
            raise ConflictException("SYNC_PUBLISHER_SCOPE_REQUIRED")
        # Serialize publishers for this channel while keeping the transaction short.
        db.execute(select(text("pg_advisory_xact_lock(hashtext(:channel))")).params(channel=channel))
        already_published = select(SyncEventPublication.id).where(
            SyncEventPublication.event_uuid == SyncChange.change_uuid,
            SyncEventPublication.channel == channel,
            SyncEventPublication.publisher_device_uuid == publisher_device_uuid,
            SyncEventPublication.publisher_generation_uuid == publisher_generation_uuid,
        ).exists()
        filters = [
            SyncChange.revision_uuid.is_not(None), SyncChange.source_device_uuid.is_not(None),
            SyncChange.source_generation_uuid.is_not(None), SyncChange.source_clinic_uuid.is_not(None),
            ~already_published,
        ]
        if source_device_uuid is not None: filters.append(SyncChange.source_device_uuid == source_device_uuid)
        if source_generation_uuid is not None: filters.append(SyncChange.source_generation_uuid == source_generation_uuid)
        if source_clinic_uuid is not None: filters.append(SyncChange.source_clinic_uuid == source_clinic_uuid)
        rows = db.scalars(select(SyncChange).where(*filters).order_by(SyncChange.id.asc()).limit(limit)).all()
        created = 0
        for row in rows:
            if db.scalar(select(SyncTransportEvent.id).where(SyncTransportEvent.event_uuid == row.change_uuid)) is None:
                db.add(SyncTransportEvent(
                    event_uuid=row.change_uuid, source_clinic_uuid=row.source_clinic_uuid,
                    source_device_uuid=row.source_device_uuid, source_generation_uuid=row.source_generation_uuid,
                    source_sequence=int(row.source_sequence or row.id), entity_type=row.entity_type,
                    entity_uuid=row.entity_uuid, revision_uuid=row.revision_uuid,
                    operation=row.operation, schema_version=int(row.schema_version or TRANSPORT_SCHEMA_VERSION),
                    content_sha256=row.content_sha256 or payload_sha256(dict(row.payload or {})),
                    payload=dict(row.payload or {}), origin_kind="local", created_at=_now(),
                ))
            existing = db.scalar(select(SyncEventPublication).where(
                SyncEventPublication.event_uuid == row.change_uuid,
                SyncEventPublication.publisher_device_uuid == publisher_device_uuid,
                SyncEventPublication.publisher_generation_uuid == publisher_generation_uuid,
                SyncEventPublication.channel == channel).with_for_update())
            if existing is not None:
                continue
            counter = db.scalar(select(SyncPublicationCounter).where(
                SyncPublicationCounter.clinic_uuid == row.source_clinic_uuid,
                SyncPublicationCounter.publisher_device_uuid == publisher_device_uuid,
                SyncPublicationCounter.publisher_generation_uuid == publisher_generation_uuid,
                SyncPublicationCounter.channel == channel).with_for_update())
            if counter is None:
                db.execute(insert(SyncPublicationCounter).values(
                    source_device_uuid=row.source_device_uuid,
                    source_generation_uuid=row.source_generation_uuid,
                    clinic_uuid=row.source_clinic_uuid,
                    publisher_device_uuid=publisher_device_uuid,
                    publisher_generation_uuid=publisher_generation_uuid,
                    channel=channel, next_sequence=1
                ).on_conflict_do_nothing(index_elements=["clinic_uuid", "publisher_device_uuid", "publisher_generation_uuid", "channel"]))
                counter = db.scalar(select(SyncPublicationCounter).where(
                    SyncPublicationCounter.clinic_uuid == row.source_clinic_uuid,
                    SyncPublicationCounter.publisher_device_uuid == publisher_device_uuid,
                    SyncPublicationCounter.publisher_generation_uuid == publisher_generation_uuid,
                    SyncPublicationCounter.channel == channel).with_for_update())
            seq = counter.next_sequence; counter.next_sequence += 1
            db.add(SyncEventPublication(event_uuid=row.change_uuid, source_device_uuid=row.source_device_uuid,
                source_generation_uuid=row.source_generation_uuid, channel=channel, publish_sequence=seq, published_at=_now(),
                publisher_device_uuid=publisher_device_uuid, publisher_generation_uuid=publisher_generation_uuid))
            created += 1
        if _fail_before_commit:
            db.rollback()
            raise RuntimeError("synthetic publication failure before commit")
        db.commit()
        return {"published": created, "has_more": len(rows) == limit}

    def publication_batch(self, db: Session, *, source_device_uuid: uuid.UUID,
                          source_generation_uuid: uuid.UUID, channel: str,
                          after_sequence: int = 0, limit: int = 100) -> dict[str, Any]:
        rows = db.scalars(select(SyncEventPublication).where(
            SyncEventPublication.source_device_uuid == source_device_uuid,
            SyncEventPublication.source_generation_uuid == source_generation_uuid,
            SyncEventPublication.channel == channel,
            SyncEventPublication.publish_sequence > after_sequence
        ).order_by(SyncEventPublication.publish_sequence.asc()).limit(limit + 1)).all()
        more = len(rows) > limit; rows = rows[:limit]
        return {"events": [str(r.event_uuid) for r in rows], "has_more": more,
                "cursor": rows[-1].publish_sequence if rows else after_sequence}
    def authorize_device(self, db: Session, device_uuid: uuid.UUID) -> SyncDevice:
        device = db.scalar(select(SyncDevice).where(SyncDevice.uuid == device_uuid))
        if device is None:
            raise NotFoundException("SYNC_DEVICE_NOT_FOUND")
        if not device.is_active or device.is_revoked:
            raise ForbiddenException("SYNC_DEVICE_NOT_AUTHORIZED")
        return device

    def event_envelope(self, change: SyncChange, *, source_clinic_uuid: uuid.UUID,
                       source_generation_uuid: uuid.UUID, source_sequence: int,
                       publication_sequence: int | None = None, publication_source_device_uuid: uuid.UUID | None = None) -> dict[str, Any]:
        payload = dict(change.payload or {})
        return {
            "event_uuid": str(change.change_uuid), "source_clinic_uuid": str(source_clinic_uuid),
            "source_device_uuid": str(change.source_device_uuid), "source_generation_uuid": str(source_generation_uuid),
            "source_sequence": source_sequence, "entity_type": change.entity_type,
            "entity_uuid": str(change.entity_uuid), "revision_uuid": str(change.revision_uuid) if change.revision_uuid else None,
            "parent_revision_uuid": None, "operation": change.operation,
            "schema_version": int(change.schema_version or TRANSPORT_SCHEMA_VERSION), "payload": payload,
            "content_sha256": change.content_sha256 or payload_sha256(payload),
            "publication_source_device_uuid": str(publication_source_device_uuid or change.source_device_uuid),
            "publication_source_generation_uuid": str(source_generation_uuid),
            "publication_channel": None,
            "publish_sequence": publication_sequence,
        }

    def queue_for_peer(self, db: Session, *, peer_device_uuid: uuid.UUID, channel: str,
                       source_clinic_uuid: uuid.UUID, source_generation_uuid: uuid.UUID,
                       source_device_uuid: uuid.UUID | None = None,
                       limit: int = 100) -> dict[str, Any]:
        if limit < 1 or limit > 1000:
            raise ConflictException("SYNC_BATCH_LIMIT_INVALID")
        self.authorize_device(db, peer_device_uuid)
        criteria = [SyncChange.revision_uuid.is_not(None), SyncChange.source_clinic_uuid == source_clinic_uuid,
                    SyncChange.source_generation_uuid == source_generation_uuid]
        if source_device_uuid is not None: criteria.append(SyncChange.source_device_uuid == source_device_uuid)
        rows = db.scalars(select(SyncChange).where(*criteria).order_by(SyncChange.id.asc()).limit(limit)).all()
        existing_ids = {r.change_uuid for r in rows}
        relay_delivery_exists = select(SyncEventDelivery.id).where(
            SyncEventDelivery.event_uuid == SyncTransportEvent.event_uuid,
            SyncEventDelivery.peer_device_uuid == peer_device_uuid,
            SyncEventDelivery.channel == channel,
            SyncEventDelivery.publisher_device_uuid == SyncEventPublication.publisher_device_uuid,
            SyncEventDelivery.publisher_generation_uuid == SyncEventPublication.publisher_generation_uuid,
            SyncEventDelivery.clinic_uuid == SyncTransportEvent.source_clinic_uuid,
        ).exists()
        relay_rows = db.scalars(select(SyncTransportEvent).join(SyncEventPublication, SyncEventPublication.event_uuid == SyncTransportEvent.event_uuid).where(
            SyncTransportEvent.source_clinic_uuid == source_clinic_uuid,
            SyncTransportEvent.source_generation_uuid == source_generation_uuid,
            ~SyncTransportEvent.event_uuid.in_(existing_ids) if existing_ids else True,
            SyncEventPublication.channel == channel,
            ~relay_delivery_exists,
        ).order_by(SyncTransportEvent.event_uuid, SyncEventPublication.publish_sequence.asc()).distinct(SyncTransportEvent.event_uuid).limit(limit)).all()
        now = _now()
        queued = 0
        for row in rows:
            sequence = int(row.source_sequence or row.id)
            if row.source_device_uuid is None or row.source_clinic_uuid is None:
                db.execute(insert(SyncEventDelivery).values(
                    event_uuid=row.change_uuid, peer_device_uuid=peer_device_uuid, channel=channel,
                    status="rejected", attempt_count=0, last_error_code="SOURCE_IDENTITY_MISSING",
                    last_error_message="Source clinic and device identities are required before transport", available_at=now,
                ).on_conflict_do_nothing(index_elements=["event_uuid", "peer_device_uuid", "channel", "publisher_device_uuid", "publisher_generation_uuid", "clinic_uuid"]))
                continue
            pubs = db.scalars(select(SyncEventPublication).where(
                SyncEventPublication.event_uuid == row.change_uuid,
                SyncEventPublication.channel == channel).order_by(SyncEventPublication.publish_sequence.asc())).all()
            if not pubs:
                pubs = [None]
            for pub in pubs:
                db.execute(insert(SyncEventDelivery).values(
                    event_uuid=row.change_uuid, peer_device_uuid=peer_device_uuid, channel=channel,
                    publisher_device_uuid=(pub.publisher_device_uuid if pub else row.source_device_uuid),
                    publisher_generation_uuid=(pub.publisher_generation_uuid if pub else row.source_generation_uuid),
                    clinic_uuid=row.source_clinic_uuid,
                    status="pending", attempt_count=0, available_at=now,
                ).on_conflict_do_nothing(index_elements=["event_uuid", "peer_device_uuid", "channel", "publisher_device_uuid", "publisher_generation_uuid", "clinic_uuid"]))
            if row.source_generation_uuid is None:
                row.source_generation_uuid = source_generation_uuid
                row.source_sequence = sequence
                row.schema_version = row.schema_version or TRANSPORT_SCHEMA_VERSION
                row.content_sha256 = row.content_sha256 or payload_sha256(dict(row.payload or {}))
            queued += 1
        for event in relay_rows:
            pubs = db.scalars(select(SyncEventPublication).where(
                SyncEventPublication.event_uuid == event.event_uuid,
                SyncEventPublication.channel == channel).order_by(SyncEventPublication.publish_sequence.asc())).all()
            for pub in pubs:
                db.execute(insert(SyncEventDelivery).values(
                    event_uuid=event.event_uuid, peer_device_uuid=peer_device_uuid, channel=channel,
                    publisher_device_uuid=pub.publisher_device_uuid,
                    publisher_generation_uuid=pub.publisher_generation_uuid,
                    clinic_uuid=event.source_clinic_uuid,
                    status="pending", attempt_count=0, available_at=now,
                ).on_conflict_do_nothing(index_elements=["event_uuid", "peer_device_uuid", "channel", "publisher_device_uuid", "publisher_generation_uuid", "clinic_uuid"]))
                queued += 1
        db.commit()
        return {"queued": queued, "has_more": len(rows) == limit}

    def claim_batch(self, db: Session, *, peer_device_uuid: uuid.UUID, channel: str,
                    limit: int = 100, publisher_device_uuid: uuid.UUID | None = None,
                    publisher_generation_uuid: uuid.UUID | None = None,
                    publisher_clinic_uuid: uuid.UUID | None = None) -> list[dict[str, Any]]:
        if not publisher_device_uuid or not publisher_generation_uuid or not publisher_clinic_uuid:
            raise ConflictException("SYNC_PUBLISHER_SCOPE_REQUIRED")
        self.authorize_device(db, peer_device_uuid)
        now = _now()
        delivery_q = select(SyncEventDelivery).where(
            SyncEventDelivery.peer_device_uuid == peer_device_uuid,
            SyncEventDelivery.channel == channel,
            ((SyncEventDelivery.status == "pending") & (SyncEventDelivery.available_at <= now)) |
            ((SyncEventDelivery.status == "sending") & (SyncEventDelivery.lease_expires_at < now)),
        )
        if publisher_device_uuid is not None:
            delivery_q = delivery_q.where(SyncEventDelivery.publisher_device_uuid == publisher_device_uuid,
                                          SyncEventDelivery.publisher_generation_uuid == publisher_generation_uuid,
                                          SyncEventDelivery.clinic_uuid == publisher_clinic_uuid)
        rows = db.scalars(delivery_q.order_by(SyncEventDelivery.id.asc()).limit(min(limit, 1000)).with_for_update(skip_locked=True)).all()
        result = []
        for delivery in rows:
            change = db.scalar(select(SyncChange).where(SyncChange.change_uuid == delivery.event_uuid))
            transport_event = db.scalar(select(SyncTransportEvent).where(SyncTransportEvent.event_uuid == delivery.event_uuid))
            if change is None and transport_event is None:
                delivery.status = "rejected"; delivery.last_error_code = "EVENT_NOT_FOUND"
                continue
            origin = change or transport_event
            generation = origin.source_generation_uuid or uuid.UUID(int=0)
            delivery.status = "sending"
            delivery.lease_token = uuid.uuid4()
            delivery.lease_expires_at = now + timedelta(seconds=DELIVERY_LEASE_SECONDS)
            delivery.attempt_count += 1
            db.add(SyncTransportAttempt(event_uuid=delivery.event_uuid, peer_device_uuid=peer_device_uuid,
                                        channel=channel, attempt_no=delivery.attempt_count, outcome="sent", attempted_at=now))
            pub_q = select(SyncEventPublication).where(SyncEventPublication.event_uuid == delivery.event_uuid, SyncEventPublication.channel == channel)
            if delivery.publisher_device_uuid is not None:
                pub_q = pub_q.where(SyncEventPublication.publisher_device_uuid == delivery.publisher_device_uuid, SyncEventPublication.publisher_generation_uuid == delivery.publisher_generation_uuid)
            pub = db.scalar(pub_q.order_by(SyncEventPublication.publish_sequence.asc()))
            if pub is None:
                raise ConflictException("SYNC_PUBLICATION_MISSING")
            if change is None:
                envelope = {"event_uuid": str(transport_event.event_uuid), "source_clinic_uuid": str(transport_event.source_clinic_uuid), "source_device_uuid": str(transport_event.source_device_uuid), "source_generation_uuid": str(transport_event.source_generation_uuid), "source_sequence": transport_event.source_sequence, "entity_type": transport_event.entity_type, "entity_uuid": str(transport_event.entity_uuid), "revision_uuid": str(transport_event.revision_uuid) if transport_event.revision_uuid else None, "parent_revision_uuid": str(transport_event.parent_revision_uuid) if transport_event.parent_revision_uuid else None, "operation": transport_event.operation, "schema_version": transport_event.schema_version, "payload": transport_event.payload, "content_sha256": transport_event.content_sha256}
            else:
                envelope = self.event_envelope(change, source_clinic_uuid=change.source_clinic_uuid,
                                               source_generation_uuid=generation, source_sequence=int(change.source_sequence or change.id),
                                               publication_sequence=pub.publish_sequence if pub else None,
                                               publication_source_device_uuid=pub.source_device_uuid if pub else change.source_device_uuid)
            envelope["publication_source_device_uuid"] = str(pub.publisher_device_uuid or pub.source_device_uuid) if pub else None
            envelope["publication_source_generation_uuid"] = str(pub.publisher_generation_uuid or pub.source_generation_uuid) if pub else None
            envelope["publication_channel"] = channel
            envelope["publish_sequence"] = int(pub.publish_sequence) if pub else None
            envelope["lease_token"] = str(delivery.lease_token)
            result.append(envelope)
        db.commit()
        return result

    def acknowledge(self, db: Session, *, event_uuid: uuid.UUID, peer_device_uuid: uuid.UUID,
                    channel: str, lease_token: uuid.UUID, publisher_device_uuid: uuid.UUID | None = None,
                    publisher_generation_uuid: uuid.UUID | None = None, publisher_clinic_uuid: uuid.UUID | None = None) -> None:
        dq = select(SyncEventDelivery).where(
            SyncEventDelivery.event_uuid == event_uuid, SyncEventDelivery.peer_device_uuid == peer_device_uuid,
            SyncEventDelivery.channel == channel)
        if publisher_device_uuid is not None:
            dq = dq.where(SyncEventDelivery.publisher_device_uuid == publisher_device_uuid, SyncEventDelivery.publisher_generation_uuid == publisher_generation_uuid, SyncEventDelivery.clinic_uuid == publisher_clinic_uuid)
        delivery = db.scalar(dq.with_for_update())
        if delivery is None:
            raise NotFoundException("SYNC_DELIVERY_NOT_FOUND")
        if publisher_device_uuid is not None and (delivery.publisher_device_uuid != publisher_device_uuid or delivery.publisher_generation_uuid != publisher_generation_uuid or delivery.clinic_uuid != publisher_clinic_uuid):
            raise ConflictException("SYNC_ACK_SCOPE_MISMATCH")
        if delivery.status == "delivered":
            if delivery.lease_token != lease_token:
                raise ConflictException("SYNC_ACK_TOKEN_MISMATCH")
            db.commit()
            return
        if delivery.status != "sending" or delivery.lease_token != lease_token or not delivery.lease_expires_at or delivery.lease_expires_at < _now():
            raise ConflictException("SYNC_STALE_LEASE")
        delivery.status = "delivered"
        delivery.delivered_at = _now()
        # Retain the final token as an idempotency proof for safe repeated ACKs.
        delivery.lease_expires_at = None
        db.commit()

    def record_failure(self, db: Session, *, event_uuid: uuid.UUID, peer_device_uuid: uuid.UUID,
                       channel: str, error_code: str, error_message: str, permanent: bool = False) -> None:
        """Persist retry state without logging or returning event content."""
        delivery = db.scalar(select(SyncEventDelivery).where(
            SyncEventDelivery.event_uuid == event_uuid,
            SyncEventDelivery.peer_device_uuid == peer_device_uuid,
            SyncEventDelivery.channel == channel,
        ).with_for_update())
        if delivery is None:
            raise NotFoundException("SYNC_DELIVERY_NOT_FOUND")
        now = _now()
        delivery.attempt_count += 1
        delivery.last_error_code = error_code[:100]
        delivery.last_error_message = error_message[:500]
        delivery.status = "rejected" if permanent else "pending"
        delivery.lease_token = None
        delivery.lease_expires_at = None
        delivery.available_at = now if permanent else now + timedelta(seconds=min(900, 2 ** min(delivery.attempt_count, 10)))
        db.add(SyncTransportAttempt(event_uuid=event_uuid, peer_device_uuid=peer_device_uuid, channel=channel,
                                    attempt_no=delivery.attempt_count, outcome="rejected" if permanent else "retry_scheduled",
                                    error_code=error_code[:100], error_message=error_message[:500], attempted_at=now))
        db.commit()

    def receive_batch(self, db: Session, *, receiver_device_uuid: uuid.UUID, source_clinic_uuid: uuid.UUID,
                      source_device_uuid: uuid.UUID, channel: str, events: list[dict[str, Any]],
                      source_generation_uuid: uuid.UUID, limit: int = 100, _fail_before_commit: bool = False,
                      publisher_device_uuid: uuid.UUID | None = None, publisher_generation_uuid: uuid.UUID | None = None,
                      publisher_clinic_uuid: uuid.UUID | None = None,
                      _failure_stage: str | None = None) -> dict[str, Any]:
        receiver = self.authorize_device(db, receiver_device_uuid)
        del receiver
        self.authorize_device(db, source_device_uuid)
        if publisher_device_uuid is None or publisher_generation_uuid is None or publisher_clinic_uuid is None:
            raise ConflictException("SYNC_PUBLISHER_SCOPE_REQUIRED")
        if len(events) > min(limit, 1000):
            raise ConflictException("SYNC_BATCH_LIMIT_EXCEEDED")
        # Serialize first-seen UUIDs so two authorized publisher scopes can
        # converge on one durable source/inbox without an unhandled unique
        # violation. Receipts remain independent and are inserted below.
        for incoming in sorted(events, key=lambda item: str(item['event_uuid'])):
            db.execute(select(text("pg_advisory_xact_lock(hashtext(:key))")).params(key=f"sync-receive:{incoming['event_uuid']}"))
        cursor_q = select(SyncTransportCursor).where(SyncTransportCursor.peer_device_uuid == receiver_device_uuid, SyncTransportCursor.source_device_uuid == source_device_uuid, SyncTransportCursor.source_generation_uuid == source_generation_uuid, SyncTransportCursor.channel == channel)
        if publisher_device_uuid is not None:
            cursor_q = cursor_q.where(SyncTransportCursor.publisher_device_uuid == publisher_device_uuid, SyncTransportCursor.publisher_generation_uuid == publisher_generation_uuid, SyncTransportCursor.clinic_uuid == publisher_clinic_uuid)
        cursor = db.scalar(cursor_q.with_for_update())
        prior_generation = db.scalar(select(SyncTransportCursor.source_generation_uuid).where(
            SyncTransportCursor.peer_device_uuid == receiver_device_uuid,
            SyncTransportCursor.source_device_uuid == source_device_uuid,
            SyncTransportCursor.channel == channel,
            SyncTransportCursor.source_generation_uuid != source_generation_uuid,
            SyncTransportCursor.last_publish_sequence > 0,
        ).limit(1))
        if prior_generation is not None:
            raise ConflictException("SOURCE_GENERATION_CHANGED")
        prior_clinic = db.scalar(select(SyncEventInbox.source_clinic_uuid).where(
            SyncEventInbox.source_device_uuid == source_device_uuid,
            SyncEventInbox.source_generation_uuid == source_generation_uuid,
        ).limit(1))
        if prior_clinic is not None and prior_clinic != source_clinic_uuid:
            raise ForbiddenException("SYNC_CLINIC_IDENTITY_MISMATCH")
        if cursor is None:
            db.execute(insert(SyncTransportCursor).values(
                peer_device_uuid=receiver_device_uuid, source_device_uuid=source_device_uuid,
                source_generation_uuid=source_generation_uuid, channel=channel,
                last_source_sequence=0, publisher_device_uuid=publisher_device_uuid, publisher_generation_uuid=publisher_generation_uuid, clinic_uuid=publisher_clinic_uuid, updated_at=_now()
            ).on_conflict_do_nothing(index_elements=["peer_device_uuid", "source_device_uuid", "source_generation_uuid", "channel", "publisher_device_uuid", "publisher_generation_uuid", "clinic_uuid"]))
            cursor_q = select(SyncTransportCursor).where(SyncTransportCursor.peer_device_uuid == receiver_device_uuid, SyncTransportCursor.source_device_uuid == source_device_uuid, SyncTransportCursor.source_generation_uuid == source_generation_uuid, SyncTransportCursor.channel == channel)
            if publisher_device_uuid is not None:
                cursor_q = cursor_q.where(SyncTransportCursor.publisher_device_uuid == publisher_device_uuid, SyncTransportCursor.publisher_generation_uuid == publisher_generation_uuid, SyncTransportCursor.clinic_uuid == publisher_clinic_uuid)
            cursor = db.scalar(cursor_q.with_for_update())
        accepted = 0; duplicates = 0
        for event in sorted(events, key=lambda item: int(item["source_sequence"])):
            if uuid.UUID(str(event["source_clinic_uuid"])) != source_clinic_uuid:
                raise ForbiddenException("SYNC_CLINIC_IDENTITY_MISMATCH")
            if uuid.UUID(str(event["source_device_uuid"])) != source_device_uuid:
                raise ForbiddenException("SYNC_SOURCE_DEVICE_MISMATCH")
            if event.get("publication_source_device_uuid") != str(publisher_device_uuid) or event.get("publication_source_generation_uuid") != str(publisher_generation_uuid):
                raise ConflictException("SYNC_PUBLISHER_SCOPE_MISMATCH")
            if int(event["schema_version"]) != TRANSPORT_SCHEMA_VERSION:
                raise ConflictException("SYNC_EVENT_SCHEMA_UNSUPPORTED")
            if event.get("publication_channel") != channel or event.get("publish_sequence") is None:
                raise ConflictException("SYNC_PUBLICATION_POSITION_REQUIRED")
            expected_hash = payload_sha256(dict(event["payload"] or {}))
            if expected_hash != event.get("content_sha256"):
                raise ConflictException("SYNC_EVENT_CONTENT_HASH_MISMATCH")
            event_uuid = uuid.UUID(str(event["event_uuid"]))
            occupied = db.scalar(select(SyncPublicationReceipt.event_uuid).where(
                SyncPublicationReceipt.peer_device_uuid == receiver_device_uuid,
                SyncPublicationReceipt.source_device_uuid == source_device_uuid,
                SyncPublicationReceipt.source_generation_uuid == source_generation_uuid,
                SyncPublicationReceipt.channel == channel,
                SyncPublicationReceipt.publish_sequence == int(event["publish_sequence"])))
            if occupied is not None and occupied != event_uuid:
                raise ConflictException("SYNC_PUBLICATION_POSITION_CONFLICT")
            existing = db.scalar(select(SyncEventInbox).where(SyncEventInbox.event_uuid == event_uuid).with_for_update())
            if existing is not None:
                if (existing.content_sha256 != expected_hash or
                    existing.source_clinic_uuid != source_clinic_uuid or
                    existing.source_device_uuid != source_device_uuid or
                    existing.source_generation_uuid != source_generation_uuid):
                    db.rollback()
                    raise ConflictException("EVENT_UUID_CONTENT_MISMATCH")
                prior_receipt = db.scalar(select(SyncPublicationReceipt).where(
                    SyncPublicationReceipt.event_uuid == event_uuid,
                    SyncPublicationReceipt.peer_device_uuid == receiver_device_uuid,
                    SyncPublicationReceipt.source_device_uuid == source_device_uuid,
                    SyncPublicationReceipt.source_generation_uuid == source_generation_uuid,
                    SyncPublicationReceipt.channel == channel,
                ))
                if prior_receipt is not None and prior_receipt.publish_sequence != int(event["publish_sequence"]):
                    raise ConflictException("SYNC_PUBLICATION_POSITION_MISMATCH")
                duplicates += 1
            else:
                inbox = SyncEventInbox(
                    event_uuid=event_uuid, source_clinic_uuid=source_clinic_uuid, source_device_uuid=source_device_uuid,
                    source_generation_uuid=source_generation_uuid, source_sequence=int(event["source_sequence"]),
                    entity_type=event["entity_type"], entity_uuid=uuid.UUID(str(event["entity_uuid"])),
                    revision_uuid=uuid.UUID(str(event["revision_uuid"])) if event.get("revision_uuid") else None,
                    parent_revision_uuid=uuid.UUID(str(event["parent_revision_uuid"])) if event.get("parent_revision_uuid") else None,
                    operation=event["operation"], schema_version=TRANSPORT_SCHEMA_VERSION, content_sha256=expected_hash,
                    payload=event["payload"], status="received_waiting_application", received_at=_now(),
                )
                db.add(inbox)
                db.flush()
                transport_existing = db.scalar(select(SyncTransportEvent).where(SyncTransportEvent.event_uuid == event_uuid).with_for_update())
                if transport_existing is not None:
                    if (transport_existing.content_sha256 != expected_hash or
                        transport_existing.source_device_uuid != source_device_uuid or
                        transport_existing.source_generation_uuid != source_generation_uuid or
                        transport_existing.source_clinic_uuid != source_clinic_uuid):
                        db.rollback()
                        raise ConflictException("EVENT_UUID_CONTENT_MISMATCH")
                else:
                    db.add(SyncTransportEvent(
                        event_uuid=event_uuid, source_clinic_uuid=source_clinic_uuid,
                        source_device_uuid=source_device_uuid, source_generation_uuid=source_generation_uuid,
                        source_sequence=int(event["source_sequence"]), entity_type=event["entity_type"],
                        entity_uuid=uuid.UUID(str(event["entity_uuid"])),
                        revision_uuid=uuid.UUID(str(event["revision_uuid"])) if event.get("revision_uuid") else None,
                        parent_revision_uuid=uuid.UUID(str(event["parent_revision_uuid"])) if event.get("parent_revision_uuid") else None,
                        operation=event["operation"], schema_version=TRANSPORT_SCHEMA_VERSION,
                        content_sha256=expected_hash, payload=event["payload"], origin_kind="inbox",
                        origin_inbox_id=inbox.id, created_at=_now(),
                    ))
                if _failure_stage == "after_source":
                    db.rollback()
                    raise RuntimeError("synthetic receive failure after shared source insertion")
                accepted += 1
                if _failure_stage == "after_inbox":
                    db.rollback()
                    raise RuntimeError("synthetic receive failure after inbox insertion")
            db.execute(insert(SyncPublicationReceipt).values(event_uuid=event_uuid, peer_device_uuid=receiver_device_uuid,
                source_device_uuid=source_device_uuid, source_generation_uuid=source_generation_uuid,
                channel=channel, publish_sequence=int(event["publish_sequence"]), received_at=_now(),
                publisher_device_uuid=event.get("publication_source_device_uuid"),
                publisher_generation_uuid=event.get("publication_source_generation_uuid"),
                clinic_uuid=source_clinic_uuid).on_conflict_do_nothing())
            if _failure_stage == "after_receipt":
                db.rollback()
                raise RuntimeError("synthetic receive failure after receipt insertion")
        # Publication positions are the transport cursor. Publisher positions
        # are contiguous within a source/generation/channel by contract; source
        # sequence remains legacy metadata and is never used for this cursor.
        if events:
            cursor.clinic_uuid = source_clinic_uuid
            cursor.publisher_device_uuid = uuid.UUID(str(events[0]["publication_source_device_uuid"])) if events[0].get("publication_source_device_uuid") else None
            cursor.publisher_generation_uuid = uuid.UUID(str(events[0]["publication_source_generation_uuid"])) if events[0].get("publication_source_generation_uuid") else None
        positions = db.scalars(select(SyncPublicationReceipt.publish_sequence).where(
            SyncPublicationReceipt.peer_device_uuid == receiver_device_uuid,
            SyncPublicationReceipt.source_device_uuid == source_device_uuid,
            SyncPublicationReceipt.source_generation_uuid == source_generation_uuid,
            SyncPublicationReceipt.channel == channel,
            SyncPublicationReceipt.publish_sequence > cursor.last_publish_sequence,
        ).order_by(SyncPublicationReceipt.publish_sequence.asc())).all()
        next_pos = cursor.last_publish_sequence + 1
        for pos in positions:
            if int(pos) != next_pos:
                break
            next_pos += 1
        cursor.last_publish_sequence = next_pos - 1
        terminal = db.scalar(select(SyncPublicationReceipt.event_uuid).where(
            SyncPublicationReceipt.peer_device_uuid == receiver_device_uuid,
            SyncPublicationReceipt.source_device_uuid == source_device_uuid,
            SyncPublicationReceipt.source_generation_uuid == source_generation_uuid,
            SyncPublicationReceipt.channel == channel,
            SyncPublicationReceipt.publish_sequence == cursor.last_publish_sequence))
        if terminal:
            cursor.last_publication_event_uuid = terminal
        if _failure_stage == "after_cursor":
            db.rollback()
            raise RuntimeError("synthetic receive failure after cursor update")
        cursor.updated_at = _now()
        if _fail_before_commit:
            db.rollback()
            raise RuntimeError("synthetic receive failure before commit")
        db.commit()
        return {"accepted": accepted, "duplicates": duplicates, "has_more": len(events) == min(limit, 1000),
                "cursor": {"source_device_uuid": str(source_device_uuid), "source_generation_uuid": str(source_generation_uuid),
                           "channel": channel, "last_publish_sequence": cursor.last_publish_sequence,
                           "last_publication_event_uuid": str(cursor.last_publication_event_uuid) if cursor.last_publication_event_uuid else None}}


