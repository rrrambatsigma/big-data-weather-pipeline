import time
from pathlib import Path

import pandas as pd
import requests
from tqdm import tqdm


BASE_DIR = Path(__file__).resolve().parents[1]

INPUT_PATH = BASE_DIR / "data" / "metadata" / "plan_b_location_candidates_fixed.csv"
OUTPUT_PATH = BASE_DIR / "data" / "metadata" / "plan_b_location_coordinates.csv"
FAILED_PATH = BASE_DIR / "data" / "metadata" / "plan_b_location_geocoding_failed.csv"

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"

REQUIRED_COLUMNS = [
    "province",
    "city_regency",
    "selection_basis",
    "geocoding_query",
    "selection_method",
]


def validate_input(df: pd.DataFrame) -> None:
    missing_columns = [col for col in REQUIRED_COLUMNS if col not in df.columns]

    if missing_columns:
        raise ValueError(f"Kolom wajib tidak ditemukan: {missing_columns}")

    if df.empty:
        raise ValueError("File plan_b_location_candidates.csv kosong.")

    duplicated = df[df.duplicated(subset=["province", "city_regency"], keep=False)]

    if not duplicated.empty:
        print("\nWARNING: Ada duplikasi province-city_regency:")
        print(duplicated[["province", "city_regency"]].to_string(index=False))

    print("\nJumlah lokasi per provinsi pada input:")
    print(df.groupby("province")["city_regency"].nunique().to_string())

    print(f"\nTotal kandidat lokasi: {len(df)}")


def normalize_query(query: str) -> str:
    return str(query).strip()


def search_location(query: str, max_retries: int = 5) -> dict | None:
    params = {
        "name": query,
        "count": 10,
        "language": "en",
        "format": "json",
    }

    last_error = None

    for attempt in range(1, max_retries + 1):
        try:
            response = requests.get(
                GEOCODING_URL,
                params=params,
                timeout=60,
            )
            response.raise_for_status()

            data = response.json()
            results = data.get("results", [])

            if not results:
                return None

            indonesia_results = [
                item for item in results
                if item.get("country_code") == "ID"
            ]

            if indonesia_results:
                return indonesia_results[0]

            return results[0]

        except requests.exceptions.RequestException as error:
            last_error = error
            wait_time = attempt * 5

            print(f"  Retry {attempt}/{max_retries} gagal: {error}")
            print(f"  Tunggu {wait_time} detik...")
            time.sleep(wait_time)

    raise RuntimeError(f"Gagal request geocoding. Error terakhir: {last_error}")


def build_result_row(row: pd.Series, result: dict) -> dict:
    return {
        "province": row["province"],
        "city_regency": row["city_regency"],
        "selection_basis": row["selection_basis"],
        "selection_method": row["selection_method"],
        "geocoding_query": row["geocoding_query"],
        "matched_name": result.get("name"),
        "latitude": result.get("latitude"),
        "longitude": result.get("longitude"),
        "elevation": result.get("elevation"),
        "country_code": result.get("country_code"),
        "country": result.get("country"),
        "admin1": result.get("admin1"),
        "admin2": result.get("admin2"),
        "admin3": result.get("admin3"),
        "timezone": result.get("timezone"),
        "population": result.get("population"),
        "source": "Open-Meteo Geocoding API",
    }


def validate_output(success_df: pd.DataFrame, failed_df: pd.DataFrame | None) -> None:
    print("\nValidasi hasil geocoding Plan B:")

    print(f"Total berhasil: {len(success_df)}")

    if failed_df is not None and not failed_df.empty:
        print(f"Total gagal: {len(failed_df)}")
    else:
        print("Total gagal: 0")

    print("\nJumlah lokasi berhasil per provinsi:")
    print(success_df.groupby("province")["city_regency"].nunique().to_string())

    non_indonesia = success_df[success_df["country_code"] != "ID"]

    if not non_indonesia.empty:
        print("\nWARNING: Ada hasil geocoding bukan Indonesia:")
        print(
            non_indonesia[
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

    missing_coordinate = success_df[
        success_df["latitude"].isna() | success_df["longitude"].isna()
    ]

    if not missing_coordinate.empty:
        print("\nWARNING: Ada latitude/longitude kosong:")
        print(
            missing_coordinate[
                ["province", "city_regency", "geocoding_query", "matched_name"]
            ].to_string(index=False)
        )

    print("\nPreview hasil geocoding:")
    print(
        success_df[
            [
                "province",
                "city_regency",
                "geocoding_query",
                "matched_name",
                "latitude",
                "longitude",
                "admin1",
                "admin2",
                "timezone",
            ]
        ].head(20).to_string(index=False)
    )


def main():
    print("Membaca metadata kandidat Plan B:")
    print(INPUT_PATH)

    locations = pd.read_csv(INPUT_PATH)

    validate_input(locations)

    success_rows = []
    failed_rows = []

    for _, row in tqdm(
        locations.iterrows(),
        total=len(locations),
        desc="Geocoding Plan B",
    ):
        province = row["province"]
        city_regency = row["city_regency"]
        query = normalize_query(row["geocoding_query"])

        print(f"\nSearching: {province} - {city_regency} using query '{query}'")

        try:
            result = search_location(query)

            if result is None:
                failed_rows.append({
                    "province": province,
                    "city_regency": city_regency,
                    "selection_basis": row["selection_basis"],
                    "selection_method": row["selection_method"],
                    "geocoding_query": query,
                    "reason": "No result from Open-Meteo Geocoding API",
                })

                print(f"  FAILED: {province} - {city_regency}")
                continue

            result_row = build_result_row(row, result)
            success_rows.append(result_row)

            print(
                f"  OK: {result_row['matched_name']} "
                f"({result_row['latitude']}, {result_row['longitude']}) "
                f"| {result_row['admin1']} | {result_row['admin2']}"
            )

            time.sleep(1)

        except Exception as error:
            failed_rows.append({
                "province": province,
                "city_regency": city_regency,
                "selection_basis": row["selection_basis"],
                "selection_method": row["selection_method"],
                "geocoding_query": query,
                "reason": str(error),
            })

            print(f"  FAILED: {province} - {city_regency} | {error}")

    success_df = pd.DataFrame(success_rows)
    failed_df = pd.DataFrame(failed_rows)

    if success_df.empty:
        raise RuntimeError("Tidak ada lokasi yang berhasil digeocoding.")

    success_df.to_csv(OUTPUT_PATH, index=False)

    if not failed_df.empty:
        failed_df.to_csv(FAILED_PATH, index=False)

    print("\nGeocoding Plan B selesai.")
    print(f"Output berhasil disimpan di: {OUTPUT_PATH}")

    if not failed_df.empty:
        print(f"Data gagal disimpan di: {FAILED_PATH}")

    validate_output(success_df, failed_df)


if __name__ == "__main__":
    main()