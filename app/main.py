import json
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd
import streamlit as st

APP_DIR = Path(__file__).resolve().parent
ROOT = APP_DIR.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

st.set_page_config(
    page_title="Bagaimana Kesejahteraan di Indonesia?",
    page_icon=":material/public:",
    layout="wide",
    initial_sidebar_state="collapsed",
)

from components.common import add_pulau, require_columns
from components.storytelling import render_story


@st.cache_data(show_spinner="Memuat peta dan indikator...")
def load_app_data() -> tuple[pd.DataFrame, dict, list[str], dict[str, int]]:
    path = ROOT / "data" / "processed" / "df_geo.parquet"
    if not path.exists():
        raise FileNotFoundError(f"File tidak ditemukan: {path}")
    required = [
        "kode_kab",
        "tahun",
        "nama_kab",
        "nama_prov",
        "persen_miskin",
        "jumlah_miskin",
        "P1",
        "P2",
        "IPM",
        "pdrb_perkapita",
        "geometry",
    ]
    gdf = gpd.read_parquet(path, columns=required)
    missing = [column for column in required if column not in gdf.columns]
    if missing:
        raise ValueError(f"Kolom wajib tidak ditemukan di df_geo.parquet: {', '.join(missing)}")
    if gdf["kode_kab"].isna().any():
        raise ValueError("df_geo.parquet memiliki kode kabupaten/kota kosong.")

    gdf["kode_kab"] = gdf["kode_kab"].astype(str).str.strip().str.zfill(4)
    duplicate_rows = int(gdf.duplicated(["kode_kab", "tahun"]).sum())
    if duplicate_rows:
        raise ValueError(
            f"df_geo.parquet memiliki {duplicate_rows} pasangan kode kabupaten/kota-tahun duplikat."
        )

    geometry_by_code = gdf.loc[gdf.geometry.notna() & ~gdf.geometry.is_empty].copy()
    geometry_by_code["_geometry_wkb"] = geometry_by_code.geometry.to_wkb()
    inconsistent_geometry = int(
        (geometry_by_code.groupby("kode_kab")["_geometry_wkb"].nunique() > 1).sum()
    )
    geom = geometry_by_code.drop_duplicates("kode_kab")[["kode_kab", "geometry"]].copy()
    geometry_issues = {
        "empty_geometry": int(gdf.geometry.isna().sum() + gdf.geometry.is_empty.sum()),
        "unmatched_codes": 0,
        "inconsistent_geometry": inconsistent_geometry,
    }
    data_codes = set(gdf["kode_kab"].unique())
    geometry_codes = set(geom["kode_kab"].unique())
    geometry_issues["unmatched_codes"] = len(data_codes - geometry_codes)
    if geom.empty:
        raise ValueError("Tidak ada geometri kabupaten/kota yang dapat digunakan di df_geo.parquet.")

    geom["geometry"] = geom.geometry.simplify(0.012, preserve_topology=True)
    points = geom.copy()
    points["geometry"] = points.geometry.representative_point()
    points["lon"] = points.geometry.x
    points["lat"] = points.geometry.y
    geojson = json.loads(geom.to_json())
    df = pd.DataFrame(gdf.drop(columns="geometry"))
    df = df.merge(points[["kode_kab", "lon", "lat"]], on="kode_kab", how="left")
    df = add_pulau(df)
    df["tahun"] = df["tahun"].astype(int)
    unmapped = sorted(df.loc[df["pulau"] == "Lainnya", "nama_prov"].dropna().unique().tolist())
    return df, geojson, unmapped, geometry_issues


try:
    data, geojson, unmapped_provinces, geometry_issues = load_app_data()
except Exception as exc:
    st.error(f"Gagal memuat `data/processed/df_geo.parquet`: {exc}")
    st.stop()

if not require_columns(
    data,
    [
        "tahun",
        "kode_kab",
        "nama_kab",
        "nama_prov",
        "persen_miskin",
        "jumlah_miskin",
        "P1",
        "P2",
        "IPM",
        "pdrb_perkapita",
        "pulau",
        "lon",
        "lat",
    ],
    "data utama",
):
    st.stop()

years = sorted(int(year) for year in data["tahun"].dropna().unique())
if not years:
    st.error("Tidak ada tahun yang valid pada data untuk ditampilkan.")
    st.stop()

for issue, count in geometry_issues.items():
    if count:
        st.warning(f"Masalah geometri ({issue}): {count}. Visualisasi hanya memakai geometri yang tersedia.")

render_story(data, geojson, unmapped_provinces)
