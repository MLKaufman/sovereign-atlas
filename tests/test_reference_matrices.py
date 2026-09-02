import re

import pytest

from markercodex.reference_matrices import (
    DuplicateMatrixError,
    add_reference_matrix,
    initialize_reference_catalog,
    inspect_matrix_file,
    reference_database,
)


def metadata():
    return {
        "title": "Human lung marker scores",
        "species_scientific_name": "Homo sapiens",
        "species_common_name": "human",
        "tissue": "lung",
        "assay": "scRNA-seq",
        "row_entity": "genes",
        "column_entity": "cell types",
        "feature_id_type": "HGNC symbol",
        "value_type": "marker score",
        "normalization": "z-score",
        "source_title": "Example atlas",
        "doi": "10.1234/example.2025.1",
        "publication_year": 2025,
        "submitter": "BBSR",
    }


def test_reference_catalog_is_independent_and_idempotent(tmp_path):
    path = tmp_path / "references.duckdb"
    initialize_reference_catalog(path)
    initialize_reference_catalog(path)
    with reference_database(path, read_only=True) as con:
        tables = {row[0] for row in con.execute("SHOW TABLES").fetchall()}
    assert tables == {"reference_matrices"}


def test_csv_is_renamed_stored_and_cataloged(tmp_path):
    catalog = tmp_path / "references.duckdb"
    storage = tmp_path / "files"
    matrix_id = add_reference_matrix(
        data=b"gene,B cell,T cell\nCD19,5,0\nCD3D,0,7\n",
        original_filename="authors supplementary table.csv",
        catalog_path=catalog,
        storage_dir=storage,
        **metadata(),
    )
    with reference_database(catalog, read_only=True) as con:
        row = con.execute(
            "SELECT matrix_id, stored_filename, row_count, column_count, original_filename, storage_path FROM reference_matrices"
        ).fetchone()
    assert str(row[0]) == matrix_id
    assert re.fullmatch(
        r"refmat--homo-sapiens--lung--scrna-seq--10-1234-example-2025-1--2025--[a-f0-9]{8}\.csv",
        row[1],
    )
    assert row[2:5] == (2, 3, "authors supplementary table.csv")
    assert (storage / row[1]).read_text() == "gene,B cell,T cell\nCD19,5,0\nCD3D,0,7\n"
    assert row[5] == str(storage / row[1])


def test_tsv_profile_and_duplicate_detection(tmp_path):
    data = b"gene\tB cell\nCD19\t1\n"
    profile = inspect_matrix_file(data, "matrix.tsv")
    assert (profile.delimiter, profile.row_count, profile.column_count) == ("tab", 1, 2)
    kwargs = dict(
        data=data,
        original_filename="matrix.tsv",
        catalog_path=tmp_path / "references.duckdb",
        storage_dir=tmp_path / "files",
        **metadata(),
    )
    add_reference_matrix(**kwargs)
    with pytest.raises(DuplicateMatrixError, match="already stored"):
        add_reference_matrix(**kwargs)


@pytest.mark.parametrize(
    ("data", "name", "message"),
    [
        (b"", "matrix.csv", "empty"),
        (b"gene\nCD19\n", "matrix.csv", "at least two"),
        (b"a,b\n1\n", "matrix.csv", "Row 2"),
        (b"a,a\n1,2\n", "matrix.csv", "duplicate"),
        (b"a,b\n1,2\n", "matrix.xlsx", "CSV or TSV"),
    ],
)
def test_invalid_matrix_files_are_rejected(data, name, message):
    with pytest.raises(ValueError, match=message):
        inspect_matrix_file(data, name)
