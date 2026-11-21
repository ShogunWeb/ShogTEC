#!/usr/bin/env python3
"""Generate compact per-region line geometries from GTFS trips/shapes/routes.

Outputs files in data/:
- line_shapes_LG.js
- line_shapes_CHOI.js
- line_shapes_BW.js
- line_shapes_H.js
- line_shapes_NAM.js
- line_shapes_LUX.js

Each file sets window.lineShapesChunk = { lineShortName: [polyline1, polyline2, ...] }
where each polyline is [[lat, lon], ...].
"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

ROUTES_TXT = DATA / "routes.txt"
TRIPS_TXT = DATA / "trips.txt"
SHAPES_TXT = DATA / "shapes.txt"

REGION_BY_ROUTE_PREFIX = {
    "L": "LG",
    "C": "CHOI",
    "B": "BW",
    "H": "H",
    "N": "NAM",
    "X": "LUX",
}

OUTPUT_REGIONS = ["LG", "CHOI", "BW", "H", "NAM", "LUX"]

# Keep geometry payload bounded.
MAX_SHAPES_PER_LINE = 10
MAX_POINTS_PER_SHAPE = 120
ROUND_DIGITS = 5


def simplify_points(points: list[tuple[float, float]]) -> list[list[float]]:
    if len(points) <= 2:
        return [[round(lat, ROUND_DIGITS), round(lon, ROUND_DIGITS)] for lat, lon in points]

    stride = max(1, len(points) // MAX_POINTS_PER_SHAPE)
    sampled = [points[0]]
    for i in range(1, len(points) - 1):
        if i % stride == 0:
            sampled.append(points[i])
    sampled.append(points[-1])

    compact = []
    prev = None
    for lat, lon in sampled:
        pair = (round(lat, ROUND_DIGITS), round(lon, ROUND_DIGITS))
        if pair != prev:
            compact.append([pair[0], pair[1]])
            prev = pair
    return compact


def shape_signature(polyline: list[list[float]]) -> str:
    if not polyline:
        return ""
    start = polyline[0]
    end = polyline[-1]
    return f"{start[0]},{start[1]}->{end[0]},{end[1]}:{len(polyline)}"


def main() -> None:
    for required in [ROUTES_TXT, TRIPS_TXT, SHAPES_TXT]:
        if not required.exists():
            raise FileNotFoundError(f"Missing required input: {required}")

    route_short_by_id: dict[str, str] = {}
    with ROUTES_TXT.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            route_id = row.get("route_id", "")
            rsn = (row.get("route_short_name", "") or "").strip()
            if route_id and rsn:
                route_short_by_id[route_id] = rsn.upper()

    # region -> line -> set(shape_id)
    shape_ids_by_region_line: dict[str, dict[str, set[str]]] = {
        region: defaultdict(set) for region in OUTPUT_REGIONS
    }

    # shape_id -> set((region, line))
    owners_by_shape: dict[str, set[tuple[str, str]]] = defaultdict(set)

    with TRIPS_TXT.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            route_id = row.get("route_id", "")
            shape_id = row.get("shape_id", "")
            if not route_id or not shape_id:
                continue

            line = route_short_by_id.get(route_id, "").upper()
            if not line:
                continue

            region = REGION_BY_ROUTE_PREFIX.get(route_id[0].upper())
            if not region:
                continue

            shape_ids_by_region_line[region][line].add(shape_id)
            owners_by_shape[shape_id].add((region, line))

    # Collect ordered points by shape id.
    points_by_shape: dict[str, list[tuple[int, float, float]]] = defaultdict(list)

    with SHAPES_TXT.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            shape_id = row.get("shape_id", "")
            if shape_id not in owners_by_shape:
                continue
            try:
                lat = float(row["shape_pt_lat"])
                lon = float(row["shape_pt_lon"])
                seq = int(float(row["shape_pt_sequence"]))
            except (ValueError, KeyError, TypeError):
                continue
            points_by_shape[shape_id].append((seq, lat, lon))

    output_data: dict[str, dict[str, list[list[list[float]]]]] = {
        region: {} for region in OUTPUT_REGIONS
    }

    for shape_id, owners in owners_by_shape.items():
        ordered = sorted(points_by_shape.get(shape_id, []), key=lambda x: x[0])
        if len(ordered) < 2:
            continue

        simplified = simplify_points([(lat, lon) for _, lat, lon in ordered])
        if len(simplified) < 2:
            continue

        sig = shape_signature(simplified)
        if not sig:
            continue

        for region, line in owners:
            bucket = output_data[region].setdefault(line, [])
            # Basic dedupe on coarse signature.
            known = {shape_signature(poly) for poly in bucket}
            if sig in known:
                continue
            if len(bucket) >= MAX_SHAPES_PER_LINE:
                continue
            bucket.append(simplified)

    for region in OUTPUT_REGIONS:
        target = DATA / f"line_shapes_{region}.js"
        payload = output_data[region]
        js = "window.lineShapesChunk = " + json.dumps(payload, separators=(",", ":"), ensure_ascii=False) + ";\n"
        target.write_text(js, encoding="utf-8")
        print(f"Wrote {target.name}: {len(payload)} lines")


if __name__ == "__main__":
    main()
