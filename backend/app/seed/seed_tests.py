from __future__ import annotations

import json

from sqlalchemy import select

from app.database import SessionLocal
from app.models.medical_test import MedicalTest

DEFAULT_TESTS = [
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


def build_description(fields: list[str]) -> str:
    return json.dumps(
        {
            "type": "dynamic_medical_test",
            "fields": fields,
        },
        ensure_ascii=False,
    )


def seed_medical_tests() -> None:
    inserted = 0
    updated = 0

    with SessionLocal() as db:
        for payload in DEFAULT_TESTS:
            name = str(payload["name"])
            section = str(payload["section"])
            fields = payload["fields"]

            description = build_description(fields)

            existing = db.scalar(
                select(MedicalTest).where(
                    MedicalTest.name == name,
                    MedicalTest.section == section,
                )
            )

            if existing:
                existing.category = section
                existing.description = description
                existing.requires_doctor_review = False
                existing.is_active = True
                updated += 1
                continue

            db.add(
                MedicalTest(
                    name=name,
                    section=section,
                    category=section,
                    description=description,
                    requires_doctor_review=False,
                    is_active=True,
                )
            )
            inserted += 1

        db.commit()

    print(f"Inserted: {inserted}")
    print(f"Updated: {updated}")


if __name__ == "__main__":
    seed_medical_tests()
