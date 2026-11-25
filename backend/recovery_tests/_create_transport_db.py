import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import settings
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
u=make_url(settings.database_url).set(database='postgres')
e=create_engine(u)
name = 'ibn_sina_transport_d'
with e.connect() as c:
    c.execution_options(isolation_level='AUTOCOMMIT').execute(text('CREATE DATABASE ' + name))
print('created')
