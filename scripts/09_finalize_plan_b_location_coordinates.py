from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]

AUTO_PATH = BASE_DIR / "data" / "metadata" / "plan_b_location_coordinates.csv"
MANUAL_PATH = BASE_DIR / "data" / "metadata" / "plan_b_manual_coordinate_corrections.csv"
OUTPUT_PATH = BASE_DIR / "data" / "metadata" / "plan_b_location_coordinates_final.csv"

VALIDATION_ISSUES_PATH = BASE_DIR / "data" / "metadata" / "plan_b_location_final_validation_issues.csv"

KEY_COLUMNS = ["province", "city_regency"]


def validate_file_exists(path: Path, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"{label} tidak ditemukan: {path}")

    if path.stat().st_size == 0:
        raise ValueError(f"{label} ada, tapi file kosong: {path}")


def main():
    print("Membaca file auto geocoding:")
    print(AUTO_PATH)

    validate_file_exists(AUTO_PATH, "File auto geocoding")

    auto_df = pd.read_csv(AUTO_PATH)

    print(f"Auto geocoding rows: {len(auto_df)}")

    if MANUAL_PATH.exists() and MANUAL_PATH.stat().st_size > 0:
        print("\nMembaca file manual correction:")
        print(MANUAL_PATH)
        manual_df = pd.read_csv(MANUAL_PATH)
    else:
        print("\nWARNING: File manual correction belum ada / masih kosong.")
        print("Finalize tetap bisa jalan, tapi lokasi gagal tidak akan masuk.")
        manual_df = pd.DataFrame(columns=auto_df.columns)

    print(f"Manual correction rows: {len(manual_df)}")

    required_columns = [
        "province",
        "city_regency",
        "selection_basis",
        "selection_method",
        "geocoding_query",
        "matched_name",
        "latitude",
        "longitude",
        "elevation",
        "country_code",
        "country",
        "admin1",
        "admin2",
        "admin3",
        "timezone",
        "population",
        "source",
    ]

    for col in required_columns:
        if col not in auto_df.columns:
            auto_df[col] = None

        if col not in manual_df.columns:
            manual_df[col] = None

    auto_df = auto_df[required_columns].copy()
    manual_df = manual_df[required_columns].copy()

    # Buang hasil auto yang bukan Indonesia
    non_id = auto_df[auto_df["country_code"] != "ID"]

    if not non_id.empty:
        print("\nHasil auto non-ID akan dibuang:")
        print(
            non_id[
                [
                    "province",
                    "city_regency",
                    "geocoding_query",
                    "matched_name",
                    "country_code",
                    "country",
                ]
            ].to_string(index=False)
        )

    auto_clean = auto_df[auto_df["country_code"] == "ID"].copy()

    # Kalau lokasi ada di manual correction, manual correction menggantikan hasil auto
    if not manual_df.empty:
        manual_keys = manual_df[KEY_COLUMNS].drop_duplicates()

        auto_clean = auto_clean.merge(
            manual_keys.assign(_manual_flag=1),
            on=KEY_COLUMNS,
            how="left",
        )

        auto_clean = auto_clean[auto_clean["_manual_flag"].isna()].drop(
            columns=["_manual_flag"]
        )

    final_df = pd.concat([auto_clean, manual_df], ignore_index=True)

    final_df = final_df.drop_duplicates(subset=KEY_COLUMNS, keep="last")

    final_df = final_df.sort_values(["province", "city_regency"]).reset_index(drop=True)

    issues = []

    missing_latlon = final_df[
        final_df["latitude"].isna() | final_df["longitude"].isna()
    ]

    if not missing_latlon.empty:
        temp = missing_latlon.copy()
        temp["issue"] = "missing_latitude_or_longitude"
        issues.append(temp)

    non_id_final = final_df[final_df["country_code"] != "ID"]

    if not non_id_final.empty:
        temp = non_id_final.copy()
        temp["issue"] = "country_code_not_ID"
        issues.append(temp)

    duplicated = final_df[final_df.duplicated(subset=KEY_COLUMNS, keep=False)]

    if not duplicated.empty:
        temp = duplicated.copy()
        temp["issue"] = "duplicated_province_city"
        issues.append(temp)

    final_df.to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")

    print("\nFinal coordinates disimpan di:")
    print(OUTPUT_PATH)

    print("\nFinal rows:", len(final_df))

    print("\nJumlah lokasi final per provinsi:")
    print(final_df.groupby("province")["city_regency"].nunique().to_string())

    print("\nValidasi:")
    print("Non-ID:", len(final_df[final_df["country_code"] != "ID"]))
    print(
        "Missing lat/lon:",
        final_df[["latitude", "longitude"]].isna().any(axis=1).sum(),
    )

    if issues:
        issue_df = pd.concat(issues, ignore_index=True)
        issue_df.to_csv(VALIDATION_ISSUES_PATH, index=False, encoding="utf-8-sig")

        print("\nWARNING: Ada issue validasi final.")
        print(VALIDATION_ISSUES_PATH)
    else:
        print("\nValidasi final aman.")


if __name__ == "__main__":
    main()