"""Portable data and static-site exports."""

from __future__ import annotations

import json
import shutil
from importlib.resources import files
from pathlib import Path

from markercodex.db import database, initialize


def export_all(db_path: str | Path, output_dir: str | Path = "data/exports") -> dict[str, Path]:
    initialize(db_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    parquet = output_dir / "markers.parquet"
    csv = output_dir / "markers.csv"
    with database(db_path, read_only=True) as con:
        con.execute(
            "COPY (SELECT * FROM marker_atlas ORDER BY species, cell_type, gene_symbol) TO ? (FORMAT PARQUET, COMPRESSION ZSTD)",
            [str(parquet)],
        )
        con.execute(
            "COPY (SELECT * FROM marker_atlas ORDER BY species, cell_type, gene_symbol) TO ? (HEADER, DELIMITER ',')",
            [str(csv)],
        )
    return {"parquet": parquet, "csv": csv}


def build_site(db_path: str | Path, site_dir: str | Path = "site") -> Path:
    initialize(db_path)
    site_dir = Path(site_dir)
    site_dir.mkdir(parents=True, exist_ok=True)
    template = files("markercodex").joinpath("site_template")
    for name in ("index.html", "app.js", "styles.css"):
        shutil.copyfile(str(template.joinpath(name)), site_dir / name)
    with database(db_path, read_only=True) as con:
        df = con.execute(
            "SELECT * FROM marker_atlas ORDER BY species, cell_type, gene_symbol"
        ).fetchdf()
    records = json.loads(df.to_json(orient="records", date_format="iso"))
    (site_dir / "markers.json").write_text(json.dumps(records, indent=2), encoding="utf-8")
    (site_dir / ".nojekyll").touch()
    return site_dir / "index.html"
