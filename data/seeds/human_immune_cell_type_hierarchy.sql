-- Apply to an initialized database before importing
-- human_b_t_macrophage_markers.csv. DuckDB does not permit updating a
-- cell-type row after marker_assertions reference it, so parents are assigned
-- when each cell type is first inserted.
BEGIN TRANSACTION;

INSERT INTO species (scientific_name, common_name, taxonomy_id)
VALUES ('Homo sapiens', 'human', 9606)
ON CONFLICT (scientific_name) DO NOTHING;

INSERT INTO cell_types (name, ontology_id, description)
VALUES
    ('lymphocyte', '', 'Parent category for B and T lymphocytes.'),
    ('mononuclear phagocyte', '', 'Parent category for macrophages and related phagocytes.')
ON CONFLICT (name, ontology_id) DO NOTHING;

INSERT INTO cell_types (name, ontology_id, parent_cell_type_id)
SELECT child.name, '', parent.cell_type_id
FROM (VALUES
    ('B cell', 'lymphocyte'),
    ('T cell', 'lymphocyte'),
    ('macrophage', 'mononuclear phagocyte')
) AS child(name, parent_name)
JOIN cell_types AS parent ON parent.name = child.parent_name AND parent.ontology_id = ''
ON CONFLICT (name, ontology_id) DO NOTHING;

INSERT INTO cell_types (name, ontology_id, parent_cell_type_id)
SELECT child.name, '', parent.cell_type_id
FROM (VALUES
    ('transitional B cell', 'B cell'),
    ('naive B cell', 'B cell'),
    ('memory B cell', 'B cell'),
    ('plasmablast', 'B cell'),
    ('CD4-positive helper T cell', 'T cell'),
    ('CD8-positive cytotoxic T cell', 'T cell'),
    ('mucosal-associated invariant T cell', 'T cell'),
    ('gamma-delta T cell', 'T cell'),
    ('tissue-resident memory T cell', 'T cell'),
    ('resident macrophage', 'macrophage'),
    ('C1QC-positive macrophage', 'macrophage'),
    ('FCN1-positive monocyte-derived macrophage', 'macrophage'),
    ('TREM2-positive SPP1-positive tumor-associated macrophage', 'macrophage'),
    ('IL4I1-positive tumor-associated macrophage', 'macrophage'),
    ('alveolar macrophage', 'macrophage'),
    ('Kupffer cell', 'macrophage'),
    ('microglial cell', 'macrophage')
) AS child(name, parent_name)
JOIN cell_types AS parent ON parent.name = child.parent_name AND parent.ontology_id = ''
ON CONFLICT (name, ontology_id) DO NOTHING;

INSERT INTO cell_types (name, ontology_id, parent_cell_type_id)
SELECT child.name, '', parent.cell_type_id
FROM (VALUES
    ('unswitched memory B cell', 'memory B cell'),
    ('switched memory B cell', 'memory B cell'),
    ('naive CD4-positive T cell', 'CD4-positive helper T cell'),
    ('central memory CD4-positive T cell', 'CD4-positive helper T cell'),
    ('effector memory CD4-positive T cell', 'CD4-positive helper T cell'),
    ('regulatory T cell', 'CD4-positive helper T cell'),
    ('follicular helper T cell', 'CD4-positive helper T cell'),
    ('naive CD8-positive T cell', 'CD8-positive cytotoxic T cell'),
    ('central memory CD8-positive T cell', 'CD8-positive cytotoxic T cell'),
    ('effector memory CD8-positive T cell', 'CD8-positive cytotoxic T cell'),
    ('terminally differentiated effector memory CD8-positive T cell', 'CD8-positive cytotoxic T cell')
) AS child(name, parent_name)
JOIN cell_types AS parent ON parent.name = child.parent_name AND parent.ontology_id = ''
ON CONFLICT (name, ontology_id) DO NOTHING;

COMMIT;
