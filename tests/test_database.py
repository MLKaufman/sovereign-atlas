from markercodex.db import database, initialize
from markercodex.operations import (
    add_assertion,
    add_source,
    link_evidence,
    upsert_cell_type,
    upsert_gene,
    upsert_species,
)


def test_initialize_is_idempotent(tmp_path):
    path = tmp_path / "atlas.duckdb"
    initialize(path)
    initialize(path)
    with database(path, read_only=True) as con:
        assert con.execute("SELECT count(*) FROM schema_migrations").fetchone()[0] == 5
        assert con.execute("SELECT count(*) FROM marker_atlas").fetchone()[0] == 0


def test_gene_can_mark_multiple_cell_types_with_shared_source(tmp_path):
    path = tmp_path / "atlas.duckdb"
    initialize(path)
    with database(path) as con:
        species_id = upsert_species(con, "Homo sapiens", "human", 9606)
        gene_id = upsert_gene(con, species_id, "GENE1")
        source_id = add_source(con, title="Example study", doi="10.0000/example")
        for name in ("Cell type A", "Cell type B"):
            cell_type_id = upsert_cell_type(con, name)
            assertion_id = add_assertion(
                con, gene_id=gene_id, cell_type_id=cell_type_id, tissue="example"
            )
            link_evidence(con, assertion_id, source_id)
        rows = con.execute(
            "SELECT gene_symbol, cell_type, evidence_count FROM marker_atlas ORDER BY cell_type"
        ).fetchall()
    assert rows == [("GENE1", "Cell type A", 1), ("GENE1", "Cell type B", 1)]


def test_upsert_assertion_updates_curation_fields(tmp_path):
    path = tmp_path / "atlas.duckdb"
    initialize(path)
    with database(path) as con:
        species_id = upsert_species(con, "Mus musculus", "mouse", 10090)
        gene_id = upsert_gene(con, species_id, "Gene1")
        cell_id = upsert_cell_type(con, "Example cell")
        first = add_assertion(con, gene_id=gene_id, cell_type_id=cell_id)
        second = add_assertion(
            con,
            gene_id=gene_id,
            cell_type_id=cell_id,
            confidence="high",
            bbsr_verified=True,
            submitter="BBSR curator",
        )
        value = con.execute(
            "SELECT confidence, bbsr_verified, submitter FROM marker_assertions WHERE assertion_id=?",
            [first],
        ).fetchone()
    assert first == second
    assert value == ("high", True, "BBSR curator")


def test_cell_type_without_ontology_is_not_duplicated(tmp_path):
    path = tmp_path / "atlas.duckdb"
    initialize(path)
    with database(path) as con:
        first = upsert_cell_type(con, "Shared type")
        second = upsert_cell_type(con, "Shared type")
        count = con.execute("SELECT count(*) FROM cell_types").fetchone()[0]
    assert first == second
    assert count == 1
