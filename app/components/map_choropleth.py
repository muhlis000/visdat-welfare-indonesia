"""Mapbox 3D choropleth for kabupaten/kota welfare indicators."""

from __future__ import annotations

import pandas as pd
import pydeck as pdk
import streamlit as st

from components.common import (
    INDICATORS,
    MAP_TOOLTIP_HTML,
    MAP_TOOLTIP_STYLE,
    MAPBOX_STYLE,
    format_number,
    get_mapbox_token,
    map_view,
    require_columns,
    source_caption,
    values_to_rgba,
)


CHOROPLETH_METRICS = ["persen_miskin", "IPM", "P1"]


def render_choropleth(
    df: pd.DataFrame,
    geojson_url: str,
    *,
    default_metric: str = "persen_miskin",
    show_metric_control: bool = True,
    view_state: dict | None = None,
    height: int = 560,
    key: str | None = None,
    show_controls: bool = True,
    show_source: bool = True,
    show_legend: bool = True,
) -> None:
    token = get_mapbox_token()
    if token is None:
        return
    if not require_columns(
        df,
        ["kode_kab", "nama_kab", "nama_prov", "tahun", "persen_miskin", "IPM", "P1"],
        "peta choropleth",
    ):
        return

    if show_metric_control:
        metric = st.segmented_control(
            "Indikator warna",
            options=CHOROPLETH_METRICS,
            format_func=lambda k: INDICATORS[k]["short"],
            default=default_metric if default_metric in CHOROPLETH_METRICS else "persen_miskin",
            key="choropleth_metric",
        )
    else:
        metric = default_metric
    if metric is None:
        metric = default_metric

    view_mode = "2D"
    extrude = False
    if show_controls:
        view_mode = st.segmented_control(
            "Sudut peta",
            options=["3D", "2D"],
            default="3D",
            key="choropleth_view",
            help="3D memakai pitch Mapbox. Extrusi tinggi bersifat opsional dan dapat menyesatkan perbandingan luas.",
        )
        extrude = st.toggle(
            "Extrusi tinggi mengikuti nilai indikator",
            value=False,
            key="choropleth_extrude",
            help="Tinggi bangun mewakili indikator yang sama dengan warna. Matikan jika ingin membandingkan warna secara datar.",
        )

    meta = INDICATORS[metric]
    missing_metric = df[metric].isna().sum()
    if missing_metric:
        st.warning(f"{missing_metric} wilayah tanpa nilai {meta['short']} tidak diisi secara palsu.")

    pitch = 48.0 if view_mode == "3D" else 0.0
    bearing = -20.0 if view_mode == "3D" else 0.0
    view = view_state or map_view(df, pitch=pitch, bearing=bearing)
    year = int(df["tahun"].iloc[0])
    color_field = f"properties.color_{metric}_{year}"
    elevation_field = f"properties.elevation_{metric}_{year}"
    tooltip_value_field = f"{{value_{metric}_{year}}}"
    tooltip_html = (
        MAP_TOOLTIP_HTML.replace("{tooltip_label}", meta["label"])
        .replace("{tahun}", str(year))
        .replace("{tooltip_value}", tooltip_value_field)
    )

    layer = pdk.Layer(
        "GeoJsonLayer",
        data=geojson_url,
        id=f"{key or 'choropleth'}-geojson",
        opacity=0.92,
        stroked=True,
        filled=True,
        extruded=bool(extrude and view_mode == "3D"),
        wireframe=False,
        get_fill_color=color_field,
        get_line_color=[80, 70, 60, 140],
        line_width_min_pixels=0.4,
        get_elevation=elevation_field,
        pickable=True,
        auto_highlight=True,
    )
    deck = pdk.Deck(
        layers=[layer],
        views=[
            pdk.View(
                type="MapView",
                controller={
                    "dragPan": True,
                    "dragRotate": False,
                    "scrollZoom": False,
                    "doubleClickZoom": True,
                    "touchZoom": True,
                },
            )
        ],
        initial_view_state=pdk.ViewState(**view),
        map_provider="mapbox",
        map_style=MAPBOX_STYLE,
        api_keys={"mapbox": token},
        tooltip={"html": tooltip_html, "style": MAP_TOOLTIP_STYLE},
    )
    st.pydeck_chart(deck, height=height, key=key)

    if show_legend:
        series = pd.to_numeric(df[metric], errors="coerce")
        st.caption(
            f"Legenda warna — {meta['label']} ({meta['unit']}): "
            f"min {format_number(series.min(), meta['unit'])} · "
            f"median {format_number(series.median(), meta['unit'])} · "
            f"max {format_number(series.max(), meta['unit'])}. {meta['note']}"
        )
    if show_source:
        source_caption(
            "Basemap: Mapbox. Choropleth tidak dipakai untuk jumlah penduduk miskin absolut."
        )
