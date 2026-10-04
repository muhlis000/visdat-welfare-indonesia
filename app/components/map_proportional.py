"""Mapbox proportional-symbol map for absolute poor population."""

from __future__ import annotations

import copy

import numpy as np
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


@st.cache_data(show_spinner=False, max_entries=1)
def _heatmap_base_features(geometry_id: int, _geojson: dict) -> dict:
    features = [
        {
            "type": "Feature",
            "geometry": feature.get("geometry"),
            "properties": {"fill_color": [183, 190, 185, 90]},
        }
        for feature in _geojson.get("features", [])
    ]
    return {"type": "FeatureCollection", "features": features}


def render_proportional(df: pd.DataFrame, geojson: dict) -> None:
    token = get_mapbox_token()
    if token is None:
        return
    needed = [
        "kode_kab",
        "nama_kab",
        "nama_prov",
        "tahun",
        "jumlah_miskin",
        "persen_miskin",
        "lon",
        "lat",
    ]
    if not require_columns(df, needed, "peta simbol proporsional"):
        return

    overlay = st.toggle(
        "Latar choropleth persentase miskin",
        value=True,
        key="prop_overlay",
        help="Warna polygon = tingkat kemiskinan. Ukuran titik = jumlah penduduk miskin.",
    )
    view_mode = st.segmented_control(
        "Sudut peta",
        options=["3D", "2D"],
        default="3D",
        key="prop_view",
    )

    work = df.dropna(subset=["jumlah_miskin", "lon", "lat"]).copy()
    dropped = len(df) - len(work)
    if dropped:
        st.warning(f"{dropped} wilayah tanpa jumlah miskin atau titik peta dilewati.")
    negative = int((work["jumlah_miskin"] < 0).sum())
    if negative:
        st.warning(f"{negative} wilayah dengan jumlah miskin negatif dilewati karena nilainya tidak valid.")
        work = work[work["jumlah_miskin"] >= 0].copy()
    if work.empty:
        st.error("Tidak ada titik yang dapat dipetakan.")
        return

    pitch = 46.0 if view_mode == "3D" else 0.0
    bearing = -18.0 if view_mode == "3D" else 0.0
    view = map_view(work, pitch=pitch, bearing=bearing)

    layers = []
    if overlay:
        lookup = work.drop_duplicates("kode_kab").set_index("kode_kab")
        colors = values_to_rgba(lookup["persen_miskin"], "Cividis", reverse=False, alpha=95)
        color_map = {kode: colors[i] for i, kode in enumerate(lookup.index)}
        features = []
        for feat in copy.deepcopy(geojson)["features"]:
            props = dict(feat.get("properties") or {})
            kode = str(props.get("kode_kab", "")).zfill(4)
            props["fill_color"] = color_map.get(kode, [200, 200, 200, 30])
            features.append({"type": "Feature", "geometry": feat.get("geometry"), "properties": props})
        layers.append(
            pdk.Layer(
                "GeoJsonLayer",
                data={"type": "FeatureCollection", "features": features},
                stroked=True,
                filled=True,
                extruded=False,
                get_fill_color="properties.fill_color",
                get_line_color=[90, 80, 70, 80],
                line_width_min_pixels=0.3,
                pickable=False,
            )
        )

    max_count = work["jumlah_miskin"].max()
    if max_count > 0:
        work["radius"] = 2500 + np.sqrt(work["jumlah_miskin"] / max_count) * 52000
    else:
        work["radius"] = 2500
    year = int(work["tahun"].iloc[0])
    work["tooltip_label"] = "Jumlah penduduk miskin"
    work["tooltip_value"] = work["jumlah_miskin"].map(
        lambda value: f"{format_number(value, 'orang')} orang"
    )
    work["nama_kab"] = work["nama_kab"].map(escape_tooltip)
    work["nama_prov"] = work["nama_prov"].map(escape_tooltip)
    fill = values_to_rgba(work["persen_miskin"], "Cividis", reverse=False, alpha=210)
    work["fill_color"] = fill

    layers.append(
        pdk.Layer(
            "ScatterplotLayer",
            data=work[
                [
                    "lon",
                    "lat",
                    "radius",
                    "fill_color",
                    "nama_kab",
                    "nama_prov",
                    "tooltip_label",
                    "tooltip_value",
                    "tahun",
                ]
            ].to_dict("records"),
            get_position=["lon", "lat"],
            get_radius="radius",
            get_fill_color="fill_color",
            get_line_color=[40, 30, 20, 180],
            line_width_min_pixels=1,
            stroked=True,
            pickable=True,
            radius_min_pixels=3,
            radius_max_pixels=70,
        )
    )

    deck = pdk.Deck(
        layers=layers,
        initial_view_state=pdk.ViewState(**view),
        map_provider="mapbox",
        map_style=MAPBOX_STYLE,
        api_keys={"mapbox": token},
        tooltip={"html": MAP_TOOLTIP_HTML, "style": MAP_TOOLTIP_STYLE},
    )
    st.pydeck_chart(deck, height=560)

    meta_n = INDICATORS["jumlah_miskin"]
    meta_p = INDICATORS["persen_miskin"]
    st.caption(
        f"Ukuran simbol = {meta_n['label']} (min {format_number(work['jumlah_miskin'].min(), 'orang')}, "
        f"max {format_number(work['jumlah_miskin'].max(), 'orang')} orang). "
        f"Warna = {meta_p['label']} (min {format_number(work['persen_miskin'].min(), 'persen')}, "
        f"max {format_number(work['persen_miskin'].max(), 'persen')}). "
        "Radius memakai akar kuadrat agar perbedaan ekstrem tidak menelan peta."
    )
    source_caption("Basemap: Mapbox.")


def render_heatmap_map(
    df: pd.DataFrame,
    *,
    geojson: dict | None = None,
    metric: str = "jumlah_miskin",
    view_state: dict | None = None,
    height: int = 560,
    key: str | None = None,
) -> None:
    """Render weighted point density using the existing Mapbox/pydeck stack."""
    token = get_mapbox_token()
    if token is None:
        return
    needed = ["nama_kab", "nama_prov", "tahun", metric, "lon", "lat"]
    if not require_columns(df, needed, "peta heatmap"):
        return

    work = df.dropna(subset=[metric, "lon", "lat"]).copy()
    work[metric] = pd.to_numeric(work[metric], errors="coerce")
    work = work.dropna(subset=[metric])
    if work.empty:
        st.warning(f"Tidak ada titik dengan nilai {metric} yang dapat dipetakan.")
        return
    if (work[metric] < 0).any():
        raise ValueError(f"Nilai negatif pada {metric} tidak dapat digunakan sebagai bobot heatmap.")

    year = int(work["tahun"].iloc[0])
    meta = INDICATORS.get(metric, {"label": metric, "unit": "indeks"})
    work["heat_weight"] = np.sqrt(work[metric])
    p95_weight = float(work["heat_weight"].quantile(0.95))
    if p95_weight > 0:
        work["heat_weight"] = (work["heat_weight"] / p95_weight * 100).clip(upper=100)
    work["nama_kab"] = work["nama_kab"].map(escape_tooltip)
    work["nama_prov"] = work["nama_prov"].map(escape_tooltip)
    work["tooltip_label"] = escape_tooltip(meta["label"])
    work["tooltip_value"] = work[metric].map(
        lambda value: escape_tooltip(
            format_number(value, meta["unit"])
            + (" orang" if meta["unit"] == "orang" else "")
        )
    )
    points = work[
        ["lon", "lat", "heat_weight", "nama_kab", "nama_prov", "tooltip_label", "tooltip_value", "tahun"]
    ].to_dict("records")
    layers = []
    if geojson is not None:
        base_features = _heatmap_base_features(id(geojson), geojson)
        layers.append(
            pdk.Layer(
                "GeoJsonLayer",
                data=base_features,
                stroked=True,
                filled=True,
                get_fill_color="properties.fill_color",
                get_line_color=[115, 124, 118, 95],
                line_width_min_pixels=0.35,
                pickable=False,
            )
        )
    view = view_state or map_view(work, pitch=0.0, bearing=0.0)
    zoom = float(view.get("zoom", 5.0))
    radius_pixels = max(52, min(100, 72 * 2 ** ((5.5 - zoom) / 1.5)))
    layers.extend([
        pdk.Layer(
            "HeatmapLayer",
            data=points,
            get_position=["lon", "lat"],
            get_weight="heat_weight",
            aggregation="SUM",
            radius_pixels=radius_pixels,
            intensity=1.45,
            threshold=0.005,
            color_range=[
                [0, 34, 78, 150],
                [43, 62, 105, 165],
                [93, 91, 111, 180],
                [151, 135, 112, 200],
                [254, 232, 56, 235],
            ],
            pickable=False,
        ),
        pdk.Layer(
            "ScatterplotLayer",
            data=points,
            get_position=["lon", "lat"],
            get_radius=15000,
            get_fill_color=[35, 35, 35, 2],
            stroked=False,
            pickable=True,
            radius_min_pixels=9,
            radius_max_pixels=20,
        ),
    ])
    deck = pdk.Deck(
        layers=layers,
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
    meta = INDICATORS.get(metric, {"label": metric, "unit": "indeks"})
    st.html(
        '<div class="story-heat-legend">'
        f'<strong>Bobot akar kuadrat · {meta["short"]}</strong>'
        '<div class="story-heat-ramp"></div>'
        f'<span>{format_number(work[metric].min(), meta["unit"])} · '
        f'median {format_number(work[metric].median(), meta["unit"])} · '
        f'{format_number(work[metric].max(), meta["unit"])} {meta["unit"]}</span>'
        '</div>'
    )
