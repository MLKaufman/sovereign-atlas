"""Validated operations shared by the CLI, tests, and Streamlit curator."""

from __future__ import annotations

from typing import Any

import duckdb


def upsert_species(
    con: duckdb.DuckDBPyConnection,
    scientific_name: str,
    common_name: str | None = None,
    taxonomy_id: int | None = None,
) -> int:
    scientific_name = scientific_name.strip()
    existing = con.execute(
        "SELECT species_id FROM species WHERE scientific_name = ?", [scientific_name]
    ).fetchone()
    if existing:
        return existing[0]
    con.execute(
        "INSERT INTO species(scientific_name, common_name, taxonomy_id) VALUES (?, ?, ?)",
        [scientific_name, common_name or None, taxonomy_id],
    )
    return con.execute(
        "SELECT species_id FROM species WHERE scientific_name = ?", [scientific_name]
    ).fetchone()[0]


def set_gene_aliases(
    con: duckdb.DuckDBPyConnection, gene_id: int, aliases: list[str]
) -> None:
    normalized = sorted({alias.strip() for alias in aliases if alias.strip()})
    con.execute("DELETE FROM gene_aliases WHERE gene_id = ?", [gene_id])
    if normalized:
        con.executemany(
            "INSERT INTO gene_aliases(gene_id, alias) VALUES (?, ?)",
            [[gene_id, alias] for alias in normalized],
        )


def upsert_gene(
    con: duckdb.DuckDBPyConnection,
    species_id: int,
    symbol: str,
    stable_id: str | None = None,
    aliases: list[str] | None = None,
) -> int:
    symbol = symbol.strip()
    if not symbol:
        raise ValueError("Gene symbol is required")
    existing = con.execute(
        "SELECT gene_id FROM genes WHERE species_id = ? AND symbol = ?", [species_id, symbol]
    ).fetchone()
    if existing:
        if aliases is not None:
            set_gene_aliases(con, existing[0], aliases)
        return existing[0]
    con.execute(
        "INSERT INTO genes(species_id, symbol, stable_id) VALUES (?, ?, ?)",
        [species_id, symbol, stable_id or None],
    )
    gene_id = con.execute(
        "SELECT gene_id FROM genes WHERE species_id = ? AND symbol = ?", [species_id, symbol]
    ).fetchone()[0]
    if aliases is not None:
        set_gene_aliases(con, gene_id, aliases)
    return gene_id


def upsert_cell_type(
    con: duckdb.DuckDBPyConnection,
    name: str,
    ontology_id: str | None = None,
    description: str | None = None,
    parent_cell_type_id: int | None = None,
) -> int:
    name = name.strip()
    if not name:
        raise ValueError("Cell type is required")
    ontology_id = ontology_id or ""
    existing = con.execute(
        "SELECT cell_type_id FROM cell_types WHERE name = ? AND ontology_id = ?",
        [name, ontology_id],
    ).fetchone()
    if existing:
        return existing[0]
    con.execute(
        "INSERT INTO cell_types(name, ontology_id, description, parent_cell_type_id) VALUES (?, ?, ?, ?)",
        [name, ontology_id, description or None, parent_cell_type_id],
    )
    return con.execute(
        "SELECT cell_type_id FROM cell_types WHERE name = ? AND ontology_id = ?",
        [name, ontology_id],
    ).fetchone()[0]


def add_assertion(
    con: duckdb.DuckDBPyConnection,
    *,
    gene_id: int,
    cell_type_id: int,
    marker_direction: str = "positive",
    tissue: str = "",
    condition: str = "",
    developmental_stage: str = "",
    assay: str = "scRNA-seq",
    confidence: str = "moderate",
    bbsr_verified: bool = False,
    submitter: str | None = None,
    notes: str | None = None,
) -> int:
    values: list[Any] = [
        gene_id,
        cell_type_id,
        marker_direction,
        tissue,
        condition,
        developmental_stage,
        assay,
        confidence,
        bbsr_verified,
        submitter or None,
        notes or None,
    ]
    con.execute(
        """INSERT INTO marker_assertions(
          gene_id, cell_type_id, marker_direction, tissue, condition,
          developmental_stage, assay, confidence, bbsr_verified, submitter, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(gene_id, cell_type_id, marker_direction, tissue, condition, developmental_stage, assay)
        DO UPDATE SET confidence = excluded.confidence,
          bbsr_verified = excluded.bbsr_verified, submitter = excluded.submitter,
          notes = excluded.notes,
          updated_at = now()""",
        values,
    )
    return con.execute(
        """SELECT assertion_id FROM marker_assertions WHERE gene_id = ? AND cell_type_id = ?
        AND marker_direction = ? AND tissue = ? AND condition = ?
        AND developmental_stage = ? AND assay = ?""",
        values[:7],
    ).fetchone()[0]


def add_source(
    con: duckdb.DuckDBPyConnection,
    *,
    title: str,
    citation: str | None = None,
    doi: str | None = None,
    pmid: str | None = None,
    url: str | None = None,
    publication_year: int | None = None,
    source_type: str = "publication",
    notes: str | None = None,
) -> int:
    if not title.strip():
        raise ValueError("Source title is required")
    con.execute(
        """INSERT INTO sources(title, citation, doi, pmid, url, publication_year, source_type, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            title.strip(),
            citation or None,
            doi or None,
            pmid or None,
            url or None,
            publication_year,
            source_type,
            notes or None,
        ],
    )
    return con.execute("SELECT currval('reference_id_seq')").fetchone()[0]


def link_evidence(
    con: duckdb.DuckDBPyConnection,
    assertion_id: int,
    source_id: int,
    evidence_type: str = "reported_marker",
    location: str = "",
    evidence_note: str | None = None,
) -> int:
    con.execute(
        """INSERT INTO evidence(assertion_id, source_id, evidence_type, location, evidence_note)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(assertion_id, source_id, evidence_type, location)
        DO UPDATE SET evidence_note = excluded.evidence_note""",
        [assertion_id, source_id, evidence_type, location, evidence_note or None],
    )
    return con.execute(
        "SELECT evidence_id FROM evidence WHERE assertion_id=? AND source_id=? AND evidence_type=? AND location=?",
        [assertion_id, source_id, evidence_type, location],
    ).fetchone()[0]
