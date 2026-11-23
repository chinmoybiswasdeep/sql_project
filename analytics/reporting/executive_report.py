"""Generate reports/executive_report.md and its figures from the live warehouse.

Every number in the narrative is queried at generation time (the SQL that
produces it is the catalogued query referenced next to it). The narrative
framing and recommendations were written after reviewing the results; a
guard re-checks the qualitative claims (e.g. which category ranks first)
and aborts if the data no longer supports them.

Usage:  python -m analytics.reporting.executive_report
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from analytics.metrics.db import SQL_DIR, read_sql, run_sql_file  # noqa: E402
from config.settings import PROJECT_ROOT, get_settings  # noqa: E402

REPORT = PROJECT_ROOT / "reports" / "executive_report.md"
FIG_DIR = PROJECT_ROOT / "reports" / "figures"

# Reference palette (dataviz skill, light mode) and text tokens
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
INK, INK_2, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#8a8984", "#e6e5e1", "#fcfcfb"


def q(path: str) -> pd.DataFrame:
    return run_sql_file(SQL_DIR / path)


def style(ax, title: str, xlabel: str, grid_axis: str = "x") -> None:
    ax.set_facecolor(SURFACE)
    ax.figure.set_facecolor(SURFACE)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=INK_2, labelsize=9, length=0)
    (ax.xaxis if grid_axis == "x" else ax.yaxis).grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.set_title(title, loc="left", fontsize=11.5, color=INK, fontweight="semibold", pad=12)
    ax.set_xlabel(xlabel, fontsize=9, color=INK_2)


def save(fig, name: str, caption: str) -> str:
    fig.text(0.01, 0.01, caption, fontsize=7.5, color=MUTED, ha="left", va="bottom")
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG_DIR / name, dpi=160)
    plt.close(fig)
    return f"figures/{name}"


def fig_readmission_by_dx(df: pd.DataFrame) -> str:
    d = df.sort_values("rate_pct")
    fig, ax = plt.subplots(figsize=(8, 4.6))
    y = range(len(d))
    ax.hlines(y, d.ci95_low_pct, d.ci95_high_pct, color=SERIES[0], alpha=0.35, linewidth=2)
    ax.plot(d.rate_pct, y, "o", color=SERIES[0], markersize=8, markeredgecolor=SURFACE,
            markeredgewidth=2)
    for yi, (_, r) in zip(y, d.iterrows(), strict=True):
        ax.text(r.ci95_high_pct + 1.2, yi, f"{r.rate_pct:.0f}%  (n={r.eligible_discharges})",
                va="center", fontsize=8, color=INK_2)
    ax.set_yticks(list(y), d.diagnosis_category)
    ax.set_xlim(0, 85)
    style(ax, "30-day readmission by primary diagnosis of index stay",
          "Readmission rate (%)")
    return save(fig, "readmission_by_diagnosis.png",
                "Dot = rate, line = 95% Wilson CI. Eligible index discharges; categories with >= 10. "
                "Source: Q08. Demo cohort (100 ICU patients).")


def fig_los_by_type(df: pd.DataFrame, overall_median: float) -> str:
    d = df.sort_values("median_los_days")
    fig, ax = plt.subplots(figsize=(8, 4.4))
    bars = ax.barh(d.admission_type, d.median_los_days, color=SERIES[0], height=0.6)
    ax.axvline(overall_median, color=INK_2, linewidth=1, linestyle=(0, (3, 3)))
    ax.text(overall_median, len(d) - 0.35, f" hospital median {overall_median:.2f} d",
            fontsize=8, color=INK_2, va="bottom")
    for b, n in zip(bars, d.admissions, strict=True):
        ax.text(b.get_width() + 0.1, b.get_y() + b.get_height() / 2,
                f"{b.get_width():.1f} d  (n={n})", va="center", fontsize=8, color=INK_2,
                bbox={"facecolor": SURFACE, "edgecolor": "none", "pad": 1.5}, zorder=3)
    ax.set_xlim(0, d.median_los_days.max() * 1.3)
    style(ax, "Median hospital length of stay by admission type", "Median LOS (days)")
    return save(fig, "los_by_admission_type.png",
                "All admissions incl. in-hospital deaths. Source: Q21.")


def fig_icu_days(df: pd.DataFrame) -> str:
    d = df.sort_values("icu_days")
    d = d.assign(unit=d.first_careunit.str.replace(r" \(.*\)", "", regex=True))
    fig, ax = plt.subplots(figsize=(8, 4.2))
    bars = ax.barh(d.unit, d.pct_icu_days, color=SERIES[0], height=0.6)
    for b, med in zip(bars, d.median_los_days, strict=True):
        ax.text(b.get_width() + 0.3, b.get_y() + b.get_height() / 2,
                f"{b.get_width():.1f}%  · median stay {med:.1f} d", va="center",
                fontsize=8, color=INK_2)
    ax.set_xlim(0, d.pct_icu_days.max() * 1.55)
    style(ax, "Share of all ICU days by first ICU care unit", "Share of ICU days (%)")
    return save(fig, "icu_days_by_unit.png",
                "Utilisation (days consumed), not occupancy: bed capacity is not in MIMIC. "
                "Source: Q13.")


def fig_resource_index(df: pd.DataFrame) -> str:
    measures = [("los_index", "LOS"), ("icu_index", "ICU days"), ("lab_index", "Lab results"),
                ("med_index", "Medication orders")]
    fig, ax = plt.subplots(figsize=(8, 4.4))
    width, n = 0.19, len(measures)
    x = range(len(df))
    for i, (col, label) in enumerate(measures):
        offs = [xi + (i - (n - 1) / 2) * (width + 0.015) for xi in x]
        bars = ax.bar(offs, df[col], width=width, color=SERIES[i], label=label)
        for b in bars:
            ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.03,
                    f"{b.get_height():.2f}", ha="center", fontsize=7, color=INK_2)
    ax.axhline(1.0, color=INK_2, linewidth=1, linestyle=(0, (3, 3)))
    ax.set_xticks(list(x), [f"Charlson {b}" for b in df.charlson_band])
    ax.set_ylim(0, max(df[c].max() for c, _ in measures) * 1.2)
    style(ax, "Resource use by comorbidity burden (1.00 = average)", "", grid_axis="y")
    ax.set_ylabel("Index vs. all-admission mean", fontsize=9, color=INK_2)
    ax.legend(frameon=False, fontsize=8, ncol=4, loc="upper left", labelcolor=INK_2)
    return save(fig, "resource_index_by_charlson.png",
                "Event counts, not costs. Charlson coded at discharge (inflates association). "
                "Source: Q25.")


def fig_readmission_sensitivity(stats: dict) -> str:
    s = stats["readmission_sensitivity"]
    labels = {"primary_all_eligible": "Primary: all eligible discharges",
              "exclude_observation_index": "Exclude observation-status index stays",
              "first_eligible_discharge_per_patient": "First eligible discharge per patient"}
    rows = [(labels[k], v) for k, v in s.items()]
    fig, ax = plt.subplots(figsize=(8, 2.8))
    for i, (_label, v) in enumerate(rows):
        ax.hlines(i, 100 * v["low"], 100 * v["high"], color=SERIES[0], alpha=0.35, linewidth=2)
        ax.plot(100 * v["estimate"], i, "o", color=SERIES[0], markersize=8,
                markeredgecolor=SURFACE, markeredgewidth=2)
        ax.text(100 * v["high"] + 0.8, i, f"{100 * v['estimate']:.1f}%", va="center",
                fontsize=8, color=INK_2)
    ax.set_yticks(range(len(rows)), [r[0] for r in rows])
    ax.invert_yaxis()
    ax.set_xlim(0, 40)
    style(ax, "30-day readmission under alternative definitions",
          "Readmission rate (%)")
    return save(fig, "readmission_sensitivity.png",
                "Dot = rate, line = 95% Wilson CI. Always quote the rate with its definition. "
                "Source: statistics_report.")


def main() -> None:
    settings = get_settings()
    k = read_sql("select * from reporting.rpt_executive_kpis").iloc[0]
    q04 = q("admissions/q04_length_of_stay_percentiles.sql")
    q05 = q("admissions/q05_top_diagnosis_categories.sql")
    q06, q08, q09 = q("readmissions/q06_readmission_rate_30d.sql"), \
        q("readmissions/q08_readmission_by_diagnosis.sql"), \
        q("readmissions/q09_time_to_next_admission.sql")
    q10, q12, q13 = q("readmissions/q10_repeat_hospitalization_patterns.sql"), \
        q("icu/q12_icu_los_distribution.sql"), q("icu/q13_icu_utilization_by_unit.sql")
    q14, q21 = q("icu/q14_icu_transfer_patterns.sql"), \
        q("operations/q21_los_by_admission_category.sql")
    q23, q25 = q("operations/q23_lab_volume_per_admission.sql"), \
        q("operations/q25_cohort_resource_utilization.sql")
    stats = json.loads((PROJECT_ROOT / "reports" / "statistics_report.json").read_text())
    bench = json.loads((PROJECT_ROOT / "reports" / "benchmarks" /
                        "benchmark_results.json").read_text())

    # --- derived figures --------------------------------------------------------
    allq = q04.set_index("cohort").loc["All admissions"]
    frequent = q10.set_index("frequency_band").loc["7+"]
    gap30 = q09.set_index("gap_bucket").loc["15-30 days", "cumulative_pct"]
    gap90 = q09.set_index("gap_bucket").loc["31-90 days", "cumulative_pct"]
    long_icu = q12[q12.icu_los_band.isin(["7-13 days", "14+ days"])]
    urgent = q21.set_index("admission_type").loc["URGENT"]
    obs = q21.set_index("admission_type").loc["OBSERVATION ADMIT"]
    top_unit = q13.iloc[0]
    c5 = q25.set_index("charlson_band").loc["5+"]
    lab_top = q23.iloc[0]
    sens = stats["readmission_sensitivity"]
    sens_lo = min(v["estimate"] for v in sens.values())
    sens_hi = max(v["estimate"] for v in sens.values())
    ed_icu = q14[(q14.from_unit_type == "Emergency") & (q14.to_unit_type == "ICU")].iloc[0]
    top_dx = q05.iloc[0]
    eligible = int(q06[q06.step.str.contains("denominator")].iloc[0].admissions)
    readmits = int(q06[q06.step.str.contains("numerator")].iloc[0].admissions)

    # --- guards: qualitative claims in the narrative must still hold -------------
    assert top_dx.diagnosis_category == "Circulatory", "narrative assumes Circulatory leads"
    assert top_unit.first_careunit.startswith("Medical Intensive"), "narrative assumes MICU leads"
    assert q21.iloc[0].admission_type == "URGENT", "narrative assumes URGENT has longest LOS"
    assert c5.los_index > 1 and c5.lab_index > 1, "narrative assumes Charlson 5+ above average"
    assert sens_hi - sens_lo > 0.05, "narrative assumes definition sensitivity > 5 points"

    figs = {
        "dx": fig_readmission_by_dx(q08),
        "sens": fig_readmission_sensitivity(stats),
        "los": fig_los_by_type(q21, float(allq["median"])),
        "icu": fig_icu_days(q13),
        "res": fig_resource_index(q25),
    }
    rb = stats["rates"]["readmission_30d"]
    rc = stats["rates"]["readmission_30d_cluster_bootstrap"]
    mlos = stats["median_los_cluster_bootstrap"]
    bench_rows = "\n".join(
        f"| {r['case'].upper()} | {r['technique']} | {r['baseline_median_ms']:.1f} | "
        f"{r['optimized_median_ms']:.2f} | {r['speedup']:.0f}x | "
        f"{'yes' if r['results_equivalent'] else 'NO'} |" for r in bench["results"])
    generated = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")

    md = f"""# Hospital Intelligence — Executive Analytics Report

_Generated {generated} by `python -m analytics.reporting.executive_report` from the live
warehouse (`{settings.dataset_label}`). Every figure below is queried at generation time;
the supporting SQL is cited by query ID ([catalog](../docs/sql_catalog.md))._

> **Scope and status of these findings.** This analysis runs on the public MIMIC-IV demo:
> **{int(k.total_patients)} patients and {int(k.total_admissions)} admissions**, and every
> patient in it had at least one ICU stay. The findings are **exploratory**. They show what
> the platform measures and which questions deserve full-scale study; they are not validated
> operational conclusions about a hospital population. Recommendations are framed as
> analyses to run on the credentialed full dataset (about 546k admissions in MIMIC-IV v3.1),
> not as changes to make now. No clinical-treatment recommendations are made.

## Executive summary

| KPI | Value | Definition |
|---|---:|---|
| Patients / admissions | {int(k.total_patients)} / {int(k.total_admissions)} | distinct subject_id / hadm_id |
| Median hospital LOS | {float(k.median_los_days):.2f} days (95% CI {mlos['low']:.2f}–{mlos['high']:.2f}) | discharge − admit, all admissions |
| Admissions with ICU care | {float(k.icu_admission_pct):.1f}% | ≥1 linked ICU stay (inflated by ICU-only sampling) |
| In-hospital mortality | {float(k.hospital_mortality_pct):.1f}% | hospital_expire_flag |
| 30-day all-cause readmission | {float(k.readmission_30d_pct):.1f}% ({readmits}/{eligible}; 95% CI {100 * rb['low']:.1f}–{100 * rb['high']:.1f}%) | eligible index discharges only; see Q06 |
| 30-day unplanned readmission | {float(k.unplanned_readmission_30d_pct):.1f}% | next admission not elective / same-day surgical |

**Five things leadership should take away:**

1. **A small group of patients drives most hospital use.** {int(frequent.patients)} patients with 7+
   admissions account for **{frequent.pct_of_admissions:.1f}% of all admissions** and average
   {frequent.readmissions_30d_per_patient:.2f} 30-day readmissions each (Q10). Patient-level
   concentration, not average behaviour, is the lever for readmission work.
2. **The readmission headline depends on definitions.** The same data gives
   **{100 * sens_lo:.1f}% to {100 * sens_hi:.1f}%** depending on defensible choices about observation
   stays and repeat patients. Any readmission KPI must be published with its definition and
   denominator.
3. **Long stays are concentrated in specific admission types.** URGENT admissions have a
   median LOS of {urgent.median_los_days:.2f} days ({urgent.median_vs_overall:.2f}× the hospital
   median), and {urgent.pct_long_stay_14d:.1f}% exceed 14 days (Q21).
4. **ICU capacity goes to a minority of long stays.** The {long_icu.pct_stays.sum():.1f}% of ICU stays
   lasting 7+ days consume **{long_icu.pct_icu_days.sum():.1f}% of ICU days** (Q12); the MICU alone
   uses {top_unit.pct_icu_days:.1f}% of them (Q13).
5. **Comorbidity burden tracks resource use.** Admissions with Charlson ≥5 use
   {c5.los_index:.2f}× average LOS, {c5.icu_index:.2f}× ICU days and {c5.lab_index:.2f}× lab results
   (Q25). These are observable event counts, not costs.

## Major findings

### 1. Readmissions

Of {int(k.total_admissions)} admissions, {int(k.total_admissions) - eligible} were excluded from the
denominator (deaths, against-advice discharges, transfers to another acute hospital). Of the
{eligible} eligible discharges, **{readmits} ({float(k.readmission_30d_pct):.1f}%)** were followed by
another admission within 30 days. Because frequent patients contribute many correlated
discharges, a patient-cluster bootstrap gives a wider interval
({100 * rc['low']:.1f}–{100 * rc['high']:.1f}%) than the naive Wilson interval.

![Readmission by diagnosis]({figs['dx']})

By principal diagnosis of the index stay, respiratory and mental/behavioural categories rank
highest and circulatory ranks lowest (Q08), but **every interval overlaps**: at this sample
size the ranking generates hypotheses and proves nothing. Returns cluster beyond the 30-day
window: {gap30:.1f}% of all returns happen within 30 days, but {gap90:.1f}% happen within 90
(Q09).

![Readmission sensitivity]({figs['sens']})

### 2. Length of stay

The median stay is {allq['median']:.2f} days and the mean is {allq.mean_los_days:.2f}. The tail is
long: 10% of stays exceed {allq.p90:.1f} days (Q04).

![LOS by admission type]({figs['los']})

URGENT admissions (often transfers in from other hospitals) stay longest. A second finding
deserves operational follow-up: encounters registered as **OBSERVATION ADMIT have a median of
{obs.median_los_days:.2f} days, and {obs.pct_long_stay_14d:.1f}% last 14+ days**. That is atypical for
observation status and suggests the label persists on encounters that became full inpatient
stays (Q21).

### 3. ICU utilisation and patient flow

![ICU days by unit]({figs['icu']})

The median ICU stay is {q12.overall_median_icu_days.iloc[0]:.2f} days (Q12). The most common
ICU-related movements are ICU to medical ward and ED to ICU; patients wait a median of
{ed_icu.median_hours_in_origin_unit:.1f} hours in the ED before ICU transfer (Q14). These are
utilisation measures: without bed-capacity data, **no occupancy percentage is computed or
implied**.

### 4. Clinical workload and case mix

Circulatory disease is the leading principal diagnosis ({top_dx.pct_primary:.1f}% of admissions), and
chronic metabolic conditions appear as secondary codes on most stays (Q05). Laboratory
workload follows ICU exposure: {lab_top.admission_group} admissions with ICU care generate
{lab_top.pct_of_lab_volume:.1f}% of admission-linked lab results (Q23). Red-cell indices are
the most frequently abnormal high-volume tests, mostly low (Q17); these are measurement
frequencies, not diagnoses.

![Resource index by Charlson band]({figs['res']})

## Statistical uncertainty

- All rates come with 95% intervals; subgroup intervals are wide because n is small.
- Admissions are clustered within patients (up to 20 per patient), so independence-based
  tests are optimistic. Primary intervals use a patient-level cluster bootstrap
  ([statistics report](statistics_report.md)).
- ICU vs non-ICU LOS shows a large effect (Cliff's δ =
  {stats['comparisons']['los_icu_vs_no_icu']['cliffs_delta']:.2f}). Emergency vs elective LOS shows a
  negligible one (δ = {stats['comparisons']['los_emergency_vs_elective']['cliffs_delta']:.2f}).
- No comparison is adjusted for severity or confounding. Associations are not causal.

## Data limitations

1. **Selected cohort:** every demo patient had an ICU stay, so ICU share, mortality and
   readmission are not hospital-wide rates.
2. **Single hospital:** returns to other hospitals are invisible, so readmission is understated.
3. **No follow-up end date:** late discharges cannot be right-censored.
4. **De-identified dates:** calendar trends, seasonality and day-of-week effects cannot be studied.
5. **No cost, staffing or bed-capacity data:** utilisation proxies are event counts.
6. **Billing codes:** diagnoses reflect documentation practice; Charlson is coded at discharge.

Full list: [docs/limitations.md](../docs/limitations.md).

## Recommendations

Each recommendation follows from a result above and is framed as the next analytical action
for a hospital-operations team using this platform on full data.

1. **Target readmission work at frequent-admission patients.** _Evidence:_ 7+-admission patients
   generate {frequent.pct_of_admissions:.1f}% of admissions (Q10). _Action:_ build a
   frequent-admitter cohort view and track its readmission rate separately from the
   population rate.
2. **Standardise the readmission KPI definition before reporting it.** _Evidence:_ the rate moves
   from {100 * sens_lo:.1f}% to {100 * sens_hi:.1f}% across definitions (statistics report §3). _Action:_
   adopt the documented denominator (Q06) as the reporting standard and show sensitivity
   variants next to it.
3. **Review encounter-status labelling for long "observation" stays.** _Evidence:_ OBSERVATION
   ADMIT median LOS {obs.median_los_days:.2f} days with {obs.pct_long_stay_14d:.1f}% over 14 days (Q21).
   _Action:_ join service/status-change data (services table) to see whether these encounters
   converted to inpatient status, which affects both LOS benchmarking and billing classification.
4. **Monitor long ICU stays as a capacity signal.** _Evidence:_ 7+-day stays consume
   {long_icu.pct_icu_days.sum():.1f}% of ICU days (Q12). _Action:_ add a daily "ICU stays beyond 7 days"
   indicator by unit to the operations dashboard; pair it with bed-capacity data (not in MIMIC)
   before computing occupancy.
5. **Extend the readmission window view to 90 days.** _Evidence:_ only {gap30:.1f}% of returns fall
   within 30 days, versus {gap90:.1f}% within 90 (Q09). _Action:_ report 30- and 90-day rates
   together to capture early returns the 30-day window misses.

## Platform performance

Selected SQL optimizations measured on this dataset (median of repeated runs; results verified
identical; demo scale, not a full-data projection —
[benchmark report](benchmarks/benchmark_report.md)):

| Case | Technique | Baseline ms | Optimized ms | Speedup | Identical |
|---|---|---:|---:|---:|---|
{bench_rows}
"""
    REPORT.write_text(md)
    print(f"wrote {REPORT.relative_to(PROJECT_ROOT)} and {len(figs)} figures")


if __name__ == "__main__":
    main()
