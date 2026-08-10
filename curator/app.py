"""Local Streamlit curator for MarkerCodex."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from markercodex.db import DEFAULT_DB, database, initialize
from markercodex.importer import import_csv
from markercodex.operations import (
    add_assertion,
    add_source,
    link_evidence,
    upsert_cell_type,
    upsert_gene,
    upsert_species,
)

st.set_page_config(page_title="MarkerCodex Curator", page_icon="🧬", layout="wide")
DB_PATH = Path(os.environ.get("MARKERCODEX_DB", DEFAULT_DB))
initialize(DB_PATH)
st.title("MarkerCodex Curator")
st.caption(f"Local curation workspace · {DB_PATH}")


def frame(query: str, params: list | None = None) -> pd.DataFrame:
    with database(DB_PATH, read_only=True) as con:
        return con.execute(query, params or []).fetchdf()


browse, add_tab, edit_tab, import_tab, sources_tab = st.tabs(
    ["Browse", "Add marker", "Edit / delete", "Bulk import", "References"]
)

with browse:
    query = st.text_input("Search", placeholder="Gene, cell type, tissue, or source")
    sql = "SELECT * FROM marker_atlas"
    params = []
    if query:
        sql += (
            " WHERE concat_ws(' ', gene_symbol, cell_type, species, tissue, source_titles) ILIKE ?"
        )
        params = [f"%{query}%"]
    st.dataframe(
        frame(sql + " ORDER BY cell_type, gene_symbol", params),
        use_container_width=True,
        hide_index=True,
    )

with add_tab:
    with st.form("new_assertion", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        species = c1.text_input("Scientific species name*", value="Homo sapiens")
        common = c1.text_input("Common name", value="human")
        symbol = c2.text_input("Gene symbol*")
        stable_id = c2.text_input("Stable gene ID")
        cell_type = c3.text_input("Cell type*")
        ontology = c3.text_input("Cell Ontology ID", placeholder="CL:0000540")
        tissue = c1.text_input("Tissue")
        condition = c2.text_input("Condition")
        stage = c3.text_input("Developmental stage")
        direction = c1.selectbox("Direction", ["positive", "negative"])
        confidence = c2.selectbox("Confidence", ["moderate", "high", "low"])
        assay = c3.text_input("Assay", value="scRNA-seq")
        verified = st.checkbox("BBSR verified")
        notes = st.text_area("Curator notes")
        submitted = st.form_submit_button("Save marker assertion", type="primary")
    if submitted:
        try:
            with database(DB_PATH) as con:
                species_id = upsert_species(con, species, common)
                gene_id = upsert_gene(con, species_id, symbol, stable_id)
                cell_id = upsert_cell_type(con, cell_type, ontology)
                assertion_id = add_assertion(
                    con,
                    gene_id=gene_id,
                    cell_type_id=cell_id,
                    marker_direction=direction,
                    tissue=tissue,
                    condition=condition,
                    developmental_stage=stage,
                    assay=assay,
                    confidence=confidence,
                    bbsr_verified=verified,
                    notes=notes,
                )
            st.success(f"Saved assertion {assertion_id}")
        except Exception as exc:
            st.error(str(exc))

with edit_tab:
    assertions = frame(
        "SELECT assertion_id, gene_symbol, cell_type, tissue, marker_direction, confidence, bbsr_verified, notes FROM marker_atlas ORDER BY assertion_id"
    )
    if assertions.empty:
        st.info("No assertions to edit yet.")
    else:
        choice = st.selectbox(
            "Assertion",
            assertions.assertion_id.tolist(),
            format_func=lambda value: (
                f"#{value} · {assertions.loc[assertions.assertion_id == value, 'gene_symbol'].iloc[0]} → {assertions.loc[assertions.assertion_id == value, 'cell_type'].iloc[0]}"
            ),
        )
        current = assertions.loc[assertions.assertion_id == choice].iloc[0]
        with st.form("edit_assertion"):
            confidence = st.selectbox(
                "Confidence",
                ["low", "moderate", "high"],
                index=["low", "moderate", "high"].index(current.confidence),
            )
            verified = st.checkbox("BBSR verified", value=bool(current.bbsr_verified))
            notes = st.text_area("Notes", value=current.notes or "")
            save = st.form_submit_button("Save changes", type="primary")
        if save:
            with database(DB_PATH) as con:
                con.execute(
                    "UPDATE marker_assertions SET confidence=?, bbsr_verified=?, notes=?, updated_at=now() WHERE assertion_id=?",
                    [confidence, verified, notes or None, int(choice)],
                )
            st.success("Changes saved")
            st.rerun()
        if st.button("Delete assertion", type="secondary"):
            with database(DB_PATH) as con:
                con.execute("DELETE FROM evidence WHERE assertion_id=?", [int(choice)])
                con.execute("DELETE FROM marker_assertions WHERE assertion_id=?", [int(choice)])
            st.success("Assertion and its evidence links deleted")
            st.rerun()

with import_tab:
    st.markdown(
        "Upload a CSV with at least `species`, `gene_symbol`, and `cell_type`. Optional source and context columns are documented in the README."
    )
    upload = st.file_uploader("Marker CSV", type="csv")
    if upload:
        preview = pd.read_csv(upload, keep_default_na=False)
        st.dataframe(preview.head(25), use_container_width=True)
        if st.button("Import rows", type="primary"):
            with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
                tmp.write(upload.getvalue())
                temporary_path = tmp.name
            try:
                st.success(f"Imported {import_csv(temporary_path, DB_PATH)} rows")
            except Exception as exc:
                st.error(str(exc))
            finally:
                Path(temporary_path).unlink(missing_ok=True)

with sources_tab:
    st.dataframe(
        frame("SELECT * FROM sources ORDER BY publication_year DESC NULLS LAST, title"),
        use_container_width=True,
        hide_index=True,
    )
    with st.form("new_source", clear_on_submit=True):
        title = st.text_input("Title*")
        citation = st.text_area("Citation")
        c1, c2, c3 = st.columns(3)
        doi = c1.text_input("DOI")
        pmid = c2.text_input("PMID")
        url = c3.text_input("URL")
        year = c1.number_input("Year", min_value=0, max_value=2200, value=0)
        source_type = c2.selectbox(
            "Type", ["publication", "database", "preprint", "expert", "other"]
        )
        create = st.form_submit_button("Add reference", type="primary")
    if create:
        try:
            with database(DB_PATH) as con:
                source_id = add_source(
                    con,
                    title=title,
                    citation=citation,
                    doi=doi,
                    pmid=pmid,
                    url=url,
                    publication_year=int(year) or None,
                    source_type=source_type,
                )
            st.success(f"Added reference {source_id}")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))

    st.subheader("Edit or delete a reference")
    editable_sources = frame("SELECT * FROM sources ORDER BY title")
    if not editable_sources.empty:
        edit_source_id = st.selectbox(
            "Reference to manage",
            editable_sources.source_id.tolist(),
            format_func=lambda value: editable_sources.loc[
                editable_sources.source_id == value, "title"
            ].iloc[0],
            key="edit_source_id",
        )
        source_row = editable_sources.loc[editable_sources.source_id == edit_source_id].iloc[0]
        with st.form("edit_source"):
            edit_title = st.text_input("Title", value=source_row.title)
            edit_citation = st.text_area("Citation", value=source_row.citation or "")
            edit_doi = st.text_input("DOI", value=source_row.doi or "")
            edit_pmid = st.text_input("PMID", value=source_row.pmid or "")
            edit_url = st.text_input("URL", value=source_row.url or "")
            update_source = st.form_submit_button("Save reference changes")
        if update_source:
            with database(DB_PATH) as con:
                con.execute(
                    """UPDATE sources SET title=?, citation=?, doi=?, pmid=?, url=?
                    WHERE source_id=?""",
                    [
                        edit_title,
                        edit_citation or None,
                        edit_doi or None,
                        edit_pmid or None,
                        edit_url or None,
                        int(edit_source_id),
                    ],
                )
            st.success("Reference updated")
            st.rerun()
        linked_count = int(
            frame(
                "SELECT count(*) AS n FROM evidence WHERE source_id=?",
                [int(edit_source_id)],
            )
            .iloc[0]
            .n
        )
        if st.button(
            f"Delete reference and {linked_count} evidence link(s)",
            type="secondary",
        ):
            with database(DB_PATH) as con:
                con.execute("DELETE FROM evidence WHERE source_id=?", [int(edit_source_id)])
                con.execute("DELETE FROM sources WHERE source_id=?", [int(edit_source_id)])
            st.success("Reference and its evidence links deleted")
            st.rerun()

    st.subheader("Link reference to assertion")
    assertions_for_link = frame(
        "SELECT assertion_id, gene_symbol, cell_type FROM marker_atlas ORDER BY assertion_id"
    )
    sources_for_link = frame("SELECT source_id, title FROM sources ORDER BY title")
    if not assertions_for_link.empty and not sources_for_link.empty:
        a = st.selectbox(
            "Marker assertion", assertions_for_link.assertion_id.tolist(), key="link_assertion"
        )
        s = st.selectbox(
            "Reference",
            sources_for_link.source_id.tolist(),
            format_func=lambda value: sources_for_link.loc[
                sources_for_link.source_id == value, "title"
            ].iloc[0],
        )
        evidence_type = st.selectbox(
            "Evidence type",
            [
                "reported_marker",
                "differential_expression",
                "figure",
                "table",
                "expert_review",
                "other",
            ],
        )
        location = st.text_input("Location", placeholder="Figure 2, Table S4, page 8")
        evidence_note = st.text_area("Evidence note")
        if st.button("Link evidence"):
            with database(DB_PATH) as con:
                link_evidence(con, int(a), int(s), evidence_type, location, evidence_note)
            st.success("Evidence linked")
    else:
        st.info("Add at least one assertion and one reference to link evidence.")

    st.subheader("Evidence links")
    evidence_links = frame(
        """SELECT e.evidence_id, m.gene_symbol, m.cell_type, s.title,
        e.evidence_type, e.location, e.evidence_note
        FROM evidence e
        JOIN marker_atlas m ON m.assertion_id=e.assertion_id
        JOIN sources s ON s.source_id=e.source_id
        ORDER BY e.evidence_id"""
    )
    st.dataframe(evidence_links, use_container_width=True, hide_index=True)
    if not evidence_links.empty:
        unlink_id = st.selectbox("Evidence link to remove", evidence_links.evidence_id.tolist())
        if st.button("Remove evidence link"):
            with database(DB_PATH) as con:
                con.execute("DELETE FROM evidence WHERE evidence_id=?", [int(unlink_id)])
            st.success("Evidence link removed")
            st.rerun()
