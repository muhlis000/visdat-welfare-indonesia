# Mapping kode lama (GeoJSON) → kode baru (BPS / df_kab)
KODE_MAPPING = {
    # Papua Selatan (93xx)
    "9101": "9301",  # Merauke
    "9116": "9302",  # Boven Digoel
    "9117": "9303",  # Mappi
    "9118": "9304",  # Asmat

    # Papua Tengah (94xx)
    "9104": "9401",  # Nabire
    "9107": "9402",  # Puncak Jaya
    "9108": "9403",  # Paniai
    "9109": "9404",  # Mimika
    "9125": "9405",  # Puncak
    "9126": "9406",  # Dogiyai
    "9127": "9407",  # Intan Jaya
    "9128": "9408",  # Deiyai

    # Papua Pegunungan (95xx)
    "9102": "9501",  # Jayawijaya
    "9112": "9502",  # Pegunungan Bintang
    "9113": "9503",  # Yahukimo
    "9114": "9504",  # Tolikara
    "9121": "9505",  # Mamberamo Tengah
    "9122": "9506",  # Yalimo
    "9123": "9507",  # Lanny Jaya
    "9124": "9508",  # Nduga

    # Papua Barat Daya (96xx)
    "9201": "9601",  # Sorong
    "9204": "9602",  # Sorong Selatan
    "9205": "9603",  # Raja Ampat
    "9209": "9604",  # Tambrauw
    "9210": "9605",  # Maybrat
    "9271": "9671",  # Kota Sorong
}

import geopandas as gpd
import pandas as pd
from pathlib import Path

# Baca GeoJSON yang sudah digabung
gdf = gpd.read_file("data/_big_local/geo/kabkota.geojson")

# Pastikan kode_kab sudah string 4 digit tanpa titik
gdf["kode_kab"] = gdf["kode_kab"].astype(str).str.zfill(4)

# Terapkan mapping
gdf["kode_kab"] = gdf["kode_kab"].replace(KODE_MAPPING)

# Simpan ulang
gdf.to_file("data/_big_local/geo/kabkota.geojson", driver="GeoJSON")
print("GeoJSON berhasil diperbarui dengan kode BPS terbaru")

df = pd.read_csv("data/processed/df_kab.csv", dtype={"kode_kab": str})

df = pd.read_csv("data/processed/df_kab.csv", dtype={"kode_kab": str})

kode_data = set(df["kode_kab"].unique())
kode_geo  = set(gdf["kode_kab"].unique())

print("Kode di df_kab tapi tidak di GeoJSON:", sorted(kode_data - kode_geo))
print("Kode di GeoJSON tapi tidak di df_kab:", sorted(kode_geo - kode_data))
print("Jumlah yang cocok:", len(kode_data & kode_geo))