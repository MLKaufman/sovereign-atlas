# Data model

MarkerCodex stores biological claims separately from the evidence that supports them.

```text
species 1 ── * genes 1 ── * marker_assertions * ── 1 cell_types
                                  │
                                  *
                               evidence
                                  *
                                  │
                                  1
                               sources
```

## Why assertions and evidence are separate

A marker assertion says that one gene is a positive or negative marker for one cell type in a defined biological context. A source is a paper, database, preprint, or expert review. The `evidence` junction allows multiple sources to support one assertion without repeating the biological claim. It also lets one source support many assertions.

The context fields—species (through the gene), tissue, condition, developmental stage, assay, and direction—are part of assertion identity. This prevents a broad claim from overwriting a context-specific one.

## Stable consumer interface

Consumers should prefer the `marker_atlas` view. It joins normalized tables and aggregates citations to one row per assertion. The generated Parquet and CSV files contain the same view. Internal table structure can therefore evolve through migrations without forcing downstream apps to change immediately.

## Reference matrix catalog

Reusable CSV and TSV reference matrices are intentionally stored outside the marker
assertion database. `data/reference_matrices.duckdb` contains one
`reference_matrices` record per file, and `data/reference_matrices/files/` contains
the uploaded bytes. The catalog records:

- identity and context: title, description, species, tissue, condition, stage,
  assay, and platform;
- interpretation: row and column entity types, feature identifier type, value type,
  and normalization;
- provenance: source title, citation, DOI, PMID, URL, year, license, submitter, and notes;
- file integrity: original and stored names, path, format, delimiter, dimensions,
  column names, byte size, SHA-256 checksum, UUID, and timestamps.

Stored filenames follow this convention:

```text
refmat--{species}--{tissue}--{assay}--{source}--{year}--{id8}.{csv|tsv}
```

The readable fields make loose files identifiable; the final eight UUID characters
make names unique. The full UUID and SHA-256 checksum remain in the catalog. Exact
duplicate files are rejected.

## Deletion behavior

The curator explicitly removes evidence links before deleting an assertion. Genes, cell types, species, and sources are retained because they may be shared by other assertions. Orphan cleanup should be deliberate and reviewed.
