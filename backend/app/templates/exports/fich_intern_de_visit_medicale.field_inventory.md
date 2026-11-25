# Fich intern de visit Medicale field inventory

This inventory preserves the current backend export keys and records whether each key has a visible destination on the scanned paper template.

## Page 1: header and internal visit

- Visible: `worker_full_name`, `worker_birth_date`, `worker_position`, `visit_type_hire`, `visit_type_periodic`, `visit_date`, `visit_doctor`, `visit_weight`, `visit_height`, `visit_ta`, `visit_fc`, `visit_vision_od_sc`, `visit_vision_od_ac`, `visit_vision_og_sc`, `visit_vision_og_ac`, `visit_vision_odg`
- Unresolved: `worker_direction`, `worker_employee_code`, `worker_national_id`

## Page 1: examen clinique

- Visible: `clinical_ophthalmology_observations`, `clinical_ent_nose`, `clinical_ent_ears`, `clinical_ent_throat`, `clinical_stomatology_teeth`, `clinical_stomatology_others`, `clinical_cardiovascular_blood_pressure`, `clinical_cardiovascular_dyspnea`, `clinical_respiratory_chronic_cough`, `clinical_respiratory_asthma`, `clinical_digestive_ulcer`, `clinical_digestive_colopathy`, `clinical_digestive_hemorrhoids`, `clinical_digestive_others`, `clinical_urogenital_dysuria`, `clinical_urogenital_impotence`, `clinical_urogenital_others`, `clinical_endocrine_diabetes`, `clinical_endocrine_thyroid`, `clinical_endocrine_others`, `clinical_hematology_hemostasis`, `clinical_hematology_adenopathy`, `clinical_hematology_others`, `clinical_neuro_headaches_vertigo`, `clinical_neuro_neurological_signs`, `clinical_neuro_personality_disorders`, `clinical_neuro_others`, `clinical_osteo_polyarthralgia`, `clinical_dermatology_lesions`, `clinical_dermatology_skin_allergies`, `clinical_dermatology_urticaria`
- Unresolved: `clinical_general_comments`, `clinical_general_recommendations`

## Page 2: examens complémentaires

- Visible: `complementary_cardiology_ecg`, `complementary_audiology_audiogram`, `complementary_respiratory_efr`, `complementary_biology_blood_group_rhesus`, `complementary_biology_glycemia`, `complementary_biology_hba1c`, `complementary_biology_urea`, `complementary_biology_creatinine`, `complementary_biology_cholesterol`, `complementary_biology_triglycerides`, `complementary_biology_hdl_ldl`, `complementary_biology_urine_chemistry`, `complementary_hematology_gr`, `complementary_hematology_gb`, `complementary_hematology_hb`, `complementary_hematology_ht`, `complementary_hematology_vgm`, `complementary_hematology_ccmh`, `complementary_hematology_plt`, `complementary_hematology_pn`, `complementary_hematology_lymphocytes`, `complementary_hematology_bem`, `complementary_hematology_vs`, `complementary_parasitology_stool_exam`, `complementary_other_exams`
- Unresolved: `complementary_radiology_chest_xray`, `complementary_radiology_others`

## Page 2: orientation and décision

- Visible: `decision_orientation_specialty`, `decision_orientation_specialist_advice`, `decision_orientation_specialist_advice_details`, `decision_orientation_treatment`, `decision_orientation_treatment_details`, `decision_orientation_hospitalization`, `decision_orientation_hospitalization_details`, `decision_specialist_response`, `decision_specialist_social_service`, `decision_specialist_employment_service`, `decision_cat_conduct`, `decision_aptitude`, `decision_aptitude_apte`, `decision_aptitude_apte_with_restrictions`, `decision_aptitude_temporarily_unfit`, `decision_aptitude_definitively_unfit`, `decision_validation_signature`
- Unresolved: `decision_interpretation`, `decision_next_visit_schedule`, `decision_next_visit_date`, `decision_validation_doctor`, `decision_validation_date`

## Notes

- Coordinates are stored in `fitz_top_left` space to match `backend/pdf_coordinate_picker.py`.
- `decision_validation_signature` now uses a dedicated custom overlay zone on page 2 for the workspace PNG signature image.
- Unresolved keys intentionally keep empty placement lists so the exporter contract stays stable while avoiding bad placements on the real paper form.
