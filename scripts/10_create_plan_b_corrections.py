from pathlib import Path
import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]

OUTPUT_PATH = BASE_DIR / "data" / "metadata" / "plan_b_geocoding_query_corrections.csv"

corrections = [
    {
        "province": "Aceh",
        "city_regency": "Aceh Utara",
        "old_geocoding_query": "Aceh Utara",
        "new_geocoding_query": "Lhoksukon",
        "correction_note": "Ibu kota Kabupaten Aceh Utara",
    },
    {
        "province": "Aceh",
        "city_regency": "Aceh Besar",
        "old_geocoding_query": "Aceh Besar",
        "new_geocoding_query": "Kota Jantho",
        "correction_note": "Ibu kota Kabupaten Aceh Besar",
    },
    {
        "province": "Aceh",
        "city_regency": "Bireuen",
        "old_geocoding_query": "Bireuen",
        "new_geocoding_query": "Kota Juang",
        "correction_note": "Ibu kota Kabupaten Bireuen",
    },
    {
        "province": "Aceh",
        "city_regency": "Aceh Timur",
        "old_geocoding_query": "Aceh Timur",
        "new_geocoding_query": "Idi Rayeuk",
        "correction_note": "Ibu kota Kabupaten Aceh Timur",
    },
    {
        "province": "Riau",
        "city_regency": "Rokan Hilir",
        "old_geocoding_query": "Bagan Siapiapi",
        "new_geocoding_query": "Bagansiapiapi",
        "correction_note": "Ejaan alternatif tanpa spasi",
    },
    {
        "province": "DKI Jakarta",
        "city_regency": "Jakarta Timur",
        "old_geocoding_query": "Jakarta Timur",
        "new_geocoding_query": "East Jakarta",
        "correction_note": "Nama bahasa Inggris wilayah administrasi",
    },
    {
        "province": "DKI Jakarta",
        "city_regency": "Jakarta Selatan",
        "old_geocoding_query": "Jakarta Selatan",
        "new_geocoding_query": "South Jakarta",
        "correction_note": "Nama bahasa Inggris wilayah administrasi",
    },
    {
        "province": "DKI Jakarta",
        "city_regency": "Jakarta Barat",
        "old_geocoding_query": "Jakarta Barat",
        "new_geocoding_query": "West Jakarta",
        "correction_note": "Nama bahasa Inggris wilayah administrasi",
    },
    {
        "province": "DKI Jakarta",
        "city_regency": "Jakarta Utara",
        "old_geocoding_query": "Jakarta Utara",
        "new_geocoding_query": "North Jakarta",
        "correction_note": "Nama bahasa Inggris wilayah administrasi",
    },
    {
        "province": "Sulawesi Utara",
        "city_regency": "Minahasa Selatan",
        "old_geocoding_query": "Amurang",
        "new_geocoding_query": "South Minahasa",
        "correction_note": "Nama bahasa Inggris wilayah administrasi",
    },
    {
        "province": "Sulawesi Selatan",
        "city_regency": "Sidenreng Rappang",
        "old_geocoding_query": "Pangkajene Sidenreng",
        "new_geocoding_query": "Sidenreng Rappang",
        "correction_note": "Nama kabupaten lengkap",
    },
    {
        "province": "Kalimantan Tengah",
        "city_regency": "Kapuas",
        "old_geocoding_query": "Kuala Kapuas",
        "new_geocoding_query": "Kuala Kapuas Kalimantan Tengah",
        "correction_note": "Query diperjelas agar tidak match ke Malaysia",
    },
]

OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

df = pd.DataFrame(corrections)
df.to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")

print("File koreksi berhasil dibuat:")
print(OUTPUT_PATH)
print(f"Total koreksi: {len(df)}")