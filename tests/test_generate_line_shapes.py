import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import generate_line_shapes


class GenerateLineShapesTests(unittest.TestCase):
    def test_generates_region_shapes_from_prefixed_tec_route_ids(self):
        with tempfile.TemporaryDirectory() as temporary:
            data_dir = Path(temporary)
            routes_file = data_dir / "routes.txt"
            trips_file = data_dir / "trips.txt"
            shapes_file = data_dir / "shapes.txt"

            routes_file.write_text(
                "route_id,route_short_name\n"
                "gr:tec:C0001-21650,12\n",
                encoding="utf-8",
            )
            trips_file.write_text(
                "route_id,shape_id\n"
                "gr:tec:C0001-21650,shape-1\n",
                encoding="utf-8",
            )
            shapes_file.write_text(
                "shape_id,shape_pt_lat,shape_pt_lon,shape_pt_sequence\n"
                "shape-1,50.0,5.0,1\n"
                "shape-1,50.1,5.1,2\n",
                encoding="utf-8",
            )

            with (
                patch.object(generate_line_shapes, "DATA", data_dir),
                patch.object(generate_line_shapes, "ROUTES_TXT", routes_file),
                patch.object(generate_line_shapes, "TRIPS_TXT", trips_file),
                patch.object(generate_line_shapes, "SHAPES_TXT", shapes_file),
            ):
                generate_line_shapes.main()

            generated_file = data_dir / "line_shapes_CHOI.js"
            generated_data = json.loads(
                generated_file.read_text(encoding="utf-8")
                .removeprefix("window.lineShapesChunk = ")
                .removesuffix(";\n")
            )

            self.assertEqual(generated_data["12"], [[[50.0, 5.0], [50.1, 5.1]]])


if __name__ == "__main__":
    unittest.main()
