import json
from pathlib import Path

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
                "gene_aliases": "ALIAS2; ALIAS1",
                "major_cell_type": "Immune cell",
                "cell_subtype": "Example cell",
                "tissue": "example tissue",
                "bbsr_verified": "true",
                "submitter": "Example curator",
                "source_title": "Example reference",
                "doi": "10.0000/example",
            }
        ]
    ).to_csv(csv_path, index=False)
    csv_path.write_text("# Documentation comments are ignored during import.\n" + csv_path.read_text())
    db_path = tmp_path / "atlas.duckdb"
    assert import_csv(csv_path, db_path) == 1

    exports = export_all(db_path, tmp_path / "exports")
    assert exports["csv"].exists()
    assert exports["parquet"].exists()
    exported = pd.read_parquet(exports["parquet"])
    assert exported.loc[0, "gene_symbol"] == "GENE1"
    assert list(exported.loc[0, "gene_aliases"]) == ["ALIAS1", "ALIAS2"]
    assert exported.loc[0, "major_cell_type"] == "Immune cell"
    assert exported.loc[0, "cell_subtype"] == "Example cell"
    assert exported.loc[0, "submitter"] == "Example curator"

    index = build_site(db_path, tmp_path / "site")
    assert index.exists()
    rows = json.loads((index.parent / "markers.json").read_text())
    assert rows[0]["cell_type"] == "Example cell"
    assert rows[0]["source_links"] == [
        {"title": "Example reference", "url": "https://doi.org/10.0000/example"}
    ]
    assert 'target="_blank"' in (index.parent / "app.js").read_text()
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


def test_import_reuses_referenced_species_genes_and_cell_types(tmp_path):
    csv_path = tmp_path / "repeated.csv"
    pd.DataFrame(
        [
            {
                "species": "Homo sapiens",
                "gene_symbol": "GENE1",
                "cell_type": "Cell type A",
            },
            {
                "species": "Homo sapiens",
                "gene_symbol": "GENE2",
                "cell_type": "Cell type A",
            },
            {
                "species": "Homo sapiens",
                "gene_symbol": "GENE1",
                "cell_type": "Cell type B",
            },
        ]
    ).to_csv(csv_path, index=False)

    db_path = tmp_path / "atlas.duckdb"
    assert import_csv(csv_path, db_path) == 3

    import duckdb

    with duckdb.connect(str(db_path), read_only=True) as con:
        assert con.execute("SELECT count(*) FROM species").fetchone()[0] == 1
        assert con.execute("SELECT count(*) FROM genes").fetchone()[0] == 2
        assert con.execute("SELECT count(*) FROM cell_types").fetchone()[0] == 2
        assert con.execute("SELECT count(*) FROM marker_assertions").fetchone()[0] == 3


def test_import_template_documents_all_supported_columns():
    template = Path("data/import_template.csv")
    text = template.read_text()
    assert text.startswith("# MarkerCodex bulk import template")
    columns = set(pd.read_csv(template, comment="#").columns)
    assert columns == {
        "species",
        "species_common_name",
        "gene_symbol",
        "gene_aliases",
        "stable_id",
        "major_cell_type",
        "cell_subtype",
        "ontology_id",
        "marker_direction",
        "tissue",
        "condition",
        "developmental_stage",
        "assay",
        "confidence",
        "bbsr_verified",
        "submitter",
        "notes",
        "source_title",
        "citation",
        "doi",
        "pmid",
        "url",
        "evidence_type",
        "evidence_location",
        "evidence_note",
    }
