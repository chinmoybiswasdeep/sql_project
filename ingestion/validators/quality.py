"""Post-load plausibility checks on the raw layer.

Each check counts rows matching a *suspicious* condition. Rows are flagged,
never removed: clinically extreme values can be real, and the decision about
how to treat them belongs in documented analytical logic, not in ingestion.

Severity
  error  structural problem that would corrupt metrics (status 'fail' if > 0)
  warn   suspicious but plausible; investigate (status 'flag' if > 0)
  info   known source characteristic worth surfacing (status 'flag' if > 0)
"""

from __future__ import annotations

from dataclasses import dataclass

import psycopg


@dataclass(frozen=True)
class Check:
    name: str
    table: str
    severity: str
    description: str
    sql: str  # must return a single integer: the number of flagged rows
    requires: tuple[str, ...] = ()


CHECKS: list[Check] = [
    Check("admissions_discharge_before_admit", "admissions", "error",
          "Discharge timestamp earlier than admission timestamp (negative LOS).",
          "SELECT count(*) FROM raw.admissions WHERE dischtime < admittime"),
    Check("admissions_missing_dischtime", "admissions", "error",
          "Admissions with no discharge timestamp (LOS cannot be computed).",
          "SELECT count(*) FROM raw.admissions WHERE dischtime IS NULL"),
    Check("admissions_deathtime_outside_stay", "admissions", "warn",
          "Death timestamp more than 24h outside the admission window.",
          """SELECT count(*) FROM raw.admissions WHERE deathtime IS NOT NULL AND
             (deathtime < admittime - interval '24 hours'
              OR deathtime > dischtime + interval '24 hours')"""),
    Check("admissions_expire_flag_mismatch", "admissions", "warn",
          "hospital_expire_flag disagrees with presence of deathtime.",
          """SELECT count(*) FROM raw.admissions
             WHERE (hospital_expire_flag = 1) <> (deathtime IS NOT NULL)"""),
    Check("admissions_overlapping_same_patient", "admissions", "warn",
          "Admission begins before the same patient's previous admission ended.",
          """SELECT count(*) FROM (
               SELECT admittime, lag(dischtime) OVER (PARTITION BY subject_id
                      ORDER BY admittime, hadm_id) AS prev_disch
               FROM raw.admissions) s WHERE admittime < prev_disch"""),
    Check("admissions_los_over_180_days", "admissions", "info",
          "Hospital stays longer than 180 days (extreme but possible).",
          "SELECT count(*) FROM raw.admissions WHERE dischtime - admittime > interval '180 days'"),
    Check("admissions_null_discharge_location", "admissions", "info",
          "Admissions with no recorded discharge location.",
          "SELECT count(*) FROM raw.admissions WHERE discharge_location IS NULL"),
    Check("patients_dod_before_last_discharge", "patients", "warn",
          "Date of death earlier than the patient's last discharge date.",
          """SELECT count(*) FROM raw.patients p JOIN (
               SELECT subject_id, max(dischtime)::date AS last_disch FROM raw.admissions
               GROUP BY subject_id) a USING (subject_id) WHERE p.dod < a.last_disch"""),
    Check("icustays_outtime_before_intime", "icustays", "error",
          "ICU outtime earlier than intime.",
          "SELECT count(*) FROM raw.icustays WHERE outtime < intime"),
    Check("icustays_outside_admission_window", "icustays", "info",
          "ICU stay starts before admittime or ends after dischtime (commonly ED/OR"
          " time recorded before the formal admission).",
          """SELECT count(*) FROM raw.icustays i JOIN raw.admissions a USING (hadm_id)
             WHERE i.intime < a.admittime OR i.outtime > a.dischtime"""),
    Check("icustays_los_mismatch", "icustays", "warn",
          "Source los differs from (outtime - intime) by more than 1 hour.",
          """SELECT count(*) FROM raw.icustays WHERE abs(los -
             extract(epoch FROM outtime - intime) / 86400.0) > 1.0 / 24"""),
    Check("transfers_outtime_before_intime", "transfers", "error",
          "Transfer outtime earlier than intime.",
          "SELECT count(*) FROM raw.transfers WHERE outtime < intime"),
    Check("labevents_without_admission", "labevents", "info",
          "Lab events with no hadm_id (outpatient or pre-admission draws).",
          "SELECT count(*) FROM raw.labevents WHERE hadm_id IS NULL"),
    Check("labevents_inverted_reference_range", "labevents", "warn",
          "Reference range lower bound above upper bound.",
          "SELECT count(*) FROM raw.labevents WHERE ref_range_lower > ref_range_upper"),
    Check("labevents_flag_without_range", "labevents", "info",
          "Results flagged abnormal that carry no numeric reference range.",
          """SELECT count(*) FROM raw.labevents WHERE flag = 'abnormal'
             AND (ref_range_lower IS NULL OR ref_range_upper IS NULL)"""),
    Check("prescriptions_stop_before_start", "prescriptions", "warn",
          "Prescription stoptime earlier than starttime.",
          "SELECT count(*) FROM raw.prescriptions WHERE stoptime < starttime"),
    Check("chartevents_negative_heart_rate", "chartevents", "warn",
          "Heart rate (itemid 220045) recorded below 0 or above 300 bpm.",
          """SELECT count(*) FROM raw.chartevents WHERE itemid = 220045
             AND (valuenum < 0 OR valuenum > 300)""",
          requires=("chartevents",)),
]


def _has_rows(cur, table: str) -> bool:
    cur.execute(
        "SELECT to_regclass(%s) IS NOT NULL", (f"raw.{table}",)
    )
    if not cur.fetchone()[0]:
        return False
    cur.execute(f"SELECT EXISTS (SELECT 1 FROM raw.{table})")  # table names are internal
    return bool(cur.fetchone()[0])


def run_checks(conn: psycopg.Connection, run_id: int) -> list[dict]:
    results = []
    with conn.cursor() as cur:
        for check in CHECKS:
            if not all(_has_rows(cur, t) for t in (check.table, *check.requires)):
                continue
            cur.execute(check.sql)
            flagged = int(cur.fetchone()[0])
            if flagged == 0:
                status = "pass"
            else:
                status = "fail" if check.severity == "error" else "flag"
            cur.execute(
                """INSERT INTO meta.validation_results
                   (run_id, check_name, table_name, severity, status, flagged_rows, description)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (run_id, check.name, check.table, check.severity, status, flagged,
                 check.description),
            )
            results.append({"check": check.name, "table": check.table,
                            "severity": check.severity, "status": status,
                            "flagged_rows": flagged, "description": check.description})
    conn.commit()
    return results
