from __future__ import annotations

import argparse
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any

from openpyxl import load_workbook
from sqlalchemy import select

from app.core.security import hash_password
from app.database import SessionLocal
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


@dataclass(frozen=True)
class SheetConfig:
    company_name: str
    site_index: int
    doctor_index: int
    matricule_index: int
    last_name_index: int
    first_name_index: int | None
    birth_date_index: int
    job_title_index: int
    visit_date_index: int
    blood_group_index: int | None
    conclusion_index: int
    next_visit_index: int | None
    summary_index: int | None
    chronic_index: int | None
    audiogram_index: int | None
    ecg_index: int | None
    efr_index: int | None
    vision_index: int | None
    orientation_index: int | None
    address_index: int | None
    default_year: int


SHEETS: dict[str, SheetConfig] = {
    "ENAGEO 2025": SheetConfig(
        company_name="ENAGEO",
        site_index=1,
        doctor_index=3,
        matricule_index=4,
        last_name_index=5,
        first_name_index=6,
        birth_date_index=7,
        job_title_index=8,
        visit_date_index=9,
        blood_group_index=10,
        conclusion_index=11,
        next_visit_index=12,
        summary_index=13,
        chronic_index=14,
        audiogram_index=15,
        ecg_index=16,
        efr_index=17,
        vision_index=18,
        orientation_index=19,
        address_index=2,
        default_year=2025,
    ),
    "ENGCB": SheetConfig(
        company_name="ENGCB",
        site_index=2,
        doctor_index=3,
        matricule_index=1,
        last_name_index=4,
        first_name_index=5,
        birth_date_index=6,
        job_title_index=7,
        visit_date_index=8,
        blood_group_index=17,
        conclusion_index=9,
        next_visit_index=10,
        summary_index=11,
        chronic_index=12,
        audiogram_index=13,
        ecg_index=14,
        efr_index=15,
        vision_index=16,
        orientation_index=None,
        address_index=None,
        default_year=2024,
    ),
}

PLACEHOLDER_PASSWORD = "ImportLegacy2026!"
DEFAULT_BRANCH_NAME = "Structures importees"


def normalize_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def normalize_multiline(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).replace("\r\n", "\n").replace("\r", "\n")
    text = "\n".join(part.rstrip() for part in text.split("\n")).strip()
    return text or None


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_text = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_text.lower()).strip("-")
    return ascii_text or "item"


def normalize_key(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "", ascii_text.lower())


def parse_visit_date(value: Any, fallback_year: int) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = normalize_text(value)
    if not text:
        return date(fallback_year, 1, 1)
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return date(fallback_year, 1, 1)


def parse_birth_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = normalize_text(value)
    if not text:
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def split_name(full_name: str) -> tuple[str, str]:
    parts = full_name.split()
    if not parts:
        return "Inconnu", "Inconnu"
    if len(parts) == 1:
        return parts[0].title(), "Inconnu"
    return parts[0].title(), " ".join(part.title() for part in parts[1:])


def parse_names(row: tuple[Any, ...], config: SheetConfig) -> tuple[str, str]:
    last_name = normalize_text(row[config.last_name_index])
    first_name = normalize_text(row[config.first_name_index]) if config.first_name_index is not None else None
    if last_name and first_name:
        return last_name.title(), first_name.title()
    full_name = last_name or first_name or "Inconnu Inconnu"
    return split_name(full_name)


def normalize_doctor_label(value: str) -> str:
    text = normalize_text(value) or "Docteur inconnu"
    text = re.sub(r"(?i)^dr[.\s]*", "", text).strip()
    return text.title() or "Docteur inconnu"


def trim_for_column(value: str | None, limit: int) -> str | None:
    if value is None:
        return None
    return value[:limit]


def infer_worker_status(conclusion: str | None) -> str | None:
    if not conclusion:
        return None
    text = normalize_key(conclusion)
    if "inapte" in text:
        return "Inapte"
    if "convoquer" in text or "controler" in text or "controle" in text:
        return "A convoquer"
    if "apte" in text:
        return "Apte"
    return trim_for_column(conclusion, 100)


def infer_is_normal(*values: str | None) -> bool | None:
    merged = " ".join(value for value in values if value)
    if not merged:
        return None
    text = normalize_key(merged)
    negative_markers = ("inapte", "anormal", "convoquer", "controle", "ischemie", "pathologique")
    if any(marker in text for marker in negative_markers):
        return False
    positive_markers = ("normal", "ras", "apte", "sansparticularite")
    if any(marker in text for marker in positive_markers):
        return True
    return None


def visit_datetime(value: date) -> datetime:
    return datetime.combine(value, time.min, tzinfo=timezone.utc)


def build_employee_number(
    sheet_name: str,
    row_number: int,
    matricule: str | None,
    last_name: str,
    first_name: str,
    birth_date: date | None,
) -> str:
    if matricule:
        return matricule
    birth_part = birth_date.strftime("%Y%m%d") if birth_date else f"R{row_number:04d}"
    base = slugify(f"{sheet_name}-{last_name}-{first_name}")[:24].upper()
    return f"LEG-{base}-{birth_part}"[:100]


def build_worker_local_id(
    company_name: str,
    employee_number: str,
    site_name: str,
    last_name: str,
    first_name: str,
    birth_date: date | None,
) -> str:
    birth_part = birth_date.isoformat() if birth_date else "unknown-birth"
    token = slugify(f"{company_name}-{employee_number}-{site_name}-{last_name}-{first_name}-{birth_part}")
    return f"legacy-worker-{token}"[:100]


def get_or_create_company(db, cache: dict[str, Company], company_name: str) -> tuple[Company, bool]:
    key = normalize_key(company_name)
    if key in cache:
        return cache[key], False
    local_id = f"legacy-company-{slugify(company_name)}"
    company = db.scalar(select(Company).where(Company.local_id == local_id))
    created = False
    if not company:
        company = Company(
            name=company_name,
            notes="Importe depuis le fichier historique CDM Ibn Sina.",
            local_id=local_id,
            sync_status="synced",
        )
        db.add(company)
        db.flush()
        created = True
    cache[key] = company
    return company, created


def get_or_create_branch(db, cache: dict[str, Branch], company: Company) -> tuple[Branch, bool]:
    key = str(company.id)
    if key in cache:
        return cache[key], False
    local_id = f"legacy-branch-{company.local_id}"
    branch = db.scalar(select(Branch).where(Branch.local_id == local_id))
    created = False
    if not branch:
        branch = Branch(
            company_id=company.id,
            name=DEFAULT_BRANCH_NAME,
            location=company.name,
            notes="Filiale technique creee pour l'import historique.",
            local_id=local_id,
            sync_status="synced",
        )
        db.add(branch)
        db.flush()
        created = True
    cache[key] = branch
    return branch, created


def get_or_create_site(
    db,
    cache: dict[str, DrillingSite],
    company: Company,
    branch: Branch,
    site_name: str,
    location: str | None,
) -> tuple[DrillingSite, bool]:
    key = f"{company.id}:{normalize_key(site_name)}"
    if key in cache:
        return cache[key], False
    local_id = f"legacy-site-{slugify(company.name)}-{slugify(site_name)}"[:100]
    site = db.scalar(select(DrillingSite).where(DrillingSite.local_id == local_id))
    created = False
    if not site:
        site = DrillingSite(
            company_id=company.id,
            branch_id=branch.id,
            name=site_name,
            location=location or site_name,
            status="active",
            notes="Site importe depuis le fichier historique.",
            local_id=local_id,
            sync_status="synced",
        )
        db.add(site)
        db.flush()
        created = True
    cache[key] = site
    return site, created


def get_or_create_doctor(db, cache: dict[str, User], raw_name: str | None) -> tuple[User | None, bool]:
    if not raw_name:
        return None, False
    clean_name = normalize_doctor_label(raw_name)
    key = normalize_key(clean_name)
    if key in cache:
        return cache[key], False
    local_id = f"legacy-doctor-{slugify(clean_name)}"[:100]
    doctor = db.scalar(select(User).where(User.local_id == local_id))
    created = False
    if not doctor:
        existing = db.scalars(select(User).where(User.role == "doctor")).all()
        doctor = next(
            (
                user
                for user in existing
                if normalize_key(f"{user.first_name} {user.last_name}") == key
            ),
            None,
        )
    if not doctor:
        first_name, last_name = split_name(clean_name)
        email = f"{slugify(clean_name)}@import.ibnsina.local"
        doctor = User(
            first_name=first_name,
            last_name=last_name,
            email=email[:255],
            password_hash=hash_password(PLACEHOLDER_PASSWORD),
            role="doctor",
            is_active=False,
            local_id=local_id,
            sync_status="synced",
        )
        db.add(doctor)
        db.flush()
        created = True
    cache[key] = doctor
    return doctor, created


def get_or_create_campaign(
    db,
    cache: dict[str, MedicalCampaign],
    company: Company,
    branch: Branch,
    site: DrillingSite,
    visit_day: date,
    created_by: int | None,
) -> tuple[MedicalCampaign, bool]:
    year = visit_day.year
    key = f"{company.id}:{site.id}:{year}"
    if key in cache:
        campaign = cache[key]
        if visit_day < campaign.start_date:
            campaign.start_date = visit_day
        if visit_day > campaign.end_date:
            campaign.end_date = visit_day
        return campaign, False
    local_id = f"legacy-campaign-{company.id}-{site.id}-{year}"
    campaign = db.scalar(select(MedicalCampaign).where(MedicalCampaign.local_id == local_id))
    created = False
    if not campaign:
        campaign = MedicalCampaign(
            company_id=company.id,
            branch_id=branch.id,
            drilling_site_id=site.id,
            title=f"Campagne historique {company.name} - {site.name} - {year}",
            description="Campagne importee depuis le fichier historique CDM Ibn Sina.",
            start_date=visit_day,
            end_date=visit_day,
            status="completed",
            created_by=created_by,
            local_id=local_id,
            sync_status="synced",
        )
        db.add(campaign)
        db.flush()
        created = True
    cache[key] = campaign
    return campaign, created


def get_or_create_worker(
    db,
    cache: dict[str, Worker],
    company: Company,
    branch: Branch,
    site: DrillingSite,
    employee_number: str,
    last_name: str,
    first_name: str,
    birth_date: date | None,
    blood_group: str | None,
    job_title: str | None,
    medical_status: str | None,
    address: str | None,
    department: str,
) -> tuple[Worker, bool]:
    local_id = build_worker_local_id(company.name, employee_number, site.name, last_name, first_name, birth_date)
    if local_id in cache:
        worker = cache[local_id]
        worker.company_id = company.id
        worker.branch_id = branch.id
        worker.drilling_site_id = site.id
        worker.last_name = last_name
        worker.first_name = first_name
        worker.birth_date = birth_date
        worker.blood_group = blood_group or worker.blood_group
        worker.job_title = job_title or worker.job_title
        worker.medical_status = medical_status or worker.medical_status
        worker.address = address or worker.address
        worker.department = department or worker.department
        return worker, False
    worker = db.scalar(select(Worker).where(Worker.local_id == local_id))
    created = False
    if not worker:
        worker = Worker(
            company_id=company.id,
            branch_id=branch.id,
            drilling_site_id=site.id,
            employee_number=employee_number,
            first_name=first_name,
            last_name=last_name,
            birth_date=birth_date,
            blood_group=blood_group,
            job_title=job_title,
            medical_status=medical_status,
            address=address,
            department=department,
            is_active=True,
            local_id=local_id,
            sync_status="synced",
        )
        db.add(worker)
        db.flush()
        created = True
    else:
        worker.company_id = company.id
        worker.branch_id = branch.id
        worker.drilling_site_id = site.id
        worker.employee_number = employee_number
        worker.first_name = first_name
        worker.last_name = last_name
        worker.birth_date = birth_date
        worker.blood_group = blood_group
        worker.job_title = job_title
        worker.medical_status = medical_status
        worker.address = address
        worker.department = department
    cache[local_id] = worker
    return worker, created


def ensure_campaign_worker(db, campaign: MedicalCampaign, worker: Worker) -> bool:
    exists = db.scalar(
        select(CampaignWorker).where(
            CampaignWorker.campaign_id == campaign.id,
            CampaignWorker.worker_id == worker.id,
        )
    )
    if exists:
        return False
    db.add(CampaignWorker(campaign_id=campaign.id, worker_id=worker.id, status="completed"))
    return True


def ensure_doctor_assignment(db, campaign: MedicalCampaign, doctor: User | None) -> bool:
    if not doctor:
        return False
    exists = db.scalar(
        select(DoctorCampaign).where(
            DoctorCampaign.campaign_id == campaign.id,
            DoctorCampaign.doctor_id == doctor.id,
        )
    )
    if exists:
        return False
    db.add(DoctorCampaign(campaign_id=campaign.id, doctor_id=doctor.id))
    return True


def get_or_create_test(db, cache: dict[str, MedicalTest], name: str, category: str) -> tuple[MedicalTest, bool]:
    key = normalize_key(name)
    if key in cache:
        return cache[key], False
    existing = db.scalar(select(MedicalTest).where(MedicalTest.name == name))
    created = False
    if not existing:
        existing = MedicalTest(
            name=name,
            category=category,
            description="Test cree pour l'import historique.",
            requires_doctor_review=False,
            is_active=True,
        )
        db.add(existing)
        db.flush()
        created = True
    cache[key] = existing
    return existing, created


def ensure_campaign_test(db, campaign: MedicalCampaign, test: MedicalTest) -> bool:
    exists = db.scalar(
        select(CampaignTest).where(
            CampaignTest.campaign_id == campaign.id,
            CampaignTest.test_id == test.id,
        )
    )
    if exists:
        return False
    db.add(CampaignTest(campaign_id=campaign.id, test_id=test.id, required=True))
    return True


def ensure_worker_test(
    db,
    local_id: str,
    campaign: MedicalCampaign,
    worker: Worker,
    test: MedicalTest,
    doctor: User | None,
    visit_day: date,
    status: str,
    result: str | None,
    notes: str | None,
    is_normal: bool | None,
) -> bool:
    exists = db.scalar(select(WorkerTest).where(WorkerTest.local_id == local_id))
    if exists:
        exists.campaign_id = campaign.id
        exists.worker_id = worker.id
        exists.test_id = test.id
        exists.doctor_id = doctor.id if doctor else None
        exists.status = status
        exists.result = result
        exists.notes = notes
        exists.is_normal = is_normal
        exists.completed_at = visit_datetime(visit_day)
        return False
    db.add(
        WorkerTest(
            campaign_id=campaign.id,
            worker_id=worker.id,
            test_id=test.id,
            doctor_id=doctor.id if doctor else None,
            status=status,
            result=result,
            notes=notes,
            is_normal=is_normal,
            completed_at=visit_datetime(visit_day),
            local_id=local_id[:100],
            sync_status="synced",
        )
    )
    return True


def general_notes(
    blood_group: str | None,
    next_visit: str | None,
    summary: str | None,
    chronic: str | None,
    orientation: str | None,
) -> str | None:
    blocks = []
    if blood_group:
        blocks.append(f"Groupage: {blood_group}")
    if next_visit:
        blocks.append(f"Prochaine visite: {next_visit}")
    if chronic:
        blocks.append(f"Maladies chroniques: {chronic}")
    if orientation:
        blocks.append(f"Orientation: {orientation}")
    if summary:
        blocks.append(summary)
    return "\n\n".join(blocks) if blocks else None


def import_workbook(workbook_path: Path) -> dict[str, int]:
    summary = {
        "companies_created": 0,
        "branches_created": 0,
        "sites_created": 0,
        "doctors_created": 0,
        "campaigns_created": 0,
        "workers_created": 0,
        "campaign_workers_created": 0,
        "doctor_assignments_created": 0,
        "campaign_tests_created": 0,
        "worker_tests_created": 0,
        "medical_tests_created": 0,
        "rows_processed": 0,
    }

    workbook = load_workbook(workbook_path, read_only=True, data_only=True)
    company_cache: dict[str, Company] = {}
    branch_cache: dict[str, Branch] = {}
    site_cache: dict[str, DrillingSite] = {}
    doctor_cache: dict[str, User] = {}
    campaign_cache: dict[str, MedicalCampaign] = {}
    worker_cache: dict[str, Worker] = {}
    test_cache: dict[str, MedicalTest] = {}

    with SessionLocal() as db:
        creator_id = db.scalar(
            select(User.id).where(User.role.in_(("super_admin", "admin"))).order_by(User.id)
        )

        for test_name, category in (
            ("Visite medicale generale", "Occupational Health"),
            ("Audiometry", "Screening"),
            ("ECG", "Cardiology"),
            ("Spirometry", "Respiratory"),
            ("Vision Test", "Screening"),
        ):
            _, created = get_or_create_test(db, test_cache, test_name, category)
            if created:
                summary["medical_tests_created"] += 1

        test_aliases = {
            "general": test_cache[normalize_key("Visite medicale generale")],
            "audiogram": test_cache[normalize_key("Audiometry")],
            "ecg": test_cache[normalize_key("ECG")],
            "efr": test_cache[normalize_key("Spirometry")],
            "vision": test_cache[normalize_key("Vision Test")],
        }

        for sheet_name, config in SHEETS.items():
            if sheet_name not in workbook.sheetnames:
                continue

            sheet = workbook[sheet_name]
            company, created = get_or_create_company(db, company_cache, config.company_name)
            summary["companies_created"] += int(created)
            branch, created = get_or_create_branch(db, branch_cache, company)
            summary["branches_created"] += int(created)

            for row_number, row in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=2):
                if not row:
                    continue

                site_name = normalize_text(row[config.site_index]) or "Site non renseigne"
                last_name, first_name = parse_names(row, config)
                if not normalize_text(last_name) and not normalize_text(first_name):
                    continue

                summary["rows_processed"] += 1

                address = normalize_text(row[config.address_index]) if config.address_index is not None else None
                site, created = get_or_create_site(db, site_cache, company, branch, site_name, address)
                summary["sites_created"] += int(created)

                doctor_name = normalize_text(row[config.doctor_index])
                doctor, created = get_or_create_doctor(db, doctor_cache, doctor_name)
                summary["doctors_created"] += int(created)

                visit_day = parse_visit_date(row[config.visit_date_index], config.default_year)
                campaign, created = get_or_create_campaign(db, campaign_cache, company, branch, site, visit_day, creator_id)
                summary["campaigns_created"] += int(created)
                summary["doctor_assignments_created"] += int(ensure_doctor_assignment(db, campaign, doctor))

                blood_group = (
                    normalize_text(row[config.blood_group_index])
                    if config.blood_group_index is not None and config.blood_group_index < len(row)
                    else None
                )
                conclusion = normalize_text(row[config.conclusion_index])
                next_visit = (
                    normalize_text(row[config.next_visit_index])
                    if config.next_visit_index is not None and config.next_visit_index < len(row)
                    else None
                )
                summary_text = (
                    normalize_multiline(row[config.summary_index])
                    if config.summary_index is not None and config.summary_index < len(row)
                    else None
                )
                chronic_text = (
                    normalize_multiline(row[config.chronic_index])
                    if config.chronic_index is not None and config.chronic_index < len(row)
                    else None
                )
                orientation = (
                    normalize_multiline(row[config.orientation_index])
                    if config.orientation_index is not None and config.orientation_index < len(row)
                    else None
                )
                birth_date = parse_birth_date(row[config.birth_date_index])
                matricule = normalize_text(row[config.matricule_index])
                employee_number = build_employee_number(
                    sheet_name, row_number, matricule, last_name, first_name, birth_date
                )
                worker, created = get_or_create_worker(
                    db=db,
                    cache=worker_cache,
                    company=company,
                    branch=branch,
                    site=site,
                    employee_number=employee_number,
                    last_name=last_name,
                    first_name=first_name,
                    birth_date=birth_date,
                    blood_group=blood_group,
                    job_title=normalize_text(row[config.job_title_index]),
                    medical_status=infer_worker_status(conclusion),
                    address=address,
                    department=sheet_name,
                )
                summary["workers_created"] += int(created)
                summary["campaign_workers_created"] += int(ensure_campaign_worker(db, campaign, worker))

                general_test = test_aliases["general"]
                summary["campaign_tests_created"] += int(ensure_campaign_test(db, campaign, general_test))
                general_local_id = f"legacy-worker-test-{slugify(sheet_name)}-{row_number}-general"
                created = ensure_worker_test(
                    db=db,
                    local_id=general_local_id,
                    campaign=campaign,
                    worker=worker,
                    test=general_test,
                    doctor=doctor,
                    visit_day=visit_day,
                    status="reviewed" if doctor else "completed",
                    result=conclusion,
                    notes=general_notes(blood_group, next_visit, summary_text, chronic_text, orientation),
                    is_normal=infer_is_normal(conclusion, summary_text),
                )
                summary["worker_tests_created"] += int(created)

                for suffix, index, alias in (
                    ("audiogram", config.audiogram_index, "audiogram"),
                    ("ecg", config.ecg_index, "ecg"),
                    ("efr", config.efr_index, "efr"),
                    ("vision", config.vision_index, "vision"),
                ):
                    if index is None or index >= len(row):
                        continue
                    value = normalize_multiline(row[index])
                    if not value:
                        continue
                    test = test_aliases[alias]
                    summary["campaign_tests_created"] += int(ensure_campaign_test(db, campaign, test))
                    local_id = f"legacy-worker-test-{slugify(sheet_name)}-{row_number}-{suffix}"
                    created = ensure_worker_test(
                        db=db,
                        local_id=local_id,
                        campaign=campaign,
                        worker=worker,
                        test=test,
                        doctor=doctor,
                        visit_day=visit_day,
                        status="reviewed" if doctor else "completed",
                        result=value,
                        notes=summary_text,
                        is_normal=infer_is_normal(value),
                    )
                    summary["worker_tests_created"] += int(created)

        db.commit()

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Importe un classeur historique dans la base applicative.")
    parser.add_argument("workbook", type=Path, help="Chemin du fichier .xlsx a importer")
    args = parser.parse_args()

    summary = import_workbook(args.workbook)
    print("Import termine.")
    for key, value in summary.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
