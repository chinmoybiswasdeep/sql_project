-- Raw-layer indexes, created *after* bulk load (building once is far cheaper
-- than maintaining indexes during COPY). Chosen for the join and filter
-- paths used by dbt staging models and the analytical SQL:
--   * every child table is joined to admissions on hadm_id
--   * readmission logic partitions admissions by subject_id ordered by admittime
--   * lab analytics filter/group by itemid
-- IF NOT EXISTS keeps the script idempotent across restarts.

CREATE INDEX IF NOT EXISTS ix_raw_admissions_subject_admit ON raw.admissions (subject_id, admittime);
CREATE INDEX IF NOT EXISTS ix_raw_admissions_hadm         ON raw.admissions (hadm_id);
CREATE INDEX IF NOT EXISTS ix_raw_patients_subject        ON raw.patients (subject_id);
CREATE INDEX IF NOT EXISTS ix_raw_transfers_hadm          ON raw.transfers (hadm_id, intime);
CREATE INDEX IF NOT EXISTS ix_raw_services_hadm           ON raw.services (hadm_id, transfertime);
CREATE INDEX IF NOT EXISTS ix_raw_diagnoses_hadm          ON raw.diagnoses_icd (hadm_id, seq_num);
CREATE INDEX IF NOT EXISTS ix_raw_diagnoses_code          ON raw.diagnoses_icd (icd_version, icd_code);
CREATE INDEX IF NOT EXISTS ix_raw_procedures_hadm         ON raw.procedures_icd (hadm_id);
CREATE INDEX IF NOT EXISTS ix_raw_icustays_hadm           ON raw.icustays (hadm_id);
CREATE INDEX IF NOT EXISTS ix_raw_prescriptions_hadm      ON raw.prescriptions (hadm_id);
CREATE INDEX IF NOT EXISTS ix_raw_labevents_hadm          ON raw.labevents (hadm_id);
CREATE INDEX IF NOT EXISTS ix_raw_labevents_item          ON raw.labevents (itemid);
CREATE INDEX IF NOT EXISTS ix_raw_labevents_subject_time  ON raw.labevents (subject_id, charttime);
