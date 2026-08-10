import json

import pandas as pd

from markercodex.export import build_site, export_all
from markercodex.importer import import_csv


def test_import_export_and_site_build(tmp_path):
    csv_path = tmp_path / "input.csv"
    pd.DataFrame(
        [
            {
                "species": "Homo sapiens",
                "species_common_name": "human",
                "gene_symbol": "GENE1",
                "cell_type": "Example cell",
                "tissue": "example tissue",
                "human_verified": "true",
                "source_title": "Example reference",
                "doi": "10.0000/example",
            }
        ]
    ).to_csv(csv_path, index=False)
    db_path = tmp_path / "atlas.duckdb"
    assert import_csv(csv_path, db_path) == 1

    exports = export_all(db_path, tmp_path / "exports")
    assert exports["csv"].exists()
    assert exports["parquet"].exists()
    exported = pd.read_parquet(exports["parquet"])
    assert exported.loc[0, "gene_symbol"] == "GENE1"

    index = build_site(db_path, tmp_path / "site")
    assert index.exists()
    rows = json.loads((index.parent / "markers.json").read_text())
    assert rows[0]["cell_type"] == "Example cell"
    assert (index.parent / ".nojekyll").exists()


def test_import_requires_core_columns(tmp_path):
    csv_path = tmp_path / "bad.csv"
    csv_path.write_text("gene_symbol\nGENE1\n")
    try:
        import_csv(csv_path, tmp_path / "atlas.duckdb")
    except ValueError as exc:
        assert "Missing required columns" in str(exc)
    else:
        raise AssertionError("Expected ValueError")
