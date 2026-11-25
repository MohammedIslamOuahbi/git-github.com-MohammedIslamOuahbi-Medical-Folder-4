from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from random import Random

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.constants import DEFAULT_ADMIN_EMAIL, DEFAULT_ADMIN_PASSWORD
from app.core.security import hash_password
from app.database import SessionLocal
from app.models.assistant_campaign import AssistantCampaign
from app.models.branch import Branch
from app.models.campaign_test import CampaignTest
from app.models.campaign_worker import CampaignWorker
from app.models.company import Company
from app.models.doctor_campaign import DoctorCampaign
from app.models.drilling_site import DrillingSite
from app.models.medical_campaign import MedicalCampaign
from app.models.medical_test import MedicalTest
from app.models.user import User
from app.models.worker import Worker
from app.models.worker_test import WorkerTest
from app.models.workspace import Workspace
from app.seed.seed_tests import DEFAULT_TESTS

RNG = Random(42)
DEMO_PASSWORD = "demo12345"
DEMO_PREFIX = "demo_seed"

USER_COUNTS = {
    "doctor": 4,
    "assistant": 8,
}

COMPANY_COUNT = 20
BRANCHES_PER_COMPANY = 5
SITES_PER_BRANCH = 2
WORKERS_PER_BRANCH = 5
CAMPAIGNS_PER_COMPANY = 3
TESTS_PER_CAMPAIGN = 4
WORKERS_PER_CAMPAIGN = 12

COMPANY_PROFILES = [
    {
        "name": "SONATRACH",
        "email": "contact@sonatrach.dz",
        "phone": "+21323000001",
        "contact_person": "Corporate Affairs",
        "notes": "Algeria's national integrated oil and gas company.",
    },
    {
        "name": "NAFTAL",
        "email": "contact@naftal.dz",
        "phone": "+21323000002",
        "contact_person": "Commercial Operations",
        "notes": "Downstream petroleum products distribution company in Algeria.",
    },
    {
        "name": "ENAFOR",
        "email": "contact@enafor.dz",
        "phone": "+21323000003",
        "contact_person": "Drilling Operations",
        "notes": "National drilling company serving the Algerian oilfield sector.",
    },
    {
        "name": "ENAGEO",
        "email": "communication@enageo.com",
        "phone": "+21323000004",
        "contact_person": "Geophysics Operations",
        "notes": "National geophysics company supporting exploration and seismic activities.",
    },
    {
        "name": "ENTP",
        "email": "contact@entp.dz",
        "phone": "+21323000005",
        "contact_person": "Well Works Division",
        "notes": "National well works company within the SONATRACH Group.",
    },
    {
        "name": "ENSP",
        "email": "contact@ensp.dz",
        "phone": "+21323000006",
        "contact_person": "Well Services Operations",
        "notes": "National well services company for oil and gas field operations.",
    },
    {
        "name": "ENGTP",
        "email": "contact@engtp.dz",
        "phone": "+21323000007",
        "contact_person": "Project Delivery Office",
        "notes": "National company for major petroleum works and field projects.",
    },
    {
        "name": "ENGCB",
        "email": "contact@engcb.dz",
        "phone": "+21323000008",
        "contact_person": "Civil Works Operations",
        "notes": "Civil engineering and construction company serving energy infrastructure.",
    },
    {
        "name": "ENAC",
        "email": "contact@enac.dz",
        "phone": "+21323000009",
        "contact_person": "Pipeline Projects",
        "notes": "National pipeline and energy transport infrastructure company.",
    },
    {
        "name": "SARPI",
        "email": "contact@sarpi.dz",
        "phone": "+21323000010",
        "contact_person": "Industrial Services",
        "notes": "Industrial services and risk prevention company in the energy sector.",
    },
    {
        "name": "SONELGAZ",
        "email": "contact@sonelgaz.dz",
        "phone": "+21323000011",
        "contact_person": "Energy Operations",
        "notes": "Major Algerian energy utility working across gas and power infrastructure.",
    },
    {
        "name": "GCB",
        "email": "contact@gcb.dz",
        "phone": "+21323000012",
        "contact_person": "Construction Projects",
        "notes": "National engineering and construction company serving hydrocarbon projects.",
    },
    {
        "name": "FERTIAL",
        "email": "contact@fertial-dz.com",
        "phone": "+21323000013",
        "contact_person": "Industrial Medical Coordination",
        "notes": "Industrial operator in Algeria with heavy-process and energy-linked activities.",
    },
    {
        "name": "PETROJET ALGERIA",
        "email": "contact@petrojet.dz",
        "phone": "+21323000014",
        "contact_person": "Field Projects",
        "notes": "Oil and gas EPC contractor supporting upstream and infrastructure work in Algeria.",
    },
    {
        "name": "ROUINA PIPE SERVICES",
        "email": "contact@rouinapipe.dz",
        "phone": "+21323000015",
        "contact_person": "Pipeline Maintenance",
        "notes": "Test-sector pipeline services contractor focused on desert transport corridors.",
    },
    {
        "name": "SAIPEM ALGERIA CONTRACTING",
        "email": "contact@saipem.dz",
        "phone": "+21323000016",
        "contact_person": "Offshore and Onshore Projects",
        "notes": "Engineering and contracting operator active in major Algerian energy projects.",
    },
    {
        "name": "HALLIBURTON ALGERIA",
        "email": "contact@halliburton.dz",
        "phone": "+21323000017",
        "contact_person": "Well Services",
        "notes": "International oilfield services provider with activity in Algerian drilling programs.",
    },
    {
        "name": "SCHLUMBERGER ALGERIA",
        "email": "contact@slb.dz",
        "phone": "+21323000018",
        "contact_person": "Integrated Well Delivery",
        "notes": "Integrated oilfield technology and services operator in Algerian basins.",
    },
    {
        "name": "BAKER HUGHES ALGERIA",
        "email": "contact@bakerhughes.dz",
        "phone": "+21323000019",
        "contact_person": "Production Services",
        "notes": "Oilfield services and equipment company supporting Algerian field operations.",
    },
    {
        "name": "WEATHERFORD ALGERIA",
        "email": "contact@weatherford.dz",
        "phone": "+21323000020",
        "contact_person": "Completion Services",
        "notes": "Field services contractor for drilling, completion, and intervention support.",
    },
]

BRANCH_TEMPLATES = [
    {
        "name": "Hassi Messaoud Operations",
        "location": "Hassi Messaoud, Ouargla",
        "address": "Zone Industrielle, Hassi Messaoud",
        "sites": [
            {"name": "North Production Block", "location": "Hassi Messaoud North", "status": "active"},
            {"name": "South Gathering Station", "location": "Hassi Messaoud South", "status": "standby"},
        ],
    },
    {
        "name": "Hassi R'Mel Gas Center",
        "location": "Hassi R'Mel, Laghouat",
        "address": "Base Industrielle, Hassi R'Mel",
        "sites": [
            {"name": "Gas Compression Train A", "location": "Hassi R'Mel Central", "status": "active"},
            {"name": "Processing Extension Yard", "location": "Hassi R'Mel East", "status": "active"},
        ],
    },
    {
        "name": "In Amenas South Hub",
        "location": "In Amenas, Illizi",
        "address": "Route Industrielle, In Amenas",
        "sites": [
            {"name": "South Hub CPF", "location": "In Amenas South", "status": "active"},
            {"name": "Tiguentourine Utility Pad", "location": "Tiguentourine", "status": "standby"},
        ],
    },
    {
        "name": "In Salah Production Unit",
        "location": "In Salah, Tamanrasset",
        "address": "Centre de Production, In Salah",
        "sites": [
            {"name": "Krechba Production Pad", "location": "Krechba", "status": "active"},
            {"name": "Reg Compression Zone", "location": "Reg", "status": "active"},
        ],
    },
    {
        "name": "Skikda Refining Complex",
        "location": "Skikda",
        "address": "Zone Petrochimique, Skikda",
        "sites": [
            {"name": "Refinery Utilities Block", "location": "Skikda Port Area", "status": "active"},
            {"name": "Storage and Loading Area", "location": "Skikda Terminal", "status": "standby"},
        ],
    },
    {
        "name": "Arzew LNG Terminal",
        "location": "Arzew, Oran",
        "address": "Complexe GNL, Arzew",
        "sites": [
            {"name": "GL1Z Operations Yard", "location": "Arzew Industrial Zone", "status": "active"},
            {"name": "Export Loading Berth", "location": "Arzew Harbor", "status": "active"},
        ],
    },
    {
        "name": "Adrar Basin Base",
        "location": "Adrar",
        "address": "Base de Soutien, Adrar",
        "sites": [
            {"name": "Touat Field Camp", "location": "Touat", "status": "active"},
            {"name": "Reggane Logistics Yard", "location": "Reggane", "status": "standby"},
        ],
    },
    {
        "name": "Illizi Exploration Hub",
        "location": "Illizi",
        "address": "Pole Exploration, Illizi",
        "sites": [
            {"name": "Berkine Survey Base", "location": "Berkine Basin", "status": "active"},
            {"name": "Tin Fouye Tabankort Area", "location": "TFT", "status": "standby"},
        ],
    },
    {
        "name": "Ouargla Support Center",
        "location": "Ouargla",
        "address": "Centre de Support, Ouargla",
        "sites": [
            {"name": "Maintenance and Workshops", "location": "Ouargla Industrial Area", "status": "active"},
            {"name": "Field Logistics Yard", "location": "Ouargla South", "status": "active"},
        ],
    },
    {
        "name": "Bechar Logistics Unit",
        "location": "Bechar",
        "address": "Base Logistique, Bechar",
        "sites": [
            {"name": "Southwest Supply Base", "location": "Bechar Operations Zone", "status": "active"},
            {"name": "Remote Camp Support Pad", "location": "Hamada Sector", "status": "standby"},
        ],
    },
]

FIRST_NAMES = [
    "Ahmed",
    "Mohamed",
    "Yacine",
    "Sofiane",
    "Samir",
    "Nadia",
    "Amina",
    "Lina",
    "Karim",
    "Sara",
    "Omar",
    "Imane",
]

LAST_NAMES = [
    "Benali",
    "Mansouri",
    "Brahimi",
    "Khelifi",
    "Saadi",
    "Touati",
    "Meziane",
    "Belaid",
    "Haddad",
    "Rahmani",
]

JOB_TITLES = [
    "Rig Operator",
    "Field Engineer",
    "Safety Officer",
    "Mechanic",
    "Electrician",
    "Site Supervisor",
]

DEPARTMENTS = [
    "Drilling",
    "Maintenance",
    "Safety",
    "Operations",
    "Logistics",
]

MEDICAL_STATUSES = ["fit", "pending", "under_review", "unfit"]
CAMPAIGN_STATUSES = ["draft", "planned", "active", "completed"]
WORKER_TEST_STATUSES = ["pending", "completed", "review"]


@dataclass
class DemoBundle:
    admin: User
    doctors: list[User]
    assistants: list[User]
    tests: list[MedicalTest]
    companies: list[Company]
    branches: list[Branch]
    sites: list[DrillingSite]
    workers: list[Worker]
    campaigns: list[MedicalCampaign]


def select_branch_templates(company_index: int) -> list[dict]:
    start = ((company_index - 1) * BRANCHES_PER_COMPANY) % len(BRANCH_TEMPLATES)
    return [
        BRANCH_TEMPLATES[(start + offset) % len(BRANCH_TEMPLATES)]
        for offset in range(BRANCHES_PER_COMPANY)
    ]


def seed_demo_data() -> None:
    with SessionLocal() as db:
        bundle = DemoBundle(
            admin=ensure_admin(db),
            doctors=[],
            assistants=[],
            tests=[],
            companies=[],
            branches=[],
            sites=[],
            workers=[],
            campaigns=[],
        )

        bundle.doctors = ensure_staff(db, "doctor", USER_COUNTS["doctor"])
        bundle.assistants = ensure_staff(db, "assistant", USER_COUNTS["assistant"])
        bundle.tests = ensure_tests(db)
        bundle.companies, bundle.branches, bundle.sites = ensure_companies_and_structure(db)
        bundle.workers = ensure_workers(db, bundle.companies, bundle.branches, bundle.sites)
        bundle.campaigns = ensure_campaigns(db, bundle)
        ensure_workspaces(db, bundle.campaigns)

        db.commit()

        print("Demo data seeded successfully.")
        print(f"Companies target: {COMPANY_COUNT}")
        print(f"Branches per company: {BRANCHES_PER_COMPANY}")
        print(f"Sites per branch: {SITES_PER_BRANCH}")
        print(f"Workers per branch: {WORKERS_PER_BRANCH}")
        print(f"Admin: {bundle.admin.email} / {DEFAULT_ADMIN_PASSWORD}")
        print(f"Doctors: {len(bundle.doctors)}")
        print(f"Assistants: {len(bundle.assistants)}")
        print(f"Medical tests: {len(bundle.tests)}")
        print(f"Companies: {len(bundle.companies)}")
        print(f"Branches: {len(bundle.branches)}")
        print(f"Drilling sites: {len(bundle.sites)}")
        print(f"Workers: {len(bundle.workers)}")
        print(f"Campaigns: {len(bundle.campaigns)}")
        print(f"Workspaces: {len(bundle.campaigns)}")


def ensure_admin(db: Session) -> User:
    existing = db.scalar(select(User).where(User.email == DEFAULT_ADMIN_EMAIL))
    if existing:
        return existing

    admin = User(
        first_name="System",
        last_name="Administrator",
        email=DEFAULT_ADMIN_EMAIL,
        password_hash=hash_password(DEFAULT_ADMIN_PASSWORD),
        role="admin",
        phone="+213550000001",
        is_active=True,
        sync_status="synced",
        local_id=f"{DEMO_PREFIX}_admin",
    )
    db.add(admin)
    db.flush()
    return admin


def ensure_staff(db: Session, role: str, count: int) -> list[User]:
    staff: list[User] = []
    for index in range(1, count + 1):
        email = f"{role}{index}@demo.ibnsina.com"
        existing = db.scalar(select(User).where(User.email == email))
        if existing:
            staff.append(existing)
            continue

        first_name = pick_name(index)
        last_name = pick_surname(index * 3)
        user = User(
            first_name=first_name,
            last_name=last_name,
            email=email,
            password_hash=hash_password(DEMO_PASSWORD),
            role=role,
            phone=f"+2135501{index:04d}",
            is_active=True,
            last_login=datetime.now(timezone.utc) - timedelta(days=index),
            sync_status="synced",
            local_id=f"{DEMO_PREFIX}_{role}_{index}",
        )
        db.add(user)
        db.flush()
        staff.append(user)
    return staff


def ensure_tests(db: Session) -> list[MedicalTest]:
    tests: list[MedicalTest] = []
    for payload in DEFAULT_TESTS:
        name = payload["name"]
        section = payload["section"]
        existing = db.scalar(
            select(MedicalTest).where(
                MedicalTest.name == name,
                MedicalTest.section == section,
            )
        )
        if existing:
            tests.append(existing)
            continue

        test = MedicalTest(
            name=name,
            section=section,
            category=payload.get("category") or section,
            description=payload.get("description") or f"Demo test definition for {name}.",
            normal_range=payload.get("normal_range"),
            unit=payload.get("unit"),
            requires_doctor_review=payload.get("requires_doctor_review", False),
            is_active=True,
        )
        db.add(test)
        db.flush()
        tests.append(test)
    return tests


def ensure_companies_and_structure(db: Session) -> tuple[list[Company], list[Branch], list[DrillingSite]]:
    companies: list[Company] = []
    branches: list[Branch] = []
    sites: list[DrillingSite] = []

    for company_index, profile in enumerate(COMPANY_PROFILES[:COMPANY_COUNT], start=1):
        company_local_id = f"{DEMO_PREFIX}_company_{company_index}"
        company = db.scalar(select(Company).where(Company.local_id == company_local_id))
        if not company:
            company = db.scalar(select(Company).where(Company.name == profile["name"]))
        if not company:
            company = Company(
                name=profile["name"],
                address=BRANCH_TEMPLATES[0]["address"],
                phone=profile["phone"],
                email=profile["email"],
                contact_person=profile["contact_person"],
                notes=profile["notes"],
                sync_status="synced",
                local_id=company_local_id,
            )
            db.add(company)
            db.flush()
        else:
            company.name = profile["name"]
            company.address = BRANCH_TEMPLATES[0]["address"]
            company.phone = profile["phone"]
            company.email = profile["email"]
            company.contact_person = profile["contact_person"]
            company.notes = profile["notes"]
            company.sync_status = "synced"
            company.local_id = company_local_id
        companies.append(company)

        company_branch_templates = select_branch_templates(company_index)
        for branch_index, branch_template in enumerate(company_branch_templates, start=1):
            branch_local_id = f"{DEMO_PREFIX}_branch_{company_index}_{branch_index}"
            branch = db.scalar(select(Branch).where(Branch.local_id == branch_local_id))
            if not branch:
                branch = db.scalar(
                    select(Branch).where(Branch.company_id == company.id, Branch.name == branch_template["name"])
                )
            if not branch:
                branch = Branch(
                    company_id=company.id,
                    name=branch_template["name"],
                    location=branch_template["location"],
                    address=branch_template["address"],
                    notes=f"{company.name} operating base in {branch_template['location']}.",
                    sync_status="synced",
                    local_id=branch_local_id,
                )
                db.add(branch)
                db.flush()
            else:
                branch.company_id = company.id
                branch.name = branch_template["name"]
                branch.location = branch_template["location"]
                branch.address = branch_template["address"]
                branch.notes = f"{company.name} operating base in {branch_template['location']}."
                branch.sync_status = "synced"
                branch.local_id = branch_local_id
            branches.append(branch)

            for site_index, site_template in enumerate(branch_template["sites"][:SITES_PER_BRANCH], start=1):
                site_local_id = f"{DEMO_PREFIX}_site_{company_index}_{branch_index}_{site_index}"
                site = db.scalar(select(DrillingSite).where(DrillingSite.local_id == site_local_id))
                if not site:
                    site = db.scalar(
                        select(DrillingSite).where(
                            DrillingSite.branch_id == branch.id,
                            DrillingSite.name == site_template["name"],
                        )
                    )
                if not site:
                    site = DrillingSite(
                        company_id=company.id,
                        branch_id=branch.id,
                        name=site_template["name"],
                        location=site_template["location"],
                        status=site_template["status"],
                        notes=f"{company.name} field site for {branch_template['name']}.",
                        sync_status="synced",
                        local_id=site_local_id,
                    )
                    db.add(site)
                    db.flush()
                else:
                    site.company_id = company.id
                    site.branch_id = branch.id
                    site.name = site_template["name"]
                    site.location = site_template["location"]
                    site.status = site_template["status"]
                    site.notes = f"{company.name} field site for {branch_template['name']}."
                    site.sync_status = "synced"
                    site.local_id = site_local_id
                sites.append(site)

    return companies, branches, sites


def ensure_workers(
    db: Session,
    companies: list[Company],
    branches: list[Branch],
    sites: list[DrillingSite],
) -> list[Worker]:
    branch_lookup: dict[int, list[DrillingSite]] = {}
    for site in sites:
        branch_lookup.setdefault(site.branch_id, []).append(site)

    workers: list[Worker] = []
    for branch_position, branch in enumerate(branches, start=1):
        company = next(company for company in companies if company.id == branch.company_id)
        branch_sites = branch_lookup.get(branch.id, [])

        for worker_index in range(1, WORKERS_PER_BRANCH + 1):
            employee_number = f"EMP-{company.id:02d}{branch_position:03d}{worker_index:02d}"
            worker = db.scalar(select(Worker).where(Worker.employee_number == employee_number))
            if worker:
                workers.append(worker)
                continue

            sequence = branch_position * 10 + worker_index
            worker = Worker(
                company_id=company.id,
                branch_id=branch.id,
                drilling_site_id=branch_sites[(worker_index - 1) % len(branch_sites)].id if branch_sites else None,
                employee_number=employee_number,
                national_id=f"NID-{company.id:02d}{branch.id:03d}{worker_index:03d}",
                first_name=pick_name(sequence),
                last_name=pick_surname(sequence),
                gender="male" if worker_index % 2 else "female",
                birth_date=date(1980 + (sequence % 20), (sequence % 12) + 1, ((sequence * 2) % 27) + 1),
                birth_wilaya=f"Wilaya {(sequence % 12) + 1}",
                marital_status="married" if sequence % 3 == 0 else "single",
                blood_group=["O+", "A+", "B+", "AB+"][sequence % 4],
                phone=f"+213660{company.id:02d}{branch.id:03d}{worker_index:02d}",
                emergency_phone=f"+213770{company.id:02d}{branch.id:03d}{worker_index:02d}",
                address=f"Camp {branch.name}, {company.name}",
                job_title=JOB_TITLES[sequence % len(JOB_TITLES)],
                department=DEPARTMENTS[sequence % len(DEPARTMENTS)],
                hire_date=date(2015 + (sequence % 8), ((sequence + 2) % 12) + 1, ((sequence + 5) % 27) + 1),
                medical_status=MEDICAL_STATUSES[sequence % len(MEDICAL_STATUSES)],
                is_active=True,
                sync_status="synced",
                local_id=f"{DEMO_PREFIX}_worker_{company.id}_{branch.id}_{worker_index}",
            )
            db.add(worker)
            db.flush()
            workers.append(worker)
    return workers


def ensure_campaigns(db: Session, bundle: DemoBundle) -> list[MedicalCampaign]:
    campaigns: list[MedicalCampaign] = []
    tests_by_index = bundle.tests
    workers_by_branch: dict[int, list[Worker]] = {}
    for worker in bundle.workers:
        workers_by_branch.setdefault(worker.branch_id, []).append(worker)

    sites_by_branch: dict[int, list[DrillingSite]] = {}
    for site in bundle.sites:
        sites_by_branch.setdefault(site.branch_id, []).append(site)

    for company_offset, company in enumerate(bundle.companies, start=1):
        company_branches = [branch for branch in bundle.branches if branch.company_id == company.id][:CAMPAIGNS_PER_COMPANY]

        for campaign_offset, branch in enumerate(company_branches, start=1):
            site_options = sites_by_branch.get(branch.id, [])
            drilling_site = site_options[(campaign_offset - 1) % len(site_options)] if site_options else None
            title = f"{company.name} Occupational Campaign {campaign_offset}"
            campaign_local_id = f"{DEMO_PREFIX}_campaign_{company.id}_{branch.id}_{campaign_offset}"
            campaign = db.scalar(select(MedicalCampaign).where(MedicalCampaign.local_id == campaign_local_id))
            if not campaign:
                campaign = db.scalar(
                    select(MedicalCampaign).where(
                        MedicalCampaign.company_id == company.id,
                        MedicalCampaign.branch_id == branch.id,
                        MedicalCampaign.title == title,
                    )
                )
            if not campaign:
                start_date = date.today() - timedelta(days=company_offset * campaign_offset)
                campaign = MedicalCampaign(
                    company_id=company.id,
                    branch_id=branch.id,
                    drilling_site_id=drilling_site.id if drilling_site else None,
                    title=title,
                    description="Generated demo campaign for occupational health workflow testing.",
                    start_date=start_date,
                    end_date=start_date + timedelta(days=5),
                    status=CAMPAIGN_STATUSES[(company_offset + campaign_offset) % len(CAMPAIGN_STATUSES)],
                    created_by=bundle.admin.id,
                    sync_status="synced",
                    local_id=campaign_local_id,
                )
                db.add(campaign)
                db.flush()
            else:
                start_date = date.today() - timedelta(days=company_offset * campaign_offset)
                campaign.company_id = company.id
                campaign.branch_id = branch.id
                campaign.drilling_site_id = drilling_site.id if drilling_site else None
                campaign.title = title
                campaign.description = "Generated demo campaign for occupational health workflow testing."
                campaign.start_date = start_date
                campaign.end_date = start_date + timedelta(days=5)
                campaign.status = CAMPAIGN_STATUSES[(company_offset + campaign_offset) % len(CAMPAIGN_STATUSES)]
                campaign.created_by = bundle.admin.id
                campaign.sync_status = "synced"
                campaign.local_id = campaign_local_id
            campaigns.append(campaign)

            attach_campaign_assignments(db, campaign, bundle.doctors, bundle.assistants, company_offset, campaign_offset)
            attach_campaign_tests(db, campaign, tests_by_index, company_offset, campaign_offset)
            attach_campaign_workers_and_results(
                db,
                campaign,
                workers_by_branch.get(branch.id, []),
                tests_by_index,
                bundle.doctors,
                company_offset,
                campaign_offset,
            )

    return campaigns


def ensure_workspaces(db: Session, campaigns: list[MedicalCampaign]) -> list[Workspace]:
    workspaces: list[Workspace] = []
    for campaign in campaigns:
        workspace_code = f"WS-{campaign.id:05d}"
        workspace = db.scalar(select(Workspace).where(Workspace.campaign_id == campaign.id))
        if not workspace:
            workspace = Workspace(
                name=f"{campaign.title} Workspace",
                campaign_id=campaign.id,
                company_id=campaign.company_id,
                branch_id=campaign.branch_id,
                drilling_site_id=campaign.drilling_site_id,
                workspace_code=workspace_code,
                workspace_password_hash=hash_password(workspace_code),
                start_date=campaign.start_date,
                end_date=campaign.end_date,
                status=campaign.status,
                is_locked=campaign.status == "completed",
                sync_status="synced",
                local_id=f"{DEMO_PREFIX}_workspace_{campaign.id}",
            )
            db.add(workspace)
            db.flush()
        else:
            workspace.name = f"{campaign.title} Workspace"
            workspace.company_id = campaign.company_id
            workspace.branch_id = campaign.branch_id
            workspace.drilling_site_id = campaign.drilling_site_id
            workspace.workspace_code = workspace_code
            workspace.workspace_password_hash = hash_password(workspace_code)
            workspace.start_date = campaign.start_date
            workspace.end_date = campaign.end_date
            workspace.status = campaign.status
            workspace.is_locked = campaign.status == "completed"
            workspace.sync_status = "synced"
            workspace.local_id = f"{DEMO_PREFIX}_workspace_{campaign.id}"
        workspaces.append(workspace)
    return workspaces


def attach_campaign_assignments(
    db: Session,
    campaign: MedicalCampaign,
    doctors: list[User],
    assistants: list[User],
    company_offset: int,
    campaign_offset: int,
) -> None:
    doctor = doctors[(company_offset + campaign_offset) % len(doctors)]
    doctor_link = db.scalar(
        select(DoctorCampaign).where(
            DoctorCampaign.campaign_id == campaign.id,
            DoctorCampaign.doctor_id == doctor.id,
        )
    )
    if not doctor_link:
        db.add(DoctorCampaign(campaign_id=campaign.id, doctor_id=doctor.id))

    for step in range(2):
        assistant = assistants[(company_offset + campaign_offset + step) % len(assistants)]
        assistant_link = db.scalar(
            select(AssistantCampaign).where(
                AssistantCampaign.campaign_id == campaign.id,
                AssistantCampaign.assistant_id == assistant.id,
            )
        )
        if not assistant_link:
            db.add(AssistantCampaign(campaign_id=campaign.id, assistant_id=assistant.id))


def attach_campaign_tests(
    db: Session,
    campaign: MedicalCampaign,
    tests: list[MedicalTest],
    company_offset: int,
    campaign_offset: int,
) -> list[MedicalTest]:
    selected_tests = [
        tests[(company_offset + campaign_offset + idx) % len(tests)] for idx in range(TESTS_PER_CAMPAIGN)
    ]
    for test in selected_tests:
        exists = db.scalar(
            select(CampaignTest).where(CampaignTest.campaign_id == campaign.id, CampaignTest.test_id == test.id)
        )
        if not exists:
            db.add(CampaignTest(campaign_id=campaign.id, test_id=test.id, required=True))
    return selected_tests


def attach_campaign_workers_and_results(
    db: Session,
    campaign: MedicalCampaign,
    branch_workers: list[Worker],
    tests: list[MedicalTest],
    doctors: list[User],
    company_offset: int,
    campaign_offset: int,
) -> None:
    if not branch_workers:
        return

    selected_workers = branch_workers[:WORKERS_PER_CAMPAIGN]
    selected_tests = [
        tests[(company_offset + campaign_offset + idx) % len(tests)] for idx in range(TESTS_PER_CAMPAIGN)
    ]
    assigned_doctor = doctors[(company_offset + campaign_offset) % len(doctors)]

    for worker_position, worker in enumerate(selected_workers, start=1):
        worker_link = db.scalar(
            select(CampaignWorker).where(
                CampaignWorker.campaign_id == campaign.id,
                CampaignWorker.worker_id == worker.id,
            )
        )
        if not worker_link:
            db.add(
                CampaignWorker(
                    campaign_id=campaign.id,
                    worker_id=worker.id,
                    added_by=campaign.created_by,
                    status="completed" if worker_position % 3 == 0 else "pending",
                )
            )

        for test_position, test in enumerate(selected_tests, start=1):
            worker_test = db.scalar(
                select(WorkerTest).where(
                    WorkerTest.campaign_id == campaign.id,
                    WorkerTest.worker_id == worker.id,
                    WorkerTest.test_id == test.id,
                )
            )
            if worker_test:
                continue

            completed = (worker_position + test_position) % 2 == 0
            is_normal = (worker_position + test_position) % 4 != 0 if completed else None
            status = "completed" if completed else WORKER_TEST_STATUSES[(worker_position + test_position) % 3]
            worker_test = WorkerTest(
                campaign_id=campaign.id,
                worker_id=worker.id,
                test_id=test.id,
                doctor_id=assigned_doctor.id,
                status=status,
                result=build_result_text(test, is_normal) if completed else None,
                notes="Generated demo worker test result.",
                is_normal=is_normal,
                completed_at=datetime.now(timezone.utc) - timedelta(days=test_position) if completed else None,
                sync_status="synced",
                local_id=f"{DEMO_PREFIX}_worker_test_{campaign.id}_{worker.id}_{test.id}",
            )
            db.add(worker_test)


def build_result_text(test: MedicalTest, is_normal: bool | None) -> str:
    if is_normal is None:
        return "Awaiting result entry."
    if is_normal:
        return f"{test.name} within normal range."
    return f"{test.name} requires follow-up review."


def pick_name(index: int) -> str:
    return FIRST_NAMES[index % len(FIRST_NAMES)]


def pick_surname(index: int) -> str:
    return LAST_NAMES[index % len(LAST_NAMES)]


if __name__ == "__main__":
    seed_demo_data()
