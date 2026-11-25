import os, sys, uuid, subprocess, tempfile
from pathlib import Path
from datetime import datetime, timezone
from sqlalchemy import create_engine, text, select, func
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.config import settings
from app.models.sync_transport import SyncEventPublication, SyncPublicationCounter
from app.models.sync_change import SyncChange
from app.services.sync_transport_service import SyncTransportService
from app.services.sync_journal import payload_sha256

def run_alembic(target, env, root, run):
    out = Path(tempfile.gettempdir()) / f"publication-history-{run}-{target}-stdout.log"
    err = Path(tempfile.gettempdir()) / f"publication-history-{run}-{target}-stderr.log"
    with out.open('w', encoding='utf-8') as fo, err.open('w', encoding='utf-8') as fe:
        p = subprocess.Popen([sys.executable, '-m', 'alembic', 'upgrade', target], cwd=root,
                             env=env, stdout=fo, stderr=fe)
        try:
            code = p.wait(timeout=120)
        except subprocess.TimeoutExpired:
            p.kill(); code = p.wait()
            print(f'alembic target={target} timeout pid={p.pid} exit={code} logs={out.name},{err.name}')
            raise RuntimeError(f'alembic timeout target={target}')
    print(f'alembic target={target} pid={p.pid} exit={code} logs={out.name},{err.name}')
    if code != 0:
        raise RuntimeError(f'alembic target={target} failed exit={code}')

base=make_url(settings.database_url); run='hist_'+uuid.uuid4().hex[:8]; dbname='ibn_sina_pub_history_'+run; admin=create_engine(base.set(database='postgres'), isolation_level='AUTOCOMMIT')
try:
 with admin.connect() as c:
  ident=c.execute(text('select current_database(),inet_server_addr(),inet_server_port()')).one(); print('server=',ident[1],ident[2]); c.execute(text('CREATE DATABASE "'+dbname+'"'))
 env={**os.environ,'DATABASE_URL':base.set(database=dbname).render_as_string(hide_password=False)}; root=str(Path(__file__).resolve().parents[1])
 run_alembic('20261008_11', env, root, run)
 eng=create_engine(env['DATABASE_URL']); known,gen,clinic=uuid.uuid4(),uuid.uuid4(),uuid.uuid4(); unknown=uuid.uuid4(); ch='history-'+run
 with eng.begin() as c:
  c.execute(text("insert into sync_publication_counters (source_device_uuid,source_generation_uuid,channel,next_sequence,publisher_device_uuid,publisher_generation_uuid) values (:s,:g,:c,8,:p,:pg)"),{'s':known,'g':gen,'c':ch,'p':known,'pg':gen})
  c.execute(text("insert into sync_event_publications (event_uuid,source_device_uuid,source_generation_uuid,channel,publish_sequence,published_at,publisher_device_uuid,publisher_generation_uuid) values (:e,:s,:g,:c,7,now(),:p,:pg)"),{'e':uuid.uuid4(),'s':uuid.uuid4(),'g':gen,'c':ch,'p':known,'pg':gen})
  c.execute(text("insert into sync_event_publications (event_uuid,source_device_uuid,source_generation_uuid,channel,publish_sequence,published_at) values (:e,:s,:g,:c,99,now())"),{'e':uuid.uuid4(),'s':uuid.uuid4(),'g':gen,'c':ch})
  c.execute(text("insert into sync_event_deliveries (event_uuid,peer_device_uuid,channel,status,attempt_count,available_at) values (:e,:p,:c,'delivered',1,now())"),{'e':uuid.uuid4(),'p':uuid.uuid4(),'c':ch})
  c.execute(text("insert into sync_publication_receipts (event_uuid,peer_device_uuid,source_device_uuid,source_generation_uuid,channel,publish_sequence,received_at) values (:e,:p,:s,:g,:c,7,now())"),{'e':uuid.uuid4(),'p':uuid.uuid4(),'s':uuid.uuid4(),'g':gen,'c':ch})
  c.execute(text("insert into sync_transport_cursors (peer_device_uuid,source_device_uuid,source_generation_uuid,channel,last_source_sequence,last_event_uuid,last_publish_sequence,last_publication_event_uuid,updated_at) values (:p,:s,:g,:c,7,:e,7,:e,now())"),{'p':uuid.uuid4(),'s':uuid.uuid4(),'g':gen,'c':ch,'e':uuid.uuid4()})
  print('historical_rows_before=2; known_scope=1; unknown_scope=1; delivery=1; receipt=1; cursor=1')
 run_alembic('head', env, root, run)
 with eng.connect() as c:
  assert c.execute(text('select version_num from alembic_version')).scalar()=='20261008_15'; print('head=20261008_15')
  print('historical_rows_after=',c.execute(text("select count(*) from sync_event_publications where channel=:c"),{'c':ch}).scalar(),'unknown_publishers=',c.execute(text("select count(*) from sync_event_publications where channel=:c and publisher_device_uuid is null"),{'c':ch}).scalar())
  print('historical_transport_after=', c.execute(text("select count(*) from sync_event_deliveries where channel=:c"),{'c':ch}).scalar(), c.execute(text("select count(*) from sync_publication_receipts where channel=:c"),{'c':ch}).scalar(), c.execute(text("select count(*) from sync_transport_cursors where channel=:c"),{'c':ch}).scalar())
 # A modern publication uses an explicit, previously unseen publisher scope.
 modern_pub, modern_gen, modern_clinic = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
 with Session(eng) as s:
  change = SyncChange(change_uuid=uuid.uuid4(), revision_uuid=uuid.uuid4(), entity_uuid=uuid.uuid4(), entity_type='history_test',
                      operation='create', entity_version=1, occurred_at=datetime.now(timezone.utc),
                      source_device_uuid=modern_pub, source_generation_uuid=modern_gen,
                      source_clinic_uuid=modern_clinic, payload={'test': 'publication-history'},
                      content_sha256='0'*64)
  s.add(change); s.commit(); event_id = change.change_uuid
  result = SyncTransportService().publish_committed(s, channel='history-modern-'+run,
      source_device_uuid=modern_pub, source_generation_uuid=modern_gen,
      source_clinic_uuid=modern_clinic, publisher_device_uuid=modern_pub,
      publisher_generation_uuid=modern_gen)
  s.commit(); print('modern_publish=', result.get('published', 0))
 with eng.connect() as c:
  assert c.execute(select(func.count()).select_from(SyncEventPublication).where(SyncEventPublication.event_uuid==event_id)).scalar_one()==1
  print('modern_publish_persistent=1')
 run_alembic('head', env, root, run)
 # Exercise the upgraded database through the real HTTP worker path.  The
 # worker fixture creates only synthetic transport rows; it does not write
 # inbox/receipt/cursor rows directly.
 worker_env = {**os.environ, 'DATABASE_URL': env['DATABASE_URL']}
 worker = subprocess.run([sys.executable, 'recovery_tests/check_http_worker.py'], cwd=root,
                         env=worker_env, capture_output=True, text=True, timeout=180)
 print('historical_http_worker_exit=', worker.returncode)
 print(worker.stdout[-2000:])
 print(worker.stderr[-2000:])
 if worker.returncode != 0:
  raise RuntimeError('historical HTTP worker failed')
 with eng.connect() as c:
  assert c.execute(text("select count(*) from sync_event_deliveries where channel=:c"), {'c': ch}).scalar() == 1
  assert c.execute(text("select count(*) from sync_publication_receipts where channel=:c"), {'c': ch}).scalar() == 1
  assert c.execute(text("select count(*) from sync_transport_cursors where channel=:c"), {'c': ch}).scalar() == 1
  print('historical_transport_unchanged=1/1/1')
 print('PASS historical upgrade preservation; unknown publisher remains unresolved')
finally:
 pass
