import pandas as pd
import geopandas as gpd
from pathlib import Path

# ============================================================
# 1. PATH
# ============================================================

GEO_DIR = Path("data/_big_local/geo/provinsi")
OUTPUT_PATH = Path("data/_big_local/geo/kabkota.geojson")

OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

# ============================================================
# 2. BACA SEMUA GEOJSON
# ============================================================

files = sorted(GEO_DIR.glob("*.geojson"))

if not files:
    raise FileNotFoundError(
        f"Tidak ditemukan file GeoJSON di: {GEO_DIR}"
    )

all_gdfs = []

for file in files:

    print(f"Membaca: {file.name}")

    gdf = gpd.read_file(file)

    print(f"  Jumlah fitur: {len(gdf)}")
    print(f"  CRS: {gdf.crs}")

    all_gdfs.append(gdf)

# ============================================================
# 3. GABUNGKAN
# ============================================================

gdf_all = gpd.GeoDataFrame(
    pd.concat(all_gdfs, ignore_index=True),
    crs=all_gdfs[0].crs
)

print("\n========================================")
print("HASIL PENGGABUNGAN")
print("========================================")

print(f"Total fitur: {len(gdf_all)}")

# ============================================================
# 4. NORMALISASI KODE KAB/KOTA
# ============================================================

gdf_all["kode_kab"] = (
    gdf_all["kode_kk"]
    .astype(str)
    .str.replace(".", "", regex=False)
    .str.zfill(4)
)

# ============================================================
# 5. CEK KODE
# ============================================================

print("\nContoh kode:")

print(
    gdf_all[
        ["kode_kk", "kode_kab", "kab_kota", "provinsi"]
    ].head(10)
)

print(
    f"\nJumlah kode kab/kota unik: "
    f"{gdf_all['kode_kab'].nunique()}"
)

# ============================================================
# 6. CEK DUPLIKAT
# ============================================================

duplicates = gdf_all[
    gdf_all["kode_kab"].duplicated(keep=False)
]

if len(duplicates) > 0:

    print("\nDITEMUKAN KODE DUPLIKAT:")

    print(
        duplicates[
            ["kode_kab", "kab_kota", "provinsi"]
        ]
    )

else:

    print("\nTidak ada kode kab/kota duplikat.")

# ============================================================
# 7. BUANG KOLOM YANG TIDAK DIPERLUKAN
# ============================================================

gdf_all = gdf_all[
    [
        "kode_kab",
        "kode_prov",
        "kab_kota",
        "provinsi",
        "geometry"
    ]
]

# ============================================================
# 8. PASTIKAN CRS
# ============================================================

gdf_all = gdf_all.to_crs(epsg=4326)

# ============================================================
# 9. SIMPAN
# ============================================================

gdf_all.to_file(
    OUTPUT_PATH,
    driver="GeoJSON"
)

print("\n========================================")
print("SELESAI")
print("========================================")

print(f"File: {OUTPUT_PATH}")
print(f"Total fitur: {len(gdf_all)}")
print(f"CRS: {gdf_all.crs}")