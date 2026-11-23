# Statistical Analysis Report

_Generated 2026-11-23 03:35 UTC by `python -m analytics.statistics.run_statistics` on `mimic-iv-demo-2.2`. Bootstrap replicates: 2000 (seeded, reproducible)._

## Read this first

- **Population.** 100 demo patients, all of whom had at least one ICU stay. Every estimate describes this sample, not a hospital population.
- **Clustering.** Patients contribute several admissions (up to 20). Admissions are not independent, so the primary intervals use a **patient-level cluster bootstrap**. Classical tests (Mann-Whitney, Fisher) assume independence; their p-values are shown for reference only and are optimistic.
- **Association is not causation.** No comparison here is adjusted for confounding.
- **Effect sizes first.** Each comparison reports an effect size with a CI. A small p-value is not evidence of a large or important effect, and a large p-value in a sample this small is not evidence of no effect.

## 1. Descriptive statistics

| Measure | n | Mean | SD | Variance | P10 | P25 | Median | P75 | P90 | P95 | Skew |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Hospital LOS (days) | 275 | 6.88 | 6.73 | 45.34 | 0.97 | 2.69 | 4.85 | 8.77 | 14.50 | 22.94 | 2.16 |
| ICU LOS (days) | 140 | 3.68 | 3.90 | 15.18 | 0.81 | 1.17 | 2.16 | 4.91 | 8.86 | 13.22 | 2.04 |
| Lab results / admission | 275 | 288.39 | 390.06 | 152144.48 | 16.40 | 63.00 | 163.00 | 350.50 | 723.80 | 1038.10 | 2.98 |
| Lab results / inpatient day | 275 | 37.21 | 27.36 | 748.39 | 7.04 | 21.19 | 33.23 | 48.44 | 67.21 | 76.92 | 1.88 |
| Charlson score | 275 | 2.77 | 2.20 | 4.83 | 0.00 | 1.00 | 2.00 | 4.00 | 6.00 | 6.30 | 0.58 |

All distributions are right-skewed (skew > 0), so medians and percentiles are the headline statistics and means are secondary.

## 2. Key rates with 95% confidence intervals

| Metric | Wilson interval (independent obs.) | Patient-cluster bootstrap |
|---|---|---|
| 30-day readmission | 20.4% (95% CI 15.9-25.8%) | 20.4% (95% CI 14.1-26.1%) |
| In-hospital mortality | 5.5% (95% CI 3.3-8.8%) | — |
| Admissions with ICU care | 46.5% (95% CI 40.7-52.4%) | — |
| ICU mortality (per stay) | 8.6% (95% CI 5.0-14.4%) | — |
| Median hospital LOS (days) | — | 4.85 (95% CI 4.21-5.71) |

The cluster bootstrap interval for readmission is wider than the Wilson interval. That is expected: frequent patients' readmissions are correlated, so the effective sample size is smaller than the number of discharges.

## 3. Readmission sensitivity analysis

| Definition | Rate |
|---|---|
| Primary: all eligible index discharges | 20.4% (95% CI 15.9-25.8%) |
| Exclude observation-status index encounters | 23.7% (95% CI 18.0-30.6%) |
| First eligible discharge per patient only (removes clustering) | 15.8% (95% CI 9.8-24.4%) |

If the rate moves materially between definitions, the headline figure depends on methodological choices and should always be quoted with its definition.

## 4. Cohort comparisons

### Continuous outcomes (LOS, days)

| Comparison | n (A / B) | Median A | Median B | Median diff (cluster-bootstrap CI) | Cliff's δ (magnitude) | Mann-Whitney p* |
|---|---|---:|---:|---|---|---:|
| Emergency vs Elective | 119 / 31 | 5.55 | 5.66 | -0.12 (-1.72 to 1.03) | -0.04 (negligible) | 0.738 |
| ICU vs no ICU | 128 / 147 | 6.92 | 3.26 | 3.66 (2.23 to 4.92) | 0.48 (large) | <0.001 |

### Binary outcomes

| Comparison | Rate A | Rate B | Risk difference (Newcombe CI*) | RD patient-cluster bootstrap CI | Risk ratio (CI*) | Fisher p* |
|---|---|---|---|---|---|---:|
| 30-day readmission: Charlson 5+ vs 0-4 | 14/55 (25.5%) | 38/200 (19.0%) | 6.5 pts (-4.9 to 20.2) | -11.7 to 20.7 pts | 1.34 (0.78-2.29) | 0.344 |
| In-hospital mortality: male vs female | 12/142 (8.5%) | 3/133 (2.3%) | 6.2 pts (0.7 to 12.1) | 0.9 to 12.4 pts | 3.75 (1.08-12.98) | 0.032 |

\* Assumes independent observations; optimistic under patient clustering.

## 5. Correlation analysis (Spearman, patient-cluster bootstrap CI)

| X | Y | n | ρ | 95% CI |
|---|---|---:|---:|---|
| charlson_comorbidity_score | los_days | 275 | 0.17 | 0.06 to 0.31 |
| n_unit_changes | los_days | 275 | 0.43 | 0.32 to 0.55 |
| charlson_comorbidity_score | n_lab_events | 275 | 0.29 | 0.18 to 0.40 |

Spearman's rank correlation is used because the variables are skewed and the relationships need not be linear. Charlson is coded at discharge, so its correlation with LOS and lab volume is partly reverse-causal: longer, more intensive stays document more conditions.

## Assumptions and limitations

1. Wilson and Newcombe intervals assume independent Bernoulli trials; the cluster bootstrap relaxes this by resampling patients.
2. Percentile bootstrap intervals with ~100 clusters can under-cover slightly; they are a reasonable, transparent choice for a descriptive analysis.
3. No multiple-comparison correction is applied. The comparisons were chosen in advance as illustrative, not as a search for significance.
4. Nothing here supports causal or clinical-treatment conclusions.
