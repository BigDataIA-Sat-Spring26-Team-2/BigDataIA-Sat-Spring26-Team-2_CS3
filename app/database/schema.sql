-- Industries table
CREATE TABLE IF NOT EXISTS industries (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    sector VARCHAR(100) NOT NULL,
    h_r_base DECIMAL(5,2) CHECK (h_r_base BETWEEN 0 AND 100),
    created_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

-- Companies table
CREATE TABLE IF NOT EXISTS companies (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    ticker VARCHAR(10),
    industry_id VARCHAR(36) REFERENCES industries(id),
    position_factor DECIMAL(4,3) DEFAULT 0.0 
        CHECK (position_factor BETWEEN -1.0 AND 1.0),
    is_deleted BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    updated_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

-- Assessments table
CREATE TABLE IF NOT EXISTS assessments (
    id VARCHAR(36) PRIMARY KEY,
    company_id VARCHAR(36) NOT NULL REFERENCES companies(id),
    assessment_type VARCHAR(20) NOT NULL
        CHECK (assessment_type IN ('screening', 'due_diligence', 'quarterly', 'exit_prep')),
    assessment_date DATE NOT NULL,
    status VARCHAR(20) DEFAULT 'draft'
        CHECK (status IN ('draft', 'in_progress', 'submitted', 'approved', 'superseded')),
    primary_assessor VARCHAR(255),
    secondary_assessor VARCHAR(255),
    v_r_score DECIMAL(5,2) CHECK (v_r_score BETWEEN 0 AND 100),
    confidence_lower DECIMAL(5,2),
    confidence_upper DECIMAL(5,2),
    created_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

-- Dimension scores table
CREATE TABLE IF NOT EXISTS dimension_scores (
    id VARCHAR(36) PRIMARY KEY,
    assessment_id VARCHAR(36) NOT NULL REFERENCES assessments(id),
    dimension VARCHAR(30) NOT NULL
        CHECK (dimension IN (
            'data_infrastructure', 'ai_governance', 'technology_stack',
            'talent_skills', 'leadership_vision', 'use_case_portfolio',
            'culture_change'
        )),
    score DECIMAL(5,2) NOT NULL CHECK (score BETWEEN 0 AND 100),
    weight DECIMAL(4,3) CHECK (weight BETWEEN 0 AND 1),
    confidence DECIMAL(4,3) DEFAULT 0.8 CHECK (confidence BETWEEN 0 AND 1),
    evidence_count INT DEFAULT 0,
    created_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    UNIQUE (assessment_id, dimension)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_companies_industry ON companies(industry_id);
CREATE INDEX IF NOT EXISTS idx_assessments_company ON assessments(company_id);
CREATE INDEX IF NOT EXISTS idx_dimension_scores_assessment ON dimension_scores(assessment_id);

-- Seed Data
INSERT INTO industries (id, name, sector, h_r_base) VALUES
    ('550e8400-e29b-41d4-a716-446655440001', 'Manufacturing', 'Industrials', 72),
    ('550e8400-e29b-41d4-a716-446655440002', 'Healthcare Services', 'Healthcare', 78),
    ('550e8400-e29b-41d4-a716-446655440003', 'Business Services', 'Services', 75),
    ('550e8400-e29b-41d4-a716-446655440004', 'Retail', 'Consumer', 70),
    ('550e8400-e29b-41d4-a716-446655440005', 'Financial Services', 'Financial', 80);
    -- =========================
-- Case Study 2: Documents
-- =========================
CREATE TABLE IF NOT EXISTS documents (
    id VARCHAR(36) PRIMARY KEY,
    company_id VARCHAR(36) NOT NULL REFERENCES companies(id),
    cik VARCHAR(20), -- optional (if you use ticker->CIK mapping later)
    ticker VARCHAR(10),
    filing_type VARCHAR(20) NOT NULL,
    accession_number VARCHAR(30) NOT NULL,
    source VARCHAR(50) DEFAULT 'sec_edgar', -- helps later when you add other sources
    source_url VARCHAR(2000),
    file_path VARCHAR(2000) NOT NULL, -- local path for now
    filing_date DATE,
    content_hash VARCHAR(64) NOT NULL, -- sha256 of normalized full text
    word_count INT DEFAULT 0,
    section VARCHAR(50)
    created_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    
    UNIQUE (content_hash),
    UNIQUE (company_id, accession_number, filing_type)
);

CREATE INDEX IF NOT EXISTS idx_documents_company ON documents(company_id);
CREATE INDEX IF NOT EXISTS idx_documents_filing_type ON documents(filing_type);

-- =========================
-- Case Study 2: Document Chunks
-- =========================
CREATE TABLE IF NOT EXISTS document_chunks (
    id VARCHAR(36) PRIMARY KEY,
    document_id VARCHAR(36) NOT NULL REFERENCES documents(id),
    chunk_index INT NOT NULL,
    chunk_text TEXT NOT NULL,
    content_hash VARCHAR(64) NOT NULL, -- sha256 of chunk text
    word_count INT DEFAULT 0,
    created_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    UNIQUE (document_id, chunk_index),
    UNIQUE (content_hash)
);

CREATE INDEX IF NOT EXISTS idx_chunks_document ON document_chunks(document_id);

-- Add section tracking columns to documents table
ALTER TABLE PE_ORGAIR.PUBLIC.documents 
ADD COLUMN sections_extracted INT DEFAULT 0;

ALTER TABLE PE_ORGAIR.PUBLIC.documents
ADD COLUMN sections_stored INT DEFAULT 0;

ALTER TABLE PE_ORGAIR.PUBLIC.documents
ADD COLUMN sections_duplicates INT DEFAULT 0;

CREATE INDEX IF NOT EXISTS idx_chunks_section ON document_chunks(section);
