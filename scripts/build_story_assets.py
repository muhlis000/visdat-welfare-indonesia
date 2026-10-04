"""Build compact, static assets consumed by the Streamlit story at runtime."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

import geopandas as gpd
import pandas as pd
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
STATIC_DIR = APP_DIR / "static"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from components.common import (  # noqa: E402
    INDICATORS,
    add_pulau,
    escape_tooltip,
    format_number,
    values_to_rgba,
)

DEFAULT_SOURCE = ROOT / "data" / "processed" / "df_geo.parquet"
GEOMETRY_METRICS = ("persen_miskin", "IPM", "P1")
OVERVIEW_TOLERANCE = 0.1
DETAIL_TOLERANCE = 0.01
COORDINATE_PRECISION = 0.001
REQUIRED_COLUMNS = (
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
)


def _silhouette_svg(gdf: gpd.GeoDataFrame) -> str:
    dissolved = unary_union(
        gdf.geometry.simplify(0.08, preserve_topology=True).tolist()
    )
    min_x, min_y, max_x, max_y = 94, -12, 142, 8
    width, height = 1000, 420

    def project(x: float, y: float) -> tuple[float, float]:
        return (
            (x - min_x) / (max_x - min_x) * width,
            (max_y - y) / (max_y - min_y) * height,
        )

    polygons = [dissolved] if dissolved.geom_type == "Polygon" else list(dissolved.geoms)
    paths: list[str] = []
    for polygon in polygons:
        coordinates = list(polygon.exterior.coords)
        if len(coordinates) < 4:
            continue
        points = [project(coordinate[0], coordinate[1]) for coordinate in coordinates]
        paths.append(
            "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in points) + " Z"
        )
    if not paths:
        raise ValueError("Could not create a non-empty silhouette from source geometry.")
    return (
        f'<svg class="hero-map" viewBox="0 0 {width} {height}" aria-hidden="true">'
        f'<path d="{" ".join(paths)}"/></svg>'
    )


def _feature_collection(
    geometries: gpd.GeoDataFrame,
    values_by_code: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], int]:
    features = []
    coordinate_count = 0
    for row in geometries.itertuples(index=False):
        code = str(row.kode_kab)
        geometry = row.geometry.__geo_interface__
        feature_values = values_by_code[code]

        def count_coordinates(value: Any) -> int:
            if isinstance(value, (tuple, list)):
                if len(value) >= 2 and all(
                    isinstance(component, (int, float)) for component in value[:2]
                ):
                    return 1
                return sum(count_coordinates(item) for item in value)
            return 0

        coordinate_count += count_coordinates(geometry["coordinates"])
        features.append(
            {
                "type": "Feature",
                "geometry": geometry,
                "properties": {
                    "kode_kab": code,
                    "nama_kab": escape_tooltip(row.nama_kab),
                    "nama_prov": escape_tooltip(row.nama_prov),
                    "fill_color": [183, 190, 185, 90],
                    **feature_values,
                },
            }
        )
    return {"type": "FeatureCollection", "features": features}, coordinate_count


def _sha256_file(path: Path) -> str:
    with path.open("rb") as source_file:
        return hashlib.file_digest(source_file, "sha256").hexdigest()


def _geometry_values(
    data: pd.DataFrame,
    codes: list[str],
    years: list[int],
    metrics: tuple[str, ...],
    *,
    include_elevation: bool,
) -> dict[str, dict[str, Any]]:
    values_by_code: dict[str, dict[str, Any]] = {code: {} for code in codes}
    for metric in metrics:
        meta = INDICATORS[metric]
        for year in years:
            year_data = data.loc[data["tahun"] == year].set_index("kode_kab")
            metric_values = pd.to_numeric(
                year_data[metric].reindex(codes), errors="coerce"
            )
            colors = values_to_rgba(
                metric_values,
                meta["colorscale"],
                reverse=not meta["higher_is_worse"],
                alpha=200,
            )
            valid_max = metric_values.max(skipna=True)
            for index, code in enumerate(codes):
                value = metric_values.iloc[index]
                safe_metric = metric.replace("-", "_")
                values_by_code[code][f"color_{safe_metric}_{year}"] = colors[index]
                values_by_code[code][f"value_{safe_metric}_{year}"] = format_number(
                    value, meta["unit"]
                )
                if include_elevation:
                    values_by_code[code][f"elevation_{safe_metric}_{year}"] = (
                        float(value) / float(valid_max) * 180000
                        if pd.notna(value) and valid_max and valid_max != 0
                        else 0.0
                    )
    return values_by_code


def build_story_assets(source: Path, output_dir: Path) -> None:
    if not source.is_file():
        raise FileNotFoundError(f"Source GeoParquet not found: {source}")

    gdf = gpd.read_parquet(source)
    missing = [column for column in REQUIRED_COLUMNS if column not in gdf.columns]
    if missing:
        raise ValueError(f"Source is missing required columns: {', '.join(missing)}")
    if gdf["kode_kab"].isna().any():
        raise ValueError("Source has null kode_kab values.")
    gdf["kode_kab"] = gdf["kode_kab"].astype(str).str.strip().str.zfill(4)
    gdf["tahun"] = pd.to_numeric(gdf["tahun"], errors="raise").astype(int)
    if gdf.duplicated(["kode_kab", "tahun"]).any():
        raise ValueError("Source has duplicate kode_kab/tahun rows.")
    if gdf.geometry.isna().any() or gdf.geometry.is_empty.any():
        raise ValueError("Source has null or empty geometries.")
    if not gdf.geometry.is_valid.all():
        raise ValueError("Source has invalid geometries.")

    geometry_hashes = gdf.assign(_wkb=gdf.geometry.to_wkb()).groupby("kode_kab")[
        "_wkb"
    ].nunique()
    if (geometry_hashes > 1).any():
        raise ValueError(
            "Source has geometries that differ across years for the same kode_kab."
        )

    codes = sorted(gdf["kode_kab"].unique())
    years = sorted(gdf["tahun"].unique().tolist())
    if not years:
        raise ValueError("Source has no year values.")

    data = pd.DataFrame(gdf.drop(columns="geometry"))
    data = add_pulau(data)
    unmapped = sorted(
        data.loc[data["pulau"] == "Lainnya", "nama_prov"].dropna().unique().tolist()
    )
    if unmapped:
        raise ValueError(f"Unmapped provinces in source data: {', '.join(unmapped)}")

    detailed_geometry = (
        gdf.sort_values(["kode_kab", "tahun"])
        .drop_duplicates("kode_kab")
        .set_index("kode_kab")
        .reindex(codes)[["nama_kab", "nama_prov", "geometry"]]
        .copy()
    )
    detailed_geometry = gpd.GeoDataFrame(
        detailed_geometry, geometry="geometry", crs=gdf.crs
    )
    points = detailed_geometry.geometry.simplify(
        DETAIL_TOLERANCE, preserve_topology=True
    ).representative_point()
    point_data = pd.DataFrame(
        {
            "kode_kab": codes,
            "lon": [point.x for point in points],
            "lat": [point.y for point in points],
        }
    )
    data = data.merge(point_data, on="kode_kab", how="left", validate="many_to_one")
    data["tahun"] = data["tahun"].astype(int)
    overview_values = _geometry_values(
        data, codes, years, ("persen_miskin",), include_elevation=False
    )
    detail_values = _geometry_values(
        data, codes, years, GEOMETRY_METRICS, include_elevation=True
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    outputs: dict[str, dict[str, Any]] = {}
    with tempfile.TemporaryDirectory(prefix=".story-assets-", dir=output_dir) as temp:
        staged_dir = Path(temp)
        for name, tolerance, map_values in (
            ("overview", OVERVIEW_TOLERANCE, overview_values),
            ("detail", DETAIL_TOLERANCE, detail_values),
        ):
            simplified = detailed_geometry.copy()
            simplified["geometry"] = simplified.geometry.simplify(
                tolerance, preserve_topology=True
            )
            simplified["geometry"] = simplified.geometry.set_precision(
                COORDINATE_PRECISION
            )
            if simplified.geometry.is_empty.any() or not simplified.geometry.is_valid.all():
                raise ValueError(
                    f"{name} geometry became empty or invalid after simplification."
                )
            collection, coordinate_count = _feature_collection(
                simplified.reset_index(), map_values
            )
            target = staged_dir / f"kabkota-{name}.json"
            target.write_text(
                json.dumps(
                    collection,
                    ensure_ascii=False,
                    separators=(",", ":"),
                    allow_nan=False,
                ),
                encoding="utf-8",
            )
            if name == "overview" and target.stat().st_size > 1_000_000:
                raise ValueError(
                    "Overview GeoJSON exceeds the 1 MB target "
                    f"({target.stat().st_size:,} bytes)."
                )
            outputs[name] = {
                "path": target.name,
                "bytes": target.stat().st_size,
                "coordinate_count": coordinate_count,
                "tolerance_degrees": tolerance,
            }

        story_data_path = staged_dir / "story-data.json"
        story_data_path.write_text(
            data.to_json(
                orient="records",
                force_ascii=False,
                double_precision=6,
            ),
            encoding="utf-8",
        )
        source_hash = _sha256_file(source)

        silhouette_path = staged_dir / "indonesia-silhouette.svg"
        silhouette_path.write_text(
            _silhouette_svg(detailed_geometry), encoding="utf-8"
        )
        version_hash = hashlib.sha256(source_hash.encode("ascii"))
        for filename in (
            "kabkota-overview.json",
            "kabkota-detail.json",
            "story-data.json",
            "indonesia-silhouette.svg",
        ):
            version_hash.update(filename.encode("utf-8"))
            version_hash.update(_sha256_file(staged_dir / filename).encode("ascii"))
        manifest = {
            "schema_version": 1,
            "source_sha256": source_hash,
            "asset_version": version_hash.hexdigest(),
            "row_count": len(data),
            "unique_codes": len(codes),
            "years": years,
            "island_codes": data.groupby("pulau")["kode_kab"].nunique().sort_index().to_dict(),
            "unmapped_provinces": unmapped,
            "geometry_issues": {
                "empty_geometry": 0,
                "unmatched_codes": 0,
                "inconsistent_geometry": 0,
            },
            "story_data_bytes": story_data_path.stat().st_size,
            "map_assets": outputs,
            "coordinate_precision_degrees": COORDINATE_PRECISION,
        }
        manifest_path = staged_dir / "story-manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        for filename in (
            "kabkota-overview.json",
            "kabkota-detail.json",
            "story-data.json",
            "indonesia-silhouette.svg",
            "story-manifest.json",
        ):
            os.replace(staged_dir / filename, output_dir / filename)

    print(json.dumps(manifest, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output-dir", type=Path, default=STATIC_DIR)
    args = parser.parse_args()
    build_story_assets(args.source, args.output_dir)


if __name__ == "__main__":
    main()
