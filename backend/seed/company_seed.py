"""Seed 20 oil/gas companies, 200 demo filiales, and 1,000 demo drilling sites.

Run from backend: python seed/company_seed.py
Requires the configured PostgreSQL database with migrations already applied.

Company names represent Algerian companies and international operators/services
present in Algeria, not an official ranking. Filiales and drilling sites are
fictional demo records, not the companies' actual corporate structure or assets.
Company-name references:
https://sonatrach.com/fr/filiales-et-participations/
https://www.trade.gov/energy-resource-guide-algeria-oil-and-gas
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import select, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models.branch import Branch  # noqa: E402
from app.models.company import Company  # noqa: E402
from app.models.drilling_site import DrillingSite  # noqa: E402


COMPANY_NAMES = (
    "SONATRACH",
    "ENSP",
    "ENAFOR",
    "ENTP",
    "ENAGEO",
    "ENGTP",
    "GCB",
    "ENAC",
    "SARPI",
    "NAFTAL",
    "ENI",
    "TOTALENERGIES",
    "OCCIDENTAL",
    "REPSOL",
    "EQUINOR",
    "PTTEP",
    "PETROVIETNAM",
    "HALLIBURTON ALGERIA",
    "SCHLUMBERGER ALGERIA",
    "BAKER HUGHES ALGERIA",
)

FILIALE_LOCATIONS = (
    "Hassi Messaoud",
    "Hassi R'Mel",
    "In Amenas",
    "In Salah",
    "Ouargla",
    "Touggourt",
    "Illizi",
    "Adrar",
    "Timimoun",
    "Berkine",
)
SITES_PER_FILIALE = 5
DEMO_NOTE = (
    "company_seed: Donnees de demonstration. Les filiales et sites de forage "
    "sont fictifs et ne representent pas les actifs reels de cette entreprise."
)


def name_key(name: str) -> str:
    return " ".join(name.split()).casefold()


def require_active(record: Company | Branch | DrillingSite) -> None:
    if record.deleted_at is not None:
        raise ValueError(
            f"Cannot seed beneath or reuse deleted {type(record).__name__}: "
            f"{record.name!r}. Restore or rename that record before retrying."
        )


def seed_companies(db: Session) -> dict[str, int]:
    """Insert missing records; the caller owns the transaction.

    Match companies by name and children by parent plus name. Existing records
    and any additional branches/sites are preserved. Ambiguous company names
    or matching soft-deleted records fail instead of choosing an unsafe parent.
    """
    inserted = {"companies": 0, "filiales": 0, "sites": 0}
    companies: dict[str, Company] = {}
    wanted_names = {name_key(name) for name in COMPANY_NAMES}
    for company in db.scalars(select(Company)).all():
        key = name_key(company.name)
        if key not in wanted_names:
            continue
        if key in companies:
            raise ValueError(f"Multiple companies match {company.name!r}; resolve duplicates first.")
        companies[key] = company

    for company_name in COMPANY_NAMES:
        company = companies.get(name_key(company_name))
        if company is None:
            company = Company(name=company_name, notes=DEMO_NOTE)
            db.add(company)
            db.flush()
            inserted["companies"] += 1
        require_active(company)

        for filiale_number, location in enumerate(FILIALE_LOCATIONS, start=1):
            filiale_name = f"{company_name} - Filiale {filiale_number:02d} - {location}"
            branch = db.scalars(
                select(Branch).where(
                    Branch.company_id == company.id,
                    Branch.name == filiale_name,
                )
            ).one_or_none()
            if branch is None:
                branch = Branch(
                    company_id=company.id,
                    name=filiale_name,
                    location=location,
                    notes=DEMO_NOTE,
                )
                db.add(branch)
                db.flush()
                inserted["filiales"] += 1
            require_active(branch)

            for site_number in range(1, SITES_PER_FILIALE + 1):
                site_name = (
                    f"{company_name} - Site de forage "
                    f"{filiale_number:02d}-{site_number:02d} - {location}"
                )
                site = db.scalars(
                    select(DrillingSite).where(
                        DrillingSite.branch_id == branch.id,
                        DrillingSite.name == site_name,
                    )
                ).one_or_none()
                if site is None:
                    site = DrillingSite(
                        company_id=company.id,
                        branch_id=branch.id,
                        name=site_name,
                        location=location,
                        status="active",
                        notes=DEMO_NOTE,
                    )
                    db.add(site)
                    inserted["sites"] += 1
                require_active(site)
                if site.company_id != company.id:
                    raise ValueError(f"Site {site.name!r} belongs to a different company.")
            db.flush()

    return inserted


def main() -> None:
    # Demo seeding is deliberately opt-in and database-bound.  The normal
    # stage-three write guard remains active everywhere else.
    import os
    if os.environ.get("LOCAL_DEMO_SEED") != "1":
        raise RuntimeError("Set LOCAL_DEMO_SEED=1 for the isolated demo database only.")
    # Commit the entire hierarchy together; any error rolls it all back.
    with SessionLocal.begin() as db:
        database = db.execute(text("SELECT current_database()" )).scalar_one()
        if database != "ibn_sina_cap_418ef234":
            raise RuntimeError(f"Refusing demo seed on database {database!r}")
        db.info["sync_bootstrap_mode"] = True
        inserted = seed_companies(db)
    print("Company seed complete: 20 companies, 200 demo filiales, 1000 demo sites.")
    print("Inserted: " + ", ".join(f"{count} {kind}" for kind, count in inserted.items()))
    print("Existing records were preserved.")


if __name__ == "__main__":
    main()
