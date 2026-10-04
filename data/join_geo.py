import pandas as pd
import geopandas as gpd
from pathlib import Path

# ============================================================
# PATH
# ============================================================
ROOT = Path(__file__).resolve().parent.parent   # -> visdat-welfare-indonesia

DF_PATH = ROOT / "data" / "processed" / "df_kab.csv"
BIG_LOCAL_DIR = ROOT / "data" / "_big_local"
GEO_PATH = BIG_LOCAL_DIR / "geo" / "kabkota.geojson"

OUTPUT_GEOJSON = BIG_LOCAL_DIR / "df_geo.geojson"
OUTPUT_PARQUET = BIG_LOCAL_DIR / "df_geo.parquet"

# ============================================================
# 1. LOAD DATA
# ============================================================
print("Loading data...")
df = pd.read_csv(DF_PATH, dtype={"kode_kab": str})
gdf = gpd.read_file(GEO_PATH)

# Pastikan kode 4 digit string
df["kode_kab"] = df["kode_kab"].astype(str).str.zfill(4)
gdf["kode_kab"] = gdf["kode_kab"].astype(str).str.zfill(4)

print(f"df_kab shape   : {df.shape}")
print(f"GeoJSON shape  : {gdf.shape}")
print(f"Kolom GeoJSON  : {list(gdf.columns)}")

# ============================================================
# 2. JOIN
# ============================================================
print("\nJoining...")

# Ambil hanya kode_kab + geometry dari GeoJSON
gdf_clean = gdf[["kode_kab", "geometry"]].copy()

# Left join agar semua baris di df tetap ada
df_geo = gdf_clean.merge(df, on="kode_kab", how="right")

print(f"Hasil join shape     : {df_geo.shape}")
print(f"Missing geometry     : {df_geo.geometry.isna().sum()}")
print(f"Jumlah kab/kota unik : {df_geo['kode_kab'].nunique()}")

# ============================================================
# 3. SIMPAN FILE FINAL
# ============================================================
print("\nSaving...")

# GeoJSON (untuk Mapbox / Plotly)
df_geo.to_file(OUTPUT_GEOJSON, driver="GeoJSON")
print(f"GeoJSON  → {OUTPUT_GEOJSON}")

# Parquet (lebih cepat untuk Streamlit)
df_geo.to_parquet(OUTPUT_PARQUET, index=False)
print(f"Parquet  → {OUTPUT_PARQUET}")

# ============================================================
# 4. RINGKASAN
# ============================================================
print("\n===== RINGKASAN FINAL =====")
print(f"Total baris          : {len(df_geo)}")
print(f"Jumlah kab/kota unik : {df_geo['kode_kab'].nunique()}")
print(f"Tahun tersedia       : {sorted(df_geo['tahun'].dropna().unique())}")
print(f"Kolom tersedia       : {list(df_geo.columns)}")
print("\nContoh 3 baris:")
print(df_geo[["tahun", "kode_kab", "nama_kab", "persen_miskin", "IPM"]].head(3).to_string())