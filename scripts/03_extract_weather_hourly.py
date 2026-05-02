import time
from pathlib import Path

import pandas as pd
import requests
from tqdm import tqdm


BASE_DIR = Path(__file__).resolve().parents[1]

LOCATION_PATH = BASE_DIR / "data" / "metadata" / "location_coordinates.csv"
OUTPUT_DIR = BASE_DIR / "data" / "raw" / "weather"

OUTPUT_PATH = OUTPUT_DIR / "weather_hourly_2020_2024.csv"
FAILED_PATH = OUTPUT_DIR / "weather_hourly_failed_locations.csv"

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

START_DATE = "2020-01-01"
END_DATE = "2024-12-31"

MAIN_WEATHER_VARIABLES = [
    "temperature_2m",
    "relative_humidity_2m",
    "precipitation",
    "rain",
    "et0_fao_evapotranspiration",
]

SOIL_MOISTURE_VARIABLES = [
    "soil_moisture_0_to_7cm",
    "soil_moisture_7_to_28cm",
    "soil_moisture_28_to_100cm",
]

SOIL_MODEL_NAME = "era5_land"


def get_timezone(row: pd.Series) -> str:
    timezone = row.get("timezone", "auto")

    if pd.isna(timezone) or str(timezone).strip() == "":
        return "auto"

    return str(timezone)


def request_open_meteo(params: dict, max_retries: int = 5) -> dict:
    last_error = None

    for attempt in range(1, max_retries + 1):
        try:
            response = requests.get(
                ARCHIVE_URL,
                params=params,
                timeout=180,
            )
            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as error:
            last_error = error
            wait_time = attempt * 5

            print(f"  Retry {attempt}/{max_retries} gagal: {error}")
            print(f"  Menunggu {wait_time} detik sebelum mencoba lagi...")

            time.sleep(wait_time)

    raise RuntimeError(
        f"Gagal request ke Open-Meteo setelah {max_retries} percobaan. "
        f"Error terakhir: {last_error}"
    )


def validate_response(data: dict, data_type: str) -> None:
    if "hourly" not in data:
        raise ValueError(f"Response {data_type} tidak memiliki key 'hourly': {data}")


def fetch_hourly_data(
    row: pd.Series,
    variables: list[str],
    data_type: str,
    model_name: str | None = None,
) -> pd.DataFrame:
    params = {
        "latitude": row["latitude"],
        "longitude": row["longitude"],
        "start_date": START_DATE,
        "end_date": END_DATE,
        "hourly": ",".join(variables),
        "timezone": get_timezone(row),
    }

    if model_name:
        params["models"] = model_name

    data = request_open_meteo(params=params, max_retries=5)
    validate_response(data, data_type=data_type)

    return pd.DataFrame(data["hourly"])


def add_location_columns(weather_df: pd.DataFrame, row: pd.Series) -> pd.DataFrame:
    weather_df.insert(0, "province", row["province"])
    weather_df.insert(1, "city_regency", row["city_regency"])
    weather_df.insert(2, "geocoding_query", row["geocoding_query"])
    weather_df.insert(3, "latitude", row["latitude"])
    weather_df.insert(4, "longitude", row["longitude"])
    weather_df.insert(5, "timezone", get_timezone(row))
    weather_df.insert(6, "source", "Open-Meteo Historical Weather API")

    return weather_df


def check_missing_columns(df: pd.DataFrame, columns: list[str], label: str) -> None:
    total_rows = len(df)

    print(f"\nCek missing value {label}:")
    for col in columns:
        if col in df.columns:
            missing_count = df[col].isna().sum()
            print(f"{col}: {missing_count} missing dari {total_rows} rows")
        else:
            print(f"{col}: kolom tidak ditemukan")


def fetch_weather_for_location(row: pd.Series) -> pd.DataFrame:
    location_name = f"{row['province']} - {row['city_regency']}"

    print(f"  Mengambil weather utama: {location_name}")
    main_df = fetch_hourly_data(
        row=row,
        variables=MAIN_WEATHER_VARIABLES,
        data_type="main weather",
        model_name=None,
    )

    print(f"  Mengambil soil moisture ERA5-Land: {location_name}")
    soil_df = fetch_hourly_data(
        row=row,
        variables=SOIL_MOISTURE_VARIABLES,
        data_type="soil moisture",
        model_name=SOIL_MODEL_NAME,
    )

    if "time" not in main_df.columns:
        raise ValueError(f"Kolom time tidak ditemukan pada main weather: {location_name}")

    if "time" not in soil_df.columns:
        raise ValueError(f"Kolom time tidak ditemukan pada soil moisture: {location_name}")

    merged_df = pd.merge(
        main_df,
        soil_df,
        on="time",
        how="left",
    )

    merged_df = add_location_columns(merged_df, row)

    return merged_df


def validate_location_file(locations: pd.DataFrame) -> None:
    required_columns = [
        "province",
        "city_regency",
        "geocoding_query",
        "latitude",
        "longitude",
        "timezone",
    ]

    missing_columns = [
        col for col in required_columns if col not in locations.columns
    ]

    if missing_columns:
        raise ValueError(f"Kolom wajib tidak ditemukan: {missing_columns}")

    if locations.empty:
        raise ValueError("File location_coordinates.csv kosong.")


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    locations = pd.read_csv(LOCATION_PATH)
    validate_location_file(locations)

    all_weather_data = []
    failed_locations = []

    for _, row in tqdm(
        locations.iterrows(),
        total=len(locations),
        desc="Extract weather",
    ):
        location_name = f"{row['province']} - {row['city_regency']}"

        try:
            print(f"\nProcessing: {location_name}")

            weather_df = fetch_weather_for_location(row)
            all_weather_data.append(weather_df)

            print(f"OK: {location_name} | rows: {len(weather_df)}")

            time.sleep(2)

        except Exception as error:
            failed_locations.append({
                "province": row["province"],
                "city_regency": row["city_regency"],
                "geocoding_query": row.get("geocoding_query"),
                "latitude": row["latitude"],
                "longitude": row["longitude"],
                "timezone": get_timezone(row),
                "reason": str(error),
            })

            print(f"FAILED: {location_name} | {error}")

    if not all_weather_data:
        raise RuntimeError("Tidak ada data cuaca yang berhasil diambil.")

    final_df = pd.concat(all_weather_data, ignore_index=True)

    final_df.to_csv(OUTPUT_PATH, index=False)

    print("\nExtraction selesai.")
    print(f"Total lokasi berhasil: {len(all_weather_data)}")
    print(f"Total lokasi gagal: {len(failed_locations)}")
    print(f"Total rows: {len(final_df)}")
    print(f"Output disimpan di: {OUTPUT_PATH}")

    check_missing_columns(
        final_df,
        MAIN_WEATHER_VARIABLES,
        label="weather utama",
    )

    check_missing_columns(
        final_df,
        SOIL_MOISTURE_VARIABLES,
        label="soil moisture",
    )

    if failed_locations:
        pd.DataFrame(failed_locations).to_csv(FAILED_PATH, index=False)
        print(f"\nData lokasi gagal disimpan di: {FAILED_PATH}")
    else:
        if FAILED_PATH.exists():
            FAILED_PATH.unlink()
        print("\nTidak ada lokasi gagal.")


if __name__ == "__main__":
    main()