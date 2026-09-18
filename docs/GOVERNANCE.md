# Medicare Claims Analytics Platform — Data Governance (Portfolio Stage)

## Principles

Only CMS's public, fully synthetic DE-SynPUF data may enter this repository
or any pipeline it defines — no real Medicare claims, no real PHI/PII, ever,
in dev, test, or a future "prod" demo environment.

## Source data

- **Dataset:** CMS DE-SynPUF ("Data Entrepreneurs' Synthetic Public Use
  File"), 2008 Beneficiary Summary File, Sample 1
  (`DE1_0_2008_Beneficiary_Summary_File_Sample_1.csv`), 116,352 records.
- **Provenance:** published by the Centers for Medicare & Medicaid Services
  specifically so developers can build against realistic Medicare data
  structures with zero re-identification risk. CMS generated it via
  statistical perturbation of real claims — it does not correspond to real
  beneficiaries. See CMS's DE-SynPUF documentation for the methodology.
- **Attribution:** any published dashboard, README, or write-up derived from
  this data must credit "CMS DE-SynPUF" and note it is synthetic, not real
  patient data — this matters for interview credibility as much as for
  compliance.
- **Extension:** CMS also publishes matching Inpatient Claims, Outpatient
  Claims, Carrier Claims, and Prescription Drug Event (PDE) synthetic files
  for the same beneficiary IDs. Only the Beneficiary Summary file is in
  scope until a human explicitly adds one of these (see
  `docs/IMPLEMENTATION_SPEC.md` §35).

## Handling in this repository

- Raw CSVs live under `data/raw/`, which is `.gitignore`d — never commit the
  full file. A small fixture sample (a few hundred rows) may be committed
  under `data/samples/` for tests.
- Treat the data with the same handling discipline as real PII would require
  (least-privilege cloud IAM, no public buckets, no secrets in logs) even
  though CMS has already cleared it for public use — this is deliberate
  practice for real-world data-engineering hygiene, not a compliance
  requirement for this specific dataset.
- No service-account keys, Databricks personal access tokens, BigQuery
  credentials, or `.pbix` files with embedded connection credentials are
  committed. Use `.env` (gitignored) and `.env.example` (committed, no real
  values).

## Model improvement / analytics use

N/A — this project has no AI/ML component in its core scope. If the optional
cost-prediction stretch goal (§35) is ever built, any model is trained only
on this synthetic dataset and is never presented as predicting real patient
risk.

## Development data

Development, testing, and demo environments use only the CMS DE-SynPUF
files (or the committed synthetic fixture sample). Never substitute real
Medicare data, scraped healthcare data, or invented "realistic" PII to fill
gaps.
