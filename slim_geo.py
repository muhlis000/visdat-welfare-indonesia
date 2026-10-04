"""Simplify the local GeoParquet geometry without dropping any attributes."""

from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path

import geopandas as gpd
import pyarrow.parquet as pq


DEFAULT_SRC = Path("data/_big_local/df_geo.parquet")
DEFAULT_DST = Path("data/processed/df_geo.parquet")
MAX_OUTPUT_MB = 25


def _empty_geometry_count(geometries: gpd.GeoSeries) -> int:
    return int((geometries.isna() | geometries.is_empty).sum())


def _valid_codes(gdf: gpd.GeoDataFrame) -> set[str]:
    valid = gdf.geometry.notna() & ~gdf.geometry.is_empty & gdf.geometry.is_valid
    return set(gdf.loc[valid, "kode_kab"].dropna().astype(str))


def _geometry_hashes_by_code(gdf: gpd.GeoDataFrame) -> dict[str, set[str]]:
    hashes: dict[str, set[str]] = {}
    for code, geometry in zip(gdf["kode_kab"], gdf.geometry.array):
        key = str(code)
        digest = (
            hashlib.sha256(geometry.wkb).hexdigest()
            if geometry is not None
            else "missing"
        )
        hashes.setdefault(key, set()).add(digest)
    return hashes


def _inconsistent_codes(hashes: dict[str, set[str]]) -> list[str]:
    return sorted(code for code, values in hashes.items() if len(values) > 1)


def slim_geo(src: Path, dst: Path, tolerance: float) -> None:
    if tolerance <= 0:
        raise ValueError("--tol must be greater than zero.")
    if not src.is_file():
        raise FileNotFoundError(f"Source GeoParquet not found: {src}")

    gdf = gpd.read_parquet(src)
    if "geometry" not in gdf.columns or gdf.geometry.name not in gdf.columns:
        raise ValueError(f"Source has no active geometry column: {src}")
    if "kode_kab" not in gdf.columns:
        raise ValueError("Source GeoParquet has no kode_kab column.")

    original_rows = len(gdf)
    original_columns = list(gdf.columns)
    original_crs = gdf.crs
    empty_before = _empty_geometry_count(gdf.geometry)
    valid_codes_before = _valid_codes(gdf)
    inconsistent_before = _inconsistent_codes(_geometry_hashes_by_code(gdf))
    if inconsistent_before:
        sample = ", ".join(inconsistent_before[:10])
        raise ValueError(
            "Source geometry differs across years for "
            f"{len(inconsistent_before)} kode_kab (sample: {sample})."
        )

    gdf["geometry"] = gdf.geometry.simplify(
        tolerance, preserve_topology=True
    )

    if len(gdf) != original_rows:
        raise ValueError("Row count changed during geometry simplification.")
    if list(gdf.columns) != original_columns:
        raise ValueError("Column list or order changed during simplification.")
    if gdf.crs != original_crs:
        raise ValueError(f"CRS changed from {original_crs} to {gdf.crs}.")

    empty_after = _empty_geometry_count(gdf.geometry)
    if empty_after > empty_before:
        raise ValueError(
            f"Empty geometries increased from {empty_before} to {empty_after}."
        )
    valid_codes_after = _valid_codes(gdf)
    if valid_codes_after != valid_codes_before:
        missing = sorted(valid_codes_before - valid_codes_after)
        added = sorted(valid_codes_after - valid_codes_before)
        raise ValueError(
            "Unique kode_kab with valid geometry changed; "
            f"lost={missing[:10]}, added={added[:10]}."
        )
    inconsistent_after = _inconsistent_codes(_geometry_hashes_by_code(gdf))
    if inconsistent_after:
        sample = ", ".join(inconsistent_after[:10])
        raise ValueError(
            "Simplified geometry differs across years for "
            f"{len(inconsistent_after)} kode_kab (sample: {sample})."
        )

    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(f"{dst.name}.tmp.{os.getpid()}")
    try:
        gdf.to_parquet(tmp, index=False, compression="zstd")
        metadata = pq.ParquetFile(tmp).metadata
        if metadata.num_rows != original_rows:
            raise ValueError(
                f"Temporary parquet has {metadata.num_rows} rows; expected {original_rows}."
            )
        output_mb = tmp.stat().st_size / (1024 * 1024)
        if output_mb >= MAX_OUTPUT_MB:
            raise ValueError(
                f"Output is {output_mb:.2f} MB; it must be smaller than "
                f"{MAX_OUTPUT_MB} MB. Retry with a larger --tol."
            )
        os.replace(tmp, dst)
    except Exception:
        if tmp.exists():
            tmp.unlink()
        raise

    source_mb = src.stat().st_size / (1024 * 1024)
    result_mb = dst.stat().st_size / (1024 * 1024)
    print(f"Source: {src} ({source_mb:.2f} MB)")
    print(f"Output: {dst} ({result_mb:.2f} MB)")
    print(f"Tolerance: {tolerance} degrees")
    print(f"Rows: {original_rows}")
    print(f"Unique kode_kab: {gdf['kode_kab'].nunique(dropna=True)}")
    print(f"Empty geometries: {empty_before} -> {empty_after}")
    print(f"CRS: {original_crs}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tol", type=float, default=0.01)
    parser.add_argument("--src", type=Path, default=DEFAULT_SRC)
    parser.add_argument("--dst", type=Path, default=DEFAULT_DST)
    args = parser.parse_args()
    slim_geo(args.src, args.dst, args.tol)


if __name__ == "__main__":
    main()
