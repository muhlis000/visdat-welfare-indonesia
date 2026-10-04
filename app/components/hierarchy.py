"""Treemap and sunburst for poor-population hierarchy."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from components.common import INDICATORS, require_columns, source_caption

COLOR_OPTIONS = ["persen_miskin", "P1", "IPM"]


@st.cache_data(show_spinner=False, max_entries=16)
def _prepare_hierarchy_frame(df: pd.DataFrame) -> tuple[pd.DataFrame, int, int, int]:
    needed = [
        "nama_kab",
        "nama_prov",
        "pulau",
        "jumlah_miskin",
        "persen_miskin",
        "P1",
        "IPM",
    ]
    work = df[needed].copy()
    for column in ["jumlah_miskin", "persen_miskin", "P1", "IPM"]:
        work[column] = pd.to_numeric(work[column], errors="coerce")
    before = len(work)
    work = work.dropna(subset=["jumlah_miskin"])
    dropped = before - len(work)
    invalid_count = int((work["jumlah_miskin"] < 0).sum())
    zero_count = int((work["jumlah_miskin"] == 0).sum())
    work = work[work["jumlah_miskin"] > 0]
    work["nasional"] = "Indonesia"
    islands = work["pulau"].dropna().unique()
    if len(islands) == 1:
        work["nasional"] = f"Indonesia · filter {islands[0]}"
    total = work["jumlah_miskin"].sum()
    work["proporsi_nasional"] = work["jumlah_miskin"] / total if total else 0
    return work, dropped, invalid_count, zero_count


def _hierarchy_frame(df: pd.DataFrame) -> pd.DataFrame | None:
    needed = [
        "nama_kab",
        "nama_prov",
        "pulau",
        "jumlah_miskin",
        "persen_miskin",
        "P1",
        "IPM",
    ]
    if not require_columns(df, needed, "hierarki"):
        return None
    work, dropped, invalid_count, zero_count = _prepare_hierarchy_frame(df)
    if dropped:
        st.warning(
            f"{dropped} kabupaten/kota tanpa jumlah penduduk miskin tidak masuk treemap/sunburst."
        )
    if invalid_count:
        st.error(
            f"{invalid_count} kabupaten/kota memiliki jumlah penduduk miskin negatif; "
            "nilai tersebut tidak dapat ditampilkan sebagai ukuran hierarki."
        )
        return None
    if zero_count:
        st.warning(f"{zero_count} wilayah dengan jumlah nol tidak terlihat sebagai area pada hierarki.")
    return work


def _color_kwargs(color_col: str) -> dict:
    meta = INDICATORS[color_col]
    return {
        "color": color_col,
        "color_continuous_scale": meta["colorscale"],
        "color_continuous_midpoint": None,
    }


def render_treemap(
    df: pd.DataFrame,
    color_col: str = "persen_miskin",
    *,
    height: int = 580,
    key: str | None = None,
    show_caption: bool = True,
) -> None:
    work = _hierarchy_frame(df)
    if work is None or work.empty:
        return
    missing_color = int(work[color_col].isna().sum())
    if missing_color:
        st.warning(
            f"{missing_color} nilai {INDICATORS[color_col]['short']} kosong; "
            "wilayah tetap ditampilkan berdasarkan jumlah, tanpa nilai warna yang dibuat-buat."
        )
    year = int(df["tahun"].iloc[0]) if "tahun" in df.columns and not df.empty else ""
    fig = px.treemap(
        work,
        path=["nasional", "pulau", "nama_prov", "nama_kab"],
        values="jumlah_miskin",
        color=color_col,
        color_continuous_scale=INDICATORS[color_col]["colorscale"],
        custom_data=["nama_prov"],
        hover_data={
            "jumlah_miskin": ":,.0f",
            color_col: ":.2f",
            "proporsi_nasional": ":.1%",
        },
    )
    fig.update_traces(
        root_color="#efeae2",
        hovertemplate=(
            "<b>%{label}</b><br>"
            "<span style='color:#626762'>%{customdata[0]}</span><br>"
            f"Jumlah penduduk miskin {year}: "
            "%{value:,.0f} orang<extra></extra>"
        ),
    )
    fig.update_layout(
        height=height,
        margin=dict(t=24, b=10, l=10, r=10),
        paper_bgcolor="#faf8f5",
        separators=",.",
        hoverlabel={"bgcolor": "rgba(255,255,255,0.96)", "font": {"size": 12, "color": "#202522"}},
        transition=dict(duration=400, easing="cubic-in-out"),
        uirevision=key,
    )
    st.plotly_chart(fig, width="stretch", key=key, config={"scrollZoom": False, "displayModeBar": True})
    if show_caption:
        st.caption(
            "Ukuran kotak = jumlah penduduk miskin (bukan tingkat kemiskinan). "
            f"Warna = {INDICATORS[color_col]['label']}. "
            "Klik untuk turun hierarki Nasional → Pulau → Provinsi → Kabupaten/Kota. "
            "Proporsi adalah bagian jumlah penduduk miskin terhadap total pada tampilan, bukan kontribusi kausal."
        )
        if work["pulau"].nunique() == 1:
            st.caption(
                "Filter hanya mencakup satu pulau; akar hierarki diberi label filter dan proporsi dihitung "
                "di dalam cakupan tersebut, bukan sebagai porsi nasional."
            )
        source_caption()


def render_sunburst(
    df: pd.DataFrame,
    color_col: str = "persen_miskin",
    *,
    height: int = 580,
    key: str | None = None,
    show_caption: bool = True,
) -> None:
    work = _hierarchy_frame(df)
    if work is None or work.empty:
        return
    missing_color = int(work[color_col].isna().sum())
    if missing_color:
        st.warning(
            f"{missing_color} nilai {INDICATORS[color_col]['short']} kosong; "
            "wilayah tetap ditampilkan berdasarkan jumlah, tanpa nilai warna yang dibuat-buat."
        )
    year = int(df["tahun"].iloc[0]) if "tahun" in df.columns and not df.empty else ""
    fig = px.sunburst(
        work,
        path=["nasional", "pulau", "nama_prov", "nama_kab"],
        values="jumlah_miskin",
        color=color_col,
        color_continuous_scale=INDICATORS[color_col]["colorscale"],
        custom_data=["nama_prov"],
        hover_data={"jumlah_miskin": ":,.0f", color_col: ":.2f"},
    )
    fig.update_traces(
        hovertemplate=(
            "<b>%{label}</b><br>"
            "<span style='color:#626762'>%{customdata[0]}</span><br>"
            f"Jumlah penduduk miskin {year}: "
            "%{value:,.0f} orang<extra></extra>"
        )
    )
    fig.update_layout(
        height=height,
        margin=dict(t=24, b=10, l=10, r=10),
        paper_bgcolor="#faf8f5",
        separators=",.",
        hoverlabel={"bgcolor": "rgba(255,255,255,0.96)", "font": {"size": 12, "color": "#202522"}},
        transition=dict(duration=400, easing="cubic-in-out"),
        uirevision=key,
    )
    st.plotly_chart(fig, width="stretch", key=key, config={"scrollZoom": False, "displayModeBar": True})
    if show_caption:
        st.caption(
            "Sunburst memakai hierarki yang sama. Klik irisan untuk drill-down; klik pusat untuk kembali. "
            "Ukuran sudut = jumlah penduduk miskin."
        )
        if work["pulau"].nunique() == 1:
            st.caption(
                "Filter hanya mencakup satu pulau; akar hierarki diberi label filter dan proporsi dihitung "
                "di dalam cakupan tersebut, bukan sebagai porsi nasional."
            )
        source_caption()


def render_hierarchy(df: pd.DataFrame, color_col: str = "persen_miskin") -> None:
    color_col = st.segmented_control(
        "Warna hierarki",
        options=COLOR_OPTIONS,
        format_func=lambda k: INDICATORS[k]["short"],
        default=color_col,
        key="hierarchy_color",
    )
    if color_col is None:
        color_col = "persen_miskin"
    st.subheader("Treemap · luas menunjukkan jumlah")
    render_treemap(df, color_col)
    st.subheader("Sunburst · telusuri cincin wilayah")
    render_sunburst(df, color_col)
