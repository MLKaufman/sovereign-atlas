"""Add, browse, and download reference matrices."""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

from markercodex.reference_matrices import (
    DEFAULT_MATRIX_STORAGE,
    DEFAULT_REFERENCE_DB,
    add_reference_matrix,
    initialize_reference_catalog,
    inspect_matrix_file,
    reference_database,
)

st.set_page_config(page_title="Refmats · MarkerCodex", page_icon="🧮", layout="wide")
st.markdown(
    """<style>
    section[data-testid="stSidebar"] div[data-testid="stPageLink"] a,
    section[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"] {
        min-height: 3.5rem;
        padding: 0.8rem 1rem;
    }
    section[data-testid="stSidebar"] div[data-testid="stPageLink"] p,
    section[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"] p {
        font-size: 1.15rem;
        font-weight: 650;
    }
    section[data-testid="stSidebar"] div[data-testid="stPageLink"] svg,
    section[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"] svg {
        width: 1.35rem;
        height: 1.35rem;
    }
    </style>""",
    unsafe_allow_html=True,
)
CATALOG_PATH = Path(os.environ.get("MARKERCODEX_REFERENCE_DB", DEFAULT_REFERENCE_DB))
STORAGE_DIR = Path(os.environ.get("MARKERCODEX_MATRIX_DIR", DEFAULT_MATRIX_STORAGE))
initialize_reference_catalog(CATALOG_PATH)

with st.sidebar:
    st.page_link("app.py", label="MarkerCodex", icon="🧬")
    st.page_link("pages/1_Refmats.py", label="Refmats", icon="🧮")

st.title("Reference matrices")
st.caption("Store, find, inspect, and download reusable CSV and TSV reference matrices.")

if saved_matrix_id := st.session_state.pop("saved_matrix_id", None):
    st.success(f"Reference matrix stored · {saved_matrix_id}")

manage_tab, add_tab = st.tabs(["View / manage matrices", "Add new matrix"])

with manage_tab:
    with reference_database(CATALOG_PATH, read_only=True) as con:
        catalog = con.execute("SELECT * FROM reference_matrices ORDER BY created_at DESC").fetchdf()

    export_catalog = catalog.copy()
    if "column_names" in export_catalog:
        export_catalog["column_names"] = export_catalog["column_names"].apply(
            lambda names: "; ".join(names.tolist() if hasattr(names, "tolist") else names)
        )
    st.download_button(
        "Export all metadata as CSV",
        data=export_catalog.to_csv(index=False).encode("utf-8"),
        file_name=f"refmat_metadata_{date.today().isoformat()}.csv",
        mime="text/csv",
        icon="📥",
    )

    if catalog.empty:
        st.info("No reference matrices have been uploaded yet. Use the Add new matrix tab to begin.")
    else:
        search = st.text_input(
            "Search", placeholder="Title, species, tissue, assay, source, submitter…"
        )
        c1, c2, c3 = st.columns(3)
        species_options = [
            "All species",
            *sorted(catalog.species_scientific_name.dropna().unique()),
        ]
        assay_options = ["All assays", *sorted(catalog.assay.dropna().unique())]
        format_options = ["All formats", *sorted(catalog.file_format.dropna().unique())]
        species_filter = c1.selectbox("Species", species_options)
        assay_filter = c2.selectbox("Assay", assay_options)
        format_filter = c3.selectbox("Format", format_options)

        visible = catalog.copy()
        if search:
            searchable = visible.fillna("").astype(str).agg(" ".join, axis=1)
            visible = visible[searchable.str.contains(search, case=False, regex=False)]
        if species_filter != "All species":
            visible = visible[visible.species_scientific_name == species_filter]
        if assay_filter != "All assays":
            visible = visible[visible.assay == assay_filter]
        if format_filter != "All formats":
            visible = visible[visible.file_format == format_filter]

        st.caption(f"{len(visible):,} of {len(catalog):,} matrices")
        summary_columns = [
            "title",
            "species_scientific_name",
            "tissue",
            "assay",
            "row_entity",
            "column_entity",
            "value_type",
            "source_title",
            "publication_year",
            "row_count",
            "column_count",
            "stored_filename",
        ]
        selection = st.dataframe(
            visible[summary_columns],
            width="stretch",
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            key="reference_matrix_catalog",
        )

        if not selection.selection.rows:
            st.info("Select a matrix to see its complete metadata and download the file.")
        else:
            matrix = visible.iloc[selection.selection.rows[0]]
            st.subheader(str(matrix.title))
            if pd.notna(matrix.description):
                st.write(matrix.description)

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Rows", f"{int(matrix.row_count):,}")
            c2.metric("Columns", f"{int(matrix.column_count):,}")
            c3.metric("Format", str(matrix.file_format).upper())
            c4.metric("Size", f"{int(matrix.size_bytes) / 1024:,.1f} KB")

            display_fields = {
                "Matrix ID": matrix.matrix_id,
                "Species": " · ".join(
                    filter(
                        None,
                        [
                            matrix.species_scientific_name,
                            matrix.species_common_name
                            if pd.notna(matrix.species_common_name)
                            else None,
                        ],
                    )
                ),
                "Biological context": " · ".join(
                    filter(
                        None,
                        [
                            matrix.tissue if pd.notna(matrix.tissue) else None,
                            matrix.condition if pd.notna(matrix.condition) else None,
                            matrix.developmental_stage
                            if pd.notna(matrix.developmental_stage)
                            else None,
                        ],
                    )
                ),
                "Assay / platform": " · ".join(
                    filter(
                        None,
                        [
                            matrix.assay,
                            matrix.platform if pd.notna(matrix.platform) else None,
                        ],
                    )
                ),
                "Orientation": f"{matrix.row_entity} × {matrix.column_entity}",
                "Feature IDs": matrix.feature_id_type,
                "Values": " · ".join(
                    filter(
                        None,
                        [
                            matrix.value_type,
                            matrix.normalization if pd.notna(matrix.normalization) else None,
                        ],
                    )
                ),
                "Source": matrix.source_title,
                "Citation": matrix.citation,
                "DOI": matrix.doi,
                "PMID": matrix.pmid,
                "Source URL": matrix.source_url,
                "Publication year": matrix.publication_year,
                "License": matrix.data_license,
                "Submitter": matrix.submitter,
                "Original filename": matrix.original_filename,
                "Stored filename": matrix.stored_filename,
                "SHA-256": matrix.sha256,
                "Columns": "; ".join(
                    matrix.column_names.tolist()
                    if hasattr(matrix.column_names, "tolist")
                    else matrix.column_names
                ),
                "Curator notes": matrix.notes,
            }
            details = pd.DataFrame(
                [
                    (label, value)
                    for label, value in display_fields.items()
                    if pd.notna(value) and str(value)
                ],
                columns=["Field", "Value"],
            )
            st.dataframe(details, width="stretch", hide_index=True)

            stored_path = Path(str(matrix.storage_path))
            if stored_path.is_file():
                st.download_button(
                    "Download stored matrix",
                    data=stored_path.read_bytes(),
                    file_name=str(matrix.stored_filename),
                    mime=(
                        "text/csv"
                        if matrix.file_format == "csv"
                        else "text/tab-separated-values"
                    ),
                    type="primary",
                )
            else:
                st.error(
                    f"The catalog record exists, but the stored file is missing: {stored_path}"
                )

with add_tab:
    st.info(
        "Files are stored under a descriptive name containing species, tissue, assay, source, "
        "publication year, and a unique ID. The original filename is retained in the catalog."
    )
    upload = st.file_uploader("Matrix file*", type=["csv", "tsv"])
    if upload:
        try:
            profile = inspect_matrix_file(upload.getvalue(), upload.name)
            c1, c2, c3 = st.columns(3)
            c1.metric("Data rows", f"{profile.row_count:,}")
            c2.metric("Columns", f"{profile.column_count:,}")
            c3.metric("File size", f"{profile.size_bytes / 1024:,.1f} KB")
            separator = "," if Path(upload.name).suffix.lower() == ".csv" else "\t"
            preview = pd.read_csv(upload, sep=separator, nrows=20)
            st.dataframe(preview, width="stretch", hide_index=True)
        except Exception as exc:
            st.error(str(exc))
            upload = None

    with st.form("reference_matrix_metadata", clear_on_submit=True):
        st.subheader("Identity and biological context")
        title = st.text_input(
            "Matrix title*", placeholder="Human lung immune-cell marker score matrix"
        )
        description = st.text_area(
            "Description", placeholder="What this matrix represents and how it should be used"
        )
        c1, c2, c3 = st.columns(3)
        species = c1.text_input("Scientific species name*", value="Homo sapiens")
        common_name = c1.text_input("Common species name", value="human")
        tissue = c2.text_input("Tissue", placeholder="lung or mixed")
        condition = c2.text_input("Condition", placeholder="healthy, disease, treatment")
        stage = c3.text_input("Developmental stage")
        assay = c3.text_input("Assay*", value="scRNA-seq")
        platform = c3.text_input("Platform", placeholder="10x Chromium, Smart-seq2")

        st.subheader("Matrix interpretation")
        c1, c2, c3 = st.columns(3)
        row_entity = c1.selectbox(
            "Rows represent*", ["genes", "cell types", "clusters", "samples", "other"]
        )
        column_entity = c2.selectbox(
            "Columns represent*", ["cell types", "genes", "clusters", "samples", "other"]
        )
        value_type = c3.text_input(
            "Values represent*", placeholder="marker score, mean expression, binary call"
        )
        feature_id_type = c1.text_input(
            "Feature identifier type",
            placeholder="HGNC symbol, Ensembl gene ID, Cell Ontology ID",
        )
        normalization = c2.text_input(
            "Normalization / transformation", placeholder="log1p CPM, z-score, none"
        )

        st.subheader("Source and stewardship")
        source_title = st.text_input(
            "Source title*", placeholder="Publication, database, or internal analysis title"
        )
        citation = st.text_area("Citation")
        c1, c2, c3 = st.columns(3)
        doi = c1.text_input("DOI")
        pmid = c2.text_input("PMID")
        source_url = c3.text_input("Source URL")
        publication_year = c1.number_input(
            "Publication year", min_value=0, max_value=2200, value=0
        )
        data_license = c2.text_input("Data license", placeholder="CC BY 4.0")
        submitter = c3.text_input("Submitter*", placeholder="Name or team")
        notes = st.text_area("Curator notes")
        submitted = st.form_submit_button("Store reference matrix", type="primary")

    if submitted:
        if upload is None:
            st.error("Choose a valid CSV or TSV matrix before submitting metadata.")
        else:
            try:
                matrix_id = add_reference_matrix(
                    data=upload.getvalue(),
                    original_filename=upload.name,
                    catalog_path=CATALOG_PATH,
                    storage_dir=STORAGE_DIR,
                    title=title,
                    description=description,
                    species_scientific_name=species,
                    species_common_name=common_name,
                    tissue=tissue,
                    condition=condition,
                    developmental_stage=stage,
                    assay=assay,
                    platform=platform,
                    row_entity=row_entity,
                    column_entity=column_entity,
                    feature_id_type=feature_id_type,
                    value_type=value_type,
                    normalization=normalization,
                    source_title=source_title,
                    citation=citation,
                    doi=doi,
                    pmid=pmid,
                    source_url=source_url,
                    publication_year=int(publication_year) or None,
                    data_license=data_license,
                    submitter=submitter,
                    notes=notes,
                )
                st.session_state["saved_matrix_id"] = matrix_id
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
