import os, sys
from pathlib import Path
from sqlalchemy import create_engine, text, select
from sqlalchemy.orm import Session
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import settings
from app.services.auth_service import AuthService
from app.models.user import User
from sqlalchemy.engine import make_url

accounts = [
    ('Babziz', 'Saleh', 'babzizsaleh@ibnsina.com', 'babziz saleh', 'super_admin'),
    ('Babziz', 'Mostafa', 'babzizmostafa@ibnsina.com', 'babziz mostafa', 'admin'),
    ('Ouahbi', 'Mohammed Islam', 'ouahbimohammedislam@ibnsina.com', 'mohammed islam', 'admin'),
]
url = make_url(settings.database_url).set(database=os.environ.get('PREVIEW_DB', 'ibn_sina_cap_418ef234')).render_as_string(hide_password=False)
engine = create_engine(url)
with engine.connect() as c:
    db, head = c.execute(text('select current_database(), (select version_num from alembic_version)')).one()
    if head != '20261008_23':
        raise SystemExit(f'Unsupported preview database head: {head}; expected 20261008_23')
with Session(engine) as db:
    db.info['sync_bootstrap_mode'] = True
    service = AuthService()
    for first_name, last_name, email, password, role in accounts:
        service.create_platform_user(db, first_name, last_name, email, password, role)
    db.commit()
print('Preview accounts ready: 3 synthetic local accounts')
