-- ============================================================
-- Migrasjon Steg 2-5: Roller, søk, tråder, tidslinje
-- Kjøres trygt flere ganger (idempotent der mulig)
-- ============================================================

-- ---------- STEG 2: Roller ----------
-- Nye roller: super_editor, editor, viewer (i tillegg til admin)
-- Marker admin opprettet ved installasjon (kan ikke slettes/endres via web)
ALTER TABLE users ADD COLUMN IF NOT EXISTS is_system_admin BOOLEAN DEFAULT FALSE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS must_change_password BOOLEAN DEFAULT FALSE;

-- Sett eksisterende admin som system-admin
UPDATE users SET is_system_admin = TRUE WHERE username = 'admin';
UPDATE users SET is_active = TRUE WHERE is_active IS NULL;

-- Oppdater rolle-rettigheter for nye roller
DELETE FROM role_permissions WHERE role IN ('super_editor','editor','viewer','doctor','specialist','psychologist','lawyer','guest');

INSERT INTO role_permissions (role, permission) VALUES
    -- Super Editor: alt unntatt brukeradmin/systemadmin
    ('super_editor','view_somatic'),
    ('super_editor','view_psychiatric'),
    ('super_editor','view_private'),
    ('super_editor','upload'),
    ('super_editor','annotate'),
    ('super_editor','export'),
    ('super_editor','print'),
    ('super_editor','ai_query'),
    ('super_editor','change_own_password'),
    -- Editor: lese helsefiler + laste opp + notere
    ('editor','view_somatic'),
    ('editor','view_psychiatric'),
    ('editor','upload'),
    ('editor','annotate'),
    ('editor','export'),
    ('editor','print'),
    ('editor','ai_query'),
    ('editor','change_own_password'),
    -- Viewer: kun lese helsefiler
    ('viewer','view_somatic'),
    ('viewer','view_psychiatric'),
    ('viewer','print')
ON CONFLICT (role, permission) DO NOTHING;

-- ---------- STEG 4: Tråder og metadata ----------
-- Felt for korrespondanse-tråding og AI-metadata
ALTER TABLE documents ADD COLUMN IF NOT EXISTS sender TEXT;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS recipient TEXT;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS is_reply BOOLEAN DEFAULT FALSE;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS correspondence_key TEXT;  -- grupperer en dialog
ALTER TABLE documents ADD COLUMN IF NOT EXISTS content_hash TEXT;        -- for duplikatsjekk (Steg 8)
ALTER TABLE documents ADD COLUMN IF NOT EXISTS ai_indexed BOOLEAN DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS idx_documents_correspondence ON documents(correspondence_key);
CREATE INDEX IF NOT EXISTS idx_documents_content_hash ON documents(content_hash);
CREATE INDEX IF NOT EXISTS idx_documents_department ON documents(department);

-- ---------- STEG 3: Søk - norsk fulltekst-indeks ----------
-- Generert tsvector-kolonne for konsekvent fulltekstsøk
ALTER TABLE documents ADD COLUMN IF NOT EXISTS search_vector tsvector;

-- Fyll search_vector for eksisterende rader
UPDATE documents SET search_vector =
    setweight(to_tsvector('norwegian', coalesce(title,'')), 'A') ||
    setweight(to_tsvector('norwegian', coalesce(document_type,'')), 'B') ||
    setweight(to_tsvector('norwegian', coalesce(doctor_name,'')), 'B') ||
    setweight(to_tsvector('norwegian', coalesce(ocr_text,'')), 'C')
WHERE search_vector IS NULL;

CREATE INDEX IF NOT EXISTS idx_documents_search_vector ON documents USING gin(search_vector);

-- Trigger som holder search_vector oppdatert ved insert/update
CREATE OR REPLACE FUNCTION documents_search_trigger() RETURNS trigger AS $$
BEGIN
    NEW.search_vector :=
        setweight(to_tsvector('norwegian', coalesce(NEW.title,'')), 'A') ||
        setweight(to_tsvector('norwegian', coalesce(NEW.document_type,'')), 'B') ||
        setweight(to_tsvector('norwegian', coalesce(NEW.doctor_name,'')), 'B') ||
        setweight(to_tsvector('norwegian', coalesce(NEW.ocr_text,'')), 'C');
    RETURN NEW;
END
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_documents_search ON documents;
CREATE TRIGGER trg_documents_search BEFORE INSERT OR UPDATE ON documents
    FOR EACH ROW EXECUTE FUNCTION documents_search_trigger();

-- ---------- STEG 5: Tidslinje ----------
-- (timeline_events finnes allerede i schema.sql)
-- Legg til felt for AI-generert flagg hvis mangler
ALTER TABLE timeline_events ADD COLUMN IF NOT EXISTS source_document_ids UUID[];
