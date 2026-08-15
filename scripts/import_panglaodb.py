"""Transform the PanglaoDB 27 Mar 2020 marker TSV and import it into MarkerCodex."""

from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

import pandas as pd

from markercodex.db import DEFAULT_DB, database, initialize
from markercodex.importer import import_csv
from markercodex.operations import add_source

SOURCE_TITLE = "PanglaoDB marker database (27 Mar 2020)"
SOURCE_CITATION = (
    "Franzén O, Gan LM, Björkegren JLM. PanglaoDB: a web server for exploration "
    "of mouse and human single-cell RNA sequencing data. Database (Oxford). 2019:baz046."
)
SOURCE_DOI = "10.1093/database/baz046"
SOURCE_PMID = "30951143"
SOURCE_URL = "https://panglaodb.se/markers.html"

SPECIES = {
    "Hs": ("Homo sapiens", "human"),
    "Mm": ("Mus musculus", "mouse"),
}


def clean(value: object) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def number(value: object) -> str:
    if pd.isna(value) or value == "":
        return "not reported"
    return f"{float(value):.6g}"


def aliases(value: object) -> set[str]:
    text = clean(value)
    return {alias.strip() for alias in text.split("|") if alias.strip()}


def gene_symbol(value: object, target: str) -> str:
    symbol = clean(value)
    return symbol[:1].upper() + symbol[1:].lower() if target == "Mm" else symbol


def transform(source_path: Path, source_title: str) -> tuple[pd.DataFrame, dict[str, int]]:
    source = pd.read_csv(
        source_path,
        sep="\t",
        keep_default_na=False,
        na_values=["NA"],
    )
    required = {
        "species",
        "official gene symbol",
        "cell type",
        "nicknames",
        "ubiquitousness index",
        "product description",
        "gene type",
        "canonical marker",
        "germ layer",
        "organ",
        "sensitivity_human",
        "sensitivity_mouse",
        "specificity_human",
        "specificity_mouse",
    }
    missing = required - set(source.columns)
    if missing:
        raise ValueError(f"Missing PanglaoDB columns: {', '.join(sorted(missing))}")

    expanded: list[tuple[pd.Series, str]] = []
    skipped = 0
    alias_map: dict[tuple[str, str], set[str]] = {}
    for _, row in source.iterrows():
        code = clean(row["species"])
        targets = [key for key in SPECIES if key in code.split()]
        if not targets:
            skipped += 1
            continue
        for target in targets:
            symbol = gene_symbol(row["official gene symbol"], target)
            expanded.append((row, target))
            alias_map.setdefault((target, symbol), set()).update(aliases(row["nicknames"]))

    records = []
    for row, target in expanded:
        scientific_name, common_name = SPECIES[target]
        symbol = gene_symbol(row["official gene symbol"], target)
        canonical = number(row["canonical marker"])
        records.append(
            {
                "species": scientific_name,
                "species_common_name": common_name,
                "gene_symbol": symbol,
                "gene_aliases": "; ".join(sorted(alias_map[(target, symbol)])),
                "stable_id": "",
                "major_cell_type": clean(row["cell type"]),
                "cell_subtype": "",
                "ontology_id": "",
                "marker_direction": "positive",
                "tissue": clean(row["organ"]),
                "condition": "",
                "developmental_stage": "",
                "assay": "PanglaoDB curation",
                "confidence": "high" if canonical == "1" else "moderate",
                "bbsr_verified": "false",
                "submitter": "",
                "notes": " | ".join(
                    [
                        f"Product: {clean(row['product description']) or 'not reported'}",
                        f"Gene type: {clean(row['gene type']) or 'not reported'}",
                        f"Germ layer: {clean(row['germ layer']) or 'not reported'}",
                        f"Ubiquitousness index: {number(row['ubiquitousness index'])}",
                    ]
                ),
                "source_title": source_title,
                "citation": SOURCE_CITATION,
                "doi": SOURCE_DOI,
                "pmid": SOURCE_PMID,
                "url": SOURCE_URL,
                "evidence_type": "reported_marker",
                "evidence_location": "PanglaoDB marker list dated 27 Mar 2020",
                "evidence_note": " | ".join(
                    [
                        f"Canonical marker: {canonical}",
                        f"Human sensitivity: {number(row['sensitivity_human'])}",
                        f"Human specificity: {number(row['specificity_human'])}",
                        f"Mouse sensitivity: {number(row['sensitivity_mouse'])}",
                        f"Mouse specificity: {number(row['specificity_mouse'])}",
                    ]
                ),
            }
        )

    frame = pd.DataFrame.from_records(records)
    key = ["species", "gene_symbol", "major_cell_type", "tissue", "assay"]
    duplicate_count = int(frame.duplicated(key).sum())
    if duplicate_count:
        raise ValueError(f"Transformation produced {duplicate_count} duplicate assertion keys")
    return frame, {
        "source_rows": len(source),
        "skipped_rows": skipped,
        "expanded_rows": len(frame),
        "cell_types": frame["major_cell_type"].nunique(),
    }


def ensure_source(db_path: Path) -> str:
    initialize(db_path)
    with database(db_path) as con:
        existing = con.execute(
            "SELECT title FROM sources WHERE doi = ?", [SOURCE_DOI]
        ).fetchone()
        if existing:
            return existing[0]
        add_source(
            con,
            title=SOURCE_TITLE,
            citation=SOURCE_CITATION,
            doi=SOURCE_DOI,
            pmid=SOURCE_PMID,
            url=SOURCE_URL,
            publication_year=2019,
            source_type="database",
            notes="Marker list snapshot dated 27 Mar 2020.",
        )
    return SOURCE_TITLE


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("tsv", type=Path)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = parser.parse_args()

    source_title = ensure_source(args.db)
    frame, stats = transform(args.tsv, source_title)
    with tempfile.NamedTemporaryFile(suffix=".csv") as temporary:
        frame.to_csv(temporary.name, index=False)
        imported = import_csv(temporary.name, args.db)
    print(
        f"Imported {imported} assertions from {stats['source_rows']} source rows; "
        f"skipped {stats['skipped_rows']} invalid-species rows; "
        f"preserved {stats['cell_types']} PanglaoDB cell types."
    )


if __name__ == "__main__":
    main()
