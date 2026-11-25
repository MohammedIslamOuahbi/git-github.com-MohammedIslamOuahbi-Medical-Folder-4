"""External sync worker entrypoint.

This module is intentionally separate from ``app.main`` (the API process).
It owns durable inbox application for central/mobile installations.  Transport
polling is enabled only when its endpoint and credentials are configured.
"""
from __future__ import annotations

import os
import signal
import time
import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.services.sync_transport_worker import SyncTransportWorker
from app.services.sync_transport_service import SyncTransportService
from app.sync_transport_runtime import http_sender


def _required_uuid(name: str) -> uuid.UUID:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} is required")
    return uuid.UUID(value)


def main() -> None:
    mode = os.environ.get("DEPLOYMENT_MODE", "central_server")
    if mode not in {"central_server", "mobile_server", "client"}:
        raise RuntimeError("DEPLOYMENT_MODE must be client, mobile_server, or central_server")
    if mode == "client" and os.environ.get("SYNC_WORKER_ALLOW_CLIENT") != "1":
        raise RuntimeError("client mode does not own inbox application; enable explicitly for a client deployment")

    engine = create_engine(settings.database_url, pool_pre_ping=True)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    peer = _required_uuid("WORKER_PEER")
    publisher_device = _required_uuid("WORKER_PUBLISHER_DEVICE")
    publisher_generation = _required_uuid("WORKER_PUBLISHER_GENERATION")
    publisher_clinic = _required_uuid("WORKER_PUBLISHER_CLINIC")
    channel = os.environ.get("WORKER_CHANNEL", mode)
    stop = False

    def request_stop(signum, frame):
        nonlocal stop
        stop = True

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)

    # The external deployment may provide a transport sender separately.  The
    # inbox application path is always available and is the only path enabled
    # by default; this preserves receipt-only ACK semantics.
    transport_enabled = os.environ.get("SYNC_WORKER_TRANSPORT") == "1"
    if transport_enabled:
        sender = http_sender(target=os.environ.get("WORKER_TARGET", ""), source=os.environ.get("WORKER_SOURCE", ""), secret=os.environ.get("WORKER_SECRET", ""), peer_device_uuid=str(peer), channel=channel)
        def before_send(events):
            if not events: return
            with factory() as db:
                SyncTransportService().authorize_relay(db, carrier_device_uuid=peer, origin_device_uuid=uuid.UUID(events[0]["source_device_uuid"]), origin_generation_uuid=uuid.UUID(events[0]["source_generation_uuid"]), destination_device_uuid=peer, channel=channel)
    else:
        def sender(events):
            raise RuntimeError("transport sender is not configured; inbox application remains enabled")
        before_send = None

    worker = SyncTransportWorker(
        factory,
        peer_device_uuid=peer,
        channel=channel,
        publisher_device_uuid=publisher_device,
        publisher_generation_uuid=publisher_generation,
        publisher_clinic_uuid=publisher_clinic,
        sender=sender,
        before_send=before_send,
        batch_size=int(os.environ.get("WORKER_BATCH_SIZE", "10")),
    )
    worker.application_enabled = os.environ.get("WORKER_APPLY_INBOX", "1") == "1"
    interval = float(os.environ.get("WORKER_INTERVAL_SECONDS", "1"))
    once = os.environ.get("SYNC_WORKER_ONCE") == "1"
    try:
        while not stop:
            if worker.application_enabled:
                applied = worker.run_application_once(limit=worker.batch_size)
                print(f"sync_worker application_claimed_or_applied={applied}", flush=True)
            if once:
                break
            time.sleep(interval)
    finally:
        worker.stop()
        engine.dispose()


if __name__ == "__main__":
    main()
