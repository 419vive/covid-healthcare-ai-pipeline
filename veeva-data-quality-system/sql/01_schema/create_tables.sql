/*
File: create_tables.sql
Purpose: Core database schema for Veeva OpenData simulation system
Author: Claude Code
Created: 2025-08-07
Description: Healthcare data quality management system with focus on provider data
*/

-- Enable foreign key constraints for SQLite
PRAGMA foreign_keys = ON;

-- =====================================================
-- Healthcare Providers Dimension Table (核心醫療人員資料)
-- =====================================================
CREATE TABLE healthcare_providers (
    provider_id VARCHAR(50) PRIMARY KEY,
    npi_number VARCHAR(10) UNIQUE,  -- National Provider Identifier
    full_name VARCHAR(200) NOT NULL,
    first_name VARCHAR(100),
    last_name VARCHAR(100) NOT NULL, 
    middle_initial VARCHAR(10),
    name_suffix VARCHAR(20),  -- Jr., Sr., III, etc.
    degree VARCHAR(50),       -- MD, DO, NP, PA, etc.
    specialty_primary VARCHAR(100),
    specialty_secondary VARCHAR(100),
    sub_specialty VARCHAR(100),
    email VARCHAR(100),
    phone_number VARCHAR(20),
    license_number VARCHAR(50),
    license_state VARCHAR(2),
    license_expiry_date DATE,
    dea_number VARCHAR(20),   -- Drug Enforcement Administration number
    board_certification VARCHAR(200),
    years_in_practice INTEGER,
    gender VARCHAR(10),
    birth_year INTEGER,
    medical_school VARCHAR(200),
    graduation_year INTEGER,
    
    -- Data quality and lineage fields
    data_source VARCHAR(50) NOT NULL DEFAULT 'UNKNOWN',
    source_confidence DECIMAL(3,2) DEFAULT 0.50,
    last_updated TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_verified DATE,
    is_golden_record BOOLEAN DEFAULT FALSE,
    record_status VARCHAR(20) DEFAULT 'ACTIVE',
    
    -- Audit fields
    created_by VARCHAR(50) DEFAULT 'SYSTEM',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by VARCHAR(50) DEFAULT 'SYSTEM',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT chk_npi_format CHECK (
        npi_number IS NULL OR 
        (LENGTH(npi_number) = 10 AND npi_number GLOB '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]')
    ),
    CONSTRAINT chk_license_state CHECK (
        license_state IS NULL OR LENGTH(license_state) = 2
    ),
    CONSTRAINT chk_gender CHECK (
        gender IS NULL OR gender IN ('Male', 'Female', 'Other', 'Unknown')
    ),
    CONSTRAINT chk_record_status CHECK (
        record_status IN ('ACTIVE', 'INACTIVE', 'PENDING', 'MERGED', 'DUPLICATE')
    ),
    CONSTRAINT chk_confidence_range CHECK (
        source_confidence >= 0.0 AND source_confidence <= 1.0
    ),
    CONSTRAINT chk_birth_year CHECK (
        birth_year IS NULL OR (birth_year >= 1920 AND birth_year <= 2005)
    ),
    CONSTRAINT chk_years_practice CHECK (
        years_in_practice IS NULL OR (years_in_practice >= 0 AND years_in_practice <= 60)
    )
);

-- =====================================================
-- Healthcare Facilities Dimension Table (醫療機構資料)
-- =====================================================
CREATE TABLE healthcare_facilities (
    facility_id VARCHAR(50) PRIMARY KEY,
    facility_name VARCHAR(300) NOT NULL,
    facility_type VARCHAR(50),  -- Hospital, Clinic, Practice, etc.
    organization_type VARCHAR(50), -- Non-profit, For-profit, Government
    
    -- Address information
    address_line1 VARCHAR(200),
    address_line2 VARCHAR(200),
    city VARCHAR(100),
    state_province VARCHAR(100),
    postal_code VARCHAR(20),
    country VARCHAR(100) DEFAULT 'USA',
    
    -- Contact information
    phone VARCHAR(50),
    fax VARCHAR(50),
    website VARCHAR(200),
    email VARCHAR(100),
    
    -- Facility details
    bed_count INTEGER,
    employee_count INTEGER,
    specialties_offered TEXT,
    accreditation_status VARCHAR(100),
    accreditation_date DATE,
    medicare_provider_number VARCHAR(20),
    
    -- Geographic and administrative
    county VARCHAR(100),
    msa_code VARCHAR(20),  -- Metropolitan Statistical Area
    cbsa_code VARCHAR(20), -- Core Based Statistical Area
    network_affiliation VARCHAR(200),
    ownership VARCHAR(100),
    
    -- Data quality fields
    data_source VARCHAR(50) NOT NULL DEFAULT 'UNKNOWN',
    source_confidence DECIMAL(3,2) DEFAULT 0.50,
    last_updated TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_verified DATE,
    validation_status VARCHAR(20) DEFAULT 'PENDING',
    
    -- Audit fields
    created_by VARCHAR(50) DEFAULT 'SYSTEM',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by VARCHAR(50) DEFAULT 'SYSTEM',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT chk_facility_type CHECK (
        facility_type IS NULL OR facility_type IN (
            'Hospital', 'Outpatient Clinic', 'Urgent Care', 'Surgery Center',
            'Diagnostic Center', 'Rehabilitation Center', 'Nursing Home',
            'Private Practice', 'Community Health Center', 'Academic Medical Center'
        )
    ),
    CONSTRAINT chk_postal_code_format CHECK (
        postal_code IS NULL OR 
        (LENGTH(postal_code) IN (5, 10) AND postal_code GLOB '[0-9]*')
    ),
    CONSTRAINT chk_validation_status CHECK (
        validation_status IN ('PENDING', 'VERIFIED', 'FAILED', 'MANUAL_REVIEW')
    ),
    CONSTRAINT chk_bed_count CHECK (
        bed_count IS NULL OR bed_count > 0
    )
);

-- =====================================================
-- Medical Activities Fact Table (醫療活動記錄)
-- =====================================================
CREATE TABLE medical_activities (
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
-- Provider-Facility Affiliations (醫生-機構關聯)
-- =====================================================
CREATE TABLE provider_facility_affiliations (
    affiliation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider_id VARCHAR(50) NOT NULL,
    facility_id VARCHAR(50) NOT NULL,
    
    -- Affiliation details
    start_date DATE NOT NULL,
    end_date DATE,  -- NULL means current/active
    position_title VARCHAR(100),
    department VARCHAR(100),
    is_primary_affiliation BOOLEAN DEFAULT FALSE,
    employment_type VARCHAR(50), -- Full-time, Part-time, Consulting, etc.
    
    -- Professional details
    admitting_privileges BOOLEAN DEFAULT FALSE,
    medical_staff_category VARCHAR(50),
    committee_memberships TEXT,
    
    -- Data quality
    data_source VARCHAR(50) NOT NULL DEFAULT 'UNKNOWN',
    confidence_score DECIMAL(3,2) DEFAULT 0.50,
    last_verified DATE,
    
    -- Audit fields
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign key constraints
    FOREIGN KEY (provider_id) REFERENCES healthcare_providers(provider_id),
    FOREIGN KEY (facility_id) REFERENCES healthcare_facilities(facility_id),
    
    -- Constraints
    CONSTRAINT chk_date_logic CHECK (
        end_date IS NULL OR start_date <= end_date
    ),
    CONSTRAINT chk_employment_type CHECK (
        employment_type IS NULL OR employment_type IN (
            'Full-time', 'Part-time', 'Consulting', 'Locum', 'Volunteer', 'Academic'
        )
    ),
    CONSTRAINT chk_confidence_score CHECK (
        confidence_score >= 0.0 AND confidence_score <= 1.0
    ),
    
    -- Unique constraint to prevent exact duplicates
    UNIQUE(provider_id, facility_id, start_date)
);

-- =====================================================
-- Data Quality Metrics Tracking (資料品質指標追蹤)
-- =====================================================
CREATE TABLE data_quality_metrics (
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
CREATE TABLE business_rule_violations (
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

-- Active providers with primary affiliations
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

-- Provider activity summary
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