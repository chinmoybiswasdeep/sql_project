# Data

Nothing in this directory is committed. `data/raw/` and `data/full/` are git-ignored.

## Demo mode (default, open access)

```bash
python -m ingestion.download_demo        # -> data/raw/{hosp,icu}/*.csv.gz
```

Source: [MIMIC-IV Clinical Database Demo v2.2](https://physionet.org/content/mimic-iv-demo/2.2/)
(100 patients, ODbL licence). Each file is verified against PhysioNet's published
`SHA256SUMS.txt`, and a mismatch aborts the download.

## Full mode (credentialed MIMIC-IV v3.1)

The full dataset requires:

1. A [PhysioNet](https://physionet.org) account with **credentialed** status.
2. Completion of the CITI "Data or Specimens Only Research" training.
3. Signing the PhysioNet Credentialed Health Data Use Agreement for
   [MIMIC-IV](https://physionet.org/content/mimiciv/3.1/).

Then download only the tables this project uses (see `config/sources.yaml`) into
`data/full/mimiciv/3.1/{hosp,icu}/` and run:

```bash
HI_DATASET_MODE=full python -m ingestion.pipelines.run_ingestion --skip-optional
```

`--skip-optional` skips `chartevents` (several hundred million rows), which only the
benchmarks use.

**The data use agreement prohibits sharing the data.** Never commit raw files, exports
(`powerbi/datasets/`), query result snapshots (`reports/sql_results/`) or any derived
patient-level table. `tests/test_privacy.py` checks that these paths are ignored.
