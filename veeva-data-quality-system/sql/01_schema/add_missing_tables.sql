-- Add missing tables to existing veeva_opendata.db
-- Created: 2025-08-07

PRAGMA foreign_keys = ON;

-- =====================================================
-- Medical Activities Fact Table (醫療活動記錄)
-- =====================================================
CREATE TABLE IF NOT EXISTS medical_activities (
    activity_id VARCHAR(50) PRIMARY KEY,
    provider_id VARCHAR(50) NOT NULL,
    facility_id VARCHAR(50),
    activity_date DATE NOT NULL,
    activity_type VARCHAR(50) NOT NULL,
    
    -- Activity details
    specialty_context VARCHAR(100),
    patient_count INTEGER,
    procedure_codes TEXT,  -- JSON array of procedure codes
    diagnosis_codes TEXT,  -- JSON array of diagnosis codes
    revenue_amount DECIMAL(12,2),
    
    -- Publication/Research specific (from CORD-19)
    publication_id VARCHAR(100),
    journal_name VARCHAR(200),
    publication_type VARCHAR(50),
    citation_count INTEGER DEFAULT 0,
    doi VARCHAR(100),
    pmid VARCHAR(50),
    is_primary_author BOOLEAN DEFAULT FALSE,
    author_position INTEGER,
    
    -- Data lineage
    data_source VARCHAR(50) NOT NULL DEFAULT 'UNKNOWN',
    batch_id VARCHAR(50),
    imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign key constraints
    FOREIGN KEY (provider_id) REFERENCES healthcare_providers(provider_id),
    FOREIGN KEY (facility_id) REFERENCES healthcare_facilities(facility_id),
    
    -- Constraints
    CONSTRAINT chk_activity_type CHECK (
        activity_type IN ('CLINICAL', 'RESEARCH', 'ADMINISTRATIVE', 'EDUCATION', 'PUBLICATION')
    ),
    CONSTRAINT chk_patient_count CHECK (
        patient_count IS NULL OR patient_count >= 0
    ),
    CONSTRAINT chk_citation_count CHECK (
        citation_count >= 0
    ),
    CONSTRAINT chk_author_position CHECK (
        author_position IS NULL OR author_position > 0
    )
);

-- =====================================================
-- Data Quality Metrics Tracking (資料品質指標追蹤)
-- =====================================================
CREATE TABLE IF NOT EXISTS data_quality_metrics (
    metric_id INTEGER PRIMARY KEY AUTOINCREMENT,
    measurement_date DATE NOT NULL,
    table_name VARCHAR(50) NOT NULL,
    
    -- Core quality dimensions
    completeness_score DECIMAL(5,2),
    consistency_score DECIMAL(5,2),
    accuracy_score DECIMAL(5,2),
    timeliness_score DECIMAL(5,2),
    uniqueness_score DECIMAL(5,2),
    validity_score DECIMAL(5,2),
    
    -- Aggregate score
    overall_quality_score DECIMAL(5,2),
    
    -- Record counts
    total_records INTEGER NOT NULL,
    valid_records INTEGER,
    invalid_records INTEGER,
    duplicate_records INTEGER,
    incomplete_records INTEGER,
    
    -- Quality status
    quality_grade VARCHAR(10),  -- A, B, C, D, F
    meets_sla BOOLEAN DEFAULT FALSE,
    
    -- Processing info
    batch_id VARCHAR(50),
    measurement_duration_seconds INTEGER,
    
    CONSTRAINT chk_quality_scores CHECK (
        completeness_score IS NULL OR (completeness_score >= 0 AND completeness_score <= 100) AND
        consistency_score IS NULL OR (consistency_score >= 0 AND consistency_score <= 100) AND
        accuracy_score IS NULL OR (accuracy_score >= 0 AND accuracy_score <= 100) AND
        timeliness_score IS NULL OR (timeliness_score >= 0 AND timeliness_score <= 100) AND
        uniqueness_score IS NULL OR (uniqueness_score >= 0 AND uniqueness_score <= 100) AND
        validity_score IS NULL OR (validity_score >= 0 AND validity_score <= 100) AND
        overall_quality_score IS NULL OR (overall_quality_score >= 0 AND overall_quality_score <= 100)
    ),
    CONSTRAINT chk_quality_grade CHECK (
        quality_grade IS NULL OR quality_grade IN ('A', 'B', 'C', 'D', 'F')
    ),
    CONSTRAINT chk_record_counts CHECK (
        total_records >= 0 AND
        (valid_records IS NULL OR valid_records >= 0) AND
        (invalid_records IS NULL OR invalid_records >= 0) AND
        (duplicate_records IS NULL OR duplicate_records >= 0)
    )
);

-- =====================================================
-- Business Rule Violations Log (商業規則違規記錄)
-- =====================================================
CREATE TABLE IF NOT EXISTS business_rule_violations (
    violation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_name VARCHAR(100) NOT NULL,
    violation_date DATE NOT NULL,
    
    -- Violation details
    entity_type VARCHAR(50), -- PROVIDER, FACILITY, AFFILIATION
    entity_id VARCHAR(50),
    severity_level VARCHAR(20), -- CRITICAL, HIGH, MEDIUM, LOW
    violation_description TEXT NOT NULL,
    
    -- Context information
    field_name VARCHAR(100),
    current_value TEXT,
    expected_value TEXT,
    violation_count INTEGER DEFAULT 1,
    
    -- Resolution tracking
    status VARCHAR(20) DEFAULT 'OPEN',
    resolution_action VARCHAR(200),
    resolved_date DATE,
    resolved_by VARCHAR(50),
    
    -- Business impact
    business_impact VARCHAR(200),
    financial_impact DECIMAL(10,2),
    
    -- System info
    detection_method VARCHAR(50), -- AUTOMATED, MANUAL, AUDIT
    batch_id VARCHAR(50),
    
    CONSTRAINT chk_severity CHECK (
        severity_level IN ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW')
    ),
    CONSTRAINT chk_violation_status CHECK (
        status IN ('OPEN', 'IN_PROGRESS', 'RESOLVED', 'FALSE_POSITIVE', 'ACCEPTED_RISK')
    ),
    CONSTRAINT chk_entity_type CHECK (
        entity_type IN ('PROVIDER', 'FACILITY', 'AFFILIATION', 'ACTIVITY')
    )
);

-- =====================================================
-- Create views for common queries
-- =====================================================

-- Active providers with primary affiliations (drop and recreate if exists)
DROP VIEW IF EXISTS active_providers_with_primary_affiliation;
CREATE VIEW active_providers_with_primary_affiliation AS
SELECT 
    hp.provider_id,
    hp.full_name,
    hp.specialty_primary,
    hp.license_state,
    hf.facility_name,
    hf.facility_type,
    hf.city,
    hf.state_province,
    pfa.position_title,
    pfa.start_date
FROM healthcare_providers hp
JOIN provider_facility_affiliations pfa ON hp.provider_id = pfa.provider_id
JOIN healthcare_facilities hf ON pfa.facility_id = hf.facility_id
WHERE hp.record_status = 'ACTIVE' 
  AND pfa.is_primary_affiliation = TRUE 
  AND pfa.end_date IS NULL;

-- Provider activity summary (drop and recreate if exists)
DROP VIEW IF EXISTS provider_activity_summary;
CREATE VIEW provider_activity_summary AS
SELECT 
    hp.provider_id,
    hp.full_name,
    hp.specialty_primary,
    COUNT(ma.activity_id) as total_activities,
    COUNT(DISTINCT ma.facility_id) as facilities_count,
    MIN(ma.activity_date) as first_activity,
    MAX(ma.activity_date) as latest_activity,
    SUM(CASE WHEN ma.activity_type = 'PUBLICATION' THEN 1 ELSE 0 END) as publication_count,
    AVG(ma.citation_count) as avg_citations
FROM healthcare_providers hp
LEFT JOIN medical_activities ma ON hp.provider_id = ma.provider_id
WHERE hp.record_status = 'ACTIVE'
GROUP BY hp.provider_id, hp.full_name, hp.specialty_primary;