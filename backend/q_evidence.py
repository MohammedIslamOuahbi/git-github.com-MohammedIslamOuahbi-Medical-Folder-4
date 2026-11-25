from sqlalchemy import create_engine,text
from app.config import settings
ids=['eb85dd6b-644a-45bc-820c-2e43d9455477','6b8b7852-9f9b-422f-850e-c4812a665558','b52ec95e-ebe1-4732-8f80-6471a50a1431','c727db03-5891-4498-b4c4-983a7d61aaa9','7cbe66fb-64a1-46e8-920e-d53f3e67066d']
e=create_engine(settings.database_url)
with e.connect() as c:
 for t in ['sync_event_deliveries','sync_publication_receipts']:
  rows=c.execute(text(f"select * from {t} where event_uuid = any(CAST(:ids AS uuid[]))"),{'ids':ids}).all(); print(t,len(rows)); print(rows[:10])
 rows=c.execute(text("select * from sync_transport_cursors where last_publication_event_uuid = any(CAST(:ids AS uuid[]))"),{'ids':ids}).all(); print('sync_transport_cursors',len(rows)); print(rows[:10])

