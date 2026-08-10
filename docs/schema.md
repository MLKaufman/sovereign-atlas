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

## Deletion behavior

The curator explicitly removes evidence links before deleting an assertion. Genes, cell types, species, and sources are retained because they may be shared by other assertions. Orphan cleanup should be deliberate and reviewed.

