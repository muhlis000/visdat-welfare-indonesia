import pandas as pd
import geopandas as gpd

# ==============================
# LOAD DATA
# ==============================
df = pd.read_csv("data/processed/df_kab.csv")
gdf = gpd.read_file("data/_big_local/geo/kabkota.geojson")

# ==============================
# NORMALISASI KODE
# ==============================
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

# ==============================
# KODE YANG TIDAK COCOK
# ==============================
df_codes = set(df["kode_kab"].unique())
geo_codes = set(gdf["kode_kab"].unique())

missing_geo = sorted(df_codes - geo_codes)

# Ambil satu tahun saja
df_check = (
    df[df["tahun"] == df["tahun"].min()]
    [["kode_kab", "nama_kab", "nama_prov"]]
    .drop_duplicates()
)

# ==============================
# FILTER PAPUA (Terdapat perbedaan kode 9xxx)
# ==============================
papua_df = df_check[
    df_check["kode_kab"].isin(missing_geo)
].copy()

papua_geo = gdf[
    gdf["kode_kab"].isin(
        sorted(geo_codes - df_codes)
    )
][
    ["kode_kab", "kab_kota", "provinsi"]
].copy()

# ==============================
# OUTPUT
# ==============================
print("\n" + "=" * 70)
print("KODE DARI df_kab YANG TIDAK ADA DI GEOJSON")
print("=" * 70)

print(
    papua_df
    .sort_values("kode_kab")
    .to_string(index=False)
)

print("\n" + "=" * 70)
print("KODE DARI GEOJSON YANG TIDAK ADA DI df_kab")
print("=" * 70)

print(
    papua_geo
    .sort_values("kode_kab")
    .to_string(index=False)
)