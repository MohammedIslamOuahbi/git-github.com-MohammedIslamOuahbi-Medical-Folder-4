"""Prepare isolated view-only test accounts in the two verified test DBs."""
import json, secrets, sys
from pathlib import Path
from sqlalchemy import create_engine, text, select
from sqlalchemy.orm import Session
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import settings
from app.models.user import User
from app.services.auth_service import AuthService
from sqlalchemy.engine import make_url
base=make_url(settings.database_url)
targets={"recovery_test":base, "transport_d":base.set(database="ibn_sina_transport_d")}
roles=("super_admin","admin","doctor","assistant")
out={}
for label,url in targets.items():
    engine=create_engine(url.render_as_string(hide_password=False), connect_args={"connect_timeout":5})
    with engine.connect() as c:
        db, schema, head=c.execute(text("select current_database(), current_schema(), (select version_num from alembic_version)")).one()
        assert db in {"ibn_sina_recovery_test","ibn_sina_transport_d"} and schema=="public"
        assert head == "20261008_06", (label, head)
    with Session(engine) as db:
        # This is an in-process, test-only bootstrap context. It is never
        # exposed through HTTP and is not enabled by the application runtime.
        db.info["sync_bootstrap_mode"] = True
        auth=AuthService(); out[label]={}
        for role in roles:
            email=f"stage4-view-{role}@{label}.invalid"
            user=db.scalar(select(User).where(User.email==email))
            password=secrets.token_urlsafe(18)
            if user is None:
                auth.create_platform_user(db, first_name="Stage4", last_name=role, email=email, password=password, role=role)
            else:
                password=None
            out[label][role]={"email":email,"password":password}
        db.commit()
Path(__file__).with_name(".stage4-view-credentials.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
print("Prepared isolated test accounts in both verified databases; credentials were written to the local ignored file.")
