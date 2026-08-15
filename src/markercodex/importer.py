"""Bulk import from a human-editable CSV file."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from markercodex.db import database, initialize
from markercodex.operations import (
    add_assertion,
    add_source,
    link_evidence,
    upsert_cell_type,
    upsert_gene,
    upsert_species,
)

REQUIRED_COLUMNS = {"species", "gene_symbol"}


def import_csv(
    path: str | Path, db_path: str | Path, *, default_common_name: str | None = None
) -> int:
    frame = pd.read_csv(path, keep_default_na=False, comment="#")
    missing = REQUIRED_COLUMNS - set(frame.columns)
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(sorted(missing))}")
    if "cell_type" not in frame.columns and "major_cell_type" not in frame.columns:
        raise ValueError("Missing required column: major_cell_type (or legacy cell_type)")
    initialize(db_path)
    count = 0
    with database(db_path) as con:
        con.begin()
        try:
            for row in frame.to_dict(orient="records"):
                species_id = upsert_species(
                    con, row["species"], row.get("species_common_name") or default_common_name
                )
                alias_text = row.get("gene_aliases") or ""
                aliases = (
                    [alias.strip() for alias in alias_text.split(";") if alias.strip()]
                    if alias_text
                    else None
                )
                gene_id = upsert_gene(
                    con,
                    species_id,
                    row["gene_symbol"],
                    row.get("stable_id"),
                    aliases,
                )
                major_name = row.get("major_cell_type") or ""
                subtype_name = row.get("cell_subtype") or ""
                legacy_name = row.get("cell_type") or ""
                if not major_name and not legacy_name:
                    raise ValueError("Each row requires major_cell_type or cell_type")
                major_id = upsert_cell_type(con, major_name) if major_name else None
                cell_type_id = upsert_cell_type(
                    con,
                    subtype_name or legacy_name or major_name,
                    row.get("ontology_id"),
                    parent_cell_type_id=major_id if subtype_name else None,
                )
                assertion_id = add_assertion(
                    con,
                    gene_id=gene_id,
                    cell_type_id=cell_type_id,
                    marker_direction=row.get("marker_direction") or "positive",
                    tissue=row.get("tissue") or "",
                    condition=row.get("condition") or "",
                    developmental_stage=row.get("developmental_stage") or "",
                    assay=row.get("assay") or "scRNA-seq",
                    confidence=row.get("confidence") or "moderate",
                    bbsr_verified=str(row.get("bbsr_verified", "")).lower()
                    in {"1", "true", "yes", "y"},
                    submitter=row.get("submitter") or None,
                    notes=row.get("notes") or None,
                )
                if row.get("source_title"):
                    existing = con.execute(
                        "SELECT source_id FROM sources WHERE title=? AND doi IS NOT DISTINCT FROM ?",
                        [row["source_title"], row.get("doi") or None],
                    ).fetchone()
                    source_id = (
                        existing[0]
                        if existing
                        else add_source(
                            con,
                            title=row["source_title"],
                            doi=row.get("doi") or None,
                            pmid=row.get("pmid") or None,
                            url=row.get("url") or None,
                            citation=row.get("citation") or None,
                        )
                    )
                    link_evidence(
                        con,
                        assertion_id,
                        source_id,
                        row.get("evidence_type") or "reported_marker",
                        row.get("evidence_location") or "",
                        row.get("evidence_note") or None,
                    )
                count += 1
            con.commit()
        except Exception:
            con.rollback()
            raise
    return count
