# Dossier médical field inventory

This template uses a dedicated 3-page coordinate map for the worker medical dossier PDF.

## Page 1

- Header and identity: `dossier_number`, `last_name`, `first_name`, `sex`, `birth_date`, `birth_place`, `family_situation`, `phone`
- Addresses and training: `origin_address`, `professional_address`, `school_education`, `professional_training`, `professional_qualification`
- Professional history table: `professional_history_position_1..3`, `professional_history_from_1..3`, `professional_history_to_1..3`, `professional_history_risks_1..3`
- National service and medical basics: `service_national_accompli`, `service_national_dispense`, `service_national_inapte`, `chronic_disease_notes`, `blood_group_rhesus`

## Page 2

- Personal history: `congenital_diseases`, `general_diseases`, `surgical_interventions`, `accidents`, `intoxications_tobacco`, `intoxications_chewing_tobacco`, `intoxications_alcoholism`, `intoxications_others`
- Vaccination table: `vaccination_name_1..3`, `vaccination_first_dose_1..3`, `vaccination_second_dose_1..3`, `vaccination_first_booster_1..3`, `vaccination_second_booster_1..3`
- Family history: `family_history_father`, `family_history_mother`, `family_history_sisters`, `family_history_brothers`, `family_history_spouse`, `family_history_children_boys`, `family_history_children_girls`
- Professional incidents: `work_accident_date_1..4`, `work_accident_place_1..4`, `work_accident_consequences_1..4`
- Occupational diseases: `occupational_disease_date_1..3`, `occupational_disease_place_1..3`, `occupational_disease_products_1..3`, `occupational_disease_symptoms_1..3`, `occupational_disease_tmp_1..3`, `occupational_disease_ipp_1..3`, `professional_disease_notes`

## Page 3

- Spontaneous consultations table: `consultation_date_1..10`, `consultation_observation_1..10`

## Notes

- Coordinates are stored in `fitz_top_left` space to match the existing PDF coordinate workflow.
- The dossier template is independent from the `Fich intern de visit Medicale` export and uses its own backend route and preview tab.
