import base64,hashlib,json,uuid
from datetime import datetime,timezone
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.exceptions import InvalidSignature
from sqlalchemy import select, text
from app.models.revocation_checkpoint import RevocationCheckpoint
CANONICALIZATION='revocation-checkpoint-deterministic-json-v1'; DOMAIN='medical-folder/revocation-checkpoint/v1'
FIELDS=('checkpoint_uuid','authority_uuid','authority_key_id','chain_scope','contract_version','policy_version','covered_sequence','covered_chain_hash','challenge','destination_device_uuid')
def canonical_checkpoint_bytes(x):
 p={'domain':DOMAIN,'canonicalization_version':CANONICALIZATION}; p.update({k:x[k] for k in FIELDS}); return json.dumps(p,sort_keys=True,separators=(',',':')).encode()
def verify_checkpoint_signature(x,public_key):
 try: Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key)).verify(base64.b64decode(x['signature']),canonical_checkpoint_bytes(x)); return 'valid'
 except (ValueError,KeyError,InvalidSignature): return 'invalid'
def store_checkpoint(db,x,*,public_key):
 if verify_checkpoint_signature(x,public_key)!='valid': raise ValueError('CHECKPOINT_SIGNATURE_INVALID')
 existing=db.scalar(select(RevocationCheckpoint).where(RevocationCheckpoint.checkpoint_uuid==x['checkpoint_uuid']))
 if existing:
  if existing.covered_chain_hash!=x['covered_chain_hash'] or existing.covered_sequence!=x['covered_sequence']: raise ValueError('CHECKPOINT_CONTENT_MISMATCH')
  return existing
 db.execute(text("select pg_advisory_xact_lock(hashtextextended(:k,0))"),{'k':str(x['authority_uuid'])+':'+x['chain_scope']})
 current=db.scalar(select(RevocationCheckpoint).where(RevocationCheckpoint.authority_uuid==x['authority_uuid'],RevocationCheckpoint.chain_scope==x['chain_scope'],RevocationCheckpoint.is_current.is_(True)).with_for_update())
 historical = bool(current and x['covered_sequence'] < current.covered_sequence)
 if current and x['covered_sequence']==current.covered_sequence and current.covered_chain_hash!=x['covered_chain_hash']: raise ValueError('CHECKPOINT_SEQUENCE_CONFLICT')
 if current and not historical: current.is_current=False
 row=RevocationCheckpoint(**{k:x[k] for k in FIELDS},canonicalization_version=CANONICALIZATION,signature=x['signature'],is_current=not historical,created_at=datetime.now(timezone.utc)); db.add(row); db.flush()
 if db.info.get('checkpoint_fail_after_insert'): raise RuntimeError('CHECKPOINT_SAVE_FAILED')
 return row
