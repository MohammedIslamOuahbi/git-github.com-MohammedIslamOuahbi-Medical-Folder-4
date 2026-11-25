from __future__ import annotations


def normalize_sentence_part(value: str | None) -> str:
    return (value or "").strip().strip(",.;")


def build_prescription_item_sentence(item: object) -> str:
    brand_name = normalize_sentence_part(
        getattr(item, "brand_name", None)
        or getattr(item, "medication_name", None)
        or getattr(item, "generic_name", None)
    )
    strength = normalize_sentence_part(getattr(item, "strength", None))
    dose_quantity = normalize_sentence_part(getattr(item, "dose_quantity", None))
    dose_unit = normalize_sentence_part(getattr(item, "dose_unit", None))
    frequency = normalize_sentence_part(getattr(item, "frequency_custom", None) or getattr(item, "frequency", None))
    duration_value = normalize_sentence_part(getattr(item, "duration_value", None))
    duration_unit = normalize_sentence_part(getattr(item, "duration_unit", None))
    instructions = normalize_sentence_part(getattr(item, "instructions", None))

    legacy_dosage = normalize_sentence_part(getattr(item, "dosage", None))
    legacy_duration = normalize_sentence_part(getattr(item, "duration", None))

    title = " ".join(part for part in [brand_name, strength] if part).strip()
    details: list[str] = []

    if dose_quantity or dose_unit:
        details.append(" ".join(part for part in [dose_quantity, dose_unit] if part).strip())
    elif legacy_dosage:
        details.append(legacy_dosage)

    if frequency:
        details.append(frequency)

    if duration_value:
        duration_text = " ".join(part for part in [duration_value, duration_unit] if part).strip()
        details.append(f"pendant {duration_text}".strip())
    elif legacy_duration:
        details.append(f"pendant {legacy_duration}".strip())

    if instructions:
        details.append(instructions.lower() if instructions[:1].isupper() else instructions)

    if title and details:
        return f"{title} - {', '.join(part for part in details if part)}."
    if title:
        return f"{title}."
    return ", ".join(part for part in details if part).strip() + ("." if details else "")


def build_prescription_preview_text(items: list[object]) -> str:
    sentences = [build_prescription_item_sentence(item) for item in items if build_prescription_item_sentence(item)]
    if not sentences:
        return "R/"
    numbered = [f"{index}. {sentence}" for index, sentence in enumerate(sentences, start=1)]
    return "R/\n\n" + "\n\n".join(numbered)
