import time
from pathlib import Path

import pandas as pd
import requests


BASE_DIR = Path(__file__).resolve().parents[1]

INPUT_PATH = BASE_DIR / "data" / "metadata" / "location_candidates.csv"
OUTPUT_PATH = BASE_DIR / "data" / "metadata" / "location_coordinates.csv"

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"


def search_location(query: str, count: int = 10) -> list:
    """
    Mengirim request ke Open-Meteo Geocoding API.
    Mengembalikan list kandidat lokasi.
    """
    params = {
        "name": query,
        "count": count,
        "language": "en",
        "format": "json",
    }

    response = requests.get(GEOCODING_URL, params=params, timeout=30)
    response.raise_for_status()

    data = response.json()
    return data.get("results", [])


def choose_best_match(results: list, expected_admin1: str) -> dict | None:
    """
    Memilih kandidat lokasi yang:
    1. country_code = ID
    2. admin1 sesuai provinsi target
    """
    for item in results:
        country_code = item.get("country_code")
        admin1 = item.get("admin1")

        if country_code == "ID" and admin1 == expected_admin1:
            return item

    return None


def main():
    locations = pd.read_csv(INPUT_PATH)

    final_rows = []
    failed_rows = []

    for _, row in locations.iterrows():
        province = row["province"]
        city_regency = row["city_regency"]
        selection_basis = row["selection_basis"]
        geocoding_query = row["geocoding_query"]
        expected_admin1 = row["expected_admin1"]

        print(f"Searching: {city_regency} using query '{geocoding_query}'")

        try:
            results = search_location(geocoding_query)
            best_match = choose_best_match(results, expected_admin1)

            if best_match is None:
                failed_rows.append({
                    "province": province,
                    "city_regency": city_regency,
                    "geocoding_query": geocoding_query,
                    "expected_admin1": expected_admin1,
                    "reason": "No matching result with country_code=ID and expected admin1",
                })
                print(f"  FAILED: {city_regency}")
                continue

            final_rows.append({
                "province": province,
                "city_regency": city_regency,
                "selection_basis": selection_basis,
                "geocoding_query": geocoding_query,
                "matched_name": best_match.get("name"),
                "latitude": best_match.get("latitude"),
                "longitude": best_match.get("longitude"),
                "elevation": best_match.get("elevation"),
                "country_code": best_match.get("country_code"),
                "country": best_match.get("country"),
                "admin1": best_match.get("admin1"),
                "admin2": best_match.get("admin2"),
                "admin3": best_match.get("admin3"),
                "timezone": best_match.get("timezone"),
                "population": best_match.get("population"),
                "source": "Open-Meteo Geocoding API",
            })

            print(
                f"  OK: {best_match.get('name')} "
                f"({best_match.get('latitude')}, {best_match.get('longitude')})"
            )

            time.sleep(0.5)

        except Exception as error:
            failed_rows.append({
                "province": province,
                "city_regency": city_regency,
                "geocoding_query": geocoding_query,
                "expected_admin1": expected_admin1,
                "reason": str(error),
            })
            print(f"  ERROR: {city_regency} - {error}")

    result_df = pd.DataFrame(final_rows)
    result_df.to_csv(OUTPUT_PATH, index=False)

    print("\nGeocoding selesai.")
    print(f"Total berhasil: {len(final_rows)}")
    print(f"Total gagal: {len(failed_rows)}")
    print(f"Output disimpan di: {OUTPUT_PATH}")

    if failed_rows:
        failed_path = BASE_DIR / "data" / "metadata" / "location_geocoding_failed.csv"
        failed_df = pd.DataFrame(failed_rows)
        failed_df.to_csv(failed_path, index=False)
        print(f"Data gagal disimpan di: {failed_path}")


if __name__ == "__main__":
    main()