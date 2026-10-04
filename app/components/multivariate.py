"""PCA, parallel coordinates, and correlation heatmap."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

from components.common import (
    INDICATORS,
    PCA_VARS,
    PULAU_COLORS,
    format_number,
    require_columns,
    source_caption,
)


@st.cache_data(show_spinner=False, max_entries=16)
def _fit_pca(work: pd.DataFrame) -> tuple[pd.DataFrame, PCA]:
    scaler = StandardScaler()
    x = scaler.fit_transform(work[PCA_VARS])
    pca = PCA(n_components=2)
    coords = pca.fit_transform(x)
    result = work.reset_index(drop=True).copy()
    result["PC1"] = coords[:, 0]
    result["PC2"] = coords[:, 1]
    return result, pca


def _pca_frame(df: pd.DataFrame) -> tuple[pd.DataFrame, PCA] | tuple[None, None]:
    if not require_columns(
        df,
        PCA_VARS + ["nama_kab", "nama_prov", "pulau", "kode_kab", "tahun"],
        "PCA",
    ):
        return None, None
    work = df[PCA_VARS + ["nama_kab", "nama_prov", "pulau", "kode_kab", "tahun"]].copy()
    for col in PCA_VARS:
        work[col] = pd.to_numeric(work[col], errors="coerce")
    before = len(work)
    work = work.dropna(subset=PCA_VARS)
    dropped = before - len(work)
    if dropped:
        st.warning(f"{dropped} kabupaten/kota dilewati karena ada indikator PCA yang kosong.")
    if len(work) < 5:
        st.error("Baris lengkap terlalu sedikit untuk PCA.")
        return None, None
    if (work[PCA_VARS].nunique(dropna=True) > 1).sum() < 2:
        st.error("PCA dua komponen memerlukan variasi pada sedikitnya dua indikator.")
        return None, None
    return _fit_pca(work)


def render_pca(
    df: pd.DataFrame,
    *,
    highlight_pulau: str | None = None,
    height: int = 520,
    key: str | None = None,
    compact: bool = False,
) -> None:
    work, pca = _pca_frame(df)
    if work is None or pca is None:
        return

    var1, var2 = pca.explained_variance_ratio_
    fig = px.scatter(
        work,
        x="PC1",
        y="PC2",
        color="pulau",
        color_discrete_map=PULAU_COLORS,
        hover_name="nama_kab",
        custom_data=["nama_prov", "tahun", "persen_miskin", "IPM"],
        hover_data={
            "nama_prov": False,
            "tahun": False,
            "persen_miskin": False,
            "IPM": False,
            "pulau": False,
            "PC1": False,
            "PC2": False,
        },
        labels={
            "PC1": f"PC1 ({var1 * 100:.1f}% varians)",
            "PC2": f"PC2 ({var2 * 100:.1f}% varians)",
            "pulau": "Pulau",
        },
    )
    for trace in fig.data:
        highlighted = highlight_pulau is None or trace.name == highlight_pulau
        trace.hovertemplate = (
            "<b>%{hovertext}</b><br>"
            "<span style='color:#626762'>%{customdata[0]}</span><br>"
            "Persentase penduduk miskin %{customdata[1]}: %{customdata[2]:.2f}%"
            " · Indeks Pembangunan Manusia: %{customdata[3]:.2f}<extra></extra>"
        )
        trace.marker = {
            "size": 9 if highlight_pulau is None or highlighted else 6,
            "opacity": 0.82 if highlighted else 0.10,
            "line": {"width": 0.4, "color": "#57534e"},
        }
    fig.update_layout(
        height=height,
        legend_title="Pulau",
        margin=dict(t=92, b=30, l=35, r=30),
        plot_bgcolor="#faf8f5",
        paper_bgcolor="#faf8f5",
        separators=",.",
        colorway=list(PULAU_COLORS.values()),
        hoverlabel={"bgcolor": "rgba(255,255,255,0.96)", "font": {"size": 12, "color": "#202522"}},
        legend={"orientation": "h", "x": 0, "y": 1.12, "xanchor": "left", "yanchor": "bottom"},
        xaxis={"tickformat": ",.2f"},
        yaxis={"tickformat": ",.2f"},
        transition=dict(duration=400, easing="cubic-in-out"),
        uirevision=key,
    )
    st.plotly_chart(
        fig,
        width="stretch",
        key=key,
        config={"scrollZoom": False, "displayModeBar": True},
    )
    if compact:
        return
    st.caption(
        f"PC1 dan PC2 bersama-sama merangkum { (var1 + var2) * 100:.1f}% varians "
        "setelah seluruh indikator distandardisasi (z-score). Warna pulau dipakai "
        "karena unit analisis geografis proyek, bukan sebagai kategori dekoratif."
    )
    loadings = pd.DataFrame(pca.components_.T, index=PCA_VARS, columns=["PC1", "PC2"])
    loadings["indikator"] = [INDICATORS[c]["short"] for c in PCA_VARS]
    fig_load = px.bar(
        loadings.melt(id_vars="indikator", value_vars=["PC1", "PC2"], var_name="komponen", value_name="loading"),
        x="loading",
        y="indikator",
        color="komponen",
        barmode="group",
        orientation="h",
        labels={"loading": "Loading", "indikator": "Indikator", "komponen": "Komponen"},
    )
    fig_load.update_layout(
        height=320,
        margin=dict(t=10, b=10),
        plot_bgcolor="#faf8f5",
        paper_bgcolor="#faf8f5",
        separators=",.",
    )
    st.plotly_chart(fig_load, width="stretch")

    pc1_top = loadings["PC1"].abs().sort_values(ascending=False)
    pc2_top = loadings["PC2"].abs().sort_values(ascending=False)
    st.caption(
        f"Loading terbesar pada PC1: {INDICATORS[pc1_top.index[0]]['short']} "
        f"({loadings.loc[pc1_top.index[0], 'PC1']:.2f}). "
        f"Pada PC2: {INDICATORS[pc2_top.index[0]]['short']} "
        f"({loadings.loc[pc2_top.index[0], 'PC2']:.2f}). "
        "Tanda loading menunjukkan arah bersama setelah standardisasi, bukan sebab-akibat."
    )
    source_caption(
        "Variabel PCA: persen miskin, P1, P2, IPM, dan PDRB per kapita. "
        "Komponen IPM (UHH, HLS, RLS, pengeluaran) tidak diikutkan agar informasi IPM tidak digandakan."
    )


@st.cache_data(show_spinner=False, max_entries=16)
def _parallel_data(
    df: pd.DataFrame,
) -> tuple[dict[str, dict[str, list]], int, dict[str, float], dict[str, float]]:
    work = df[PCA_VARS + ["nama_kab", "nama_prov", "tahun", "pulau"]].copy()
    for col in PCA_VARS:
        work[col] = pd.to_numeric(work[col], errors="coerce")
    before = len(work)
    work = work.dropna(subset=PCA_VARS).reset_index(drop=True)
    minima = work[PCA_VARS].min()
    ranges = work[PCA_VARS].max() - minima
    scaled = work[PCA_VARS].subtract(minima).divide(ranges.where(ranges != 0, 1))
    scaled.loc[:, ranges == 0] = 0.5
    payloads: dict[str, dict[str, list]] = {
        key: {"x": [], "y": [], "customdata": []}
        for key in ["__all__", *work["pulau"].dropna().unique().tolist()]
    }
    for index, row in work.iterrows():
        row_x: list[int | None] = []
        row_y: list[float | None] = []
        row_hover: list[list[str | int | None]] = []
        for axis, column in enumerate(PCA_VARS):
            row_x.append(axis)
            row_y.append(float(scaled.at[index, column]))
            row_hover.append(
                [
                    row["nama_kab"],
                    row["nama_prov"],
                    row["tahun"],
                    INDICATORS[column]["short"],
                    format_number(row[column], INDICATORS[column]["unit"]),
                ]
            )
        row_x.append(None)
        row_y.append(None)
        row_hover.append([None, None, None, None, None])
        for group in ("__all__", row["pulau"]):
            payload = payloads.get(group)
            if payload is not None:
                payload["x"].extend(row_x)
                payload["y"].extend(row_y)
                payload["customdata"].extend(row_hover)
    maxima = work[PCA_VARS].max()
    return payloads, before - len(work), minima.to_dict(), maxima.to_dict()


def render_parallel(
    df: pd.DataFrame,
    *,
    highlight_pulau: str | None = None,
    height: int = 480,
    key: str | None = None,
    show_caption: bool = True,
) -> None:
    if not require_columns(
        df,
        PCA_VARS + ["nama_kab", "nama_prov", "tahun", "pulau"],
        "parallel coordinates",
    ):
        return
    payloads, dropped, minima, maxima = _parallel_data(df)
    if dropped:
        st.warning(f"{dropped} kabupaten/kota dilewati karena indikator parallel coordinates tidak lengkap.")
    if not payloads["__all__"]["x"]:
        st.error("Tidak ada baris lengkap untuk parallel coordinates.")
        return

    labels = {
        "persen_miskin": "% miskin",
        "P1": "P1",
        "P2": "P2",
        "IPM": "IPM",
        "pdrb_perkapita": "PDRB/kapita",
    }

    def make_trace(payload: dict[str, list], *, emphasized: bool) -> go.Scattergl:
        color = (
            "rgba(15, 92, 108, 0.82)"
            if emphasized
            else "rgba(87, 83, 78, 0.12)"
            if highlight_pulau is not None
            else "rgba(15, 92, 108, 0.24)"
        )
        return go.Scattergl(
            x=payload["x"],
            y=payload["y"],
            customdata=payload["customdata"],
            mode="lines",
            connectgaps=False,
            line={"color": color, "width": 1.2 if emphasized else 0.8},
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                "<span style='color:#626762'>%{customdata[1]}</span><br>"
                "%{customdata[3]} %{customdata[2]}: %{customdata[4]}<extra></extra>"
            ),
            showlegend=False,
        )

    fig = go.Figure()
    if highlight_pulau is not None:
        fig.add_trace(make_trace(payloads["__all__"], emphasized=False))
        selected = payloads.get(highlight_pulau)
        if selected and selected["x"]:
            fig.add_trace(make_trace(selected, emphasized=True))
    else:
        fig.add_trace(make_trace(payloads["__all__"], emphasized=True))
    fig.update_layout(
        height=height,
        margin=dict(t=30, b=20, l=60, r=20),
        paper_bgcolor="#faf8f5",
        plot_bgcolor="#faf8f5",
        transition=dict(duration=400, easing="cubic-in-out"),
        separators=",.",
        hoverlabel={"bgcolor": "rgba(255,255,255,0.96)", "font": {"size": 12, "color": "#202522"}},
        xaxis={
            "tickmode": "array",
            "tickvals": list(range(len(PCA_VARS))),
            "ticktext": [labels[column] for column in PCA_VARS],
            "title": "Indikator",
            "range": [-0.1, len(PCA_VARS) - 0.9],
        },
        yaxis={"title": "Posisi min–maks (0–1)", "range": [-0.03, 1.03]},
        hovermode="closest",
        uirevision=key,
    )
    st.plotly_chart(
        fig,
        width="stretch",
        key=key,
        config={"scrollZoom": False, "displayModeBar": True},
    )
    scale_summary = "; ".join(
        f"{labels[column]}: {format_number(minima[column], INDICATORS[column]['unit'])}–"
        f"{format_number(maxima[column], INDICATORS[column]['unit'])}"
        for column in PCA_VARS
    )
    if show_caption:
        st.caption(
            "Setiap garis adalah satu kabupaten/kota. Tiap indikator dinormalisasi secara min–maks ke rentang "
            "0–1 secara terpisah; posisi menunjukkan letak relatif dalam indikator itu, bukan nilai yang "
            "sebanding antar-sumbu. Tooltip menampilkan wilayah dan nilai asli. "
            f"Rentang data: {scale_summary}."
        )
        source_caption()


@st.cache_data(show_spinner=False, max_entries=16)
def _correlation_matrix(df: pd.DataFrame) -> pd.DataFrame:
    return df[PCA_VARS].apply(pd.to_numeric, errors="coerce").corr(method="pearson")


def render_heatmap(
    df: pd.DataFrame,
    *,
    height: int = 460,
    key: str | None = None,
    show_caption: bool = True,
) -> None:
    if not require_columns(df, PCA_VARS, "heatmap korelasi"):
        return
    corr = _correlation_matrix(df)
    labels = [INDICATORS[c]["short"] for c in PCA_VARS]
    full_labels = [INDICATORS[c]["label"] for c in PCA_VARS]
    year = int(df["tahun"].iloc[0]) if "tahun" in df.columns and not df.empty else ""
    islands = df["pulau"].dropna().unique() if "pulau" in df.columns else []
    scope = f"di {islands[0]}" if len(islands) == 1 else "secara nasional"
    pair_labels = [
        [f"{full_labels[column]} × {full_labels[row]}" for column in range(len(labels))]
        for row in range(len(labels))
    ]
    fig = go.Figure(
        data=go.Heatmap(
            z=corr.values,
            x=labels,
            y=labels,
            zmin=-1,
            zmax=1,
            colorscale="PuOr",
            reversescale=True,
            text=corr.round(2).astype(str).values,
            texttemplate="%{text}",
            customdata=pair_labels,
            hovertemplate=(
                "<b>%{customdata}</b><br>"
                f"<span style='color:#626762'>Keterkaitan indikator {scope}</span><br>"
                f"Korelasi {year}: %{{z:.2f}}<extra></extra>"
            ),
            colorbar=dict(title="r Pearson"),
        )
    )
    fig.update_layout(
        height=height,
        margin=dict(t=20, b=20),
        paper_bgcolor="#faf8f5",
        plot_bgcolor="#faf8f5",
        transition=dict(duration=400, easing="cubic-in-out"),
        separators=",.",
        hoverlabel={"bgcolor": "rgba(255,255,255,0.96)", "font": {"size": 12, "color": "#202522"}},
        uirevision=key,
    )
    st.plotly_chart(
        fig,
        width="stretch",
        key=key,
        config={"scrollZoom": False, "displayModeBar": True},
    )
    if show_caption:
        st.caption(
            "Korelasi Pearson menunjukkan keterkaitan statistik linear, bukan hubungan sebab-akibat. "
            "P1 dan P2 secara konstruksi berkaitan dengan P0, sehingga korelasi tinggi di antara "
            "ketiganya diharapkan dan tidak boleh dibaca sebagai temuan kausal."
        )
        source_caption()


def render_pca_parallel(df: pd.DataFrame) -> None:
    render_pca(df)
    st.space("medium")
    render_parallel(df)
