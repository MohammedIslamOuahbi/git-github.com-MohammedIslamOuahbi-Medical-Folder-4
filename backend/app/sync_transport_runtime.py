"""Opt-in HTTP transport adapter for the external sync worker."""
from __future__ import annotations
import requests

def http_sender(*, target: str, source: str, secret: str, peer_device_uuid: str, channel: str):
    if not all((target, source, secret, peer_device_uuid, channel)):
        raise RuntimeError("INCOMPLETE_TRANSPORT_CONFIGURATION")
    def send(events):
        headers={"X-Sync-Device-UUID": peer_device_uuid, "X-Sync-Device-Secret": secret}
        body={"contract_version":"2.1","source_clinic_uuid":events[0]["source_clinic_uuid"],"source_device_uuid":events[0]["source_device_uuid"],"source_generation_uuid":events[0]["source_generation_uuid"],"channel":channel,"publisher_device_uuid":events[0].get("publication_source_device_uuid") or events[0]["source_device_uuid"],"publisher_generation_uuid":events[0].get("publication_source_generation_uuid") or events[0]["source_generation_uuid"],"publisher_clinic_uuid":events[0]["source_clinic_uuid"],"events":events,"limit":len(events)}
        r=requests.post(target.rstrip("/")+"/api/v1/sync/v2/receive",json=body,headers=headers,timeout=20);r.raise_for_status();data=r.json().get("data",{})
        if data.get("accepted",0)+data.get("duplicates",0)!=len(events): raise RuntimeError("RECEIVE_RESULT_EVENT_COUNT_MISMATCH")
        for event in events:
            ack=requests.post(source.rstrip("/")+"/api/v1/sync/v2/ack",json={"contract_version":"2.1","event_uuid":event["event_uuid"],"channel":channel,"lease_token":event["lease_token"],"publisher_device_uuid":event.get("publication_source_device_uuid") or event["source_device_uuid"],"publisher_generation_uuid":event.get("publication_source_generation_uuid") or event["source_generation_uuid"],"publisher_clinic_uuid":event["source_clinic_uuid"]},headers=headers,timeout=20);ack.raise_for_status()
    return send
