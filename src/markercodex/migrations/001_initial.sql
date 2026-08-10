CREATE SEQUENCE IF NOT EXISTS species_id_seq START 1;
CREATE SEQUENCE IF NOT EXISTS gene_id_seq START 1;
CREATE SEQUENCE IF NOT EXISTS cell_type_id_seq START 1;
CREATE SEQUENCE IF NOT EXISTS reference_id_seq START 1;
CREATE SEQUENCE IF NOT EXISTS assertion_id_seq START 1;
CREATE SEQUENCE IF NOT EXISTS evidence_id_seq START 1;

CREATE TABLE IF NOT EXISTS species (
    species_id BIGINT PRIMARY KEY DEFAULT nextval('species_id_seq'),
    scientific_name VARCHAR NOT NULL UNIQUE,
    common_name VARCHAR,
    taxonomy_id INTEGER UNIQUE
);

CREATE TABLE IF NOT EXISTS genes (
    gene_id BIGINT PRIMARY KEY DEFAULT nextval('gene_id_seq'),
    species_id BIGINT NOT NULL REFERENCES species(species_id),
    symbol VARCHAR NOT NULL,
    stable_id VARCHAR,
    aliases VARCHAR[],
    description VARCHAR,
    UNIQUE (species_id, symbol)
);

CREATE TABLE IF NOT EXISTS cell_types (
    cell_type_id BIGINT PRIMARY KEY DEFAULT nextval('cell_type_id_seq'),
    name VARCHAR NOT NULL,
    ontology_id VARCHAR NOT NULL DEFAULT '',
    parent_cell_type_id BIGINT REFERENCES cell_types(cell_type_id),
    description VARCHAR,
    UNIQUE (name, ontology_id)
);

CREATE TABLE IF NOT EXISTS sources (
    source_id BIGINT PRIMARY KEY DEFAULT nextval('reference_id_seq'),
    title VARCHAR NOT NULL,
    citation VARCHAR,
    doi VARCHAR UNIQUE,
    pmid VARCHAR UNIQUE,
    url VARCHAR,
    publication_year INTEGER,
    source_type VARCHAR NOT NULL DEFAULT 'publication',
    notes VARCHAR,
    CHECK (source_type IN ('publication', 'database', 'preprint', 'expert', 'other'))
);

CREATE TABLE IF NOT EXISTS marker_assertions (
    assertion_id BIGINT PRIMARY KEY DEFAULT nextval('assertion_id_seq'),
    gene_id BIGINT NOT NULL REFERENCES genes(gene_id),
    cell_type_id BIGINT NOT NULL REFERENCES cell_types(cell_type_id),
    marker_direction VARCHAR NOT NULL DEFAULT 'positive',
    tissue VARCHAR NOT NULL DEFAULT '',
    condition VARCHAR NOT NULL DEFAULT '',
    developmental_stage VARCHAR NOT NULL DEFAULT '',
    assay VARCHAR NOT NULL DEFAULT 'scRNA-seq',
    confidence VARCHAR NOT NULL DEFAULT 'moderate',
    human_verified BOOLEAN NOT NULL DEFAULT FALSE,
    notes VARCHAR,
    created_at TIMESTAMP NOT NULL DEFAULT current_timestamp,
    updated_at TIMESTAMP NOT NULL DEFAULT current_timestamp,
    CHECK (marker_direction IN ('positive', 'negative')),
    CHECK (confidence IN ('low', 'moderate', 'high')),
    UNIQUE (gene_id, cell_type_id, marker_direction, tissue, condition, developmental_stage, assay)
);

CREATE TABLE IF NOT EXISTS evidence (
    evidence_id BIGINT PRIMARY KEY DEFAULT nextval('evidence_id_seq'),
    assertion_id BIGINT NOT NULL REFERENCES marker_assertions(assertion_id),
    source_id BIGINT NOT NULL REFERENCES sources(source_id),
    evidence_type VARCHAR NOT NULL DEFAULT 'reported_marker',
    location VARCHAR NOT NULL DEFAULT '',
    evidence_note VARCHAR,
    added_at TIMESTAMP NOT NULL DEFAULT current_timestamp,
    CHECK (evidence_type IN ('reported_marker', 'differential_expression', 'figure', 'table', 'expert_review', 'other')),
    UNIQUE (assertion_id, source_id, evidence_type, location)
);

CREATE INDEX IF NOT EXISTS idx_genes_symbol ON genes(symbol);
CREATE INDEX IF NOT EXISTS idx_cell_types_name ON cell_types(name);
CREATE INDEX IF NOT EXISTS idx_assertions_gene ON marker_assertions(gene_id);
CREATE INDEX IF NOT EXISTS idx_assertions_cell_type ON marker_assertions(cell_type_id);

CREATE OR REPLACE VIEW marker_atlas AS
SELECT
    a.assertion_id,
    g.symbol AS gene_symbol,
    g.stable_id,
    sp.scientific_name AS species,
    sp.common_name AS species_common_name,
    ct.name AS cell_type,
    ct.ontology_id,
    a.marker_direction,
    a.tissue,
    a.condition,
    a.developmental_stage,
    a.assay,
    a.confidence,
    a.human_verified,
    a.notes,
    count(e.evidence_id) AS evidence_count,
    string_agg(DISTINCT s.title, '; ' ORDER BY s.title) AS source_titles,
    string_agg(DISTINCT coalesce(s.doi, s.pmid, s.url), '; ') FILTER (
        WHERE coalesce(s.doi, s.pmid, s.url) IS NOT NULL
    ) AS source_identifiers,
    a.updated_at
FROM marker_assertions a
JOIN genes g ON g.gene_id = a.gene_id
JOIN species sp ON sp.species_id = g.species_id
JOIN cell_types ct ON ct.cell_type_id = a.cell_type_id
LEFT JOIN evidence e ON e.assertion_id = a.assertion_id
LEFT JOIN sources s ON s.source_id = e.source_id
GROUP BY ALL;
