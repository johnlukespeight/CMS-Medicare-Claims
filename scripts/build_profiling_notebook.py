"""One-off script that (re)generates notebooks/00_data_profiling.ipynb.

Run this only if the notebook's structure needs to change. The notebook
itself is executed separately (`make profile`) so its committed outputs
reflect a real run against the full raw file.
"""

from pathlib import Path

import nbformat as nbf

NOTEBOOK_PATH = Path(__file__).resolve().parent.parent / "notebooks" / "00_data_profiling.ipynb"

nb = nbf.v4.new_notebook()
cells = []


def md(text: str) -> None:
    cells.append(nbf.v4.new_markdown_cell(text))


def code(text: str) -> None:
    cells.append(nbf.v4.new_code_cell(text))


md(
    "# 00 — Beneficiary Summary Data Profiling\n\n"
    "Profiles the raw CMS DE-SynPUF 2008 Beneficiary Summary File (Sample 1) "
    "to confirm the assumptions `docs/IMPLEMENTATION_SPEC.md` makes in "
    "sections 7-8 before any transformation code is written: chronic-condition "
    "flag encoding, death-date null rate, and value ranges for demographics "
    "and reimbursement fields."
)

code(
    "from pathlib import Path\n"
    "\n"
    "import pandas as pd\n"
    "\n"
    "RAW_PATH = Path.cwd().parent / \"data\" / \"raw\" / \"DE1_0_2008_Beneficiary_Summary_File_Sample_1.csv\"\n"
    "\n"
    "df = pd.read_csv(RAW_PATH, dtype=str)\n"
    "df.shape"
)

md("## 1. Shape and dtypes\n\nAll columns load as strings — typing happens in the silver/staging layer, not here.")
code("df.dtypes")

md(
    "## 2. Null counts per column\n\n"
    "`BENE_DEATH_DT` is expected to be null for the large majority of rows "
    "(beneficiaries alive at end of 2008) — confirms spec section 8's rule "
    "that blank means `is_deceased = false`, not missing data."
)
code(
    "null_counts = df.isna().sum().sort_values(ascending=False)\n"
    "null_counts[null_counts > 0]"
)
code(
    "death_null_rate = df[\"BENE_DEATH_DT\"].isna().mean()\n"
    "print(f\"BENE_DEATH_DT null rate: {death_null_rate:.2%}\")"
)

md("## 3. Demographic code distributions")
code("df[\"BENE_SEX_IDENT_CD\"].value_counts()")
code("df[\"BENE_RACE_CD\"].value_counts()")
code("df[\"BENE_ESRD_IND\"].value_counts()")
code(
    "print(f\"Distinct SP_STATE_CODE values: {df['SP_STATE_CODE'].nunique()}\")\n"
    "df[\"SP_STATE_CODE\"].value_counts().head(10)"
)

md(
    "## 4. Chronic-condition flag encoding\n\n"
    "Confirms every `SP_*` condition column takes only the values `{1, 2}` "
    "(CMS codebook: `1 = Yes`, `2 = No`) with no unexpected codes, per spec "
    "section 8."
)
code(
    "condition_cols = [\n"
    "    \"SP_ALZHDMTA\", \"SP_CHF\", \"SP_CHRNKIDN\", \"SP_CNCR\", \"SP_COPD\",\n"
    "    \"SP_DEPRESSN\", \"SP_DIABETES\", \"SP_ISCHMCHT\", \"SP_OSTEOPRS\",\n"
    "    \"SP_RA_OA\", \"SP_STRKETIA\",\n"
    "]\n"
    "\n"
    "for col in condition_cols:\n"
    "    values = sorted(df[col].dropna().unique())\n"
    "    print(f\"{col}: {values}\")"
)
code(
    "prevalence = pd.Series(\n"
    "    {col: (df[col] == \"1\").mean() for col in condition_cols}\n"
    ").sort_values(ascending=False)\n"
    "prevalence.map(lambda x: f\"{x:.1%}\")"
)
code(
    "chronic_condition_count = (df[condition_cols] == \"1\").sum(axis=1)\n"
    "chronic_condition_count.describe()"
)

md("## 5. Coverage-month fields")
code(
    "coverage_cols = [\n"
    "    \"BENE_HI_CVRAGE_TOT_MONS\", \"BENE_SMI_CVRAGE_TOT_MONS\",\n"
    "    \"BENE_HMO_CVRAGE_TOT_MONS\", \"PLAN_CVRG_MOS_NUM\",\n"
    "]\n"
    "df[coverage_cols].astype(int).describe()"
)

md(
    "## 6. Reimbursement fields\n\n"
    "Confirms these are non-negative and checks the scale of inpatient vs. "
    "outpatient vs. carrier amounts, informing the `total_cost` definition "
    "in spec section 14."
)
code(
    "cost_cols = [\n"
    "    \"MEDREIMB_IP\", \"BENRES_IP\", \"PPPYMT_IP\",\n"
    "    \"MEDREIMB_OP\", \"BENRES_OP\", \"PPPYMT_OP\",\n"
    "    \"MEDREIMB_CAR\", \"BENRES_CAR\", \"PPPYMT_CAR\",\n"
    "]\n"
    "df[cost_cols] = df[cost_cols].astype(float)\n"
    "df[cost_cols].describe().T"
)
md(
    "**Negative values found** — do not assume reimbursement fields are "
    "non-negative. Some rows carry negative `MEDREIMB_IP`/`MEDREIMB_OP` "
    "(claim adjustments/reversals are a known feature of CMS reimbursement "
    "data). This must be preserved, not filtered out or clipped to zero, by "
    "the silver/staging aggregation logic in spec section 14 — treat as a "
    "real data characteristic, not a data-quality defect."
)
code(
    "for col in cost_cols:\n"
    "    negative_count = (df[col] < 0).sum()\n"
    "    if negative_count:\n"
    "        print(f\"{col}: {negative_count} negative rows, min={df[col].min()}\")"
)
code(
    "total_cost = df[\"MEDREIMB_IP\"] + df[\"MEDREIMB_OP\"] + df[\"MEDREIMB_CAR\"]\n"
    "print(f\"Beneficiaries with $0 total Medicare-paid cost: {(total_cost == 0).mean():.1%}\")\n"
    "print(f\"Beneficiaries with negative total Medicare-paid cost: {(total_cost < 0).sum()}\")\n"
    "total_cost.describe()"
)

md(
    "## 7. Age computation sanity check\n\n"
    "Ages beneficiaries as of 2008-12-31 (the file's reference year, per "
    "spec section 14) and checks the distribution falls in a plausible "
    "Medicare-population range."
)
code(
    "birth_date = pd.to_datetime(df[\"BENE_BIRTH_DT\"], format=\"%Y%m%d\")\n"
    "reference_date = pd.Timestamp(\"2008-12-31\")\n"
    "age_2008 = (reference_date - birth_date).dt.days // 365\n"
    "age_2008.describe()"
)
code(
    "under_65 = (age_2008 < 65).mean()\n"
    "print(f\"Share of beneficiaries under 65 at end of 2008 (ESRD/disability-based enrollees): {under_65:.1%}\")"
)

md(
    "## 8. Findings summary\n\n"
    "- `BENE_DEATH_DT` is null for the vast majority of rows — treat blank as "
    "`is_deceased = false`, confirmed.\n"
    "- All 11 `SP_*` condition columns take only `{1, 2}` — the `1=Yes`/`2=No` "
    "decoding rule in spec section 8 is confirmed against the real file, not "
    "assumed.\n"
    "- Reimbursement fields are **not** guaranteed non-negative — a small "
    "number of `MEDREIMB_IP`/`MEDREIMB_OP` rows are negative (claim "
    "adjustments), and a non-trivial share of beneficiaries have $0 total "
    "Medicare-paid cost in 2008. The silver/staging layer must preserve "
    "both, not clip or drop them as errors.\n"
    "- A meaningful share of beneficiaries are under 65, consistent with "
    "ESRD/disability-based Medicare eligibility — the age-band logic in spec "
    "section 14 needs an under-65 band, not just the standard 65+ bands."
)

nb["cells"] = cells
NOTEBOOK_PATH.parent.mkdir(parents=True, exist_ok=True)
nbf.write(nb, NOTEBOOK_PATH)
print(f"Wrote {NOTEBOOK_PATH}")
