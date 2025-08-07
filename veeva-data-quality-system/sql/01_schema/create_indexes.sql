/*
File: create_indexes.sql
Purpose: Performance optimization indexes for Veeva OpenData simulation system
Author: Claude Code
Created: 2025-08-07
Description: AI-optimized indexes for complex data quality queries and reporting
*/

-- Enable query planner optimization
PRAGMA optimize;

-- =====================================================
-- Healthcare Providers Table Indexes
-- =====================================================

-- Primary search indexes
CREATE INDEX IF NOT EXISTS idx_provider_name ON healthcare_providers(full_name);
CREATE INDEX IF NOT EXISTS idx_provider_name_normalized ON healthcare_providers(UPPER(TRIM(full_name)));
CREATE INDEX IF NOT EXISTS idx_provider_last_first ON healthcare_providers(last_name, first_name);
CREATE INDEX IF NOT EXISTS idx_provider_npi ON healthcare_providers(npi_number);
CREATE INDEX IF NOT EXISTS idx_provider_license ON healthcare_providers(license_number, license_state);

-- Specialty and demographic indexes
CREATE INDEX IF NOT EXISTS idx_provider_specialty ON healthcare_providers(specialty_primary);
CREATE INDEX IF NOT EXISTS idx_provider_specialty_secondary ON healthcare_providers(specialty_secondary);
CREATE INDEX IF NOT EXISTS idx_provider_state ON healthcare_providers(license_state);
CREATE INDEX IF NOT EXISTS idx_provider_degree ON healthcare_providers(degree);

-- Data quality indexes
CREATE INDEX IF NOT EXISTS idx_provider_source ON healthcare_providers(data_source);
CREATE INDEX IF NOT EXISTS idx_provider_status ON healthcare_providers(record_status);
CREATE INDEX IF NOT EXISTS idx_provider_golden ON healthcare_providers(is_golden_record);
CREATE INDEX IF NOT EXISTS idx_provider_confidence ON healthcare_providers(source_confidence);
CREATE INDEX IF NOT EXISTS idx_provider_last_updated ON healthcare_providers(last_updated);

-- Contact information indexes (for duplicate detection)
CREATE INDEX IF NOT EXISTS idx_provider_email ON healthcare_providers(email) WHERE email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_provider_phone ON healthcare_providers(phone_number) WHERE phone_number IS NOT NULL;

-- Composite indexes for complex queries
CREATE INDEX IF NOT EXISTS idx_provider_name_specialty ON healthcare_providers(last_name, first_name, specialty_primary);
CREATE INDEX IF NOT EXISTS idx_provider_license_degree ON healthcare_providers(license_state, degree, specialty_primary);
CREATE INDEX IF NOT EXISTS idx_provider_active_updated ON healthcare_providers(record_status, last_updated) WHERE record_status = 'ACTIVE';

-- =====================================================
-- Healthcare Facilities Table Indexes
-- =====================================================

-- Facility identification indexes
CREATE INDEX IF NOT EXISTS idx_facility_name ON healthcare_facilities(facility_name);
CREATE INDEX IF NOT EXISTS idx_facility_name_normalized ON healthcare_facilities(UPPER(TRIM(facility_name)));
CREATE INDEX IF NOT EXISTS idx_facility_type ON healthcare_facilities(facility_type);
CREATE INDEX IF NOT EXISTS idx_facility_medicare_number ON healthcare_facilities(medicare_provider_number);

-- Geographic indexes
CREATE INDEX IF NOT EXISTS idx_facility_location ON healthcare_facilities(state_province, city);
CREATE INDEX IF NOT EXISTS idx_facility_postal ON healthcare_facilities(postal_code);
CREATE INDEX IF NOT EXISTS idx_facility_county ON healthcare_facilities(county);
CREATE INDEX IF NOT EXISTS idx_facility_state ON healthcare_facilities(state_province);

-- Facility characteristics
CREATE INDEX IF NOT EXISTS idx_facility_bed_count ON healthcare_facilities(bed_count);
CREATE INDEX IF NOT EXISTS idx_facility_type_ownership ON healthcare_facilities(facility_type, ownership);
CREATE INDEX IF NOT EXISTS idx_facility_network ON healthcare_facilities(network_affiliation) WHERE network_affiliation IS NOT NULL;

-- Data quality indexes
CREATE INDEX IF NOT EXISTS idx_facility_validation_status ON healthcare_facilities(validation_status);
CREATE INDEX IF NOT EXISTS idx_facility_source ON healthcare_facilities(data_source);
CREATE INDEX IF NOT EXISTS idx_facility_verified ON healthcare_facilities(last_verified);

-- =====================================================
-- Provider-Facility Affiliations Indexes
-- =====================================================

-- Core relationship indexes
CREATE INDEX IF NOT EXISTS idx_affiliation_provider ON provider_facility_affiliations(provider_id);
CREATE INDEX IF NOT EXISTS idx_affiliation_facility ON provider_facility_affiliations(facility_id);
CREATE INDEX IF NOT EXISTS idx_affiliation_provider_facility ON provider_facility_affiliations(provider_id, facility_id);

-- Date-based indexes
CREATE INDEX IF NOT EXISTS idx_affiliation_start_date ON provider_facility_affiliations(start_date);
CREATE INDEX IF NOT EXISTS idx_affiliation_end_date ON provider_facility_affiliations(end_date);
CREATE INDEX IF NOT EXISTS idx_affiliation_active ON provider_facility_affiliations(provider_id, facility_id) WHERE end_date IS NULL;
CREATE INDEX IF NOT EXISTS idx_affiliation_date_range ON provider_facility_affiliations(provider_id, start_date, end_date);

-- Primary affiliation indexes
CREATE INDEX IF NOT EXISTS idx_affiliation_primary ON provider_facility_affiliations(is_primary_affiliation, provider_id) WHERE is_primary_affiliation = TRUE;
CREATE INDEX IF NOT EXISTS idx_affiliation_employment ON provider_facility_affiliations(employment_type);

-- Data quality indexes
CREATE INDEX IF NOT EXISTS idx_affiliation_confidence ON provider_facility_affiliations(confidence_score);
CREATE INDEX IF NOT EXISTS idx_affiliation_source ON provider_facility_affiliations(data_source);

-- =====================================================
-- Medical Activities Table Indexes
-- =====================================================

-- Core activity indexes
CREATE INDEX IF NOT EXISTS idx_activity_provider ON medical_activities(provider_id);
CREATE INDEX IF NOT EXISTS idx_activity_facility ON medical_activities(facility_id);
CREATE INDEX IF NOT EXISTS idx_activity_date ON medical_activities(activity_date);
CREATE INDEX IF NOT EXISTS idx_activity_type ON medical_activities(activity_type);

-- Provider activity analysis
CREATE INDEX IF NOT EXISTS idx_activity_provider_date ON medical_activities(provider_id, activity_date);
CREATE INDEX IF NOT EXISTS idx_activity_provider_type ON medical_activities(provider_id, activity_type);
CREATE INDEX IF NOT EXISTS idx_activity_provider_date_type ON medical_activities(provider_id, activity_date, activity_type);

-- Publication-specific indexes
CREATE INDEX IF NOT EXISTS idx_activity_publication ON medical_activities(publication_id) WHERE publication_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_activity_journal ON medical_activities(journal_name) WHERE journal_name IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_activity_citations ON medical_activities(citation_count) WHERE citation_count > 0;
CREATE INDEX IF NOT EXISTS idx_activity_primary_author ON medical_activities(is_primary_author, provider_id) WHERE is_primary_author = TRUE;

-- Time-based analysis indexes
CREATE INDEX IF NOT EXISTS idx_activity_year_month ON medical_activities(substr(activity_date, 1, 7)); -- YYYY-MM format
CREATE INDEX IF NOT EXISTS idx_activity_recent ON medical_activities(activity_date) WHERE activity_date >= date('now', '-1 year');

-- Data lineage indexes
CREATE INDEX IF NOT EXISTS idx_activity_batch ON medical_activities(batch_id);
CREATE INDEX IF NOT EXISTS idx_activity_source ON medical_activities(data_source);
CREATE INDEX IF NOT EXISTS idx_activity_imported ON medical_activities(imported_at);

-- =====================================================
-- Data Quality Metrics Table Indexes
-- =====================================================

-- Temporal analysis indexes
CREATE INDEX IF NOT EXISTS idx_metrics_date ON data_quality_metrics(measurement_date);
CREATE INDEX IF NOT EXISTS idx_metrics_table_date ON data_quality_metrics(table_name, measurement_date);
CREATE INDEX IF NOT EXISTS idx_metrics_recent ON data_quality_metrics(measurement_date) WHERE measurement_date >= date('now', '-30 days');

-- Quality score indexes
CREATE INDEX IF NOT EXISTS idx_metrics_overall_score ON data_quality_metrics(overall_quality_score);
CREATE INDEX IF NOT EXISTS idx_metrics_completeness ON data_quality_metrics(completeness_score);
CREATE INDEX IF NOT EXISTS idx_metrics_consistency ON data_quality_metrics(consistency_score);
CREATE INDEX IF NOT EXISTS idx_metrics_accuracy ON data_quality_metrics(accuracy_score);

-- Quality grade and SLA indexes
CREATE INDEX IF NOT EXISTS idx_metrics_grade ON data_quality_metrics(quality_grade);
CREATE INDEX IF NOT EXISTS idx_metrics_sla ON data_quality_metrics(meets_sla);
CREATE INDEX IF NOT EXISTS idx_metrics_table_grade ON data_quality_metrics(table_name, quality_grade);

-- Processing indexes
CREATE INDEX IF NOT EXISTS idx_metrics_batch ON data_quality_metrics(batch_id);

-- =====================================================
-- Business Rule Violations Table Indexes
-- =====================================================

-- Violation identification indexes
CREATE INDEX IF NOT EXISTS idx_violations_rule ON business_rule_violations(rule_name);
CREATE INDEX IF NOT EXISTS idx_violations_date ON business_rule_violations(violation_date);
CREATE INDEX IF NOT EXISTS idx_violations_entity ON business_rule_violations(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_violations_severity ON business_rule_violations(severity_level);

-- Status tracking indexes
CREATE INDEX IF NOT EXISTS idx_violations_status ON business_rule_violations(status);
CREATE INDEX IF NOT EXISTS idx_violations_open ON business_rule_violations(rule_name, violation_date) WHERE status = 'OPEN';
CREATE INDEX IF NOT EXISTS idx_violations_resolved ON business_rule_violations(resolved_date) WHERE resolved_date IS NOT NULL;

-- Business impact indexes
CREATE INDEX IF NOT EXISTS idx_violations_financial ON business_rule_violations(financial_impact) WHERE financial_impact IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_violations_detection ON business_rule_violations(detection_method);

-- Recent violations index
CREATE INDEX IF NOT EXISTS idx_violations_recent ON business_rule_violations(violation_date, severity_level) WHERE violation_date >= date('now', '-7 days');

-- Processing indexes
CREATE INDEX IF NOT EXISTS idx_violations_batch ON business_rule_violations(batch_id);

-- =====================================================
-- Advanced Composite Indexes for Complex Queries
-- =====================================================

-- Provider name similarity and duplicate detection
CREATE INDEX IF NOT EXISTS idx_provider_soundex ON healthcare_providers(
    substr(last_name, 1, 1), 
    length(last_name), 
    substr(first_name, 1, 1)
) WHERE record_status = 'ACTIVE';

-- Active provider affiliations with facility info (covering index)
CREATE INDEX IF NOT EXISTS idx_active_provider_facility ON provider_facility_affiliations(
    provider_id, 
    facility_id, 
    is_primary_affiliation, 
    start_date
) WHERE end_date IS NULL;

-- High-volume provider activity pattern analysis
CREATE INDEX IF NOT EXISTS idx_provider_monthly_activity ON medical_activities(
    provider_id, 
    substr(activity_date, 1, 7), -- YYYY-MM
    activity_type
);

-- Quality trend analysis (covering index)
CREATE INDEX IF NOT EXISTS idx_quality_trend ON data_quality_metrics(
    table_name, 
    measurement_date, 
    overall_quality_score, 
    quality_grade
);

-- Critical violations monitoring
CREATE INDEX IF NOT EXISTS idx_critical_violations ON business_rule_violations(
    severity_level, 
    status, 
    violation_date, 
    entity_type
) WHERE severity_level IN ('CRITICAL', 'HIGH');

-- =====================================================
-- Partial Indexes for Data Quality Monitoring
-- =====================================================

-- Only index records that need attention
CREATE INDEX IF NOT EXISTS idx_low_quality_providers ON healthcare_providers(provider_id, full_name, source_confidence) 
WHERE source_confidence < 0.8 OR record_status != 'ACTIVE';

-- Index facilities requiring validation
CREATE INDEX IF NOT EXISTS idx_unvalidated_facilities ON healthcare_facilities(facility_id, facility_name, last_verified)
WHERE validation_status != 'VERIFIED' OR last_verified < date('now', '-90 days');

-- Index suspicious affiliations (too many facilities)
CREATE INDEX IF NOT EXISTS idx_provider_affiliation_count ON provider_facility_affiliations(provider_id)
WHERE end_date IS NULL;

-- =====================================================
-- Performance Optimization Settings
-- =====================================================

-- Update query planner statistics
ANALYZE;

-- Set optimal SQLite performance parameters
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA cache_size = 10000;
PRAGMA temp_store = MEMORY;
PRAGMA mmap_size = 268435456; -- 256MB

-- Verify index creation
SELECT 'Index creation completed. Total indexes: ' || count(*) as result
FROM sqlite_master 
WHERE type = 'index' AND name NOT LIKE 'sqlite_%';