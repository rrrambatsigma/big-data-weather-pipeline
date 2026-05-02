from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]

CANDIDATES_PATH = BASE_DIR / "data" / "metadata" / "plan_b_location_candidates.csv"
CORRECTIONS_PATH = BASE_DIR / "data" / "metadata" / "plan_b_geocoding_query_corrections.csv"
OUTPUT_PATH = BASE_DIR / "data" / "metadata" / "plan_b_location_candidates_fixed.csv"


def main():
    candidates = pd.read_csv(CANDIDATES_PATH)
    corrections = pd.read_csv(CORRECTIONS_PATH)

    required_candidate_cols = ["province", "city_regency", "geocoding_query"]
    required_correction_cols = [
        "province",
        "city_regency",
        "old_geocoding_query",
        "new_geocoding_query",
        "correction_note",
    ]

    for col in required_candidate_cols:
        if col not in candidates.columns:
            raise ValueError(f"Kolom {col} tidak ditemukan di candidates.")

    for col in required_correction_cols:
        if col not in corrections.columns:
            raise ValueError(f"Kolom {col} tidak ditemukan di corrections.")

    fixed = candidates.merge(
        corrections[
            [
                "province",
                "city_regency",
                "new_geocoding_query",
                "correction_note",
            ]
        ],
        on=["province", "city_regency"],
        how="left",
    )

    fixed["geocoding_query_original"] = fixed["geocoding_query"]

    fixed["geocoding_query"] = fixed["new_geocoding_query"].combine_first(
        fixed["geocoding_query"]
    )

    fixed["geocoding_correction_note"] = fixed["correction_note"].fillna("")

    fixed = fixed.drop(columns=["new_geocoding_query", "correction_note"])

    fixed.to_csv(OUTPUT_PATH, index=False)

    print("File candidates fixed berhasil dibuat:")
    print(OUTPUT_PATH)

    print("\nLokasi yang dikoreksi:")
    corrected = fixed[fixed["geocoding_correction_note"] != ""]
    print(
        corrected[
            [
                "province",
                "city_regency",
                "geocoding_query_original",
                "geocoding_query",
                "geocoding_correction_note",
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()