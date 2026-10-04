"""Shared labels, island grouping, Mapbox helpers, and color mapping."""

from __future__ import annotations

import re
from html import escape

import pandas as pd
import streamlit as st
from plotly.colors import sample_colorscale

PULAU_FROM_PROV = {
    "Aceh": "Sumatera",
    "Sumatera Utara": "Sumatera",
    "Sumatera Barat": "Sumatera",
    "Riau": "Sumatera",
    "Jambi": "Sumatera",
    "Sumatera Selatan": "Sumatera",
    "Bengkulu": "Sumatera",
    "Lampung": "Sumatera",
    "Kepulauan Riau": "Sumatera",
    "Bangka Belitung": "Sumatera",
    "DKI Jakarta": "Jawa",
    "Jawa Barat": "Jawa",
    "Jawa Tengah": "Jawa",
    "DI Yogyakarta": "Jawa",
    "Jawa Timur": "Jawa",
    "Banten": "Jawa",
    "Bali": "Bali & Nusa Tenggara",
    "Nusa Tenggara Barat": "Bali & Nusa Tenggara",
    "Nusa Tenggara Timur": "Bali & Nusa Tenggara",
    "Kalimantan Barat": "Kalimantan",
    "Kalimantan Tengah": "Kalimantan",
    "Kalimantan Selatan": "Kalimantan",
    "Kalimantan Timur": "Kalimantan",
    "Kalimantan Utara": "Kalimantan",
    "Sulawesi Utara": "Sulawesi",
    "Sulawesi Tengah": "Sulawesi",
    "Sulawesi Selatan": "Sulawesi",
    "Sulawesi Tenggara": "Sulawesi",
    "Gorontalo": "Sulawesi",
    "Sulawesi Barat": "Sulawesi",
    "Maluku": "Maluku",
    "Maluku Utara": "Maluku",
    "Papua": "Papua",
    "Papua Barat": "Papua",
    "Papua Selatan": "Papua",
    "Papua Tengah": "Papua",
    "Papua Pegunungan": "Papua",
    "Papua Barat Daya": "Papua",
}

PULAU_VIEW = {
    "Sumatera": {"latitude": 0.2, "longitude": 102.2, "zoom": 5.1},
    "Jawa": {"latitude": -7.4, "longitude": 110.6, "zoom": 6.0},
    "Kalimantan": {"latitude": 0.2, "longitude": 114.0, "zoom": 5.2},
    "Sulawesi": {"latitude": -2.0, "longitude": 121.0, "zoom": 5.4},
    "Bali & Nusa Tenggara": {"latitude": -8.6, "longitude": 118.0, "zoom": 5.6},
    "Maluku": {"latitude": -3.0, "longitude": 128.5, "zoom": 5.3},
    "Papua": {"latitude": -4.3, "longitude": 138.5, "zoom": 5.1},
}

INDONESIA_VIEW = {"latitude": -2.5, "longitude": 118.0, "zoom": 4.15}

PCA_VARS = ["persen_miskin", "P1", "P2", "IPM", "pdrb_perkapita"]

PULAU_COLORS = {
    "Sumatera": "#0072B2",
    "Jawa": "#D55E00",
    "Kalimantan": "#009E73",
    "Sulawesi": "#CC79A7",
    "Bali & Nusa Tenggara": "#E69F00",
    "Maluku": "#56B4E9",
    "Papua": "#332288",
}

INDICATORS = {
    "persen_miskin": {
        "label": "Persentase penduduk miskin",
        "short": "% miskin",
        "unit": "persen",
        "higher_is_worse": True,
        "colorscale": "Cividis",
        "note": "Semakin tinggi, semakin besar proporsi penduduk di bawah garis kemiskinan.",
    },
    "P1": {
        "label": "Indeks kedalaman kemiskinan (P1)",
        "short": "P1",
        "unit": "indeks",
        "higher_is_worse": True,
        "colorscale": "Cividis",
        "note": "Semakin tinggi, semakin jauh rata-rata pengeluaran penduduk miskin dari garis kemiskinan.",
    },
    "P2": {
        "label": "Indeks keparahan kemiskinan (P2)",
        "short": "P2",
        "unit": "indeks",
        "higher_is_worse": True,
        "colorscale": "Cividis",
        "note": "Semakin tinggi, semakin timpang sebaran pengeluaran di antara penduduk miskin.",
    },
    "IPM": {
        "label": "Indeks Pembangunan Manusia (IPM)",
        "short": "IPM",
        "unit": "indeks",
        "higher_is_worse": False,
        "colorscale": "Cividis",
        "note": "Semakin tinggi, semakin tinggi capaian pembangunan manusia.",
    },
    "pdrb_perkapita": {
        "label": "PDRB per kapita ADHB",
        "short": "PDRB/kapita",
        "unit": "nilai pada dataset BPS",
        "higher_is_worse": False,
        "colorscale": "Cividis",
        "note": "Proxy kondisi ekonomi regional, bukan ukuran distribusi pendapatan individu.",
    },
    "jumlah_miskin": {
        "label": "Jumlah penduduk miskin",
        "short": "Jumlah miskin",
        "unit": "orang",
        "higher_is_worse": True,
        "colorscale": "Cividis",
        "note": "Ukuran absolut populasi miskin, bukan tingkat kemiskinan.",
    },
}

BPS_SOURCE = "Sumber statistik: BPS. Batas wilayah: GeoJSON kabupaten/kota pada repository proyek."

MAPBOX_STYLE = (
    "data:application/json;charset=utf-8,"
    "%7B%22version%22%3A8%2C%22sources%22%3A%7B%7D%2C%22layers%22%3A"
    "%5B%7B%22id%22%3A%22story-background%22%2C%22type%22%3A%22background%22%2C"
    "%22paint%22%3A%7B%22background-color%22%3A%22%23e7e9e6%22%7D%7D%5D%7D"
)

MAP_TOOLTIP_HTML = (
    '<div style="font:12px/1.4 sans-serif;max-width:240px;color:#202522">'
    '<strong>{nama_kab}</strong>'
    '<div style="color:#626762">{nama_prov}</div>'
    '<div>{tooltip_label} {tahun}: {tooltip_value}</div>'
    "</div>"
)

MAP_TOOLTIP_STYLE = {
    "backgroundColor": "rgba(255,255,255,0.94)",
    "color": "#202522",
    "padding": "8px 10px",
    "border": "1px solid rgba(255,255,255,0.85)",
    "borderRadius": "10px",
    "boxShadow": "0 8px 24px rgba(23,25,24,0.16)",
    "backdropFilter": "blur(8px)",
    "maxWidth": "240px",
    "fontSize": "12px",
}


def add_pulau(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["pulau"] = out["nama_prov"].map(PULAU_FROM_PROV)
    out["pulau"] = out["pulau"].fillna("Lainnya")
    return out


def get_mapbox_token() -> str | None:
    try:
        token = st.secrets["MAPBOX_TOKEN"]
    except Exception:
        token = None
    if token is None or str(token).strip() == "":
        st.error(
            "MAPBOX_TOKEN tidak ditemukan. Tambahkan token di `.streamlit/secrets.toml` "
            "untuk menjalankan peta secara lokal, atau lewat Secrets Management "
            "jika aplikasi di-deploy. Token tidak boleh ditulis di kode."
        )
        return None
    return str(token)


def map_view(df: pd.DataFrame, pitch: float, bearing: float = -18.0) -> dict:
    pulaus = sorted(df["pulau"].dropna().unique())
    if len(pulaus) == 1 and pulaus[0] in PULAU_VIEW:
        view = dict(PULAU_VIEW[pulaus[0]])
    else:
        view = dict(INDONESIA_VIEW)
    view["pitch"] = pitch
    view["bearing"] = bearing
    return view


def _parse_rgb(color: str) -> tuple[int, int, int]:
    nums = [int(x) for x in re.findall(r"[\d.]+", color)[:3]]
    if len(nums) < 3:
        return (160, 160, 160)
    return (nums[0], nums[1], nums[2])


def values_to_rgba(
    values: pd.Series,
    colorscale: str,
    *,
    reverse: bool = False,
    alpha: int = 185,
) -> list[list[int]]:
    series = pd.to_numeric(values, errors="coerce")
    vmin = series.min(skipna=True)
    vmax = series.max(skipna=True)
    if pd.isna(vmin) or pd.isna(vmax):
        t = [-1] * len(series)
    elif vmin == vmax:
        t = [0.5 if pd.notna(value) else -1 for value in series]
    else:
        t = ((series - vmin) / (vmax - vmin)).clip(0, 1).fillna(-1).tolist()
    if reverse:
        t = [1 - x if x >= 0 else x for x in t]
    out: list[list[int]] = []
    for x in t:
        if x < 0:
            out.append([160, 160, 160, 80])
            continue
        rgb = sample_colorscale(colorscale, [x])[0]
        r, g, b = _parse_rgb(rgb)
        out.append([r, g, b, alpha])
    return out


def format_number(value, unit: str) -> str:
    if value is None or pd.isna(value):
        return "tidak tersedia"
    if unit == "orang":
        return f"{int(round(value)):,}".replace(",", ".")
    if unit == "persen":
        return f"{value:,.2f}%".replace(",", "_").replace(".", ",").replace("_", ".")
    numeric = float(value)
    decimals = 0 if abs(numeric) >= 1000 else 2
    formatted = f"{numeric:,.{decimals}f}"
    return formatted.replace(",", "_").replace(".", ",").replace("_", ".")


def escape_tooltip(value: object) -> str:
    return escape(str(value), quote=True)


def source_caption(extra: str | None = None) -> None:
    text = BPS_SOURCE
    if extra:
        text = f"{text} {extra}"
    st.caption(text)


def require_columns(df: pd.DataFrame, columns: list[str], context: str) -> bool:
    missing = [c for c in columns if c not in df.columns]
    if missing:
        st.error(
            f"Kolom tidak ditemukan untuk {context}: {', '.join(missing)}. "
            "Data tidak dilengkapi secara palsu. Periksa `df_geo` / `df_kab`."
        )
        return False
    if df.empty:
        st.warning(f"Tidak ada baris data untuk {context} pada filter yang dipilih.")
        return False
    return True
