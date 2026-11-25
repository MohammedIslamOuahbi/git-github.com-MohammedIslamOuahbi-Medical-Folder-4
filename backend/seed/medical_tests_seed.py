from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import select, text  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models.medical_test import MedicalTest  # noqa: E402


TESTS_TO_INSERT: list[dict[str, object]] = [
    {"name": "Acuité visuelle", "section": "Fiche interne de visite medicale", "fields": ["OD SC", "OD AC", "OG SC", "OG AC"]},
    {"name": "Acuité visuelle Binoculaire", "section": "Fiche interne de visite medicale", "fields": ["ODG"]},

    {"name": "Ophtalmologie", "section": "Examen clinique", "fields": ["Ophtalmologie"]},
    {"name": "ORL", "section": "Examen clinique", "fields": ["Nez", "Oreilles", "Gorge"]},
    {"name": "Stomatologie", "section": "Examen clinique", "fields": ["Gorge", "Autres"]},
    {"name": "Cardio Vasculaire", "section": "Examen clinique", "fields": ["TA", "Dyspnée"]},
    {"name": "Digestif", "section": "Examen clinique", "fields": ["Ulcère", "Colopathie fonctionnelle", "Hémorroïdes", "Autres"]},
    {"name": "Uro-génital", "section": "Examen clinique", "fields": ["Dysurie", "Impuissance", "Autres"]},
    {"name": "Endocrinien", "section": "Examen clinique", "fields": ["Diabète", "Thyroïde"]},
    {"name": "Hematologie", "section": "Examen clinique", "fields": ["Hémostase", "Adénopathie", "Autres"]},
    {"name": "Neuro-Psychiatrie", "section": "Examen clinique", "fields": ["Céphalées / Vertiges", "Signe neurologique", "Trouble de la personnalité", "Autres"]},
    {"name": "Osteo-Articulaire", "section": "Examen clinique", "fields": ["Poly arthralgies"]},
    {"name": "Dermatologie", "section": "Examen clinique", "fields": ["Lésion élémentaire", "Allergie cutanée", "Urticaire"]},

    {"name": "ECG", "section": "Examens complementaires", "fields": ["ECG"]},
    {"name": "Audiogramme", "section": "Examens complementaires", "fields": ["Audiogramme"]},
    {"name": "EFR", "section": "Examens complementaires", "fields": ["EFR"]},
    {
        "name": "Biologie",
        "section": "Examens complementaires",
        "fields": [
            "Groupe sanguin / Rhésus",
            "Chimie des urines",
            "Cholestérol",
            "Glycémie",
            "Urée sanguine",
            "Triglycérides",
            "Hb A1c",
            "Créatinine sanguine",
            "HDL / LDL",
        ],
    },
    {"name": "NFS / Hematologie", "section": "Examens complementaires", "fields": ["GR", "VGM", "GB", "PN", "Hb", "CCMH", "Lymphocytes", "B.E.M", "Ht", "PLT", "VS"]},
    {"name": "Parasitologie des selles", "section": "Examens complementaires", "fields": ["Parasitologie des selles"]},
    {"name": "Autres Examens", "section": "Examens complementaires", "fields": ["Autres Examens"]},
]


def normalize_value(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(char for char in value if not unicodedata.combining(char))
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def test_key(name: str, section: str) -> tuple[str, str]:
    return normalize_value(name), normalize_value(section)


def seed_medical_tests() -> int:
    import os
    if os.environ.get("LOCAL_DEMO_SEED") != "1":
        raise RuntimeError("Set LOCAL_DEMO_SEED=1 for the isolated demo database only.")
    inserted = 0
    preserved = 0

    with SessionLocal() as db:
        database = db.execute(text("SELECT current_database()" )).scalar_one()
        if database != "ibn_sina_cap_418ef234":
            raise RuntimeError(f"Refusing demo seed on database {database!r}")
        db.info["sync_bootstrap_mode"] = True
        existing_tests = db.scalars(select(MedicalTest)).all()

        existing_by_key = {
            test_key(test.name, test.section): test
            for test in existing_tests
        }

        for payload in TESTS_TO_INSERT:
            name = str(payload["name"])
            section = str(payload["section"])
            fields = payload["fields"]

            description = json.dumps(
                {
                    "type": "dynamic_medical_test",
                    "fields": fields,
                },
                ensure_ascii=False,
            )

            key = test_key(name, section)
            existing = existing_by_key.get(key)

            if existing:
                preserved += 1
                continue

            test = MedicalTest(
                name=name,
                section=section,
                category=section,
                description=description,
                requires_doctor_review=False,
                is_active=True,
            )

            db.add(test)
            existing_by_key[key] = test
            inserted += 1

        try:
            db.commit()
        except Exception:
            db.rollback()
            raise

    print(f"Inserted: {inserted}")
    print(f"Preserved: {preserved}")

    return inserted


if __name__ == "__main__":
    seed_medical_tests()
