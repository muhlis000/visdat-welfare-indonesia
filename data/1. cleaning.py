import pandas as pd
import numpy as np
from pathlib import Path

# ============================================================
# 1. PATH
# ============================================================
RAW_DIR = Path("data/raw")
PROCESSED_DIR = Path("data/processed")
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================
# 2. LOAD DATA
# ============================================================
ipm = pd.read_csv(RAW_DIR / "ipm_kabkota_2024_2025.csv")
kemiskinan = pd.read_csv(RAW_DIR / "kemiskinan_kabkota_2024_2025.csv")
pdrb = pd.read_csv(RAW_DIR / "pdrb_perkapita_adhb_kabkota_2021_2025.csv")

print("IPM shape        :", ipm.shape)
print("Kemiskinan shape :", kemiskinan.shape)
print("PDRB shape       :", pdrb.shape)

# ============================================================
# 3. STANDARDISASI NAMA KOLOM
# ============================================================
# --- IPM ---
ipm = ipm.rename(columns={
    "Pengeluaran": "pengeluaran_perkapita"
})

# --- Kemiskinan ---
kemiskinan = kemiskinan.rename(columns={
    "jumlah_miskin (000)": "jumlah_miskin_ribu",
    "Indeks Kedalaman Kemiskinan (P1)": "P1",
    "Indeks Keparahan Kemiskinan (P2)": "P2"
})

# --- PDRB ---
pdrb = pdrb.rename(columns={
    "pdrb_perkapita_ADHB": "pdrb_perkapita"
})

# Pastikan tipe data kode_kab konsisten (string 4 digit)
for df in [ipm, kemiskinan, pdrb]:
    df["kode_kab"] = df["kode_kab"].astype(str).str.zfill(4)

# ============================================================
# 4. FILTER TAHUN YANG DIPAKAI
# ============================================================
# Kita pakai tahun 2024 & 2025 (sesuai ketersediaan)
ipm = ipm[ipm["tahun"].isin([2024, 2025])].copy()
kemiskinan = kemiskinan[kemiskinan["tahun"].isin([2024, 2025])].copy()
pdrb = pdrb[pdrb["tahun"].isin([2024, 2025])].copy()

# ============================================================
# 5. MERGE
# ============================================================
# Merge IPM + Kemiskinan
df = pd.merge(
    ipm,
    kemiskinan[["tahun", "kode_kab", "jumlah_miskin_ribu", "persen_miskin", "P1", "P2"]],
    on=["tahun", "kode_kab"],
    how="outer",
    suffixes=("", "_kemiskinan")
)

# Merge dengan PDRB
df = pd.merge(
    df,
    pdrb[["tahun", "kode_kab", "pdrb_perkapita"]],
    on=["tahun", "kode_kab"],
    how="left"
)

print("\nSetelah merge:", df.shape)
print("Missing values:\n", df.isnull().sum())

# ============================================================
# 6. CLEANING
# ============================================================
# Jumlah miskin dalam satuan orang (bukan ribu)
df["jumlah_miskin"] = (df["jumlah_miskin_ribu"] * 1000).round(0)

# Urutkan kolom agar rapi
cols_order = [
    "tahun", "kode_kab", "nama_kab", "nama_prov",
    "persen_miskin", "jumlah_miskin", "jumlah_miskin_ribu",
    "P1", "P2",
    "IPM", "UHH", "HLS", "RLS", "pengeluaran_perkapita",
    "pdrb_perkapita"
]

# Ambil hanya kolom yang ada
cols_order = [c for c in cols_order if c in df.columns]
df = df[cols_order]

# Sort
df = df.sort_values(["tahun", "kode_kab"]).reset_index(drop=True)

# ============================================================
# 7. VALIDASI RINGKAS
# ============================================================
print("\n===== RINGKASAN DATA FINAL =====")
print(f"Jumlah baris          : {len(df)}")
print(f"Jumlah kabupaten/kota : {df['kode_kab'].nunique()}")
print(f"Tahun yang tersedia   : {sorted(df['tahun'].unique())}")
print("\nKolom final:")
print(df.columns.tolist())
print("\nContoh data (5 baris pertama):")
print(df.head())

print("\nMissing values setelah cleaning:")
print(df.isnull().sum())

# ============================================================
# 8. SIMPAN
# ============================================================
output_path = PROCESSED_DIR / "df_kab.csv"
df.to_csv(output_path, index=False)
print(f"\nFile berhasil disimpan di: {output_path}")