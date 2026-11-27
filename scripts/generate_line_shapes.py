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
import math
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
MAX_DEVIATION_METERS = 5
ROUND_DIGITS = 5


def simplify_points(points: list[tuple[float, float]]) -> list[list[float]]:
    if len(points) <= 2:
        return [[round(lat, ROUND_DIGITS), round(lon, ROUND_DIGITS)] for lat, lon in points]

    earth_radius_meters = 6_371_000
    origin_lat, origin_lon = points[0]
    latitude_scale = math.pi * earth_radius_meters / 180
    longitude_scale = latitude_scale * math.cos(math.radians(sum(lat for lat, _ in points) / len(points)))
    projected = [
        (
            (lon - origin_lon) * longitude_scale,
            (lat - origin_lat) * latitude_scale,
        )
        for lat, lon in points
    ]

    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    sections = [(0, len(points) - 1)]

    while sections:
        start_index, end_index = sections.pop()
        start_x, start_y = projected[start_index]
        end_x, end_y = projected[end_index]
        segment_x = end_x - start_x
        segment_y = end_y - start_y
        segment_length_squared = segment_x * segment_x + segment_y * segment_y

        max_distance = 0.0
        max_index = None
        for index in range(start_index + 1, end_index):
            point_x, point_y = projected[index]
            if segment_length_squared == 0:
                distance = math.hypot(point_x - start_x, point_y - start_y)
            else:
                projection = (
                    (point_x - start_x) * segment_x
                    + (point_y - start_y) * segment_y
                ) / segment_length_squared
                projection = min(1.0, max(0.0, projection))
                closest_x = start_x + projection * segment_x
                closest_y = start_y + projection * segment_y
                distance = math.hypot(point_x - closest_x, point_y - closest_y)

            if distance > max_distance:
                max_distance = distance
                max_index = index

        if max_index is not None and max_distance > MAX_DEVIATION_METERS:
            keep[max_index] = True
            sections.append((start_index, max_index))
            sections.append((max_index, end_index))

    compact = []
    previous_pair = None
    for keep_point, (lat, lon) in zip(keep, points):
        if not keep_point:
            continue
        pair = (round(lat, ROUND_DIGITS), round(lon, ROUND_DIGITS))
        if pair != previous_pair:
            compact.append([pair[0], pair[1]])
            previous_pair = pair
    return compact


def shape_signature(polyline: list[list[float]]) -> str:
    if not polyline:
        return ""
    start = polyline[0]
    end = polyline[-1]
    return f"{start[0]},{start[1]}->{end[0]},{end[1]}:{len(polyline)}"


def region_for_route_id(route_id: str) -> str | None:
    route_code = route_id.rsplit(":", maxsplit=1)[-1]
    return REGION_BY_ROUTE_PREFIX.get(route_code[:1].upper())


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

            region = region_for_route_id(route_id)
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
