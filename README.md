# MarkerCodex

**MarkerCodex is a self-contained, evidence-backed scRNA-seq marker atlas.** It models marker claims as Gene ↔ Cell type assertions in biological context, then attaches one or more sources through explicit evidence records. One gene can identify many cell types; one source can support many claims; and one claim can carry several independent sources without duplicated rows.

**[Open the live MarkerCodex atlas](https://mlkaufman.github.io/sovereign-atlas/)**

The repository is the application: DuckDB is canonical, Parquet and CSV snapshots are portable, GitHub Pages hosts the generated atlas, and a local Streamlit curator handles maintenance. There is no server, account system, or external API to operate.

## What is included

- Normalized DuckDB schema with versioned SQL migrations
- Read-stable `marker_atlas` view for downstream consumers
- Parquet and CSV exports
- Static, responsive atlas with search, filters, sorting, and filtered-gene copy buttons
- Local curator for browsing, adding, editing, deleting, bulk importing, and reference linking
- Tests, linting, GitHub Actions validation, and GitHub Pages deployment

## Quick start

Install [uv](https://docs.astral.sh/uv/), then:

```bash
uv sync --all-extras --dev
uv run markercodex init
uv run streamlit run curator/app.py
```

The curator writes to `data/markercodex.duckdb` by default. To use another database:

```bash
MARKERCODEX_DB=/path/to/atlas.duckdb uv run streamlit run curator/app.py
```

Build portable exports and the static site:

```bash
uv run markercodex export
uv run markercodex build-site
uv run python -m http.server --directory site 8000
```

Open `http://localhost:8000`. A local server is needed because browsers usually block `fetch()` from `file://` pages.

## Add data

Use the curator for individual records or copy `data/import_template.csv` for bulk work:

```bash
uv run markercodex import path/to/markers.csv
```

Required columns are `species`, `gene_symbol`, and `cell_type`. All other template columns are optional. Re-importing the same assertion updates its confidence, verification, and notes. Rows are imported in one transaction, so a bad row does not leave a partial batch.

`human_verified` accepts `true`, `yes`, `y`, or `1`. Source columns create or reuse a reference and link it to the assertion as evidence.

## Access from other apps

DuckDB gives local apps direct, read-only access:

```python
import duckdb

con = duckdb.connect("data/markercodex.duckdb", read_only=True)
markers = con.sql("""
    SELECT gene_symbol, cell_type, confidence
    FROM marker_atlas
    WHERE species = 'Homo sapiens' AND tissue = 'lung'
""").df()
```

R can query the same database with `duckdb` + `DBI`, or use the snapshots:

```r
library(arrow)
markers <- read_parquet("data/exports/markers.parquet")
lung <- subset(markers, species == "Homo sapiens" & tissue == "lung")
```

CSV is available at `data/exports/markers.csv`. For remote, read-only use, other apps can download the raw Parquet/CSV release or GitHub Pages asset. No live API is required; DuckDB can also query a hosted Parquet URL directly when its HTTP extension is available.

## Publish on GitHub Pages

1. Create a GitHub repository and push this project to its `main` branch.
2. In **Settings → Pages → Build and deployment**, choose **GitHub Actions**.
3. Commit curated changes to `data/markercodex.duckdb`.

The published atlas is available at:

<https://mlkaufman.github.io/sovereign-atlas/>

If the repository is private, GitHub Pages requires GitHub Pro, Team, or Enterprise. On GitHub Free, make the repository public before enabling Pages.

The Pages workflow regenerates the exports and site from the canonical database, then deploys the `site/` artifact. The generated site is intentionally not committed. Pull requests run schema initialization, exports, the site build, linting, and tests.

## Repository layout

```text
data/                         canonical DuckDB, import template, portable exports
curator/app.py                local Streamlit curation UI
src/markercodex/
  migrations/                 ordered SQL schema migrations
  site_template/              self-contained static atlas
  db.py                       initialization and migration runner
  operations.py               shared curation operations
  importer.py                 transactional CSV bulk import
  export.py                   Parquet, CSV, and static-site generation
tests/                        schema, relationship, import, and build tests
.github/workflows/            validation and GitHub Pages deployment
```

See [docs/schema.md](docs/schema.md) for modeling details and [CONTRIBUTING.md](CONTRIBUTING.md) for curation expectations.

## Data integrity and scope

- A marker is an evidence-backed assertion, not a universal truth. Tissue, condition, stage, assay, direction, and species matter.
- “Human verified” records source review; it is not a biological quality guarantee.
- Gene symbols are unique only within species.
- Cell Ontology IDs are strongly encouraged for interoperable annotations.
- Never edit DuckDB with two writing processes at once. Stop the curator before running a bulk import.

## License

Code is MIT licensed. Before publishing curated records, choose and document a compatible data license based on the incorporated sources; the MIT code license does not override source-database terms.
