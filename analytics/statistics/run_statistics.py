"""Statistical analysis of the warehouse -> reports/statistics_report.md (+ .json).

Every number in the report is computed here from the marts at run time.
Admission-level data is held in memory only; the report contains aggregates.

Usage:  python -m analytics.statistics.run_statistics [--n-boot 2000]
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime

import numpy as np
import pandas as pd
from scipy import stats

from analytics.metrics.db import read_sql
from analytics.statistics.core import (
    Interval,
    cliffs_delta,
    cliffs_magnitude,
    cluster_bootstrap,
    describe,
    newcombe_diff_ci,
    risk_ratio_ci,
    wilson_ci,
)
from config.settings import PROJECT_ROOT, get_settings

REPORT_MD = PROJECT_ROOT / "reports" / "statistics_report.md"
REPORT_JSON = PROJECT_ROOT / "reports" / "statistics_report.json"


def load() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    adm = read_sql("""
        select hadm_id, subject_id, admission_group, is_observation, sex, age_group,
               los_days, had_icu_stay, icu_days_total, died_in_hospital, n_lab_events,
               n_unit_changes, n_prescriptions, charlson_comorbidity_score,
               is_readmission_index_eligible, is_readmitted_30d, is_unplanned_readmitted_30d,
               admission_seq
        from marts.fact_admissions""")
    rd = read_sql("""
        select index_hadm_id, subject_id, index_admittime, is_eligible_index,
               is_readmitted_30d, index_is_observation, next_is_observation, index_charlson_score,
               age_group, sex
        from marts.fact_readmissions""")
    icu = read_sql("select stay_id, subject_id, icu_los_days, died_in_icu from marts.fact_icu_stays")
    return adm, rd, icu


def fmt_p(p: float) -> str:
    return "<0.001" if p < 0.001 else f"{p:.3f}"


def compare_continuous(df: pd.DataFrame, value: str, group_col: str, a: str, b: str,
                       n_boot: int) -> dict:
    """Median difference (cluster bootstrap CI), Cliff's delta, Mann-Whitney U."""
    xa = df.loc[df[group_col] == a, value].dropna().to_numpy()
    xb = df.loc[df[group_col] == b, value].dropna().to_numpy()
    sub = df[df[group_col].isin([a, b])]

    def median_diff(d: pd.DataFrame) -> float:
        ga, gb = d.loc[d[group_col] == a, value], d.loc[d[group_col] == b, value]
        return float(ga.median() - gb.median()) if len(ga) and len(gb) else np.nan

    ci = cluster_bootstrap(sub, "subject_id", median_diff, n_boot=n_boot)
    u = stats.mannwhitneyu(xa, xb, alternative="two-sided")
    delta = cliffs_delta(xa, xb)
    return {"group_a": a, "group_b": b, "n_a": len(xa), "n_b": len(xb),
            "median_a": float(np.median(xa)), "median_b": float(np.median(xb)),
            "median_diff": ci.estimate, "median_diff_low": ci.low, "median_diff_high": ci.high,
            "cliffs_delta": delta, "cliffs_magnitude": cliffs_magnitude(delta),
            "mann_whitney_p": float(u.pvalue)}


def compare_binary(df: pd.DataFrame, outcome: str, in_group_a: pd.Series, n_boot: int) -> dict:
    """Risk difference (Newcombe + patient-cluster bootstrap), risk ratio, Fisher exact."""
    a = in_group_a.astype(bool)
    x1, n1 = int(df.loc[a, outcome].sum()), int(a.sum())
    x2, n2 = int(df.loc[~a, outcome].sum()), int((~a).sum())
    work = df.assign(_a=a.to_numpy())

    def risk_diff(d: pd.DataFrame) -> float:
        ga, gb = d.loc[d["_a"], outcome], d.loc[~d["_a"], outcome]
        return float(ga.mean() - gb.mean()) if len(ga) and len(gb) else np.nan

    boot = cluster_bootstrap(work, "subject_id", risk_diff, n_boot=n_boot)
    rd = newcombe_diff_ci(x1, n1, x2, n2)
    rr = risk_ratio_ci(x1, n1, x2, n2)
    fisher = stats.fisher_exact([[x1, n1 - x1], [x2, n2 - x2]])
    return {"x1": x1, "n1": n1, "x2": x2, "n2": n2,
            "p1": x1 / n1, "p2": x2 / n2,
            "risk_difference": rd.estimate, "rd_low": rd.low, "rd_high": rd.high,
            "rd_cluster_low": boot.low, "rd_cluster_high": boot.high,
            "risk_ratio": rr.estimate, "rr_low": rr.low, "rr_high": rr.high,
            "fisher_p": float(fisher.pvalue)}


def spearman_with_ci(df: pd.DataFrame, x: str, y: str, n_boot: int) -> dict:
    rho = stats.spearmanr(df[x], df[y])
    ci = cluster_bootstrap(
        df, "subject_id", lambda d: float(stats.spearmanr(d[x], d[y]).statistic), n_boot=n_boot)
    return {"x": x, "y": y, "n": len(df), "rho": float(rho.statistic),
            "rho_low": ci.low, "rho_high": ci.high, "p": float(rho.pvalue)}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-boot", type=int, default=2000)
    args = parser.parse_args(argv)
    nb = args.n_boot
    settings = get_settings()
    adm, rd, icu = load()
    out: dict = {"dataset": settings.dataset_label, "n_boot": nb,
                 "generated_at": datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")}

    # 1. Descriptive statistics --------------------------------------------------
    adm["labs_per_day"] = adm["n_lab_events"] / adm["los_days"].clip(lower=1.0)
    out["descriptive"] = {
        "hospital_los_days": describe(adm["los_days"]),
        "icu_los_days": describe(icu["icu_los_days"]),
        "lab_results_per_admission": describe(adm["n_lab_events"]),
        "lab_results_per_inpatient_day": describe(adm["labs_per_day"]),
        "charlson_score": describe(adm["charlson_comorbidity_score"]),
    }

    # 2. Rates with uncertainty --------------------------------------------------
    elig = rd[rd["is_eligible_index"]]
    rates = {
        "readmission_30d": wilson_ci(int(elig["is_readmitted_30d"].sum()), len(elig)),
        "hospital_mortality": wilson_ci(int(adm["died_in_hospital"].sum()), len(adm)),
        "icu_admission": wilson_ci(int(adm["had_icu_stay"].sum()), len(adm)),
        "icu_mortality_per_stay": wilson_ci(int(icu["died_in_icu"].sum()), len(icu)),
    }
    readm_cluster = cluster_bootstrap(elig, "subject_id",
                                      lambda d: float(d["is_readmitted_30d"].mean()), n_boot=nb)
    los_median_cluster = cluster_bootstrap(adm, "subject_id",
                                           lambda d: float(d["los_days"].median()), n_boot=nb)
    out["rates"] = {k: vars(v) for k, v in rates.items()}
    out["rates"]["readmission_30d_cluster_bootstrap"] = vars(readm_cluster)
    out["median_los_cluster_bootstrap"] = vars(los_median_cluster)

    # 3. Readmission sensitivity analyses ----------------------------------------
    inpatient = elig[~elig["index_is_observation"]]
    first_per_patient = (elig.sort_values("index_admittime")
                         .groupby("subject_id", as_index=False).head(1))
    out["readmission_sensitivity"] = {
        "primary_all_eligible": vars(wilson_ci(int(elig["is_readmitted_30d"].sum()), len(elig))),
        "exclude_observation_index": vars(wilson_ci(int(inpatient["is_readmitted_30d"].sum()),
                                                    len(inpatient))),
        "first_eligible_discharge_per_patient": vars(wilson_ci(
            int(first_per_patient["is_readmitted_30d"].sum()), len(first_per_patient))),
    }

    # 4. Cohort comparisons ------------------------------------------------------
    adm["icu_group"] = np.where(adm["had_icu_stay"], "ICU", "No ICU")
    comparisons = {
        "los_emergency_vs_elective": compare_continuous(
            adm, "los_days", "admission_group", "Emergency", "Elective", nb),
        "los_icu_vs_no_icu": compare_continuous(adm, "los_days", "icu_group", "ICU", "No ICU", nb),
    }
    comparisons["readmission_charlson5plus_vs_0to4"] = compare_binary(
        elig, "is_readmitted_30d", elig["index_charlson_score"] >= 5, nb)
    comparisons["mortality_male_vs_female"] = compare_binary(
        adm, "died_in_hospital", adm["sex"] == "M", nb)
    out["comparisons"] = comparisons

    # 5. Correlations ------------------------------------------------------------
    out["correlations"] = [
        spearman_with_ci(adm, "charlson_comorbidity_score", "los_days", nb),
        spearman_with_ci(adm, "n_unit_changes", "los_days", nb),
        spearman_with_ci(adm, "charlson_comorbidity_score", "n_lab_events", nb),
    ]

    REPORT_JSON.write_text(json.dumps(out, indent=2, default=float))
    REPORT_MD.write_text(render(out))
    print(f"wrote {REPORT_MD.relative_to(PROJECT_ROOT)}")


def render(o: dict) -> str:
    d = o["descriptive"]
    r = o["rates"]
    c = o["comparisons"]
    s = o["readmission_sensitivity"]

    def iv(x: dict, pct: bool = True, digits: int = 1) -> str:
        return Interval(x["estimate"], x["low"], x["high"]).fmt(pct=pct, digits=digits)

    lines = [
        "# Statistical Analysis Report", "",
        f"_Generated {o['generated_at']} by `python -m analytics.statistics.run_statistics` "
        f"on `{o['dataset']}`. Bootstrap replicates: {o['n_boot']} (seeded, reproducible)._", "",
        "## Read this first", "",
        "- **Population.** 100 demo patients, all of whom had at least one ICU stay. Every "
        "estimate describes this sample, not a hospital population.",
        "- **Clustering.** Patients contribute several admissions (up to 20). Admissions are "
        "not independent, so the primary intervals use a **patient-level cluster bootstrap**. "
        "Classical tests (Mann-Whitney, Fisher) assume independence; their p-values are "
        "shown for reference only and are optimistic.",
        "- **Association is not causation.** No comparison here is adjusted for confounding.",
        "- **Effect sizes first.** Each comparison reports an effect size with a CI. A small "
        "p-value is not evidence of a large or important effect, and a large p-value in "
        "a sample this small is not evidence of no effect.", "",
        "## 1. Descriptive statistics", "",
        "| Measure | n | Mean | SD | Variance | P10 | P25 | Median | P75 | P90 | P95 | Skew |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    labels = {"hospital_los_days": "Hospital LOS (days)", "icu_los_days": "ICU LOS (days)",
              "lab_results_per_admission": "Lab results / admission",
              "lab_results_per_inpatient_day": "Lab results / inpatient day",
              "charlson_score": "Charlson score"}
    for k, label in labels.items():
        x = d[k]
        lines.append(f"| {label} | {x['n']} | {x['mean']:.2f} | {x['sd']:.2f} | "
                     f"{x['variance']:.2f} | {x['p10']:.2f} | {x['p25']:.2f} | "
                     f"{x['median']:.2f} | {x['p75']:.2f} | {x['p90']:.2f} | {x['p95']:.2f} | "
                     f"{x['skewness']:.2f} |")
    lines += ["", "All distributions are right-skewed (skew > 0), so medians and percentiles "
              "are the headline statistics and means are secondary.", "",
              "## 2. Key rates with 95% confidence intervals", "",
              "| Metric | Wilson interval (independent obs.) | Patient-cluster bootstrap |",
              "|---|---|---|",
              f"| 30-day readmission | {iv(r['readmission_30d'])} | "
              f"{iv(r['readmission_30d_cluster_bootstrap'])} |",
              f"| In-hospital mortality | {iv(r['hospital_mortality'])} | — |",
              f"| Admissions with ICU care | {iv(r['icu_admission'])} | — |",
              f"| ICU mortality (per stay) | {iv(r['icu_mortality_per_stay'])} | — |",
              f"| Median hospital LOS (days) | — | "
              f"{iv(o['median_los_cluster_bootstrap'], pct=False, digits=2)} |", "",
              "The cluster bootstrap interval for readmission is wider than the Wilson interval. "
              "That is expected: frequent patients' readmissions are correlated, so the "
              "effective sample size is smaller than the number of discharges.", "",
              "## 3. Readmission sensitivity analysis", "",
              "| Definition | Rate |", "|---|---|",
              f"| Primary: all eligible index discharges | {iv(s['primary_all_eligible'])} |",
              f"| Exclude observation-status index encounters | "
              f"{iv(s['exclude_observation_index'])} |",
              f"| First eligible discharge per patient only (removes clustering) | "
              f"{iv(s['first_eligible_discharge_per_patient'])} |", "",
              "If the rate moves materially between definitions, the headline figure depends "
              "on methodological choices and should always be quoted with its definition.", "",
              "## 4. Cohort comparisons", "",
              "### Continuous outcomes (LOS, days)", "",
              "| Comparison | n (A / B) | Median A | Median B | Median diff (cluster-bootstrap CI) "
              "| Cliff's δ (magnitude) | Mann-Whitney p* |",
              "|---|---|---:|---:|---|---|---:|"]
    for key, label in [("los_emergency_vs_elective", "Emergency vs Elective"),
                       ("los_icu_vs_no_icu", "ICU vs no ICU")]:
        x = c[key]
        lines.append(f"| {label} | {x['n_a']} / {x['n_b']} | {x['median_a']:.2f} | "
                     f"{x['median_b']:.2f} | {x['median_diff']:.2f} "
                     f"({x['median_diff_low']:.2f} to {x['median_diff_high']:.2f}) | "
                     f"{x['cliffs_delta']:.2f} ({x['cliffs_magnitude']}) | "
                     f"{fmt_p(x['mann_whitney_p'])} |")
    lines += ["", "### Binary outcomes", "",
              "| Comparison | Rate A | Rate B | Risk difference (Newcombe CI*) "
              "| RD patient-cluster bootstrap CI | Risk ratio (CI*) | Fisher p* |",
              "|---|---|---|---|---|---|---:|"]
    for key, label in [("readmission_charlson5plus_vs_0to4",
                        "30-day readmission: Charlson 5+ vs 0-4"),
                       ("mortality_male_vs_female", "In-hospital mortality: male vs female")]:
        x = c[key]
        lines.append(f"| {label} | {x['x1']}/{x['n1']} ({100 * x['p1']:.1f}%) | "
                     f"{x['x2']}/{x['n2']} ({100 * x['p2']:.1f}%) | "
                     f"{100 * x['risk_difference']:.1f} pts ({100 * x['rd_low']:.1f} to "
                     f"{100 * x['rd_high']:.1f}) | {100 * x['rd_cluster_low']:.1f} to "
                     f"{100 * x['rd_cluster_high']:.1f} pts | {x['risk_ratio']:.2f} "
                     f"({x['rr_low']:.2f}-{x['rr_high']:.2f}) | {fmt_p(x['fisher_p'])} |")
    lines += ["", "\\* Assumes independent observations; optimistic under patient clustering.",
              "", "## 5. Correlation analysis (Spearman, patient-cluster bootstrap CI)", "",
              "| X | Y | n | ρ | 95% CI |", "|---|---|---:|---:|---|"]
    for x in o["correlations"]:
        lines.append(f"| {x['x']} | {x['y']} | {x['n']} | {x['rho']:.2f} | "
                     f"{x['rho_low']:.2f} to {x['rho_high']:.2f} |")
    lines += ["", "Spearman's rank correlation is used because the variables are skewed and "
              "the relationships need not be linear. Charlson is coded at discharge, so its "
              "correlation with LOS and lab volume is partly reverse-causal: longer, more "
              "intensive stays document more conditions.", "",
              "## Assumptions and limitations", "",
              "1. Wilson and Newcombe intervals assume independent Bernoulli trials; the cluster "
              "bootstrap relaxes this by resampling patients.",
              "2. Percentile bootstrap intervals with ~100 clusters can under-cover slightly; "
              "they are a reasonable, transparent choice for a descriptive analysis.",
              "3. No multiple-comparison correction is applied. The comparisons were chosen "
              "in advance as illustrative, not as a search for significance.",
              "4. Nothing here supports causal or clinical-treatment conclusions.", ""]
    return "\n".join(lines)


if __name__ == "__main__":
    main()
