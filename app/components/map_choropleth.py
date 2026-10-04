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
    escape_tooltip,
    format_number,
    get_mapbox_token,
    map_view,
    require_columns,
    source_caption,
    values_to_rgba,
)


CHOROPLETH_METRICS = ["persen_miskin", "IPM", "P1"]


@st.cache_data(show_spinner=False, max_entries=4)
def _colorize_geojson_cached(
    geometry_id: int,
    df: pd.DataFrame,
    metric: str,
    extruded: bool,
    _geojson: dict,
) -> dict:
    meta = INDICATORS[metric]
    lookup = df.drop_duplicates("kode_kab").set_index("kode_kab")
    colorscale = meta["colorscale"]
    colors = values_to_rgba(
        lookup[metric],
        colorscale,
        reverse=not meta["higher_is_worse"],
        alpha=200,
    )
    color_map = {kode: colors[i] for i, kode in enumerate(lookup.index)}
    series = pd.to_numeric(lookup[metric], errors="coerce")
    vmax = series.max(skipna=True) or 1
    features = []
    year = int(df["tahun"].iloc[0]) if "tahun" in df.columns and len(df) else ""
    for feat in _geojson["features"]:
        props = dict(feat.get("properties") or {})
        kode = str(props.get("kode_kab", "")).zfill(4)
        new_props = dict(props)
        if kode not in lookup.index:
            new_props.update(
                {
                    "fill_color": [180, 180, 180, 40],
                    "elevation": 0,
                    "nama_kab": escape_tooltip(props.get("nama_kab", "Wilayah")),
                    "nama_prov": escape_tooltip(props.get("nama_prov", "")),
                    "tahun": year,
                    "tooltip_label": "Data",
                    "tooltip_value": "tidak tersedia",
                }
            )
        else:
            row = lookup.loc[kode]
            value = row[metric]
            elev = 0.0
            if extruded and pd.notna(value) and vmax:
                elev = float(value) / float(vmax) * 180000
            new_props.update(
                {
                    "fill_color": color_map[kode],
                    "elevation": elev,
                    "nama_kab": escape_tooltip(row["nama_kab"]),
                    "nama_prov": escape_tooltip(row["nama_prov"]),
                    "tahun": year,
                    "tooltip_label": escape_tooltip(meta["label"]),
                    "tooltip_value": escape_tooltip(format_number(value, meta["unit"])),
                }
            )
        features.append(
            {
                "type": "Feature",
                "geometry": feat.get("geometry"),
                "properties": new_props,
            }
        )
    return {"type": "FeatureCollection", "features": features}


def _colorize_geojson(
    geojson: dict,
    df: pd.DataFrame,
    metric: str,
    extruded: bool,
) -> dict:
    return _colorize_geojson_cached(id(geojson), df, metric, extruded, geojson)


def render_choropleth(
    df: pd.DataFrame,
    geojson: dict,
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
    colored = _colorize_geojson(geojson, df, metric, extrude and view_mode == "3D")
    view = view_state or map_view(df, pitch=pitch, bearing=bearing)

    layer = pdk.Layer(
        "GeoJsonLayer",
        data=colored,
        opacity=0.92,
        stroked=True,
        filled=True,
        extruded=bool(extrude and view_mode == "3D"),
        wireframe=False,
        get_fill_color="properties.fill_color",
        get_line_color=[80, 70, 60, 140],
        line_width_min_pixels=0.4,
        get_elevation="properties.elevation",
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
        tooltip={"html": MAP_TOOLTIP_HTML, "style": MAP_TOOLTIP_STYLE},
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
