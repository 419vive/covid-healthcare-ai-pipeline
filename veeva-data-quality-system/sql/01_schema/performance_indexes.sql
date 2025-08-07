/*
File: performance_indexes.sql
Purpose: Phase 3 performance optimization indexes
Author: Claude Code Performance Optimizer
Created: 2025-08-07
Description: Targeted indexes for validation query optimization based on profiling results
Target: Reduce query execution time by 80%+
*/

-- =====================================================
-- Performance Analysis Summary
-- =====================================================
-- Current bottlenecks identified:
-- 1. contact_validation: 1.219s → Target: <0.2s
-- 2. affiliation_anomaly: 0.598s → Target: <0.2s
-- 3. cross_reference_integrity: 0.410s → Target: <0.1s
-- 4. npi_validation: 0.346s → Target: <0.1s

-- =====================================================
-- Contact Validation Optimization Indexes
-- =====================================================

-- Index for missing email/phone detection
CREATE INDEX IF NOT EXISTS idx_provider_contact_validation ON healthcare_providers(
    record_status,
    provider_id
) WHERE email IS NULL OR TRIM(email) = '' 
     OR phone_number IS NULL OR TRIM(phone_number) = '';

-- Index for email format validation
CREATE INDEX IF NOT EXISTS idx_provider_email_format ON healthcare_providers(
    email,
    provider_id
) WHERE email IS NOT NULL 
     AND TRIM(email) != '' 
     AND record_status = 'ACTIVE';

-- Index for phone number format validation  
CREATE INDEX IF NOT EXISTS idx_provider_phone_format ON healthcare_providers(
    phone_number,
    provider_id
) WHERE phone_number IS NOT NULL 
     AND TRIM(phone_number) != ''
     AND record_status = 'ACTIVE';

-- Composite index for contact validation covering query
CREATE INDEX IF NOT EXISTS idx_provider_contact_covering ON healthcare_providers(
    record_status,
    provider_id,
    full_name,
    email,
    phone_number
) WHERE record_status = 'ACTIVE';

-- =====================================================
-- NPI Validation Optimization Indexes  
-- =====================================================

-- Index for missing NPI detection
CREATE INDEX IF NOT EXISTS idx_provider_missing_npi ON healthcare_providers(
    provider_id,
    full_name
) WHERE npi_number IS NULL AND record_status = 'ACTIVE';

-- Index for invalid NPI length detection
CREATE INDEX IF NOT EXISTS idx_provider_invalid_npi_length ON healthcare_providers(
    npi_number,
    provider_id,
    full_name
) WHERE npi_number IS NOT NULL 
     AND LENGTH(npi_number) != 10 
     AND record_status = 'ACTIVE';

-- Index for NPI duplicate detection (optimized)
CREATE INDEX IF NOT EXISTS idx_provider_npi_duplicate_check ON healthcare_providers(
    npi_number,
    provider_id,
    full_name
) WHERE npi_number IS NOT NULL 
     AND LENGTH(npi_number) = 10 
     AND record_status = 'ACTIVE';

-- =====================================================
-- Affiliation Anomaly Optimization Indexes
-- =====================================================

-- Index for providers with potential affiliation issues
CREATE INDEX IF NOT EXISTS idx_affiliation_anomaly_detection ON provider_facility_affiliations(
    provider_id,
    facility_id,
    is_primary_affiliation,
    end_date
);

-- Index for primary affiliation counting
CREATE INDEX IF NOT EXISTS idx_affiliation_primary_count ON provider_facility_affiliations(
    provider_id,
    is_primary_affiliation
) WHERE is_primary_affiliation = 1;

-- Index for active affiliation counting
CREATE INDEX IF NOT EXISTS idx_affiliation_active_count ON provider_facility_affiliations(
    provider_id,
    end_date
) WHERE end_date IS NULL;

-- Covering index for affiliation statistics
CREATE INDEX IF NOT EXISTS idx_affiliation_stats_covering ON provider_facility_affiliations(
    provider_id,
    facility_id,
    is_primary_affiliation,
    end_date
);

-- =====================================================
-- Cross Reference Integrity Optimization Indexes
-- =====================================================

-- Index for orphaned provider affiliations
CREATE INDEX IF NOT EXISTS idx_orphan_provider_affiliations ON provider_facility_affiliations(
    provider_id,
    facility_id
);

-- Index for orphaned facility affiliations  
CREATE INDEX IF NOT EXISTS idx_orphan_facility_affiliations ON provider_facility_affiliations(
    facility_id,
    provider_id
);

-- Index for active providers without affiliations
CREATE INDEX IF NOT EXISTS idx_providers_no_affiliations ON healthcare_providers(
    provider_id,
    full_name,
    record_status
) WHERE record_status = 'ACTIVE';

-- =====================================================
-- Name Consistency Optimization Indexes
-- =====================================================

-- Index for name validation covering query
CREATE INDEX IF NOT EXISTS idx_provider_name_validation ON healthcare_providers(
    record_status,
    provider_id,
    full_name,
    first_name,
    last_name
) WHERE record_status = 'ACTIVE';

-- Index for missing name components
CREATE INDEX IF NOT EXISTS idx_provider_missing_names ON healthcare_providers(
    provider_id,
    full_name,
    first_name,
    last_name
) WHERE (full_name IS NULL OR TRIM(full_name) = '')
     OR (first_name IS NULL AND last_name IS NULL)
     AND record_status = 'ACTIVE';

-- =====================================================
-- Temporal Consistency Optimization Indexes
-- =====================================================

-- Index for temporal validation covering query
CREATE INDEX IF NOT EXISTS idx_provider_temporal_validation ON healthcare_providers(
    record_status,
    birth_year,
    graduation_year,
    years_in_practice,
    license_expiry_date,
    provider_id,
    full_name
) WHERE birth_year IS NOT NULL AND record_status = 'ACTIVE';

-- =====================================================
-- Query Result Caching Support Indexes
-- =====================================================

-- Index for validation result caching by rule and date
CREATE INDEX IF NOT EXISTS idx_validation_cache ON business_rule_violations(
    rule_name,
    violation_date,
    status
) WHERE violation_date >= date('now', '-7 days');

-- Index for recent validation results
CREATE INDEX IF NOT EXISTS idx_recent_validations ON business_rule_violations(
    violation_date,
    rule_name,
    entity_type,
    entity_id
) WHERE violation_date >= date('now', '-1 day');

-- =====================================================
-- Performance Monitoring Indexes
-- =====================================================

-- Index for query performance tracking
CREATE INDEX IF NOT EXISTS idx_query_performance ON data_quality_metrics(
    table_name,
    measurement_date,
    overall_quality_score
) WHERE measurement_date >= date('now', '-30 days');

-- =====================================================
-- Specialized Function-Based Indexes
-- =====================================================

-- Index for email domain analysis
CREATE INDEX IF NOT EXISTS idx_provider_email_domain ON healthcare_providers(
    substr(email, instr(email, '@') + 1),
    provider_id
) WHERE email IS NOT NULL 
     AND email LIKE '%@%'
     AND record_status = 'ACTIVE';

-- Index for phone number normalization
CREATE INDEX IF NOT EXISTS idx_provider_phone_normalized ON healthcare_providers(
    LENGTH(REPLACE(REPLACE(REPLACE(phone_number, '(', ''), ')', ''), '-', '')),
    provider_id
) WHERE phone_number IS NOT NULL AND record_status = 'ACTIVE';

-- =====================================================
-- Composite Indexes for Multi-Query Optimization
-- =====================================================

-- Master provider validation index
CREATE INDEX IF NOT EXISTS idx_provider_validation_master ON healthcare_providers(
    record_status,
    provider_id,
    full_name,
    first_name,
    last_name,
    npi_number,
    email,
    phone_number,
    birth_year,
    graduation_year
) WHERE record_status = 'ACTIVE';

-- Master affiliation validation index
CREATE INDEX IF NOT EXISTS idx_affiliation_validation_master ON provider_facility_affiliations(
    provider_id,
    facility_id,
    is_primary_affiliation,
    end_date,
    start_date
);

-- =====================================================
-- Index Maintenance and Optimization
-- =====================================================

-- Update statistics for all new indexes
ANALYZE;

-- Enable query planner optimizations
PRAGMA optimize;

-- Set optimal SQLite performance parameters for validation workload
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA cache_size = -65536;  -- 64MB cache
PRAGMA temp_store = MEMORY;
PRAGMA mmap_size = 536870912; -- 512MB mmap
PRAGMA threads = 4;

-- Verification query
SELECT 
    'Performance indexes created: ' || count(*) || ' total indexes' as result,
    'Target: 80% query performance improvement' as goal
FROM sqlite_master 
WHERE type = 'index' 
  AND name NOT LIKE 'sqlite_%'
  AND (name LIKE 'idx_provider_%' OR name LIKE 'idx_affiliation_%' OR name LIKE 'idx_validation_%');

-- Performance test query
SELECT 'Index optimization complete. Ready for validation testing.' as status;