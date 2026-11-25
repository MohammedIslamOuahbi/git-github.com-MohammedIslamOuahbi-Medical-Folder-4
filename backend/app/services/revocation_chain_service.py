import base64, hashlib, json
from datetime import datetime, timezone
from sqlalchemy import select
from app.models.revocation_chain_record import RevocationChainRecord
CHAIN_CANONICALIZATION = "revocation-chain-deterministic-json-v1"
CHAIN_DOMAIN = "medical-folder/revocation-chain/v1"
GENESIS_RECORD_HASH = "0" * 64
def record_bytes(x):
    payload={"domain":CHAIN_DOMAIN,"canonicalization_version":CHAIN_CANONICALIZATION,"authority_uuid":str(x["authority_uuid"]),"chain_scope":x["chain_scope"],"contract_version":x["contract_version"],"sequence":int(x["sequence"]),"previous_record_hash":x["previous_record_hash"],"record":x["record"]}
    return json.dumps(payload,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
def record_hash(x): return hashlib.sha256(record_bytes(x)).hexdigest()
def store_chain_record(db,x,*,authority_public_key):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    from cryptography.exceptions import InvalidSignature
    if x.get("canonicalization_version")!=CHAIN_CANONICALIZATION: raise ValueError("REVOCATION_CHAIN_CANONICALIZATION_UNSUPPORTED")
    try: Ed25519PublicKey.from_public_bytes(base64.b64decode(authority_public_key)).verify(base64.b64decode(x["signature"]),record_bytes(x))
    except (ValueError,KeyError,InvalidSignature): raise ValueError("REVOCATION_CHAIN_SIGNATURE_INVALID")
    if x["record_hash"]!=record_hash(x): raise ValueError("REVOCATION_CHAIN_HASH_INVALID")
    old=db.scalar(select(RevocationChainRecord).where(RevocationChainRecord.record_uuid==x["record_uuid"]))
    if old:
        if old.record_hash!=x["record_hash"]: raise ValueError("REVOCATION_CHAIN_IDENTITY_CONFLICT")
        return old
    same=db.scalar(select(RevocationChainRecord).where(RevocationChainRecord.authority_uuid==x["authority_uuid"],RevocationChainRecord.chain_scope==x["chain_scope"],RevocationChainRecord.sequence==x["sequence"]))
    if same: raise ValueError("REVOCATION_CHAIN_SEQUENCE_CONFLICT")
    row=RevocationChainRecord(**x,created_at=datetime.now(timezone.utc)); db.add(row); db.flush()
    if db.info.get("revocation_chain_fail_after_insert"): raise RuntimeError("REVOCATION_CHAIN_TEST_FAILURE")
    return row
def check_coverage(db,*,authority_uuid,chain_scope,checkpoint_sequence,checkpoint_hash):
    rows=db.scalars(select(RevocationChainRecord).where(RevocationChainRecord.authority_uuid==authority_uuid,RevocationChainRecord.chain_scope==chain_scope).order_by(RevocationChainRecord.sequence)).all(); expected=GENESIS_RECORD_HASH
    for i,row in enumerate(rows,1):
        if row.sequence!=i: return {"status":"incomplete","reason":"SEQUENCE_GAP","last_sequence":i-1}
        if row.previous_record_hash!=expected: return {"status":"conflicting","reason":"PREVIOUS_HASH_MISMATCH","last_sequence":i-1}
        expected=row.record_hash
        if i==checkpoint_sequence: return {"status":"complete" if expected==checkpoint_hash else "conflicting","reason":"HEAD_MATCH" if expected==checkpoint_hash else "CHECKPOINT_HEAD_MISMATCH","last_sequence":i}
    return {"status":"incomplete","reason":"CHECKPOINT_NOT_REACHED","last_sequence":len(rows)}
