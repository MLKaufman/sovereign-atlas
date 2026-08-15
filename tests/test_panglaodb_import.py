import runpy

import pandas as pd

transform = runpy.run_path("scripts/import_panglaodb.py")["transform"]


def test_panglaodb_transform_expands_species_and_preserves_metadata(tmp_path):
    source = tmp_path / "panglaodb.tsv"
    pd.DataFrame(
        [
            {
                "species": "Mm Hs",
                "official gene symbol": "GENE1",
                "cell type": "Example cells",
                "nicknames": "B|A",
                "ubiquitousness index": 0.1,
                "product description": "Example product",
                "gene type": "protein-coding gene",
                "canonical marker": 1,
                "germ layer": "Mesoderm",
                "organ": "Immune system",
                "sensitivity_human": 0.8,
                "sensitivity_mouse": 0.7,
                "specificity_human": 0.9,
                "specificity_mouse": 0.6,
            },
            {
                "species": "invalid",
                "official gene symbol": "GENE2",
                "cell type": "Other cells",
                "nicknames": "",
                "ubiquitousness index": 0.2,
                "product description": "Other product",
                "gene type": "other",
                "canonical marker": "",
                "germ layer": "",
                "organ": "Other",
                "sensitivity_human": "",
                "sensitivity_mouse": "",
                "specificity_human": "",
                "specificity_mouse": "",
            },
        ]
    ).to_csv(source, sep="\t", index=False)

    frame, stats = transform(source, "PanglaoDB test source")

    assert stats == {
        "source_rows": 2,
        "skipped_rows": 1,
        "expanded_rows": 2,
        "cell_types": 1,
    }
    assert set(frame.species) == {"Homo sapiens", "Mus musculus"}
    assert set(frame.gene_symbol) == {"GENE1", "Gene1"}
    assert set(frame.gene_aliases) == {"A; B"}
    assert set(frame.major_cell_type) == {"Example cells"}
    assert set(frame.bbsr_verified) == {"false"}
    assert set(frame.confidence) == {"high"}
