import pandas as pd
import geopandas as gpd

# ============================================================
# 1. LOAD DATA
# ============================================================

df = pd.read_csv("data/processed/df_kab.csv")

gdf = gpd.read_file("data/_big_local/geo/kabkota.geojson")

# ============================================================
# 2. NORMALISASI KODE
# ============================================================

df["kode_kab"] = (
    df["kode_kab"]
    .astype(str)
    .str.replace(".", "", regex=False)
    .str.zfill(4)
)

gdf["kode_kab"] = (
    gdf["kode_kab"]
    .astype(str)
    .str.replace(".", "", regex=False)
    .str.zfill(4)
)

# ============================================================
# 3. KODE UNIK
# ============================================================

df_codes = set(df["kode_kab"].unique())
geo_codes = set(gdf["kode_kab"].unique())

print("========================================")
print("VALIDASI KODE KAB/KOTA")
print("========================================")

print(f"Kode unik df_kab     : {len(df_codes)}")
print(f"Kode unik GeoJSON    : {len(geo_codes)}")

# ============================================================
# 4. CEK KODE YANG TIDAK COCOK
# ============================================================

only_in_df = sorted(df_codes - geo_codes)
only_in_geo = sorted(geo_codes - df_codes)

print("\nKode ada di df_kab tetapi tidak ada di GeoJSON:")
print(only_in_df)

print("\nKode ada di GeoJSON tetapi tidak ada di df_kab:")
print(only_in_geo)

# ============================================================
# 5. HASIL VALIDASI
# ============================================================

if not only_in_df and not only_in_geo:
    print("\nSEMUA KODE KAB/KOTA COCOK!")
else:
    print("\nADA KODE YANG TIDAK COCOK!")

# ============================================================
# 6. TEST JOIN
# ============================================================

test = df.merge(
    gdf[["kode_kab", "geometry"]],
    on="kode_kab",
    how="left",
    indicator=True
)

print("\n========================================")
print("HASIL TEST JOIN")
print("========================================")

print(test["_merge"].value_counts())

# ============================================================
# 7. CEK GEOMETRY MISSING
# ============================================================

missing_geometry = test["geometry"].isna().sum()

print(f"\nBaris tanpa geometry: {missing_geometry}")

if missing_geometry == 0:
    print("Semua observasi memiliki geometry.")
else:
    print("Ada observasi yang tidak memiliki geometry.")