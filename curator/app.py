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
    set_gene_aliases,
    upsert_cell_type,
    upsert_gene,
    upsert_species,
)

st.set_page_config(page_title="MarkerCodex Curator", page_icon="🧬", layout="wide")
DB_PATH = Path(os.environ.get("MARKERCODEX_DB", DEFAULT_DB))
TEMPLATE_PATH = Path(__file__).resolve().parents[1] / "data" / "import_template.csv"
initialize(DB_PATH)
st.title("MarkerCodex Curator")
st.caption(f"Local curation workspace · {DB_PATH}")


def frame(query: str, params: list | None = None) -> pd.DataFrame:
    with database(DB_PATH, read_only=True) as con:
        return con.execute(query, params or []).fetchdf()


def render_assertion_editor(current: pd.Series, key: str) -> None:
    assertion_id = int(current.assertion_id)
    cell_label = current.major_cell_type
    if current.get("cell_subtype") and not pd.isna(current.cell_subtype):
        cell_label += f" / {current.cell_subtype}"
    st.subheader(f"Edit #{assertion_id} · {current.gene_symbol} → {cell_label}")
    source_url = current.get("source_url")
    if source_url and not pd.isna(source_url):
        st.link_button("Open source ↗", str(source_url))
    notes_value = "" if pd.isna(current.notes) else str(current.notes)
    alias_value = current.get("gene_aliases")
    aliases = alias_value.tolist() if hasattr(alias_value, "tolist") else []
    with st.form(f"edit_assertion_{key}"):
        alias_text = st.text_input(
            "Gene aliases (semicolon-separated)",
            value="; ".join(aliases),
            key=f"aliases_{key}",
        )
        confidence = st.selectbox(
            "Confidence",
            ["low", "moderate", "high"],
            index=["low", "moderate", "high"].index(current.confidence),
            key=f"confidence_{key}",
        )
        verified = st.checkbox(
            "BBSR verified", value=bool(current.bbsr_verified), key=f"verified_{key}"
        )
        submitter_value = "" if pd.isna(current.submitter) else str(current.submitter)
        submitter = st.text_input("Submitter", value=submitter_value, key=f"submitter_{key}")
        notes = st.text_area("Notes", value=notes_value, key=f"notes_{key}")
        save = st.form_submit_button("Save changes", type="primary")
    if save:
        with database(DB_PATH) as con:
            set_gene_aliases(
                con,
                int(current.gene_id),
                [alias.strip() for alias in alias_text.split(";") if alias.strip()],
            )
            con.execute(
                "UPDATE marker_assertions SET confidence=?, bbsr_verified=?, submitter=?, notes=?, updated_at=now() WHERE assertion_id=?",
                [confidence, verified, submitter or None, notes or None, assertion_id],
            )
        st.success("Changes saved")
        st.rerun()
    if st.button("Delete assertion", type="secondary", key=f"delete_{key}"):
        with database(DB_PATH) as con:
            con.execute("DELETE FROM evidence WHERE assertion_id=?", [assertion_id])
            con.execute("DELETE FROM marker_assertions WHERE assertion_id=?", [assertion_id])
        st.success("Assertion and its evidence links deleted")
        st.rerun()


browse, add_tab, edit_tab, import_tab, sources_tab = st.tabs(
    ["Browse", "Add marker", "Edit / delete", "Bulk import", "References"]
)

with browse:
    query = st.text_input("Search", placeholder="Gene, cell type, tissue, or source")
    sql = """SELECT assertion_id, gene_id, gene_symbol, gene_aliases,
        major_cell_type, cell_subtype,
        species_common_name, tissue, marker_direction, confidence, bbsr_verified,
        submitter, source_titles, source_url, notes FROM marker_atlas"""
    params = []
    if query:
        sql += (
            " WHERE concat_ws(' ', gene_symbol, major_cell_type, cell_subtype, species, tissue, source_titles, submitter) ILIKE ?"
        )
        params = [f"%{query}%"]
    browse_rows = frame(sql + " ORDER BY cell_type, gene_symbol", params)
    selection = st.dataframe(
        browse_rows,
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        key="browse_assertions",
        column_config={
            "source_url": st.column_config.LinkColumn(
                "Source link", display_text="Open source ↗"
            )
        },
    )
    st.caption("Select a row to edit it directly below the table.")
    if selection.selection.rows:
        selected = browse_rows.iloc[selection.selection.rows[0]]
        render_assertion_editor(selected, f"browse_{int(selected.assertion_id)}")

with add_tab:
    with st.form("new_assertion", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        species = c1.text_input("Scientific species name*", value="Homo sapiens")
        common = c1.text_input("Common name", value="human")
        symbol = c2.text_input("Gene symbol*")
        stable_id = c2.text_input("Stable gene ID")
        gene_aliases = c2.text_input("Gene aliases", placeholder="Alias 1; Alias 2")
        major_cell_type = c3.text_input("Major cell type*")
        cell_subtype = c3.text_input("Subtype")
        ontology = c3.text_input("Subtype or major Cell Ontology ID", placeholder="CL:0000540")
        tissue = c1.text_input("Tissue")
        condition = c2.text_input("Condition")
        stage = c3.text_input("Developmental stage")
        direction = c1.selectbox("Direction", ["positive", "negative"])
        confidence = c2.selectbox("Confidence", ["moderate", "high", "low"])
        assay = c3.text_input("Assay", value="scRNA-seq")
        submitter = c1.text_input("Submitter")
        verified = st.checkbox("BBSR verified")
        notes = st.text_area("Curator notes")
        submitted = st.form_submit_button("Save marker assertion", type="primary")
    if submitted:
        try:
            parsed_aliases = [
                alias.strip() for alias in gene_aliases.split(";") if alias.strip()
            ]
            with database(DB_PATH) as con:
                species_id = upsert_species(con, species, common)
                gene_id = upsert_gene(
                    con,
                    species_id,
                    symbol,
                    stable_id,
                    parsed_aliases or None,
                )
                major_cell_id = upsert_cell_type(con, major_cell_type)
                cell_id = (
                    upsert_cell_type(
                        con,
                        cell_subtype,
                        ontology,
                        parent_cell_type_id=major_cell_id,
                    )
                    if cell_subtype
                    else major_cell_id
                )
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
                    submitter=submitter,
                    notes=notes,
                )
            st.success(f"Saved assertion {assertion_id}")
        except Exception as exc:
            st.error(str(exc))

with edit_tab:
    assertions = frame(
        "SELECT assertion_id, gene_id, gene_symbol, gene_aliases, major_cell_type, cell_subtype, tissue, marker_direction, confidence, bbsr_verified, submitter, notes, source_url FROM marker_atlas ORDER BY assertion_id"
    )
    if assertions.empty:
        st.info("No assertions to edit yet.")
    else:
        choice = st.selectbox(
            "Assertion",
            assertions.assertion_id.tolist(),
            format_func=lambda value: (
                f"#{value} · {assertions.loc[assertions.assertion_id == value, 'gene_symbol'].iloc[0]} → {assertions.loc[assertions.assertion_id == value, 'major_cell_type'].iloc[0]}"
            ),
        )
        current = assertions.loc[assertions.assertion_id == choice].iloc[0]
        render_assertion_editor(current, f"manage_{int(choice)}")

with import_tab:
    st.markdown(
        "Upload a CSV with at least `species`, `gene_symbol`, and `major_cell_type`. "
        "The template includes every supported column and an embedded column guide."
    )
    st.download_button(
        "Download CSV template",
        data=TEMPLATE_PATH.read_bytes(),
        file_name="markercodex_import_template.csv",
        mime="text/csv",
    )
    upload = st.file_uploader("Marker CSV", type="csv")
    if upload:
        preview = pd.read_csv(upload, keep_default_na=False, comment="#")
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
        frame(
            """SELECT *, coalesce(
                url,
                CASE WHEN doi IS NOT NULL THEN 'https://doi.org/' || doi END,
                CASE WHEN pmid IS NOT NULL THEN 'https://pubmed.ncbi.nlm.nih.gov/' || pmid || '/' END
            ) AS source_link
            FROM sources ORDER BY publication_year DESC NULLS LAST, title"""
        ),
        use_container_width=True,
        hide_index=True,
        column_config={
            "source_link": st.column_config.LinkColumn(
                "Open source", display_text="Open source ↗"
            )
        },
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
