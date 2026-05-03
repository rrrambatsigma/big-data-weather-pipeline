from pathlib import Path

import geopandas as gpd
import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[2]

GEOJSON_PATH = BASE_DIR / "data" / "metadata" / "38 Provinsi Indonesia - Provinsi.json"
OUTPUT_CSV_PATH = BASE_DIR / "data" / "metadata" / "province_coordinates.csv"


def normalize_province_name(name: str) -> str:
    name = str(name).strip()

    mapping = {
        "ACEH": "Aceh",
        "SUMATERA UTARA": "Sumatera Utara",
        "SUMATERA BARAT": "Sumatera Barat",
        "RIAU": "Riau",
        "JAMBI": "Jambi",
        "SUMATERA SELATAN": "Sumatera Selatan",
        "BENGKULU": "Bengkulu",
        "LAMPUNG": "Lampung",
        "KEPULAUAN BANGKA BELITUNG": "Kepulauan Bangka Belitung",
        "KEPULAUAN RIAU": "Kepulauan Riau",
        "DKI JAKARTA": "DKI Jakarta",
        "JAWA BARAT": "Jawa Barat",
        "JAWA TENGAH": "Jawa Tengah",
        "DI YOGYAKARTA": "DI Yogyakarta",
        "DAERAH ISTIMEWA YOGYAKARTA": "DI Yogyakarta",
        "JAWA TIMUR": "Jawa Timur",
        "BANTEN": "Banten",
        "BALI": "Bali",
        "NUSA TENGGARA BARAT": "Nusa Tenggara Barat",
        "NUSA TENGGARA TIMUR": "Nusa Tenggara Timur",
        "KALIMANTAN BARAT": "Kalimantan Barat",
        "KALIMANTAN TENGAH": "Kalimantan Tengah",
        "KALIMANTAN SELATAN": "Kalimantan Selatan",
        "KALIMANTAN TIMUR": "Kalimantan Timur",
        "KALIMANTAN UTARA": "Kalimantan Utara",
        "SULAWESI UTARA": "Sulawesi Utara",
        "SULAWESI TENGAH": "Sulawesi Tengah",
        "SULAWESI SELATAN": "Sulawesi Selatan",
        "SULAWESI TENGGARA": "Sulawesi Tenggara",
        "GORONTALO": "Gorontalo",
        "SULAWESI BARAT": "Sulawesi Barat",
        "MALUKU": "Maluku",
        "MALUKU UTARA": "Maluku Utara",
        "PAPUA": "Papua",
        "PAPUA BARAT": "Papua Barat",
        "PAPUA SELATAN": "Papua Selatan",
        "PAPUA TENGAH": "Papua Tengah",
        "PAPUA PEGUNUNGAN": "Papua Pegunungan",
        "PAPUA BARAT DAYA": "Papua Barat Daya",
    }

    upper_name = name.upper()
    return mapping.get(upper_name, name.title())


def main():
    if not GEOJSON_PATH.exists():
        raise FileNotFoundError(f"File GeoJSON tidak ditemukan: {GEOJSON_PATH}")

    print(f"Membaca GeoJSON: {GEOJSON_PATH}")

    gdf = gpd.read_file(GEOJSON_PATH)

    if "PROVINSI" not in gdf.columns:
        raise ValueError(f"Kolom PROVINSI tidak ditemukan. Kolom tersedia: {list(gdf.columns)}")

    if gdf.crs is None:
        gdf = gdf.set_crs(epsg=4326)

    gdf_projected = gdf.to_crs(epsg=3857)
    centroid_geometry = gdf_projected.geometry.centroid

    centroid_gdf = gpd.GeoDataFrame(
        gdf[["PROVINSI"]].copy(),
        geometry=centroid_geometry,
        crs=gdf_projected.crs,
    ).to_crs(epsg=4326)

    result = pd.DataFrame({
        "province": centroid_gdf["PROVINSI"].apply(normalize_province_name),
        "latitude": centroid_gdf.geometry.y,
        "longitude": centroid_gdf.geometry.x,
    })

    result = result.drop_duplicates(subset=["province"])
    result = result.sort_values("province")

    OUTPUT_CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(OUTPUT_CSV_PATH, index=False)

    print(f"Berhasil membuat CSV: {OUTPUT_CSV_PATH}")
    print(result)
    print(f"Total provinsi: {len(result)}")


if __name__ == "__main__":
    main()