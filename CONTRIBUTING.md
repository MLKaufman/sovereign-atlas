# Contributing to MarkerCodex

Marker contributions need a gene, species, cell type, marker direction, biological context, and a traceable source. Prefer an exact DOI or PMID plus a figure/table/location over a bare URL.

1. Create a branch.
2. Run the local curator with `uv run streamlit run curator/app.py` or prepare a CSV from `data/import_template.csv`.
3. Export and rebuild with `uv run markercodex export` and `uv run markercodex build-site`.
4. Run `uv run ruff check .` and `uv run pytest`.
5. Open a pull request describing the curation decisions and source evidence.

Do not add sensitive or unpublished data. Only the BBSR team may check
`bbsr_verified`; it means a BBSR curator inspected the claimed source-to-marker
relationship, not that the marker is universally specific.
