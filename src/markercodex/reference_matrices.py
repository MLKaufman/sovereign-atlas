"""Reference-matrix storage and metadata catalog helpers."""

from __future__ import annotations

import csv
import hashlib
import io
import re
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb

DEFAULT_REFERENCE_DB = Path("data/reference_matrices.duckdb")
DEFAULT_MATRIX_STORAGE = Path("data/reference_matrices/files")
SUPPORTED_SUFFIXES = {".csv": ",", ".tsv": "\t"}


class DuplicateMatrixError(ValueError):
    """Raised when an identical file is already registered."""


@dataclass(frozen=True)
class MatrixFileProfile:
    delimiter: str
    row_count: int
    column_count: int
    column_names: list[str]
    sha256: str
    size_bytes: int


def _clean(value: Any) -> Any:
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


def _slug(value: str | None, fallback: str, max_length: int = 28) -> str:
    text = (value or "").lower().strip()
    text = re.sub(r"^https?://(dx\.)?doi\.org/", "", text)
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return (text[:max_length].rstrip("-") or fallback)


def inspect_matrix_file(data: bytes, original_filename: str) -> MatrixFileProfile:
    """Validate a CSV/TSV upload and return technical metadata."""
    suffix = Path(original_filename).suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ValueError("Reference matrices must be CSV or TSV files")
    if not data:
        raise ValueError("The uploaded matrix is empty")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("Reference matrices must use UTF-8 text encoding") from exc

    reader = csv.reader(io.StringIO(text, newline=""), delimiter=SUPPORTED_SUFFIXES[suffix])
    try:
        header = next(reader)
    except StopIteration as exc:
        raise ValueError("The uploaded matrix has no header row") from exc
    header = [column.strip() for column in header]
    if len(header) < 2 or any(not column for column in header):
        raise ValueError("The matrix header must contain at least two named columns")
    if len(set(header)) != len(header):
        raise ValueError("The matrix header contains duplicate column names")

    row_count = 0
    for line_number, row in enumerate(reader, start=2):
        if not row or all(not value.strip() for value in row):
            continue
        if len(row) != len(header):
            raise ValueError(
                f"Row {line_number} has {len(row)} columns; expected {len(header)}"
            )
        row_count += 1
    if row_count == 0:
        raise ValueError("The matrix must contain at least one data row")

    return MatrixFileProfile(
        delimiter="comma" if suffix == ".csv" else "tab",
        row_count=row_count,
        column_count=len(header),
        column_names=header,
        sha256=hashlib.sha256(data).hexdigest(),
        size_bytes=len(data),
    )


@contextmanager
def reference_database(
    path: str | Path = DEFAULT_REFERENCE_DB, *, read_only: bool = False
) -> Iterator[duckdb.DuckDBPyConnection]:
    path = Path(path)
    if not read_only:
        path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(path), read_only=read_only)
    try:
        yield con
    finally:
        con.close()


def initialize_reference_catalog(path: str | Path = DEFAULT_REFERENCE_DB) -> None:
    """Create the independent DuckDB catalog for uploaded reference matrices."""
    with reference_database(path) as con:
        con.execute(
            """CREATE TABLE IF NOT EXISTS reference_matrices (
                matrix_id UUID PRIMARY KEY,
                title VARCHAR NOT NULL,
                description VARCHAR,
                species_scientific_name VARCHAR NOT NULL,
                species_common_name VARCHAR,
                tissue VARCHAR,
                condition VARCHAR,
                developmental_stage VARCHAR,
                assay VARCHAR NOT NULL,
                platform VARCHAR,
                row_entity VARCHAR NOT NULL,
                column_entity VARCHAR NOT NULL,
                feature_id_type VARCHAR,
                value_type VARCHAR NOT NULL,
                normalization VARCHAR,
                source_title VARCHAR NOT NULL,
                citation VARCHAR,
                doi VARCHAR,
                pmid VARCHAR,
                source_url VARCHAR,
                publication_year INTEGER,
                data_license VARCHAR,
                submitter VARCHAR NOT NULL,
                notes VARCHAR,
                original_filename VARCHAR NOT NULL,
                stored_filename VARCHAR NOT NULL UNIQUE,
                storage_path VARCHAR NOT NULL UNIQUE,
                file_format VARCHAR NOT NULL,
                delimiter VARCHAR NOT NULL,
                row_count BIGINT NOT NULL,
                column_count BIGINT NOT NULL,
                column_names VARCHAR[] NOT NULL,
                size_bytes BIGINT NOT NULL,
                sha256 VARCHAR NOT NULL UNIQUE,
                created_at TIMESTAMP NOT NULL DEFAULT current_timestamp,
                updated_at TIMESTAMP NOT NULL DEFAULT current_timestamp,
                CHECK (file_format IN ('csv', 'tsv')),
                CHECK (row_count > 0),
                CHECK (column_count > 1)
            )"""
        )
        con.execute(
            "CREATE INDEX IF NOT EXISTS idx_reference_matrices_species ON reference_matrices(species_scientific_name)"
        )
        con.execute(
            "CREATE INDEX IF NOT EXISTS idx_reference_matrices_source ON reference_matrices(source_title)"
        )


def build_stored_filename(
    *,
    matrix_id: str,
    suffix: str,
    species: str,
    tissue: str | None,
    assay: str,
    source_title: str,
    doi: str | None = None,
    pmid: str | None = None,
    publication_year: int | None = None,
) -> str:
    """Build a unique filename that remains intelligible outside the catalog."""
    source_key = doi or (f"pmid-{pmid}" if pmid else None) or source_title
    return "--".join(
        [
            "refmat",
            _slug(species, "species"),
            _slug(tissue, "mixed-tissue"),
            _slug(assay, "assay"),
            _slug(source_key, "source"),
            str(publication_year or "nd"),
            matrix_id.replace("-", "")[:8],
        ]
    ) + suffix


def add_reference_matrix(
    *,
    data: bytes,
    original_filename: str,
    catalog_path: str | Path = DEFAULT_REFERENCE_DB,
    storage_dir: str | Path = DEFAULT_MATRIX_STORAGE,
    **metadata: Any,
) -> str:
    """Validate, rename, store, and catalog one reference matrix."""
    required = (
        "title",
        "species_scientific_name",
        "assay",
        "row_entity",
        "column_entity",
        "value_type",
        "source_title",
        "submitter",
    )
    missing = [name for name in required if not _clean(metadata.get(name))]
    if missing:
        raise ValueError("Required metadata missing: " + ", ".join(missing))

    profile = inspect_matrix_file(data, original_filename)
    initialize_reference_catalog(catalog_path)
    with reference_database(catalog_path, read_only=True) as con:
        duplicate = con.execute(
            "SELECT title, stored_filename FROM reference_matrices WHERE sha256 = ?",
            [profile.sha256],
        ).fetchone()
    if duplicate:
        raise DuplicateMatrixError(
            f"This exact file is already stored as {duplicate[1]} ({duplicate[0]})"
        )

    matrix_id = str(uuid.uuid4())
    suffix = Path(original_filename).suffix.lower()
    stored_filename = build_stored_filename(
        matrix_id=matrix_id,
        suffix=suffix,
        species=metadata["species_scientific_name"],
        tissue=metadata.get("tissue"),
        assay=metadata["assay"],
        source_title=metadata["source_title"],
        doi=metadata.get("doi"),
        pmid=metadata.get("pmid"),
        publication_year=metadata.get("publication_year"),
    )
    storage_dir = Path(storage_dir)
    storage_dir.mkdir(parents=True, exist_ok=True)
    target = storage_dir / stored_filename
    target.write_bytes(data)

    columns = [
        "matrix_id",
        "title",
        "description",
        "species_scientific_name",
        "species_common_name",
        "tissue",
        "condition",
        "developmental_stage",
        "assay",
        "platform",
        "row_entity",
        "column_entity",
        "feature_id_type",
        "value_type",
        "normalization",
        "source_title",
        "citation",
        "doi",
        "pmid",
        "source_url",
        "publication_year",
        "data_license",
        "submitter",
        "notes",
        "original_filename",
        "stored_filename",
        "storage_path",
        "file_format",
        "delimiter",
        "row_count",
        "column_count",
        "column_names",
        "size_bytes",
        "sha256",
    ]
    technical = {
        "matrix_id": matrix_id,
        "original_filename": Path(original_filename).name,
        "stored_filename": stored_filename,
        "storage_path": str(target),
        "file_format": suffix.removeprefix("."),
        "delimiter": profile.delimiter,
        "row_count": profile.row_count,
        "column_count": profile.column_count,
        "column_names": profile.column_names,
        "size_bytes": profile.size_bytes,
        "sha256": profile.sha256,
    }
    values = [
        technical[column] if column in technical else _clean(metadata.get(column))
        for column in columns
    ]
    try:
        with reference_database(catalog_path) as con:
            placeholders = ", ".join("?" for _ in columns)
            con.execute(
                f"INSERT INTO reference_matrices ({', '.join(columns)}) VALUES ({placeholders})",
                values,
            )
    except Exception:
        target.unlink(missing_ok=True)
        raise
    return matrix_id
