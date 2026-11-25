import requests

def interpret_capability_response(response, *, target, peer, scope,
                                  origin_device, origin_generation, versions,
                                  headers):
    try:
        data = response.json().get('data', {})
    except Exception:
        return 'negotiation_failed'
    if response.status_code != 200:
        return 'negotiation_failed'
    identity_ok = (
        data.get('peer_device_uuid') == str(peer)
        and data.get('connection_scope') == scope
        and data.get('origin_device_uuid') == origin_device
        and data.get('origin_generation_uuid') == origin_generation
    )
    sequence = data.get('advertisement_sequence')
    if not identity_ok or type(sequence) is not int:
        return 'negotiation_failed'
    current = requests.get(target + '/api/v1/sync/v2/proof-capabilities', params={
        'peer_device_uuid': str(peer), 'connection_scope': scope,
        'origin_device_uuid': origin_device,
        'origin_generation_uuid': origin_generation}, headers=headers, timeout=10)
    try:
        current_data = current.json().get('data', {})
    except Exception:
        return 'negotiation_failed'
    if (current.status_code != 200
            or current_data.get('peer_device_uuid') != str(peer)
            or current_data.get('connection_scope') != scope
            or current_data.get('origin_device_uuid') != origin_device
            or current_data.get('origin_generation_uuid') != origin_generation
            or current_data.get('advertisement_sequence') != sequence
            or current_data.get('status') != data.get('status')):
        return 'negotiation_failed'
    if data.get('status') == 'accepted':
        return ('supported' if type(data.get('proof_transport_version')) is int
                and data.get('proof_transport_version') in versions
                and data.get('proof_transport_version') == 1 else 'negotiation_failed')
    if data.get('status') == 'unsupported':
        return 'unsupported'
    return 'negotiation_failed'
