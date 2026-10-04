import json
import sys
from pathlib import Path

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

from components.common import require_columns
from components.storytelling import render_story


@st.cache_data(show_spinner="Memuat peta dan indikator...", max_entries=2)
def load_app_data(
    asset_version: str,
) -> tuple[pd.DataFrame, dict[str, str], list[str], dict[str, int]]:
    static_dir = APP_DIR / "static"
    data_path = static_dir / "story-data.json"
    manifest_path = static_dir / "story-manifest.json"
    if not data_path.is_file() or not manifest_path.is_file():
        raise FileNotFoundError(
            "Story assets are missing. Run `python scripts/build_story_assets.py` "
            "before starting the app."
        )
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
        "pulau",
        "lon",
        "lat",
    ]
    data = pd.read_json(data_path, orient="records")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("asset_version") != asset_version:
        raise ValueError("Story asset version changed while loading the application data.")
    missing = [column for column in required if column not in data.columns]
    if missing:
        raise ValueError(f"Story data is missing required columns: {', '.join(missing)}")
    if data["kode_kab"].isna().any():
        raise ValueError("Story data has null kode_kab values.")

    data["kode_kab"] = data["kode_kab"].astype(str).str.strip().str.zfill(4)
    duplicate_rows = int(data.duplicated(["kode_kab", "tahun"]).sum())
    if duplicate_rows:
        raise ValueError(
            f"Story data has {duplicate_rows} duplicate kode_kab/tahun rows."
        )

    if len(data) != manifest.get("row_count"):
        raise ValueError("Story data row count does not match story-manifest.json.")
    asset_version = manifest.get("asset_version")
    if not isinstance(asset_version, str) or len(asset_version) < 12:
        raise ValueError("Story manifest has no valid generated asset fingerprint.")
    if data[["lon", "lat"]].isna().any().any():
        raise ValueError("Story data has kabupaten/kota without map coordinates.")

    map_assets = {
        name: f"app/static/{asset['path']}?v={asset_version[:12]}"
        for name, asset in manifest.get("map_assets", {}).items()
    }
    if not {"overview", "detail"}.issubset(map_assets):
        raise ValueError("Story manifest must define overview and detail map assets.")
    geometry_issues = manifest.get("geometry_issues", {})
    unmapped = manifest.get("unmapped_provinces", [])
    data["tahun"] = data["tahun"].astype(int)
    return data, map_assets, unmapped, geometry_issues


try:
    manifest_path = APP_DIR / "static" / "story-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    asset_version = manifest.get("asset_version")
    if not isinstance(asset_version, str) or len(asset_version) < 12:
        raise ValueError("Story manifest has no valid generated asset fingerprint.")
    data, map_assets, unmapped_provinces, geometry_issues = load_app_data(
        asset_version
    )
except Exception as exc:
    st.error(f"Gagal memuat aset aplikasi: {exc}")
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

render_story(data, map_assets, unmapped_provinces)
