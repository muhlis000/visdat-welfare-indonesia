"""Scroll-driven story orchestration, data narratives, and presentation."""

from __future__ import annotations

import html
from typing import Any

import pandas as pd
import streamlit as st
from shapely.geometry import shape
from shapely.ops import unary_union

from components.common import (
    BPS_SOURCE,
    INDICATORS,
    PCA_VARS,
    PULAU_VIEW,
    format_number,
)
from components.hierarchy import render_sunburst, render_treemap
from components.map_choropleth import render_choropleth
from components.map_proportional import render_heatmap_map
from components.multivariate import _pca_frame, render_heatmap, render_parallel, render_pca


CONFIG: dict[str, Any] = {
    "islands": [
        "Sumatera",
        "Jawa",
        "Kalimantan",
        "Sulawesi",
        "Bali & Nusa Tenggara",
        "Maluku",
        "Papua",
    ],
    "viewsWithIslandSteps": [
        "choropleth",
        "heatmap-map",
        "pca",
        "parallel",
        "correlation",
        "treemap",
        "sunburst",
    ],
    "showYearToggle": True,
    "heatmapMetric": "jumlah_miskin",
    "showReadingGuide": True,
    "showProgressDots": False,
    "monitoring": {
        "rate": "persen_miskin",
        "humanDevelopment": "IPM",
        "limit": 3,
    },
    "credits": {
        "name": "Muhammad Muhlis Aditya Nur Wahid",
        "email": "222313249@stis.ac.id",
        "phone": "083119879906",
    },
}

MAP_VIEWS = [
    ("choropleth", "Choropleth Kemiskinan di Indonesia"),
    ("heatmap-map", "Heatmap Kemiskinan di Indonesia"),
]
CHART_VIEWS = [
    ("pca", "PCA"),
    ("parallel", "Parallel Coordinates"),
    ("correlation", "Heatmap Korelasi"),
    ("treemap", "Treemap"),
    ("sunburst", "Sunburst"),
]
GUIDES = {
    "choropleth": "Warna menunjukkan persentase penduduk miskin, bukan jumlah orang.",
    "heatmap-map": "Intensitas menunjukkan akumulasi jumlah penduduk miskin di titik representatif.",
    "pca": "Titik yang berdekatan memiliki profil multivariat yang relatif serupa; PCA bukan klaster.",
    "parallel": "Setiap garis mewakili satu kabupaten/kota; sumbu dinormalisasi secara terpisah.",
    "correlation": "Warna menunjukkan korelasi Pearson antarindikator, bukan hubungan sebab-akibat.",
    "treemap": "Luas menunjukkan jumlah penduduk miskin; warna menunjukkan persentase miskin.",
    "sunburst": "Sudut menunjukkan jumlah penduduk miskin pada setiap tingkat wilayah.",
}

SCROLL_JS = """
export default function (component) {
  const { parentElement, setStateValue, data } = component;
  const win = parentElement.ownerDocument.defaultView;
  const doc = parentElement.ownerDocument;
  if (parentElement.__storyCleanup) parentElement.__storyCleanup();

  function fadeVisualIn() {
    win.requestAnimationFrame(() => {
      const target = doc.querySelector(
        ".st-key-map-stage [data-testid='stDeckGlJsonChart'], " +
        ".st-key-chart-stage [data-testid='stPlotlyChart']"
      );
      if (target) {
        target.animate(
          [{ opacity: 0.82 }, { opacity: 1 }],
          { duration: 420, easing: "ease-out" }
        );
      }
    });
  }
  fadeVisualIn();

  const main = doc.querySelector('[data-testid="stMain"]');
  const scrollRoot = main && main.scrollHeight > main.clientHeight + 1
    ? main
    : doc.scrollingElement;
  let lastPosition = data.position || "";

  function storyPosition() {
    const height = win.innerHeight || 1;
    const focus = height * 0.5;
    for (const [name, count] of [["map", data.mapSteps], ["chart", data.chartSteps]]) {
      const block = doc.querySelector(`.st-key-${name}-block`);
      if (!block) continue;
      const rect = block.getBoundingClientRect();
      if (rect.top <= focus && rect.bottom > focus) {
        const step = Math.max(0, Math.min(count - 1, Math.floor((focus - rect.top) / height)));
        return `${name}:${step}`;
      }
    }
    const hero = doc.querySelector("[data-story-hero]");
    if (hero && hero.getBoundingClientRect().bottom > focus) return "hero";
    return "closing";
  }

  function publishPosition() {
    const position = storyPosition();
    if (position !== lastPosition) {
      lastPosition = position;
      setStateValue("position", position);
    }
  }

  let scrollTimer = 0;
  function schedulePosition() {
    win.clearTimeout(scrollTimer);
    scrollTimer = win.setTimeout(publishPosition, 120);
  }

  const listenerRoot = scrollRoot === doc.scrollingElement ? win : scrollRoot;
  listenerRoot.addEventListener("scroll", schedulePosition, { passive: true });
  win.addEventListener("resize", publishPosition, { passive: true });
  parentElement.__storyCleanup = () => {
    listenerRoot.removeEventListener("scroll", schedulePosition);
    win.removeEventListener("resize", publishPosition);
    win.clearTimeout(scrollTimer);
  };
  publishPosition();
}
"""

SCROLL_COMPONENT = st.components.v2.component(
    "welfare_story_scroll_detector",
    html="<span aria-hidden='true'></span>",
    js=SCROLL_JS,
)


def _word_animation(text: str) -> str:
    words = html.escape(text).split(" ")
    return " ".join(
        f'<span style="--word-delay:{min(index * 22, 198)}ms">{word}</span>'
        for index, word in enumerate(words)
    )


def _change_phrase(delta: float) -> str:
    if pd.isna(delta) or abs(delta) < 0.005:
        return "tidak berubah"
    direction = "turun" if delta < 0 else "naik"
    return f"{direction} {format_number(abs(delta), 'indeks')} poin"


def _comparison_sentence(df: pd.DataFrame, island: str, view: str) -> str:
    prior = df[(df["tahun"] == 2024) & (df["pulau"] == island)]
    current = df[(df["tahun"] == 2025) & (df["pulau"] == island)]
    if prior.empty or current.empty:
        return ""
    if view == "choropleth":
        old_top = prior.loc[prior["persen_miskin"].idxmax()]
        new_top = current.loc[current["persen_miskin"].idxmax()]
        return f"Puncak persentase bergeser dari {_row_name(old_top)} ke {_row_name(new_top)}."
    if view == "heatmap-map":
        old_top = prior.loc[prior["jumlah_miskin"].idxmax()]
        new_top = current.loc[current["jumlah_miskin"].idxmax()]
        return f"Puncak jumlah bergeser dari {_row_name(old_top)} ke {_row_name(new_top)}."
    if view in {"treemap", "sunburst"}:
        old_top = prior.groupby("nama_prov")["jumlah_miskin"].sum().idxmax()
        new_top = current.groupby("nama_prov")["jumlah_miskin"].sum().idxmax()
        return f"Provinsi berporsi terbesar bergeser dari {old_top} ke {new_top}."
    paired = current[["kode_kab", "nama_kab", "nama_prov", "persen_miskin"]].merge(
        prior[["kode_kab", "persen_miskin"]],
        on="kode_kab",
        how="inner",
        suffixes=("_2025", "_2024"),
    )
    if paired.empty:
        return ""
    delta = paired["persen_miskin_2025"] - paired["persen_miskin_2024"]
    improved = float((delta < 0).mean())
    median_delta = float(current["persen_miskin"].median() - prior["persen_miskin"].median())
    improvement_text = (
        f"{format_number(improved * 100, 'persen')} wilayah membaik."
        if improved > 0
        else "Tidak ada kabupaten/kota yang membaik."
    )
    return (
        f"Dari 2024 ke 2025, median pulau {_change_phrase(median_delta)}; "
        f"{improvement_text}"
    )


def _svg_silhouette(geojson: dict) -> str:
    geometries = [
        shape(feature["geometry"])
        for feature in geojson.get("features", [])
        if feature.get("geometry")
    ]
    if not geometries:
        return ""
    dissolved = unary_union(geometries).simplify(0.08, preserve_topology=True)
    min_x, min_y, max_x, max_y = 94, -12, 142, 8
    width, height = 1000, 420

    def project(x: float, y: float) -> tuple[float, float]:
        return ((x - min_x) / (max_x - min_x) * width, (max_y - y) / (max_y - min_y) * height)

    polygons = [dissolved] if dissolved.geom_type == "Polygon" else list(dissolved.geoms)
    paths: list[str] = []
    for polygon in polygons:
        coords = list(polygon.exterior.coords)
        if len(coords) < 4:
            continue
        points = [project(coord[0], coord[1]) for coord in coords]
        paths.append(
            "M"
            + " L".join(f"{x:.1f},{y:.1f}" for x, y in points)
            + " Z"
        )
    return (
        f'<svg class="hero-map" viewBox="0 0 {width} {height}" aria-hidden="true">'
        f'<path d="{" ".join(paths)}"/></svg>'
    )


def _css() -> None:
    st.html(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Lexend:wght@400;500;600;700;800&family=Source+Sans+3:wght@400;500;600;700&display=swap');
        :root {
          --paper:#f7f7f4; --ink:#171918; --muted:#626762; --accent:#0f5c6c;
          --line:#d7d9d4; --card:rgba(255,255,255,.62); --radius:24px;
          --space:clamp(1rem,3vw,3rem);
        }
        html, body, [data-testid="stAppViewContainer"], [data-testid="stMain"] {
          background:var(--paper); color:var(--ink); font-family:'Source Sans 3',sans-serif;
          scroll-behavior:smooth; scroll-snap-type:y proximity; scroll-padding:0;
        }
        [data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stSidebar"],
        [data-testid="stSidebarCollapsedControl"], footer { display:none !important; }
        [data-testid="stMainBlockContainer"] { max-width:none !important; padding:0 !important; }
        [data-testid="stMain"] { overflow-x:hidden; }
        .story-hero, .story-close { scroll-snap-align:start; scroll-snap-stop:always; }
        .story-hero {
          min-height:100svh; position:relative; overflow:hidden; display:flex; flex-direction:column;
          justify-content:center; padding:clamp(2rem,8vw,8rem); isolation:isolate;
        }
        .hero-map { position:absolute; z-index:-1; width:min(82vw,1100px); height:auto; right:-5vw; top:50%;
          transform:translateY(-50%); opacity:.12; fill:#626762; }
        .hero-title { margin:0; max-width:1100px; font:800 clamp(3rem,8.7vw,8.5rem)/.94 'Lexend',sans-serif;
          letter-spacing:-.075em; text-transform:uppercase; }
        .hero-title span { display:block; }
        .hero-title .question { display:inline-block; color:#050606; font-size:1.55em; line-height:.6; }
        .hero-subtitle { align-self:flex-end; margin:1.5rem 1vw 0 0; font:600 clamp(1rem,2vw,1.5rem) 'Lexend',sans-serif; }
        .story-hero > h1, .story-hero > p { transform:translateY(-3svh); }
        [data-story-block] { position:relative; }
        .story-step-spacer { height:100svh; scroll-snap-align:start; scroll-snap-stop:normal; pointer-events:none; }
        div[data-testid="stElementContainer"]:has(.story-step-spacer) { height:100svh !important; min-height:100svh !important; margin:0 !important; }
        .st-key-map-block, .st-key-chart-block {
          scroll-snap-align:start; scroll-snap-stop:normal;
          gap:0 !important; row-gap:0 !important;
        }
        .st-key-map-block [data-testid="stLayoutWrapper"]:has(.st-key-map-stage),
        .st-key-chart-block [data-testid="stLayoutWrapper"]:has(.st-key-chart-stage) {
          position:sticky; top:0; height:100svh; min-height:100svh; z-index:2;
        }
        .st-key-map-stage, .st-key-chart-stage {
          position:relative; top:auto; height:100svh; min-height:100svh; overflow:hidden;
          box-sizing:border-box; padding:1.25rem var(--space) 1.5rem;
          background:var(--paper); z-index:2;
        }
        .st-key-map-block [data-testid="stVerticalBlock"],
        .st-key-chart-block [data-testid="stVerticalBlock"] { gap:0 !important; }
        .stage-heading { position:absolute; z-index:5; top:1.3rem; left:var(--space); pointer-events:none; }
        .stage-kicker { color:var(--accent); text-transform:uppercase; letter-spacing:.12em; font:600 .78rem 'Lexend',sans-serif; }
        .stage-title { margin:.25rem 0; max-width:75vw; font:700 clamp(1.4rem,2.8vw,2.6rem)/1.08 'Lexend',sans-serif; letter-spacing:-.04em; }
        .stage-subtitle { color:var(--muted); font-size:.95rem; }
        .stage-source, .visual-source { color:var(--muted); font-size:.75rem; letter-spacing:.02em; }
        .stage-source { margin-top:.2rem; }
        .st-key-map-year, .st-key-chart-year {
          position:absolute !important; right:var(--space); top:1.1rem; z-index:10;
          width:auto !important; background:rgba(255,255,255,.82); border-radius:999px;
          border:1px solid rgba(255,255,255,.9); box-shadow:0 5px 20px rgba(0,0,0,.08);
        }
        .st-key-map-zoom {
          position:absolute !important; right:var(--space); bottom:5.7rem; z-index:12;
          width:auto !important; padding:.35rem; border-radius:14px; background:rgba(255,255,255,.88);
          box-shadow:0 5px 20px rgba(0,0,0,.12);
        }
        .st-key-map-zoom [data-testid="stHorizontalBlock"] { gap:.35rem; }
        .st-key-map-zoom button { min-width:2.5rem; min-height:2.5rem; font-size:1.2rem; }
        .st-key-map-stage [data-testid="stDeckGlJsonChart"] { margin-top:2.5rem; }
        .st-key-map-stage [data-testid="stCaptionContainer"] { position:absolute; right:2rem; bottom:.7rem; max-width:42%; color:#4c524e; }
        .story-heat-legend {
          position:absolute; right:var(--space); bottom:1.15rem; z-index:5; width:min(320px,34vw);
          padding:.6rem .85rem; border:1px solid rgba(255,255,255,.85); border-radius:12px;
          background:rgba(255,255,255,.82); color:#303530; font-size:.78rem; box-shadow:0 4px 18px rgba(0,0,0,.08);
        }
        .story-heat-legend strong, .story-heat-legend span { display:block; }
        .story-heat-ramp { height:8px; margin:.35rem 0; border-radius:99px;
          background:linear-gradient(90deg,#00224e,#414d6b,#7d7c78,#bcae63,#fee838); }
        .story-map-legend {
          position:absolute; right:var(--space); bottom:1rem; z-index:5; width:min(340px,36vw);
          padding:.6rem .85rem; border:1px solid rgba(255,255,255,.85); border-radius:12px;
          background:rgba(255,255,255,.86); color:#303530; font-size:.78rem; box-shadow:0 4px 18px rgba(0,0,0,.08);
        }
        .story-map-legend strong, .story-map-legend span { display:block; }
        .story-map-ramp { height:8px; margin:.35rem 0; border-radius:99px;
          background:linear-gradient(90deg,#00224e,#414d6b,#7d7c78,#bcae63,#fee838); }
        .st-key-chart-stage [data-testid="stHorizontalBlock"] { align-items:center; }
        .st-key-chart-stage [data-testid="column"] { min-width:0; }
        .st-key-map-card {
          position:absolute !important; left:var(--space); bottom:2.6rem; z-index:6;
          width:clamp(310px,36vw,540px); padding:1.4rem 1.6rem !important;
          border:1px solid rgba(255,255,255,.8); border-radius:var(--radius);
          background:var(--card); backdrop-filter:blur(16px); -webkit-backdrop-filter:blur(16px);
          box-shadow:0 15px 55px rgba(27,36,31,.14); pointer-events:none;
        }
        .story-card-empty { display:none !important; }
        .story-card-title { margin:0 0 .6rem; font:700 clamp(1.25rem,2vw,1.8rem) 'Lexend',sans-serif; }
        .story-copy { margin:0; text-align:justify; hyphens:auto; line-height:1.62; font-size:clamp(1rem,1.2vw,1.12rem); }
        .story-words span { display:inline-block; opacity:0; filter:blur(8px); transform:translateY(8px);
          animation:clarify .48s ease-out var(--word-delay) forwards; }
        @keyframes clarify { to { opacity:1; filter:blur(0); transform:translateY(0); } }
        .chart-layout { display:grid; grid-template-columns:minmax(0,1.25fr) minmax(300px,.9fr); gap:clamp(1rem,3vw,3.5rem);
          align-items:center; height:100%; padding-top:3.2rem; box-sizing:border-box; }
        .chart-visual { min-width:0; }
        .chart-story { max-height:calc(100svh - 5rem); overflow:hidden; padding:0 .6rem; }
        .chart-story h2 { margin:0 0 .35rem; font:700 clamp(1.7rem,3vw,2.6rem)/1.1 'Lexend',sans-serif; letter-spacing:-.05em; }
        .chart-story h3 { margin:0 0 1.2rem; color:var(--accent); font:600 clamp(1.1rem,1.7vw,1.4rem) 'Lexend',sans-serif; }
        .chart-story h4 { margin:1.1rem 0 .35rem; font:600 1rem 'Lexend',sans-serif; }
        .chart-story p { text-align:justify; hyphens:auto; line-height:1.55; font-size:1rem; }
        .chart-story .reading-guide { color:var(--muted); }
        .story-close { min-height:100svh; padding:clamp(3rem,9vw,8rem); display:flex; flex-direction:column; justify-content:center; }
        .close-title { margin:0 0 2rem; font:700 clamp(2rem,5vw,4.8rem)/1.02 'Lexend',sans-serif; letter-spacing:-.06em; }
        .close-layout { display:grid; grid-template-columns:1fr 1px minmax(250px,.65fr); gap:clamp(1.5rem,4vw,4rem); align-items:center; }
        .close-copy { max-width:760px; text-align:justify; hyphens:auto; line-height:1.7; font-size:clamp(1rem,1.35vw,1.15rem); }
        .close-rule { height:100%; min-height:240px; background:var(--line); }
        .credit { justify-self:end; align-self:end; line-height:1.75; }
        .credit-label { color:var(--accent); font:600 .8rem 'Lexend',sans-serif; letter-spacing:.15em; }
        .credit-name { margin:.3rem 0 .5rem; font:600 1.15rem 'Lexend',sans-serif; }
        .credit a { color:var(--ink); text-decoration:none; }
        .story-source { margin-top:2rem; color:var(--muted); font-size:.84rem; }
        .st-key-story-scroll { height:1px !important; min-height:1px !important; overflow:hidden !important; }
        [data-testid="stPlotlyChart"] { overflow:hidden; }
        [data-testid="stPlotlyChart"] .js-plotly-plot { touch-action:pan-y; }
        @media(max-width:720px) {
          .story-hero { padding:1.5rem; min-height:100svh; }
          .hero-map { width:125vw; right:-38vw; opacity:.10; }
          .hero-title { font-size:clamp(2.75rem,14vw,5rem); letter-spacing:-.07em; }
          .hero-subtitle { margin-top:1rem; text-align:right; max-width:85%; }
          .st-key-map-stage, .st-key-chart-stage { padding:.8rem .75rem 1rem; min-height:100svh; }
          .stage-heading { top:.8rem; left:.9rem; }
          .stage-title { max-width:68vw; font-size:1.25rem; }
          .st-key-map-year, .st-key-chart-year { top:.7rem; right:.7rem; }
          .st-key-map-zoom { right:.7rem; bottom:5.4rem; }
          .st-key-map-stage [data-testid="stDeckGlJsonChart"] { margin-top:3rem; }
          .st-key-map-card { left:.75rem; right:.75rem; bottom:2rem; width:auto; padding:1rem 1.1rem !important; }
          .st-key-map-stage [data-testid="stCaptionContainer"] { display:none; }
          .story-heat-legend { right:.75rem; bottom:.55rem; width:min(250px,50vw); font-size:.68rem; }
          .story-map-legend { right:.75rem; bottom:.55rem; width:min(250px,50vw); font-size:.68rem; }
          .chart-layout { display:flex; flex-direction:column; align-items:stretch; justify-content:flex-start; gap:.2rem; padding-top:3.4rem; }
          .chart-visual { width:100%; }
          .chart-story { max-height:none; overflow:visible; padding:.25rem .35rem; }
          .chart-story h2 { font-size:1.45rem; }
          .chart-story h3 { font-size:1rem; margin-bottom:.4rem; }
          .chart-story h4 { margin:.45rem 0 .1rem; }
          .chart-story p { margin:.15rem 0; font-size:.92rem; line-height:1.42; }
          .story-close { padding:2rem 1.2rem; }
          .close-layout { grid-template-columns:1fr; gap:1.25rem; }
          .close-rule { height:1px; min-height:1px; width:100%; }
          .credit { justify-self:start; }
        }
        @media(prefers-reduced-motion:reduce) {
          *,*:before,*:after { scroll-behavior:auto !important; animation-duration:.01ms !important; animation-iteration-count:1 !important; }
          .story-words span { opacity:1; filter:none; transform:none; }
        }
        .stage-kicker:empty { display:none; }
        .st-key-map-stage::before {
          content:""; position:absolute; z-index:3; top:0; left:0; right:0; height:140px;
          pointer-events:none; background:linear-gradient(180deg,rgba(255,255,255,.98) 58%,rgba(255,255,255,.78) 78%,transparent);
        }
        .stage-heading { z-index:5; }
        .st-key-map-stage [data-testid="stElementContainer"]:has([data-testid="stDeckGlJsonChart"]) {
          position:absolute; inset:0; min-height:0; margin:0 !important; z-index:1;
        }
        .st-key-map-stage [data-testid="stDeckGlJsonChart"] {
          position:absolute !important; inset:0; width:100% !important; height:100svh !important;
          min-height:100svh !important; margin:0 !important;
        }
        .st-key-map-stage [data-testid="stDeckGlJsonChart"] > div,
        .st-key-map-stage [data-testid="stDeckGlJsonChart"] canvas {
          width:100% !important; height:100% !important;
        }
        .st-key-map-stage .mapboxgl-ctrl-group { display:none !important; }
        .st-key-map-year, .st-key-chart-year { right:5.25rem; z-index:8; }
        .st-key-map-zoom { right:var(--space); bottom:2.4rem; z-index:8; }
        .st-key-map-stage [data-testid="stDeckGlJsonChart"] [aria-label*="Zoom"],
        .st-key-map-stage [data-testid="stDeckGlJsonChart"] [title*="Zoom"],
        .st-key-map-stage [data-testid="stDeckGlJsonChart"] [aria-label*="Fullscreen"] {
          display:none !important;
        }
        .st-key-map-card {
          left:var(--space); bottom:2.5rem; width:clamp(340px,34vw,520px);
          max-height:38svh; overflow:hidden; box-sizing:border-box;
        }
        .story-copy, .chart-story p, .close-copy, [data-testid="stMarkdownContainer"] p {
          text-align:justify !important; text-justify:inter-word; hyphens:auto; text-wrap:pretty;
        }
        .story-map-legend, .story-heat-legend {
          left:50%; right:auto; bottom:1.05rem; transform:translateX(-50%);
          width:min(360px,42vw); min-height:0; max-height:64px; box-sizing:border-box;
        }
        .st-key-map-stage > [data-testid="stElementContainer"]:has(.st-key-map-card) {
          position:absolute !important; left:var(--space); right:auto; bottom:2.5rem;
          width:clamp(340px,34vw,520px) !important; height:auto !important;
          min-height:0 !important; margin:0 !important; padding:0 !important;
          overflow:visible; z-index:6;
        }
        .st-key-map-card {
          position:relative !important; left:auto; right:auto; bottom:auto;
          width:100%; max-height:38svh; overflow:hidden; box-sizing:border-box;
        }
        .st-key-map-stage > [data-testid="stElementContainer"]:has(.story-map-legend),
        .st-key-map-stage > [data-testid="stElementContainer"]:has(.story-heat-legend) {
          position:absolute !important; left:calc(50% + 32px); right:auto; bottom:1.05rem;
          transform:translateX(-50%); width:min(360px,42vw) !important;
          height:auto !important; min-height:0 !important; max-height:64px;
          margin:0 !important; padding:0 !important; overflow:visible; z-index:5;
        }
        .story-map-legend, .story-heat-legend {
          position:relative; left:auto; right:auto; bottom:auto; transform:none;
          width:100%; min-height:0; max-height:64px; box-sizing:border-box;
        }
        .story-map-legend strong, .story-heat-legend strong { display:inline; margin-right:.4rem; }
        .story-map-legend span, .story-heat-legend span { display:inline; }
        .story-map-ramp, .story-heat-ramp { margin:.25rem 0; }
        .st-key-chart-stage [data-testid="stHorizontalBlock"] {
          position:absolute; top:5.4rem; left:var(--space); right:var(--space); bottom:.8rem;
          width:auto !important; box-sizing:border-box;
          align-items:flex-start !important; gap:clamp(1rem,2.5vw,2.5rem);
        }
        .st-key-chart-stage [data-testid="column"] { min-width:0; }
        .st-key-chart-stage [data-testid="column"]:first-child { flex:1.45 1 0% !important; }
        .st-key-chart-stage [data-testid="column"]:last-child { flex:1 1 0% !important; }
        .st-key-chart-stage [data-testid="stPlotlyChart"],
        .st-key-chart-stage .js-plotly-plot,
        .st-key-chart-stage .plot-container,
        .st-key-chart-stage .svg-container {
          height:calc(100svh - 7rem) !important; min-height:0 !important;
        }
        .chart-story { max-height:calc(100svh - 7rem); overflow:hidden; padding:.15rem .35rem; }
        .chart-story h2 { margin:0 0 .2rem; }
        .chart-story h3 { margin:0 0 .8rem; }
        .chart-story h4 { margin:.75rem 0 .25rem; }
        .chart-story p { margin:.2rem 0; }
        .chart-story .monitoring-criterion { margin-top:.35rem; color:var(--muted); font-size:.75rem; }
        .chart-placeholder { visibility:hidden; }
        .close-layout { align-items:center; }
        .credit { justify-self:center; align-self:center; text-align:center; }
        .credit > * { text-align:center; }
        @media(max-width:720px) {
          .st-key-map-stage [data-testid="stDeckGlJsonChart"] { height:100svh !important; }
          .st-key-map-stage::before { height:105px; }
          .stage-title { max-width:65vw; }
          .st-key-map-year, .st-key-chart-year { top:.65rem; right:4.5rem; }
          .st-key-map-year { right:.7rem; top:4.7rem; }
          .st-key-map-zoom { right:.7rem; top:6.9rem; bottom:auto; }
          .st-key-map-stage > [data-testid="stElementContainer"]:has(.st-key-map-card) {
            left:.75rem; right:.75rem; bottom:5rem; width:auto !important;
          }
          .st-key-map-card { width:100%; max-height:38svh; }
          .story-map-legend, .story-heat-legend {
            font-size:.68rem;
          }
          .st-key-map-stage > [data-testid="stElementContainer"]:has(.story-map-legend),
          .st-key-map-stage > [data-testid="stElementContainer"]:has(.story-heat-legend) {
            left:auto; right:.7rem; bottom:.6rem; transform:none;
            width:min(235px,55vw) !important;
          }
          .story-map-legend strong, .story-heat-legend strong { display:block; }
          .story-heat-legend { font-size:.62rem; padding:.45rem .6rem; }
          .st-key-chart-stage [data-testid="stHorizontalBlock"]:has(.chart-story) {
            top:4.35rem; left:.75rem; right:.75rem; bottom:.35rem;
            display:flex !important; flex-direction:column !important; align-items:stretch !important;
            gap:.15rem !important; width:auto !important;
          }
          .st-key-chart-stage [data-testid="stColumn"]:first-child {
            flex:0 0 54svh !important; width:100% !important; max-width:100% !important;
            min-width:0 !important; min-height:0 !important; height:auto !important;
          }
          .st-key-chart-stage [data-testid="stColumn"]:last-child {
            flex:0 0 auto !important; width:100% !important; max-width:100% !important;
            min-width:0 !important; min-height:0 !important; height:auto !important;
          }
          .st-key-chart-stage [data-testid="stPlotlyChart"],
          .st-key-chart-stage .js-plotly-plot,
          .st-key-chart-stage .plot-container,
          .st-key-chart-stage .svg-container { height:54svh !important; }
          .chart-story { max-height:none; overflow:hidden; padding:0 .25rem; }
          .chart-story h2 { font-size:1.2rem; }
          .chart-story h3 { font-size:.95rem; margin-bottom:.25rem; }
          .chart-story h4 { font-size:.85rem; margin:.25rem 0 .1rem; }
          .chart-story p { font-size:.78rem; line-height:1.25; margin:.1rem 0; }
          .chart-story .monitoring-criterion { font-size:.68rem; line-height:1.2; }
          .close-layout { grid-template-columns:1fr; }
          .credit { justify-self:center; }
        }
        </style>
        """
    )


def _steps(views: list[tuple[str, str]]) -> list[tuple[str, str, str | None]]:
    result: list[tuple[str, str, str | None]] = []
    for view_key, title in views:
        result.append((view_key, title, None))
        if view_key in CONFIG["viewsWithIslandSteps"]:
            result.extend((view_key, title, island) for island in CONFIG["islands"])
    return result


def _active_position() -> tuple[str, int]:
    state = st.session_state.get("story-scroll-detector", {})
    position = state.get("position", "hero") if hasattr(state, "get") else "hero"
    try:
        block, value = str(position).split(":", 1)
        return block, max(0, int(value))
    except ValueError:
        return ("map", 0) if position == "map" else ("chart", 0) if position == "chart" else ("hero", 0)


def _year(view: str, years: list[int]) -> int:
    default = 2025 if 2025 in years else years[-1]
    if not CONFIG["showYearToggle"]:
        return default
    value = st.segmented_control(
        "Tahun",
        options=years,
        default=default,
        format_func=str,
        key=f"story-year-{view}",
        label_visibility="collapsed",
    )
    return int(value or default)


def _headline(kicker: str, title: str, subtitle: str = "") -> str:
    subtitle_html = (
        f'<div class="stage-subtitle story-words">{_word_animation(subtitle)}</div>'
        if subtitle
        else ""
    )
    kicker_html = (
        f'<div class="stage-kicker story-words">{_word_animation(kicker)}</div>'
        if kicker
        else ""
    )
    return (
        '<div class="stage-heading">'
        f"{kicker_html}"
        f'<h1 class="stage-title story-words">{_word_animation(title)}</h1>'
        f"{subtitle_html}"
        '<div class="stage-source">Sumber: BPS</div></div>'
    )


def _row_name(row: pd.Series) -> str:
    return f"{row['nama_kab']}, {row['nama_prov']}"


def _extreme_rows(data: pd.DataFrame, column: str) -> tuple[pd.Series, pd.Series] | None:
    valid = data.dropna(subset=[column])
    if valid.empty:
        return None
    return valid.loc[valid[column].idxmax()], valid.loc[valid[column].idxmin()]


@st.cache_data(show_spinner=False, max_entries=128)
def _map_story(df: pd.DataFrame, island: str, year: int, view: str) -> str:
    current = df[(df["tahun"] == year) & (df["pulau"] == island)]
    if current.empty:
        return "Data tidak tersedia untuk pulau ini."
    extremes = _extreme_rows(current, "persen_miskin")
    if extremes is None:
        return "Data persentase kemiskinan tidak tersedia untuk pulau ini."
    worst, best = extremes
    if view == "heatmap-map":
        valid_counts = current.dropna(subset=["jumlah_miskin"])
        if valid_counts.empty:
            return "Jumlah penduduk miskin tidak tersedia untuk pulau ini."
        count_row = valid_counts.loc[valid_counts["jumlah_miskin"].idxmax()]
        total = valid_counts["jumlah_miskin"].sum()
        share = count_row["jumlah_miskin"] / total if total else 0
        contrast = (
            "Persentasenya juga di atas median pulau."
            if count_row["persen_miskin"] > current["persen_miskin"].median()
            else "Persentasenya justru di bawah median pulau."
        )
        text = (
            f"Jumlah penduduk miskin terbanyak ada di {_row_name(count_row)}: "
            f"{format_number(count_row['jumlah_miskin'], 'orang')} orang, "
            f"{format_number(share * 100, 'persen')} dari total pulau. {contrast}"
        )
    else:
        gap = worst["persen_miskin"] - best["persen_miskin"]
        text = (
            f"Pada {year}, persentase tertinggi berada di {_row_name(worst)} "
            f"({format_number(worst['persen_miskin'], 'persen')}); terendah di {_row_name(best)} "
            f"({format_number(best['persen_miskin'], 'persen')}). "
            f"Kesenjangan keduanya {format_number(gap, 'indeks')} poin persentase."
        )
    if year == 2025:
        text += " " + _comparison_sentence(df, island, view)
    return text.strip()


def _monitoring_rows(df: pd.DataFrame, island: str, year: int) -> pd.DataFrame:
    config = CONFIG["monitoring"]
    rate, human = config["rate"], config["humanDevelopment"]
    year_df = df[df["tahun"] == year]
    island_df = year_df[year_df["pulau"] == island].dropna(subset=[rate, human])
    if island_df.empty:
        return island_df
    watch = island_df[
        (island_df[rate] > year_df[rate].median())
        & (island_df[human] < year_df[human].median())
    ]
    if watch.empty:
        watch = island_df
    return watch.sort_values(rate, ascending=False).head(config["limit"])


def _monitoring_text(df: pd.DataFrame, island: str, year: int) -> str:
    rows = _monitoring_rows(df, island, year)
    if rows.empty:
        return "Data tidak tersedia untuk pulau ini."
    descriptions = [_row_name(row) for _, row in rows.iterrows()]
    return "; ".join(descriptions) + "."


@st.cache_data(show_spinner=False, max_entries=128)
def _monitoring_criterion(df: pd.DataFrame, island: str, year: int) -> str:
    rows = _monitoring_rows(df, island, year)
    if rows.empty:
        return ""
    national = df[df["tahun"] == year]
    high_cut = national["persen_miskin"].median()
    low_cut = national["IPM"].median()
    if ((rows["persen_miskin"] > high_cut) & (rows["IPM"] < low_cut)).all():
        return (
            "Kriteria: persentase kemiskinan di atas median nasional dan "
            "Indeks Pembangunan Manusia di bawah median nasional."
        )
    return "Peringkat mengikuti persentase kemiskinan tertinggi; tidak ada wilayah yang memenuhi kedua kriteria."


@st.cache_data(show_spinner=False, max_entries=128)
def _chart_story(df: pd.DataFrame, island: str, year: int, view: str) -> tuple[str, str]:
    data = df[(df["tahun"] == year) & (df["pulau"] == island)]
    if data.empty:
        return "Data tidak tersedia untuk pulau ini.", "Data tidak tersedia untuk pulau ini."
    if view == "pca":
        pca_data, _ = _pca_frame(df[df["tahun"] == year])
        island_scores = pca_data[pca_data["pulau"] == island].copy() if pca_data is not None else pd.DataFrame()
        if not island_scores.empty:
            center = island_scores[["PC1", "PC2"]].mean()
            island_scores["distance"] = (
                (island_scores["PC1"] - center["PC1"]) ** 2
                + (island_scores["PC2"] - center["PC2"]) ** 2
            ) ** 0.5
            national_center = pca_data[["PC1", "PC2"]].mean()
            national_distance = (
                (pca_data["PC1"] - national_center["PC1"]) ** 2
                + (pca_data["PC2"] - national_center["PC2"]) ** 2
            ) ** 0.5
            national_spread = float(national_distance.median())
            island_spread = float(island_scores["distance"].median())
            comparison = (
                "lebih rapat daripada sebaran nasional"
                if island_spread < national_spread * 0.8
                else "lebih beragam daripada sebaran nasional"
                if island_spread > national_spread * 1.2
                else "serupa dengan sebaran nasional"
            )
            outlier = island_scores.loc[island_scores["distance"].idxmax()]
            first = (
                f"Profil yang paling menyimpang dari mayoritas pulau ini berada di {_row_name(outlier)}. "
                f"Sebaran profil kabupaten/kota {comparison}."
            )
        else:
            first = "Sebaran profil gabungan indikator belum dapat dihitung."
    elif view == "parallel":
        national = df[df["tahun"] == year]
        labels = {
            "persen_miskin": "persentase kemiskinan",
            "P1": "kedalaman kemiskinan",
            "P2": "keparahan kemiskinan",
            "IPM": "pembangunan manusia",
            "pdrb_perkapita": "PDRB per kapita",
        }
        deviations = {}
        for column in PCA_VARS:
            scale = pd.to_numeric(national[column], errors="coerce").std()
            if pd.notna(scale) and scale > 0:
                deviations[column] = abs(
                    float(data[column].median() - national[column].median()) / float(scale)
                )
        if deviations:
            column = max(deviations, key=deviations.get)
            direction = "lebih tinggi" if data[column].median() > national[column].median() else "lebih rendah"
            island_center = data[column].median()
            local_scale = pd.to_numeric(data[column], errors="coerce").std()
            if pd.isna(local_scale) or local_scale == 0:
                local_scale = 1.0
            unusual = data.loc[(data[column] - island_center).abs().div(local_scale).idxmax()]
            first = (
                f"Perbedaan terbesar dari median nasional ada pada {labels[column]}: "
                f"median pulau {direction}. {_row_name(unusual)} paling menyimpang dari pola pulau."
            )
        else:
            first = "Nilai indikator belum cukup bervariasi untuk membandingkan pola pulau dan nasional."
    elif view == "correlation":
        labels = {
            "persen_miskin": "persentase kemiskinan",
            "P1": "kedalaman kemiskinan",
            "P2": "keparahan kemiskinan",
            "IPM": "pembangunan manusia",
            "pdrb_perkapita": "PDRB per kapita",
        }
        local_corr = data[PCA_VARS].corr()
        national_corr = df[df["tahun"] == year][PCA_VARS].corr()
        pairs = [
            (left, right, float(local_corr.loc[left, right]))
            for index, left in enumerate(PCA_VARS)
            for right in PCA_VARS[index + 1 :]
            if pd.notna(local_corr.loc[left, right])
        ]
        if pairs:
            strongest = max(pairs, key=lambda pair: abs(pair[2]))
            weakest = min(pairs, key=lambda pair: abs(pair[2]))
            national_value = national_corr.loc[strongest[0], strongest[1]]
            trend = (
                "arahnya berbalik dibanding nasional"
                if pd.notna(national_value) and strongest[2] * national_value < 0
                else "arahnya sejalan dengan nasional"
            )
            first = (
                f"Keterkaitan terkuat: {labels[strongest[0]]} dan {labels[strongest[1]]} "
                f"({format_number(strongest[2], 'indeks')}); terlemah: "
                f"{labels[weakest[0]]} dan {labels[weakest[1]]}. "
                f"Arah terkuat {trend}; korelasi bukan sebab-akibat."
            )
        else:
            first = "Keterkaitan antarindikator belum dapat dihitung."
    else:
        hierarchy_data = data.dropna(subset=["jumlah_miskin"])
        by_province = hierarchy_data.groupby("nama_prov")["jumlah_miskin"].sum().sort_values(ascending=False)
        total = float(hierarchy_data["jumlah_miskin"].sum())
        if by_province.empty or total <= 0:
            first = "Komposisi jumlah penduduk miskin belum dapat dihitung."
        else:
            top_three = hierarchy_data.nlargest(3, "jumlah_miskin")
            province_share = float(by_province.iloc[0] / total * 100)
            top_share = float(top_three["jumlah_miskin"].sum() / total * 100)
            first = (
                f"{by_province.index[0]} menampung porsi terbesar, "
                f"{format_number(province_share, 'persen')} dari jumlah di pulau ini. "
                f"Tiga kabupaten/kota teratas menyumbang {format_number(top_share, 'persen')}."
            )
    if year == 2025:
        first += " " + _comparison_sentence(df, island, view)
    return first, _monitoring_text(df, island, year)


def _render_css_and_hero(geojson: dict) -> None:
    _css()
    if "story-indonesia-svg" not in st.session_state:
        st.session_state["story-indonesia-svg"] = _svg_silhouette(geojson)
    svg = st.session_state["story-indonesia-svg"]
    st.html(
        '<section class="story-hero" data-story-hero lang="id">'
        f"{svg}"
        '<h1 class="hero-title"><span>BAGAIMANA</span><span>KESEJAHTERAAN DI</span>'
        '<span>INDONESIA<span class="question">?</span></span></h1>'
        '<p class="hero-subtitle">Komparasi Tahun 2024 dengan Tahun 2025</p>'
        "</section>"
    )


def _render_map_block(df: pd.DataFrame, geojson: dict, years: list[int], position: int) -> None:
    active_block, _ = _active_position()
    steps = _steps(MAP_VIEWS)
    position = min(position, len(steps) - 1)
    view, title, island = steps[position]
    view_state = dict(PULAU_VIEW[island]) if island else {
        "latitude": -2.5,
        "longitude": 118.0,
        "zoom": 4.15,
    }
    view_state.update({"pitch": 0, "bearing": 0})
    if island:
        view_state["longitude"] -= 0.16 * (360 / 2 ** view_state["zoom"])
    view_state["transitionDuration"] = 1400

    with st.container(key="map-block"):
        with st.container(key="map-stage"):
            if active_block == "map":
                st.html(
                    _headline(
                        "",
                        title,
                        GUIDES[view] if island is None and CONFIG["showReadingGuide"] else "",
                    )
                )
                with st.container(key="map-year"):
                    year = _year(view, years)
                year_df = df[df["tahun"] == year]
                zoom_key = f"story-zoom-{view}-{island or 'overview'}-{year}"
                st.session_state.setdefault(zoom_key, 0)
                with st.container(key="map-zoom"):
                    zoom_out, zoom_in = st.columns(2, gap="small")
                    with zoom_out:
                        if st.button("−", key=f"{zoom_key}-out", help="Perkecil peta"):
                            st.session_state[zoom_key] = max(-2, st.session_state[zoom_key] - 1)
                    with zoom_in:
                        if st.button("+", key=f"{zoom_key}-in", help="Perbesar peta"):
                            st.session_state[zoom_key] = min(3, st.session_state[zoom_key] + 1)
                view_state["zoom"] = max(3.0, min(9.0, view_state["zoom"] + st.session_state[zoom_key]))
                if view == "choropleth":
                    render_choropleth(
                        year_df,
                        geojson,
                        default_metric="persen_miskin",
                        show_metric_control=False,
                        view_state=view_state,
                        height=760,
                        key=f"story-map-{view}",
                        show_controls=False,
                        show_source=False,
                        show_legend=False,
                    )
                    values = pd.to_numeric(year_df["persen_miskin"], errors="coerce")
                    st.html(
                        '<div class="story-map-legend">'
                        '<strong>Persentase penduduk miskin · persen</strong>'
                        '<div class="story-map-ramp"></div>'
                        f'<span>{format_number(values.min(), "persen")} · median '
                        f'{format_number(values.median(), "persen")} · {format_number(values.max(), "persen")}</span>'
                        '</div>'
                    )
                else:
                    render_heatmap_map(
                        year_df,
                        geojson=geojson,
                        metric=CONFIG["heatmapMetric"],
                        view_state=view_state,
                        height=760,
                        key=f"story-map-{view}",
                    )
                if island:
                    story = _map_story(df, island, year, view)
                    card = (
                        '<div class="st-key-map-card"><h2 class="story-card-title story-words">'
                        f"{_word_animation(island)}</h2>"
                        f'<p class="story-copy story-words">{_word_animation(story)}</p></div>'
                    )
                else:
                    card = '<div class="st-key-map-card story-card-empty" aria-hidden="true"></div>'
                st.html(card)
            else:
                st.html('<div aria-hidden="true" style="height:100svh"></div>')
        for _ in range(len(steps) - 1):
            st.html('<div class="story-step-spacer" aria-hidden="true"></div>')
    with st.container(key="story-scroll"):
        current = st.session_state.get("story-scroll-detector", {})
        initial = current.get("position", "hero") if hasattr(current, "get") else "hero"
        SCROLL_COMPONENT(
            key="story-scroll-detector",
            data={
                "mapSteps": len(_steps(MAP_VIEWS)),
                "chartSteps": len(_steps(CHART_VIEWS)),
                "position": initial,
            },
            default={"position": initial},
            on_position_change=lambda: None,
        )


def _render_chart_block(df: pd.DataFrame, years: list[int], position: int) -> None:
    active_block, _ = _active_position()
    steps = _steps(CHART_VIEWS)
    position = min(position, len(steps) - 1)
    view, title, island = steps[position]

    with st.container(key="chart-block"):
        with st.container(key="chart-stage"):
            if active_block == "chart":
                with st.container(key="chart-year"):
                    year = _year(view, years)
                year_df = df[df["tahun"] == year]
                island_df = year_df[year_df["pulau"] == island] if island else year_df
                key = f"story-chart-{view}"
                left, right = st.columns([1.45, 1], gap="large", vertical_alignment="top")
                with left:
                    if view == "pca":
                        render_pca(year_df, highlight_pulau=island, height=620, key=key, compact=True)
                    elif view == "parallel":
                        render_parallel(
                            year_df,
                            highlight_pulau=island,
                            height=620,
                            key=key,
                            show_caption=False,
                        )
                    elif view == "correlation":
                        render_heatmap(island_df, height=620, key=key, show_caption=False)
                    elif view == "treemap":
                        render_treemap(
                            island_df,
                            color_col="persen_miskin",
                            height=620,
                            key=key,
                            show_caption=False,
                        )
                    else:
                        render_sunburst(
                            island_df,
                            color_col="persen_miskin",
                            height=620,
                            key=key,
                            show_caption=False,
                        )
                with right:
                    scene_name = "Multivariat" if view in {"pca", "parallel", "correlation"} else "Hierarki"
                    if island:
                        first, monitoring = _chart_story(df, island, year, view)
                        criterion = _monitoring_criterion(df, island, year)
                        primary_class = "story-primary"
                        monitoring_class = "story-monitoring"
                    else:
                        first = GUIDES[view] if CONFIG["showReadingGuide"] else ""
                        monitoring = criterion = ""
                        primary_class = "story-primary"
                        monitoring_class = "story-monitoring chart-placeholder"
                    st.html(
                        f'<div class="chart-story" lang="id">'
                        f'<h2 class="story-words">{_word_animation(scene_name)}</h2>'
                        f'<h3 class="story-words">{_word_animation(title)}</h3>'
                        '<div class="visual-source">Sumber: BPS</div>'
                        f'<div class="{primary_class}"><h4 class="story-words">'
                        f'{_word_animation(island or "Ringkasan wilayah")}</h4>'
                        f'<p class="story-words">{_word_animation(first)}</p></div>'
                        f'<div class="{monitoring_class}"><h4 class="story-words">'
                        f'{_word_animation(f"Kab/Kota {island} yang Memerlukan Pemantauan" if island else "Pemantauan wilayah")}</h4>'
                        f'<p class="story-words">{_word_animation(monitoring)}</p>'
                        f'<p class="monitoring-criterion">{html.escape(criterion)}</p></div>'
                        '</div>'
                    )
            else:
                st.html('<div aria-hidden="true" style="height:100svh"></div>')
        for _ in range(len(steps) - 1):
            st.html('<div class="story-step-spacer" aria-hidden="true"></div>')


def _conclusion(df: pd.DataFrame) -> None:
    years = sorted(int(value) for value in df["tahun"].unique())
    current_year = 2025 if 2025 in years else years[-1]
    current = df[df["tahun"] == current_year]
    previous = df[df["tahun"] == 2024]
    worst = current.loc[current["persen_miskin"].idxmax()]
    best = current.loc[current["persen_miskin"].idxmin()]
    high_island = current.groupby("pulau")["persen_miskin"].median().idxmax()
    island_totals = current.groupby("pulau")["jumlah_miskin"].sum().sort_values(ascending=False)
    total_people = current["jumlah_miskin"].sum()
    concentration = island_totals.index[0]
    correlation = current[["persen_miskin", "IPM"]].corr().iloc[0, 1]
    change_text = f"Data tahun 2024 tidak tersedia untuk membandingkan perubahan menuju {current_year}."
    if current_year == 2025 and not previous.empty and not current.empty:
        delta = current["persen_miskin"].median() - previous["persen_miskin"].median()
        old_top = previous.loc[previous["persen_miskin"].idxmax()]
        change_text = (
            f"Median persentase penduduk miskin nasional {_change_phrase(delta)} antara 2024 dan 2025. "
            f"Wilayah dengan persentase tertinggi bergeser dari {_row_name(old_top)} pada 2024 "
            f"ke {_row_name(worst)} pada 2025."
        )
    share = island_totals.iloc[0] / total_people if total_people else 0
    credits = CONFIG["credits"]
    spatial_text = (
        f"Pada {current_year}, median persentase penduduk miskin tertinggi berada di {high_island}. "
        f"Nilai tertinggi tercatat di {_row_name(worst)} "
        f"({format_number(worst['persen_miskin'], 'persen')}), sedangkan terendah di "
        f"{_row_name(best)} ({format_number(best['persen_miskin'], 'persen')})."
    )
    correlation_phrase = format_number(correlation, "indeks")
    multivariate_text = (
        f"Pada {current_year}, keterkaitan persentase kemiskinan dengan Indeks Pembangunan Manusia "
        f"adalah {correlation_phrase}. Hubungan ini bukan sebab-akibat; perbandingan indikator "
        "melengkapi pembacaan tanpa membentuk indeks resmi."
    )
    concentration_text = (
        f"{concentration} menampung {format_number(share * 100, 'persen')} dari seluruh penduduk "
        f"miskin pada data {current_year}. Jumlah absolut dan persentase menjawab pertanyaan berbeda."
    )
    st.html(
        '<section class="story-close" lang="id">'
        f'<h1 class="close-title story-words">{_word_animation("Kesimpulan")}</h1>'
        '<div class="close-layout">'
        '<div class="close-copy story-words">'
        f'<p>{_word_animation(spatial_text)}</p>'
        f'<p>{_word_animation(multivariate_text)}</p>'
        f'<p>{_word_animation(concentration_text)}</p>'
        f'<p>{_word_animation(change_text)}</p>'
        '</div><div class="close-rule"></div>'
        '<div class="credit"><div class="credit-label">BY:</div>'
        f'<div class="credit-name">{html.escape(credits["name"])}</div>'
        f'<div><a href="mailto:{html.escape(credits["email"])}">✉ {html.escape(credits["email"])}</a></div>'
        f'<div><a href="tel:{html.escape(credits["phone"])}">☎ {html.escape(credits["phone"])}</a></div>'
        '</div></div>'
        f'<p class="story-source">{html.escape(BPS_SOURCE)}</p></section>'
    )


@st.fragment
def _story_fragment(df: pd.DataFrame, geojson: dict, years: list[int]) -> None:
    _render_css_and_hero(geojson)
    block, index = _active_position()
    if block in {"hero", "map"}:
        _render_map_block(df, geojson, years, index if block == "map" else 0)
    else:
        _render_map_block(df, geojson, years, len(_steps(MAP_VIEWS)) - 1)
    if block in {"chart", "closing"}:
        _render_chart_block(
            df,
            years,
            index if block == "chart" else len(_steps(CHART_VIEWS)) - 1,
        )
    else:
        _render_chart_block(df, years, 0)
    _conclusion(df)


def render_story(df: pd.DataFrame, geojson: dict, unmapped: list[str]) -> None:
    if unmapped:
        print("Provinsi tanpa kelompok pulau:", ", ".join(unmapped))
    years = sorted(int(year) for year in df["tahun"].dropna().unique())
    _story_fragment(df, geojson, years)
