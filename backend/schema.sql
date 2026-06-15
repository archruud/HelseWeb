-- ============================================================
-- Helsejournal PHR - Database Schema (PostgreSQL)
-- ============================================================

-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- For fuzzy text search

-- ============================================================
-- USERS & AUTHENTICATION
-- ============================================================

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL DEFAULT 'guest',  -- admin, doctor, lawyer, psychologist, specialist, guest
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_login TIMESTAMP WITH TIME ZONE
);

-- Role permissions table
CREATE TABLE role_permissions (
    id SERIAL PRIMARY KEY,
    role VARCHAR(50) NOT NULL,
    permission VARCHAR(100) NOT NULL,  -- view_somatic, view_psychiatric, view_private, upload, annotate, admin, export, print
    UNIQUE(role, permission)
);

-- Access grants (fine-grained per-user access)
CREATE TABLE access_grants (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    grant_type VARCHAR(50) NOT NULL,  -- hospital, time_range, document_type, specific_document
    grant_value TEXT NOT NULL,  -- e.g., "Kalnes", "2020-2024", "epikrise"
    granted_by UUID REFERENCES users(id),
    expires_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================
-- HOSPITALS & INSTITUTIONS
-- ============================================================

CREATE TABLE hospitals (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    short_name VARCHAR(50),
    address TEXT,
    city VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE,  -- false for nedlagte sykehus
    parent_organization VARCHAR(255),  -- e.g., "Sykehuset Østfold HF"
    notes TEXT
);

-- ============================================================
-- DOCUMENTS
-- ============================================================

CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_number VARCHAR(50),  -- Original "Dokument nummer" from journal
    title VARCHAR(500) NOT NULL,
    document_type VARCHAR(100),  -- Epikrise, Operasjonsbeskrivelse, Poliklinisk notat, etc.
    category VARCHAR(50) DEFAULT 'somatic',  -- somatic, psychiatric, tsb, private
    hospital_id INTEGER REFERENCES hospitals(id),
    department VARCHAR(255),
    doctor_name VARCHAR(255),
    doctor_approved_by VARCHAR(255),
    
    -- Dates
    document_date DATE,  -- When the medical event happened
    created_date TIMESTAMP WITH TIME ZONE,  -- When document was created in system
    uploaded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Content
    file_path TEXT NOT NULL,  -- Path to PDF file on storage
    file_size_bytes BIGINT,
    page_count INTEGER,
    ocr_text TEXT,  -- Full extracted text for search
    summary TEXT,  -- AI-generated summary
    
    -- Metadata
    diagnoses TEXT[],  -- Array of ICD-10 codes
    procedures TEXT[],  -- Array of procedure codes
    keywords TEXT[],  -- AI-extracted keywords
    
    -- Threading
    thread_id UUID,  -- Links related documents together
    parent_document_id UUID REFERENCES documents(id),
    
    -- Status
    is_verified BOOLEAN DEFAULT FALSE,
    uploaded_by UUID REFERENCES users(id),
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Full-text search index
CREATE INDEX idx_documents_ocr_text ON documents USING gin(to_tsvector('norwegian', ocr_text));
CREATE INDEX idx_documents_title ON documents USING gin(to_tsvector('norwegian', title));
CREATE INDEX idx_documents_date ON documents(document_date);
CREATE INDEX idx_documents_hospital ON documents(hospital_id);
CREATE INDEX idx_documents_type ON documents(document_type);
CREATE INDEX idx_documents_thread ON documents(thread_id);
CREATE INDEX idx_documents_category ON documents(category);

-- ============================================================
-- DOCUMENT THREADS (linking related documents)
-- ============================================================

CREATE TABLE document_threads (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title VARCHAR(500),
    description TEXT,
    start_date DATE,
    end_date DATE,
    thread_type VARCHAR(50),  -- referral_chain, hospitalization, treatment_series
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================
-- PATIENT ANNOTATIONS (gule lapper)
-- ============================================================

CREATE TABLE annotations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id),
    annotation_type VARCHAR(50) DEFAULT 'note',  -- note, correction, important, question
    content TEXT NOT NULL,
    page_number INTEGER,  -- Which page of the PDF
    is_private BOOLEAN DEFAULT FALSE,  -- Only visible to admin/patient
    visibility VARCHAR(50) DEFAULT 'all',  -- all, doctors_only, admin_only
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_annotations_document ON annotations(document_id);

-- ============================================================
-- PRIVATE DATA (patient's own files)
-- ============================================================

CREATE TABLE private_files (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title VARCHAR(500) NOT NULL,
    description TEXT,
    file_type VARCHAR(50),  -- audio, transcript, image, document, video
    file_path TEXT NOT NULL,
    file_size_bytes BIGINT,
    duration_seconds INTEGER,  -- For audio/video
    transcript TEXT,  -- Transcribed text from audio
    
    -- Linking
    related_document_id UUID REFERENCES documents(id),  -- Optional link to a journal document
    related_date DATE,
    
    -- Access control
    visibility VARCHAR(50) DEFAULT 'admin_only',  -- admin_only, with_permission
    allowed_roles TEXT[],  -- Which roles can see this
    
    uploaded_by UUID REFERENCES users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_private_files_date ON private_files(related_date);
CREATE INDEX idx_private_files_type ON private_files(file_type);

-- ============================================================
-- TIMELINE EVENTS (key milestones)
-- ============================================================

CREATE TABLE timeline_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title VARCHAR(500) NOT NULL,
    description TEXT,
    event_date DATE NOT NULL,
    end_date DATE,  -- For events spanning multiple days
    event_type VARCHAR(50),  -- hospitalization, surgery, diagnosis, milestone, referral
    severity VARCHAR(20) DEFAULT 'normal',  -- normal, important, critical
    hospital_id INTEGER REFERENCES hospitals(id),
    document_id UUID REFERENCES documents(id),  -- Link to primary document
    auto_generated BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_timeline_date ON timeline_events(event_date);

-- ============================================================
-- AI INTERACTIONS LOG
-- ============================================================

CREATE TABLE ai_queries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id),
    query_text TEXT NOT NULL,
    response_text TEXT,
    source_documents UUID[],  -- Which documents were used
    model_used VARCHAR(100),
    tokens_used INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================
-- AUDIT LOG
-- ============================================================

CREATE TABLE audit_log (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    action VARCHAR(100) NOT NULL,  -- login, view_document, download, export, upload, annotate
    resource_type VARCHAR(50),  -- document, private_file, annotation
    resource_id UUID,
    details JSONB,
    ip_address INET,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_audit_log_user ON audit_log(user_id);
CREATE INDEX idx_audit_log_date ON audit_log(created_at);

-- ============================================================
-- SEED DATA: Default roles and permissions
-- ============================================================

INSERT INTO role_permissions (role, permission) VALUES
    ('admin', 'view_somatic'),
    ('admin', 'view_psychiatric'),
    ('admin', 'view_private'),
    ('admin', 'upload'),
    ('admin', 'annotate'),
    ('admin', 'admin'),
    ('admin', 'export'),
    ('admin', 'print'),
    ('admin', 'ai_query'),
    ('doctor', 'view_somatic'),
    ('doctor', 'view_psychiatric'),
    ('doctor', 'annotate'),
    ('doctor', 'export'),
    ('doctor', 'print'),
    ('doctor', 'ai_query'),
    ('specialist', 'view_somatic'),
    ('specialist', 'export'),
    ('specialist', 'print'),
    ('specialist', 'ai_query'),
    ('psychologist', 'view_psychiatric'),
    ('psychologist', 'annotate'),
    ('psychologist', 'print'),
    ('lawyer', 'view_somatic'),
    ('lawyer', 'export'),
    ('lawyer', 'print'),
    ('guest', 'view_somatic');

-- Seed hospitals
INSERT INTO hospitals (name, short_name, city, is_active, parent_organization) VALUES
    ('Sykehuset Telemark HF', 'STHF', 'Skien', TRUE, 'Sykehuset Telemark HF'),
    ('Sykehuset Østfold - Kalnes', 'SØ Kalnes', 'Sarpsborg', TRUE, 'Sykehuset Østfold HF'),
    ('Sykehuset Østfold - Moss', 'SØ Moss', 'Moss', FALSE, 'Sykehuset Østfold HF'),
    ('Sykehuset Østfold - Fredrikstad', 'SØ Fredrikstad', 'Fredrikstad', FALSE, 'Sykehuset Østfold HF'),
    ('Sykehuset Østfold - Askim', 'SØ Askim', 'Askim', FALSE, 'Sykehuset Østfold HF'),
    ('Sykehuset Østfold - Halden', 'SØ Halden', 'Halden', FALSE, 'Sykehuset Østfold HF'),
    ('Oslo Universitetssykehus - Ullevål', 'OUS Ullevål', 'Oslo', TRUE, 'Oslo Universitetssykehus HF'),
    ('Oslo Universitetssykehus - Rikshospitalet', 'OUS Rikshospitalet', 'Oslo', TRUE, 'Oslo Universitetssykehus HF'),
    ('Sunnaas Sykehus', 'Sunnaas', 'Nesodden', TRUE, 'Sunnaas Sykehus HF'),
    ('Sentrumsgården Legekontor', 'Fastlege', 'Ørje', TRUE, 'Primærhelsetjenesten');
