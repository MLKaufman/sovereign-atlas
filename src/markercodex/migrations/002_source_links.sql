DROP VIEW marker_atlas;

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
    a.bbsr_verified,
    a.notes,
    count(e.evidence_id) AS evidence_count,
    string_agg(DISTINCT s.title, '; ' ORDER BY s.title) AS source_titles,
    string_agg(DISTINCT coalesce(s.doi, s.pmid, s.url), '; ') FILTER (
        WHERE coalesce(s.doi, s.pmid, s.url) IS NOT NULL
    ) AS source_identifiers,
    min(coalesce(
        s.url,
        CASE WHEN s.doi IS NOT NULL THEN 'https://doi.org/' || s.doi END,
        CASE WHEN s.pmid IS NOT NULL THEN 'https://pubmed.ncbi.nlm.nih.gov/' || s.pmid || '/' END
    )) AS source_url,
    list(struct_pack(
        title := s.title,
        url := coalesce(
            s.url,
            CASE WHEN s.doi IS NOT NULL THEN 'https://doi.org/' || s.doi END,
            CASE WHEN s.pmid IS NOT NULL THEN 'https://pubmed.ncbi.nlm.nih.gov/' || s.pmid || '/' END
        )
    ) ORDER BY s.title) FILTER (WHERE s.source_id IS NOT NULL) AS source_links,
    a.updated_at
FROM marker_assertions a
JOIN genes g ON g.gene_id = a.gene_id
JOIN species sp ON sp.species_id = g.species_id
JOIN cell_types ct ON ct.cell_type_id = a.cell_type_id
LEFT JOIN evidence e ON e.assertion_id = a.assertion_id
LEFT JOIN sources s ON s.source_id = e.source_id
GROUP BY ALL;
