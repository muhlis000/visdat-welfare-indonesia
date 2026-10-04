import geopandas as gpd
import pandas as pd

# Baca data
df = pd.read_csv("data/processed/df_kab.csv", dtype={"kode_kab": str})
gdf = gpd.read_file("data/_big_local/geo/kabkota.geojson")

# Pastikan kode string 4 digit
df["kode_kab"] = df["kode_kab"].astype(str).str.zfill(4)
gdf["kode_kab"] = gdf["kode_kab"].astype(str).str.zfill(4)

# Ambil hanya tahun 2024 agar tidak dobel
df_2024 = df[df["tahun"] == 2024][["kode_kab", "nama_kab", "nama_prov"]].copy()

# Join
merged = df_2024.merge(
    gdf[["kode_kab", "kab_kota", "provinsi"]],
    on="kode_kab",
    how="inner"
)

print("=== Contoh perbandingan nama ===")
print(merged[["kode_kab", "nama_kab", "kab_kota"]].head(15).to_string())

# Cek yang namanya berbeda (case-insensitive + strip)
merged["nama_sama"] = (
    merged["nama_kab"].str.lower().str.strip() == 
    merged["kab_kota"].str.lower().str.strip()
)

beda = merged[~merged["nama_sama"]]

print(f"\nJumlah yang kode cocok tapi nama berbeda: {len(beda)}")

if len(beda) > 0:
    print("\nDaftar yang namanya berbeda:")
    print(beda[["kode_kab", "nama_kab", "kab_kota", "nama_prov"]].to_string())
else:
    print("\nSemua nama cocok (setelah di-normalize lower+strip)")