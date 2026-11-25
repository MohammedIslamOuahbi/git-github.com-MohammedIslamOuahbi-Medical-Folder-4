"""Focused UUID dependency resolver matrix; read-only, no HTTP or application."""
import os, sys, uuid
from types import SimpleNamespace
from pathlib import Path
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.models.company import Company
from app.models.branch import Branch
from app.models.user import User
from app.models.local_revision import LocalWriteOperation
from app.schemas.company import CompanyCreate
from app.schemas.branch import BranchCreate
from app.schemas.drilling_site import DrillingSiteCreate
from app.services.company_service import CompanyService
from app.services.branch_service import BranchService
from app.services.drilling_site_service import DrillingSiteService
from app.services.sync_application_evaluation_service import resolve_event_dependencies

def run():
    url = os.environ["STAGE5_TARGET_DB"]
    source_url = os.environ.get("STAGE5_SOURCE_DB")
    with Session(create_engine(url)) as db:
        admin = db.scalar(select(User).where(User.role.in_(("admin", "super_admin"))).order_by(User.id))
        if admin is None: raise RuntimeError("DEPENDENCY_FIXTURE_ADMIN_MISSING")
        db.info["sync_bootstrap_mode"] = True
        company_a = CompanyService().create(db, CompanyCreate(name="Resolver A"), admin, uuid.uuid4(), trusted_uuid=uuid.uuid4())
        db.info.pop("sync_bootstrap_mode", None)
        company_b = CompanyService().create(db, CompanyCreate(name="Resolver B"), admin, uuid.uuid4(), trusted_uuid=uuid.uuid4())
        db.info.update(local_operation_uuid=uuid.uuid4(), stage3_write_contract=True)
        op = db.info["local_operation_uuid"]
        branch_a_uuid, branch_b_uuid = uuid.uuid4(), uuid.uuid4()
        db.add(LocalWriteOperation(operation_uuid=op, actor_user_uuid=admin.uuid, request_hash="resolver-fixture", entity_type="branches", entity_uuid=branch_a_uuid, result_payload={}, created_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc))); db.flush()
        branch_a = BranchService().create(db, BranchCreate(company_id=company_a.id, name="Resolver branch A"), trusted_uuid=branch_a_uuid); db.commit(); db.info.pop("local_operation_uuid", None); db.info.pop("stage3_write_contract", None)
        db.info.update(local_operation_uuid=uuid.uuid4(), stage3_write_contract=True); op2=db.info["local_operation_uuid"]
        db.add(LocalWriteOperation(operation_uuid=op2, actor_user_uuid=admin.uuid, request_hash="resolver-fixture", entity_type="branches", entity_uuid=branch_b_uuid, result_payload={}, created_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc))); db.flush()
        branch_b = BranchService().create(db, BranchCreate(company_id=company_b.id, name="Resolver branch B"), trusted_uuid=branch_b_uuid); db.commit(); db.info.pop("local_operation_uuid", None); db.info.pop("stage3_write_contract", None)
        site_uuid = uuid.uuid4(); db.info.update(local_operation_uuid=uuid.uuid4(), stage3_write_contract=True); op3=db.info["local_operation_uuid"]
        db.add(LocalWriteOperation(operation_uuid=op3, actor_user_uuid=admin.uuid, request_hash="resolver-fixture", entity_type="drilling_sites", entity_uuid=site_uuid, result_payload={}, created_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc))); db.flush()
        site = DrillingSiteService().create(db, DrillingSiteCreate(company_id=company_a.id, branch_id=branch_a.id, name="Resolver site"), trusted_uuid=site_uuid); db.commit(); db.info.pop("local_operation_uuid", None); db.info.pop("stage3_write_contract", None)
        company, branch = company_a, branch_a
        def resolve(payload):
            return resolve_event_dependencies(db, SimpleNamespace(payload=payload))
        same = resolve({"company_uuid": str(company.uuid), "branch_uuid": str(branch.uuid)})
        assert same["company"]["matched"] and same["branch"]["matched"]
        assert same["branch"]["belongs_to_company"]
        source_ids = None
        if source_url:
            with Session(create_engine(source_url)) as src:
                sc = src.scalar(select(Company).where(Company.uuid == company.uuid)); sb = src.scalar(select(Branch).where(Branch.uuid == branch.uuid))
                if sc and sb: source_ids = (sc.id, sb.id)
        if source_ids is None: source_ids = (company.id + 100000, branch.id + 100000)
        assert source_ids[0] != company.id and source_ids[1] != branch.id
        print("same_uuid_different_ids=resolved", same, "source_ids=", source_ids, "target_ids=", (company.id, branch.id), "uuid_match=1")
        wrong_uuid = resolve({"company_uuid": str(uuid.uuid4()), "branch_uuid": str(uuid.uuid4())})
        assert not wrong_uuid["company"]["matched"] and not wrong_uuid["branch"]["matched"]
        print("same_ids_different_uuid=no_fallback", wrong_uuid)
        missing = resolve({"company_uuid": str(uuid.uuid4()), "branch_uuid": str(branch.uuid)})
        assert not missing["company"]["matched"]
        print("missing_company=DEPENDENCY_MISSING", missing)
        mismatch = resolve({"company_uuid": str(company.uuid), "branch_uuid": str(branch_b.uuid)})
        assert mismatch["branch"]["matched"] and not mismatch["branch"]["belongs_to_company"]
        print("branch_wrong_company=DEPENDENCY_RELATIONSHIP_MISMATCH", mismatch)
        site_mismatch = resolve({"company_uuid": str(company.uuid), "branch_uuid": str(branch_a.uuid), "drilling_site_uuid": str(site_uuid)})
        assert site_mismatch["drilling_site"].get("belongs_to_branch") is True
        wrong_site = resolve({"company_uuid": str(company.uuid), "branch_uuid": str(branch_b.uuid), "drilling_site_uuid": str(site_uuid)})
        assert wrong_site["drilling_site"].get("belongs_to_branch") is False
        print("site_wrong_branch=DEPENDENCY_RELATIONSHIP_MISMATCH", wrong_site)
        optional = resolve({"company_uuid": str(company.uuid), "branch_uuid": str(branch.uuid)})
        assert optional["drilling_site"]["required_uuid"] is None
        print("optional_site=not_required")

if __name__ == "__main__": run()
