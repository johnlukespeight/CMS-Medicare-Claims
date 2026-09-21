"""Generate the committed fixture sample used by unit tests and local dev.

Draws a reproducible, stratified subset of the raw CMS DE-SynPUF Beneficiary
Summary File so tests and local iteration don't require the full 116k-row
file or cloud credentials. Stratifies by state (SP_STATE_CODE) so most states
are represented, and force-includes every deceased beneficiary (non-null
BENE_DEATH_DT) since that's a rare but important edge case for the age/
death-date handling logic in spec section 8.
"""

from pathlib import Path

import pandas as pd

RAW_PATH = Path(__file__).resolve().parent.parent / "data" / "raw" / "DE1_0_2008_Beneficiary_Summary_File_Sample_1.csv"
SAMPLE_PATH = Path(__file__).resolve().parent.parent / "data" / "samples" / "beneficiary_summary_sample.csv"
RANDOM_SEED = 42
PER_STATE_SAMPLE_SIZE = 6
DECEASED_SAMPLE_SIZE = 30


def main() -> None:
    df = pd.read_csv(RAW_PATH, dtype=str)

    all_deceased = df[df["BENE_DEATH_DT"].notna()]
    deceased = all_deceased.sample(n=min(len(all_deceased), DECEASED_SAMPLE_SIZE), random_state=RANDOM_SEED)

    # pandas >=2.2 excludes the grouping column from `apply` by default unless
    # columns are selected explicitly first (df.columns) — otherwise
    # SP_STATE_CODE disappears from the result.
    stratified = df.groupby("SP_STATE_CODE", group_keys=False)[df.columns].apply(
        lambda g: g.sample(n=min(len(g), PER_STATE_SAMPLE_SIZE), random_state=RANDOM_SEED)
    )

    sample = (
        pd.concat([stratified, deceased])
        .drop_duplicates(subset="DESYNPUF_ID")
        .sample(frac=1, random_state=RANDOM_SEED)
        .reset_index(drop=True)
    )

    SAMPLE_PATH.parent.mkdir(parents=True, exist_ok=True)
    sample.to_csv(SAMPLE_PATH, index=False)

    print(f"Source rows:      {len(df):,}")
    print(f"States covered:   {sample['SP_STATE_CODE'].nunique()} / {df['SP_STATE_CODE'].nunique()}")
    print(f"Deceased rows:    {sample['BENE_DEATH_DT'].notna().sum()}")
    print(f"Sample rows:      {len(sample):,}")
    print(f"Written to:       {SAMPLE_PATH}")


if __name__ == "__main__":
    main()
