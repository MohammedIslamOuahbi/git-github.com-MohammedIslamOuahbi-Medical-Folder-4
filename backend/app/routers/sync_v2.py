from __future__ import annotations

from fastapi import APIRouter, Depends, Request, HTTPException
from datetime import datetime, timezone
import uuid
import logging
import os
import time
from sqlalchemy.orm import Session

from app.dependencies.database import get_db
from app.dependencies.sync_transport import require_sync_transport_device
from app.models.sync_device import SyncDevice
from app.schemas.sync_transport import SyncTransportReceiveRequest, SyncTransportAckRequest, SyncTransportPullRequest, SyncTransportCursorRequest, OriginProofReceiveRequest, OriginProofAckRequest
from app.models.sync_transport import SyncTransportCursor, SyncEventDelivery, SyncEventPublication, SyncTransportEvent
from sqlalchemy import select, text
from app.services.sync_transport_service import SyncTransportService
from app.utils.responses import success_response

router = APIRouter(prefix="/sync/v2", tags=["Sync transport v2"])
service = SyncTransportService()
log = logging.getLogger("sync.transport.ack")

@router.post('/proof-receive')
def receive_origin_proof(payload: OriginProofReceiveRequest, device: SyncDevice = Depends(require_sync_transport_device), db: Session = Depends(get_db)):
    if os.environ.get('PROOF_TRANSPORT_ENABLED') != '1':
        raise HTTPException(status_code=423, detail={'code':'PROOF_TRANSPORT_DISABLED'})
    service.authorize_relay(db, carrier_device_uuid=device.uuid, origin_device_uuid=payload.source_device_uuid, origin_generation_uuid=payload.source_generation_uuid, destination_device_uuid=device.uuid, channel=payload.channel)
    from app.models.origin_proof_transport import OriginProofTransportReceipt
    from datetime import datetime, timezone
    existing=db.scalar(select(OriginProofTransportReceipt).where(OriginProofTransportReceipt.proof_uuid==payload.proof_uuid, OriginProofTransportReceipt.peer_device_uuid==device.uuid))
    if existing is not None:
        if existing.content_sha256 != payload.content_sha256 or existing.event_uuid != payload.event_uuid or existing.proof != payload.proof:
            raise HTTPException(status_code=409, detail={'code':'PROOF_CONTENT_MISMATCH'})
        import hashlib
        from app.services.proof_verification_service import canonical_bytes
        return success_response('Origin proof already received', {'status':'received','duplicate':True,'receipt_uuid':str(existing.receipt_uuid),'proof_uuid':str(payload.proof_uuid),'event_uuid':str(existing.event_uuid),'content_sha256':existing.content_sha256,'proof_sha256':hashlib.sha256(canonical_bytes(existing.proof)).hexdigest(),'peer_device_uuid':str(existing.peer_device_uuid),'source_device_uuid':str(existing.source_device_uuid),'source_generation_uuid':str(existing.source_generation_uuid),'channel':existing.channel})
    from app.services.proof_verification_service import validate_required_fields, canonical_bytes
    if validate_required_fields(payload.proof) != 'valid' or str(payload.proof.get('event_uuid')) != str(payload.event_uuid) or payload.proof.get('content_sha256') != payload.content_sha256:
        raise HTTPException(status_code=422, detail={'code':'PROOF_BINDING_INVALID'})
    import hashlib
    proof_sha256=hashlib.sha256(canonical_bytes(payload.proof)).hexdigest()
    receipt_uuid=uuid.uuid4(); db.add(OriginProofTransportReceipt(receipt_uuid=receipt_uuid,proof_uuid=payload.proof_uuid,event_uuid=payload.event_uuid,content_sha256=payload.content_sha256,peer_device_uuid=device.uuid,source_device_uuid=payload.source_device_uuid,source_generation_uuid=payload.source_generation_uuid,channel=payload.channel,proof=payload.proof,status='received',received_at=datetime.now(timezone.utc)))
    if os.environ.get('ORIGIN_PROOF_RECONCILIATION_TEST') == '1':
        from app.services.proof_trust_binding_service import resolve_local_binding
        from app.services.origin_proof_reconciliation_queue import enqueue
        local = resolve_local_binding(db, proof=payload.proof, clinic_uuid=payload.proof.get('clinic_uuid'), origin_service_uuid=payload.proof.get('origin_service_uuid'), policy_version=payload.proof.get('authorization_policy_version'))
        scope = local.get('chain_scope') if local.get('status') == 'resolved' else ('unresolved:' + str(payload.proof.get('signing_key_id', 'unknown')))
        enqueue(db,event_uuid=payload.event_uuid,proof_uuid=payload.proof_uuid,peer_device_uuid=device.uuid,chain_scope=scope)
    db.commit()
    if os.environ.get('ORIGIN_PROOF_RECONCILIATION_TEST') == '1':
        from app.services.origin_proof_reconciliation import schedule_origin_proof_reconciliation
        schedule_origin_proof_reconciliation(payload.event_uuid, device.uuid)
    return success_response('Origin proof received; verification pending', {'status':'received','receipt_uuid':str(receipt_uuid),'proof_uuid':str(payload.proof_uuid),'event_uuid':str(payload.event_uuid),'content_sha256':payload.content_sha256,'proof_sha256':proof_sha256,'peer_device_uuid':str(device.uuid),'source_device_uuid':str(payload.source_device_uuid),'source_generation_uuid':str(payload.source_generation_uuid),'channel':payload.channel})

@router.post('/proof-ack')
def acknowledge_origin_proof(payload: OriginProofAckRequest, device: SyncDevice = Depends(require_sync_transport_device), db: Session = Depends(get_db)):
    if os.environ.get('PROOF_TRANSPORT_ENABLED') != '1':
        raise HTTPException(status_code=423, detail={'code':'PROOF_TRANSPORT_DISABLED'})
    from app.models.origin_proof_transport import OriginProofTransportReceipt
    from datetime import datetime, timezone
    row=db.scalar(select(OriginProofTransportReceipt).where(OriginProofTransportReceipt.receipt_uuid==payload.receipt_uuid,OriginProofTransportReceipt.proof_uuid==payload.proof_uuid,OriginProofTransportReceipt.peer_device_uuid==device.uuid,OriginProofTransportReceipt.channel==payload.channel,OriginProofTransportReceipt.source_device_uuid==payload.source_device_uuid,OriginProofTransportReceipt.source_generation_uuid==payload.source_generation_uuid).with_for_update())
    if row is None: raise HTTPException(status_code=404, detail={'code':'PROOF_NOT_RECEIVED'})
    row.status='acknowledged'; row.acknowledged_at=datetime.now(timezone.utc); db.commit(); return success_response('Origin proof acknowledged', {'status':'acknowledged','proof_uuid':str(payload.proof_uuid)})

@router.post('/proof-capabilities')
def proof_capabilities(payload: dict, device: SyncDevice = Depends(require_sync_transport_device), db: Session = Depends(get_db)):
    peer_uuid = payload.get('peer_device_uuid'); scope = payload.get('connection_scope'); versions = payload.get('supported_versions')
    origin_uuid = payload.get('origin_device_uuid'); generation_uuid = payload.get('origin_generation_uuid')
    if (peer_uuid != str(device.uuid) or not isinstance(scope, str) or not scope
            or not isinstance(versions,list) or not origin_uuid or not generation_uuid):
        raise HTTPException(status_code=400, detail={'code':'PROOF_CAPABILITY_SCOPE_INVALID'})
    # A connection scope is an authorized transport resource, not a caller label.
    # The authenticated device must have an active relay authorization for it.
    from app.models.sync_transport import SyncRelayAuthorization
    authorized = db.scalar(select(SyncRelayAuthorization.id).where(
        SyncRelayAuthorization.carrier_device_uuid == device.uuid,
        SyncRelayAuthorization.origin_device_uuid == origin_uuid,
        SyncRelayAuthorization.origin_generation_uuid == generation_uuid,
        SyncRelayAuthorization.destination_device_uuid == device.uuid,
        SyncRelayAuthorization.channel == scope,
        SyncRelayAuthorization.is_active.is_(True),
    ))
    if authorized is None:
        raise HTTPException(status_code=403, detail={'code':'PROOF_CAPABILITY_SCOPE_UNAUTHORIZED'})
    import os
    server_versions={int(v) for v in os.environ.get('PROOF_TRANSPORT_SUPPORTED_VERSIONS','1').split(',') if v.strip().isdigit()}
    # bool is an int subclass in Python but is not a protocol version.
    supported = sorted({v for v in versions if type(v) is int and v in server_versions})
    from app.models.proof_transport_capability import ProofTransportCapability
    # The advisory-lock identity must equal the durable row identity.  Origin
    # and generation remain authorization/binding inputs, not row partitioning.
    lock_key = f"{device.uuid}:{scope}"
    db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"), {"key": lock_key})
    row=db.execute(select(ProofTransportCapability).where(
        ProofTransportCapability.peer_device_uuid == device.uuid,
        ProofTransportCapability.connection_scope == scope,
    ).with_for_update()).scalar_one_or_none()
    pause_file = os.environ.get('PROOF_CAPABILITY_PAUSE_FILE') if os.environ.get('PROOF_CAPABILITY_TEST_HOOK') == '1' else None
    release_file = os.environ.get('PROOF_CAPABILITY_RELEASE_FILE')
    deadline = time.monotonic() + float(os.environ.get('PROOF_CAPABILITY_HOOK_TIMEOUT', '20'))
    if pause_file and release_file and not os.path.exists(pause_file):
        open(pause_file, 'w', encoding='utf-8').close()
        while not os.path.exists(release_file) and time.monotonic() < deadline:
            time.sleep(0.02)
        if not os.path.exists(release_file):
            raise HTTPException(status_code=409, detail={'code':'PROOF_CAPABILITY_TEST_HOOK_TIMEOUT'})
    next_sequence = (row.advertisement_sequence if row else 0) + 1
    identity = {
        'peer_device_uuid': str(device.uuid),
        'connection_scope': scope,
        'origin_device_uuid': str(origin_uuid),
        'origin_generation_uuid': str(generation_uuid),
    }
    if not supported:
        if row is not None:
            row.proof_transport_version=0; row.advertisement_sequence=next_sequence
            row.advertisement_uuid=uuid.uuid4(); row.updated_at=datetime.now(timezone.utc); db.commit()
        return success_response('Proof transport unsupported', {'status':'unsupported','reason':'PROOF_TRANSPORT_UNSUPPORTED','advertisement_sequence':next_sequence, **identity})
    if row is None: row=ProofTransportCapability(peer_device_uuid=device.uuid,connection_scope=scope,proof_transport_version=supported[-1],advertisement_uuid=uuid.uuid4(),advertisement_sequence=next_sequence,updated_at=datetime.now(timezone.utc)); db.add(row)
    else: row.proof_transport_version=supported[-1]; row.advertisement_sequence=next_sequence; row.advertisement_uuid=uuid.uuid4(); row.updated_at=datetime.now(timezone.utc)
    db.commit(); return success_response('Proof transport capability negotiated', {'status':'accepted','proof_transport_version':supported[-1],'advertisement_sequence':next_sequence, **identity})

@router.get('/proof-capabilities')
def read_proof_capability(peer_device_uuid: str, connection_scope: str,
                          origin_device_uuid: str, origin_generation_uuid: str,
                          device: SyncDevice = Depends(require_sync_transport_device),
                          db: Session = Depends(get_db)):
    if peer_device_uuid != str(device.uuid):
        raise HTTPException(status_code=400, detail={'code':'PROOF_CAPABILITY_SCOPE_INVALID'})
    from app.models.sync_transport import SyncRelayAuthorization
    authorized = db.scalar(select(SyncRelayAuthorization.id).where(
        SyncRelayAuthorization.carrier_device_uuid == device.uuid,
        SyncRelayAuthorization.origin_device_uuid == origin_device_uuid,
        SyncRelayAuthorization.origin_generation_uuid == origin_generation_uuid,
        SyncRelayAuthorization.destination_device_uuid == device.uuid,
        SyncRelayAuthorization.channel == connection_scope,
        SyncRelayAuthorization.is_active.is_(True)))
    if authorized is None:
        raise HTTPException(status_code=403, detail={'code':'PROOF_CAPABILITY_SCOPE_UNAUTHORIZED'})
    from app.models.proof_transport_capability import ProofTransportCapability
    row = db.get(ProofTransportCapability, (device.uuid, connection_scope))
    return success_response('Proof transport capability', {
        'status': 'unsupported' if not row or row.proof_transport_version == 0 else 'accepted',
        'proof_transport_version': row.proof_transport_version if row else 0,
        'advertisement_sequence': row.advertisement_sequence if row else 0,
        'peer_device_uuid': str(device.uuid), 'connection_scope': connection_scope,
        'origin_device_uuid': origin_device_uuid, 'origin_generation_uuid': origin_generation_uuid})


@router.post("/receive")
def receive_events(payload: SyncTransportReceiveRequest, device: SyncDevice = Depends(require_sync_transport_device), db: Session = Depends(get_db)):
    service.authorize_relay(db, carrier_device_uuid=device.uuid, origin_device_uuid=payload.source_device_uuid,
                            origin_generation_uuid=payload.source_generation_uuid,
                            destination_device_uuid=device.uuid, channel=payload.channel)
    result = service.receive_batch(db, receiver_device_uuid=device.uuid, source_clinic_uuid=payload.source_clinic_uuid,
                                   source_device_uuid=payload.source_device_uuid, channel=payload.channel,
                                   events=payload.events, source_generation_uuid=payload.source_generation_uuid,
                                   limit=payload.limit, publisher_device_uuid=payload.publisher_device_uuid,
                                   publisher_generation_uuid=payload.publisher_generation_uuid,
                                   publisher_clinic_uuid=payload.publisher_clinic_uuid)
    if os.environ.get('ORIGIN_PROOF_RECONCILIATION_TEST') == '1':
        from app.services.origin_proof_reconciliation import schedule_origin_proof_reconciliation
        for event in payload.events:
            schedule_origin_proof_reconciliation(uuid.UUID(str(event['event_uuid'])), device.uuid)
    return success_response("Events received and durably stored; waiting for application", result)

@router.post("/pull")
def pull_events(payload: SyncTransportPullRequest, device: SyncDevice = Depends(require_sync_transport_device), db: Session = Depends(get_db)):
    service.authorize_device(db, payload.source_device_uuid)
    service.authorize_relay(db, carrier_device_uuid=device.uuid, origin_device_uuid=payload.source_device_uuid,
                            origin_generation_uuid=payload.source_generation_uuid,
                            destination_device_uuid=device.uuid, channel=payload.channel)
    # The requested publisher scope is independently authorized; payload fields
    # alone must never confer the publisher identity.
    service.authorize_relay(db, carrier_device_uuid=device.uuid,
                            origin_device_uuid=payload.publisher_device_uuid,
                            origin_generation_uuid=payload.publisher_generation_uuid,
                            destination_device_uuid=device.uuid, channel=payload.channel)
    service.publish_committed(db, channel=payload.channel, limit=1000,
                              source_device_uuid=payload.source_device_uuid,
                              source_generation_uuid=payload.source_generation_uuid,
                              source_clinic_uuid=payload.source_clinic_uuid,
                              publisher_device_uuid=payload.publisher_device_uuid,
                              publisher_generation_uuid=payload.publisher_generation_uuid)
    service.queue_for_peer(db, peer_device_uuid=device.uuid, channel=payload.channel,
                           source_clinic_uuid=payload.source_clinic_uuid,
                           source_generation_uuid=payload.source_generation_uuid,
                           source_device_uuid=payload.source_device_uuid, limit=1000)
    events = service.claim_batch(db, peer_device_uuid=device.uuid, channel=payload.channel, limit=payload.limit,
                                 publisher_device_uuid=payload.publisher_device_uuid,
                                 publisher_generation_uuid=payload.publisher_generation_uuid,
                                 publisher_clinic_uuid=payload.publisher_clinic_uuid)
    positions = [e.get("publish_sequence") for e in events if e.get("publish_sequence") is not None]
    result = {"events": events, "has_more": len(events) == payload.limit,
              "source_device_uuid": str(payload.source_device_uuid),
              "source_generation_uuid": str(payload.source_generation_uuid), "channel": payload.channel,
              "publication": {"source_device_uuid": str(payload.source_device_uuid),
                               "source_generation_uuid": str(payload.source_generation_uuid),
                               "channel": payload.channel,
                               "first_publish_sequence": min(positions) if positions else None,
                               "last_publish_sequence": max(positions) if positions else payload.after_sequence}}
    return success_response("Committed publication events available for transport", result)

@router.post("/ack")
def acknowledge_event(payload: SyncTransportAckRequest, request: Request, device: SyncDevice = Depends(require_sync_transport_device), db: Session = Depends(get_db)):
    delivery = db.scalar(select(SyncEventDelivery).where(
        SyncEventDelivery.event_uuid == payload.event_uuid,
        SyncEventDelivery.peer_device_uuid == device.uuid,
        SyncEventDelivery.channel == payload.channel,
    ))
    publication = db.scalar(select(SyncEventPublication).where(
        SyncEventPublication.event_uuid == payload.event_uuid,
        SyncEventPublication.channel == payload.channel,
    ).order_by(SyncEventPublication.publish_sequence.asc()))
    event = db.scalar(select(SyncTransportEvent).where(SyncTransportEvent.event_uuid == payload.event_uuid))
    correlation = request.headers.get("X-Correlation-ID", "ack-unknown")[:100]
    log.info("ack_authorize_inputs correlation=%s carrier=%s origin=%s origin_generation=%s destination=%s channel=%s clinic=%s delivery_publisher=%s delivery_generation=%s delivery_clinic=%s publication_publisher=%s publication_generation=%s event_origin=%s event_generation=%s",
             correlation, device.uuid, payload.publisher_device_uuid, payload.publisher_generation_uuid,
             device.uuid, payload.channel, payload.publisher_clinic_uuid,
             getattr(delivery, "publisher_device_uuid", None), getattr(delivery, "publisher_generation_uuid", None), getattr(delivery, "clinic_uuid", None),
             getattr(publication, "publisher_device_uuid", None), getattr(publication, "publisher_generation_uuid", None),
             getattr(event, "source_device_uuid", None), getattr(event, "source_generation_uuid", None))
    service.authorize_relay(db, carrier_device_uuid=device.uuid, origin_device_uuid=payload.publisher_device_uuid,
                            origin_generation_uuid=payload.publisher_generation_uuid,
                            destination_device_uuid=device.uuid, channel=payload.channel)
    service.acknowledge(db, event_uuid=payload.event_uuid, peer_device_uuid=device.uuid,
                        channel=payload.channel, lease_token=payload.lease_token,
                        publisher_device_uuid=payload.publisher_device_uuid,
                        publisher_generation_uuid=payload.publisher_generation_uuid,
                        publisher_clinic_uuid=payload.publisher_clinic_uuid)
    return success_response("Event delivery acknowledged", {"event_uuid": str(payload.event_uuid), "status": "delivered"})

@router.post("/cursor")
def read_cursor(payload: SyncTransportCursorRequest, device: SyncDevice = Depends(require_sync_transport_device), db: Session = Depends(get_db)):
    service.authorize_relay(db, carrier_device_uuid=device.uuid, origin_device_uuid=payload.source_device_uuid,
                            origin_generation_uuid=payload.source_generation_uuid,
                            destination_device_uuid=device.uuid, channel=payload.channel)
    row = db.scalar(select(SyncTransportCursor).where(
        SyncTransportCursor.peer_device_uuid == device.uuid,
        SyncTransportCursor.source_device_uuid == payload.source_device_uuid,
        SyncTransportCursor.source_generation_uuid == payload.source_generation_uuid,
        SyncTransportCursor.channel == payload.channel,
        SyncTransportCursor.publisher_device_uuid == payload.publisher_device_uuid,
        SyncTransportCursor.publisher_generation_uuid == payload.publisher_generation_uuid,
        SyncTransportCursor.clinic_uuid == payload.publisher_clinic_uuid))
    return success_response("Durable transport cursor", {
        "last_source_sequence": row.last_source_sequence if row else 0,
        "last_event_uuid": str(row.last_event_uuid) if row and row.last_event_uuid else None,
        "last_publish_sequence": row.last_publish_sequence if row else 0,
        "last_publication_event_uuid": str(row.last_publication_event_uuid) if row and row.last_publication_event_uuid else None,
        "source_device_uuid": str(payload.source_device_uuid), "source_generation_uuid": str(payload.source_generation_uuid), "channel": payload.channel})
