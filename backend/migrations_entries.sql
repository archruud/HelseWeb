-- ============================================================
-- Migrasjon: Journaloppføringer + pgvector semantisk søk
-- Gjør innholdet søkbart per FAKTISK dato OG på betydning (semantisk)
-- ============================================================

-- Aktiver pgvector (semantisk vektorsøk)
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS journal_entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    entry_date DATE,                 -- faktisk dato funnet i teksten
    page_number INTEGER,             -- omtrentlig side i original-PDF
    heading TEXT,                    -- f.eks. "INNLEGGELSE", "JOURNALOPPTAK"
    content TEXT,                    -- selve tekstutdraget for denne datoen
    hospital_id INTEGER REFERENCES hospitals(id),
    search_vector tsvector,          -- nøkkelordsøk (norsk)
    embedding vector(768),           -- semantisk søk (nomic-embed-text = 768 dim)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_entries_date ON journal_entries(entry_date);
CREATE INDEX IF NOT EXISTS idx_entries_document ON journal_entries(document_id);
CREATE INDEX IF NOT EXISTS idx_entries_search ON journal_entries USING gin(search_vector);
-- HNSW-indeks for rask semantisk likhet (cosine)
CREATE INDEX IF NOT EXISTS idx_entries_embedding ON journal_entries USING hnsw (embedding vector_cosine_ops);

-- Trigger for nøkkelord-søkeindeks
CREATE OR REPLACE FUNCTION entries_search_trigger() RETURNS trigger AS $$
BEGIN
    NEW.search_vector :=
        setweight(to_tsvector('norwegian', coalesce(NEW.heading,'')), 'A') ||
        setweight(to_tsvector('norwegian', coalesce(NEW.content,'')), 'B');
    RETURN NEW;
END
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_entries_search ON journal_entries;
CREATE TRIGGER trg_entries_search BEFORE INSERT OR UPDATE ON journal_entries
    FOR EACH ROW EXECUTE FUNCTION entries_search_trigger();
