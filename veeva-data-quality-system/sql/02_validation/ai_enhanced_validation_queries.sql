-- AI-Enhanced Validation Queries for Veeva Data Quality System
-- Designed by Claude Code for comprehensive healthcare provider data validation
-- Created: 2025-08-07

-- Query 1: provider_name_inconsistency
SELECT 
    'provider_name_inconsistency' as rule_name,
    provider_id,
    full_name,
    first_name,
    last_name,
    'Name format inconsistency detected' as issue_description,
    CASE 
        WHEN full_name IS NULL OR TRIM(full_name) = '' THEN 'CRITICAL'
        WHEN first_name IS NULL AND last_name IS NULL THEN 'HIGH'
        WHEN full_name NOT LIKE '%' || COALESCE(first_name, '') || '%' 
             OR full_name NOT LIKE '%' || COALESCE(last_name, '') || '%' THEN 'MEDIUM'
        ELSE 'LOW'
    END as severity
FROM healthcare_providers
WHERE 
    -- Missing names
    (full_name IS NULL OR TRIM(full_name) = '') 
    OR (first_name IS NULL AND last_name IS NULL)
    -- Name component inconsistencies
    OR (first_name IS NOT NULL AND full_name NOT LIKE '%' || first_name || '%')
    OR (last_name IS NOT NULL AND full_name NOT LIKE '%' || last_name || '%')
    -- Suspicious patterns
    OR full_name LIKE '%test%' 
    OR full_name LIKE '%dummy%'
    OR full_name LIKE '%sample%'
ORDER BY severity DESC, provider_id;

-- Query 2: npi_validation
SELECT 
    'npi_validation' as rule_name,
    provider_id,
    npi_number,
    full_name,
    CASE 
        WHEN npi_number IS NULL THEN 'Missing NPI number'
        WHEN LENGTH(npi_number) != 10 THEN 'Invalid NPI length (must be 10 digits)'
        WHEN npi_number NOT GLOB '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN 'Invalid NPI format (must be numeric)'
        WHEN duplicate_count > 1 THEN 'Duplicate NPI detected'
        ELSE 'Unknown NPI issue'
    END as issue_description,
    CASE 
        WHEN npi_number IS NULL THEN 'CRITICAL'
        WHEN LENGTH(npi_number) != 10 OR npi_number NOT GLOB '[0-9]*' THEN 'HIGH'
        WHEN duplicate_count > 1 THEN 'HIGH'
        ELSE 'MEDIUM'
    END as severity
FROM (
    SELECT 
        provider_id,
        npi_number,
        full_name,
        COUNT(*) OVER (PARTITION BY npi_number) as duplicate_count
    FROM healthcare_providers
    WHERE npi_number IS NOT NULL
) providers_with_counts
WHERE 
    npi_number IS NULL 
    OR LENGTH(npi_number) != 10 
    OR npi_number NOT GLOB '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]'
    OR duplicate_count > 1
ORDER BY severity DESC, provider_id;

-- Query 3: affiliation_anomaly (Simplified for performance)
SELECT 
    'affiliation_anomaly' as rule_name,
    pfa.provider_id,
    hp.full_name,
    COUNT(pfa.facility_id) as total_affiliations,
    COUNT(CASE WHEN pfa.is_primary_affiliation = 1 THEN 1 END) as primary_affiliations,
    COUNT(CASE WHEN pfa.end_date IS NULL THEN 1 END) as active_affiliations,
    CASE 
        WHEN COUNT(CASE WHEN pfa.is_primary_affiliation = 1 THEN 1 END) = 0 THEN 'Provider has no primary affiliation'
        WHEN COUNT(CASE WHEN pfa.is_primary_affiliation = 1 THEN 1 END) > 1 THEN 'Provider has multiple primary affiliations'
        WHEN COUNT(CASE WHEN pfa.end_date IS NULL THEN 1 END) = 0 THEN 'Provider has no active affiliations'
        WHEN COUNT(pfa.facility_id) > 10 THEN 'Unusually high number of affiliations'
        ELSE 'Other affiliation anomaly'
    END as issue_description,
    CASE 
        WHEN COUNT(CASE WHEN pfa.is_primary_affiliation = 1 THEN 1 END) = 0 THEN 'CRITICAL'
        WHEN COUNT(CASE WHEN pfa.is_primary_affiliation = 1 THEN 1 END) > 1 THEN 'HIGH'
        WHEN COUNT(CASE WHEN pfa.end_date IS NULL THEN 1 END) = 0 THEN 'MEDIUM'
        WHEN COUNT(pfa.facility_id) > 10 THEN 'MEDIUM'
        ELSE 'LOW'
    END as severity
FROM provider_facility_affiliations pfa
JOIN healthcare_providers hp ON pfa.provider_id = hp.provider_id
GROUP BY pfa.provider_id, hp.full_name
HAVING 
    COUNT(CASE WHEN pfa.is_primary_affiliation = 1 THEN 1 END) != 1
    OR COUNT(CASE WHEN pfa.end_date IS NULL THEN 1 END) = 0
    OR COUNT(pfa.facility_id) > 10
ORDER BY severity DESC, total_affiliations DESC
LIMIT 1000;

-- Query 4: temporal_consistency
SELECT 
    'temporal_consistency' as rule_name,
    provider_id,
    full_name,
    birth_year,
    graduation_year,
    years_in_practice,
    license_expiry_date,
    CASE 
        WHEN birth_year < 1920 OR birth_year > (strftime('%Y', 'now') - 18) THEN 'Unrealistic birth year'
        WHEN graduation_year < birth_year + 18 THEN 'Graduation before reasonable age'
        WHEN graduation_year > birth_year + 50 THEN 'Graduation age too old'
        WHEN years_in_practice < 0 THEN 'Negative years in practice'
        WHEN years_in_practice > (strftime('%Y', 'now') - graduation_year + 5) THEN 'Years in practice exceeds possible time'
        WHEN DATE(license_expiry_date) < DATE('now') THEN 'Expired medical license'
        WHEN DATE(license_expiry_date) > DATE('now', '+10 years') THEN 'License expiry too far in future'
        ELSE 'Other temporal inconsistency'
    END as issue_description,
    CASE 
        WHEN birth_year < 1900 OR birth_year > (strftime('%Y', 'now') - 16) THEN 'CRITICAL'
        WHEN DATE(license_expiry_date) < DATE('now') THEN 'CRITICAL'
        WHEN graduation_year < birth_year + 18 OR graduation_year > birth_year + 50 THEN 'HIGH'
        WHEN years_in_practice < 0 OR years_in_practice > 60 THEN 'HIGH'
        ELSE 'MEDIUM'
    END as severity
FROM healthcare_providers
WHERE 
    birth_year IS NOT NULL AND (
        birth_year < 1920 
        OR birth_year > (strftime('%Y', 'now') - 18)
        OR (graduation_year IS NOT NULL AND graduation_year < birth_year + 18)
        OR (graduation_year IS NOT NULL AND graduation_year > birth_year + 50)
        OR years_in_practice < 0 
        OR years_in_practice > (strftime('%Y', 'now') - COALESCE(graduation_year, birth_year + 25) + 5)
        OR (license_expiry_date IS NOT NULL AND DATE(license_expiry_date) < DATE('now'))
        OR (license_expiry_date IS NOT NULL AND DATE(license_expiry_date) > DATE('now', '+10 years'))
    )
ORDER BY severity DESC, provider_id;

-- Query 5: cross_reference_integrity
SELECT 
    'cross_reference_integrity' as rule_name,
    COALESCE(orphan_type, 'unknown') as entity_type,
    COALESCE(entity_id, 'unknown') as entity_id,
    entity_name,
    'Orphaned record detected' as issue_description,
    'HIGH' as severity
FROM (
    -- Affiliations with missing providers
    SELECT 
        'affiliation_missing_provider' as orphan_type,
        pfa.provider_id as entity_id,
        'Provider ID: ' || pfa.provider_id as entity_name
    FROM provider_facility_affiliations pfa
    LEFT JOIN healthcare_providers hp ON pfa.provider_id = hp.provider_id
    WHERE hp.provider_id IS NULL
    
    UNION ALL
    
    -- Affiliations with missing facilities
    SELECT 
        'affiliation_missing_facility' as orphan_type,
        pfa.facility_id as entity_id,
        'Facility ID: ' || pfa.facility_id as entity_name
    FROM provider_facility_affiliations pfa
    LEFT JOIN healthcare_facilities hf ON pfa.facility_id = hf.facility_id
    WHERE hf.facility_id IS NULL
    
    UNION ALL
    
    -- Providers with no affiliations (if required by business rules)
    SELECT 
        'provider_no_affiliations' as orphan_type,
        hp.provider_id as entity_id,
        'Provider: ' || COALESCE(hp.full_name, hp.provider_id) as entity_name
    FROM healthcare_providers hp
    LEFT JOIN provider_facility_affiliations pfa ON hp.provider_id = pfa.provider_id
    WHERE pfa.provider_id IS NULL AND hp.record_status = 'ACTIVE'
    
    UNION ALL
    
    -- Facilities with no affiliated providers
    SELECT 
        'facility_no_providers' as orphan_type,
        hf.facility_id as entity_id,
        'Facility: ' || COALESCE(hf.facility_name, hf.facility_id) as entity_name
    FROM healthcare_facilities hf
    LEFT JOIN provider_facility_affiliations pfa ON hf.facility_id = pfa.facility_id
    WHERE pfa.facility_id IS NULL
) orphaned_records
ORDER BY orphan_type, entity_id;

-- Query 6: contact_validation
SELECT 
    'contact_validation' as rule_name,
    provider_id,
    full_name,
    email,
    phone_number,
    CASE 
        WHEN email IS NULL OR TRIM(email) = '' THEN 'Missing email address'
        WHEN email NOT LIKE '%@%.%' THEN 'Invalid email format'
        WHEN email LIKE '%test%' OR email LIKE '%example%' OR email LIKE '%dummy%' THEN 'Test/dummy email detected'
        WHEN phone_number IS NULL OR TRIM(phone_number) = '' THEN 'Missing phone number'
        WHEN LENGTH(REPLACE(REPLACE(REPLACE(phone_number, '(', ''), ')', ''), '-', '')) != 10 THEN 'Invalid phone number format'
        WHEN duplicate_email_count > 1 THEN 'Duplicate email address'
        ELSE 'Other contact validation issue'
    END as issue_description,
    CASE 
        WHEN email IS NULL OR phone_number IS NULL THEN 'HIGH'
        WHEN email NOT LIKE '%@%.%' OR LENGTH(REPLACE(REPLACE(REPLACE(phone_number, '(', ''), ')', ''), '-', '')) != 10 THEN 'MEDIUM'
        WHEN duplicate_email_count > 1 THEN 'MEDIUM'
        ELSE 'LOW'
    END as severity
FROM (
    SELECT 
        provider_id,
        full_name,
        email,
        phone_number,
        COUNT(*) OVER (PARTITION BY email) as duplicate_email_count
    FROM healthcare_providers
    WHERE email IS NOT NULL AND TRIM(email) != ''
) providers_with_counts
WHERE 
    email IS NULL OR TRIM(email) = ''
    OR phone_number IS NULL OR TRIM(phone_number) = ''
    OR email NOT LIKE '%@%.%'
    OR LENGTH(REPLACE(REPLACE(REPLACE(phone_number, '(', ''), ')', ''), '-', '')) != 10
    OR email LIKE '%test%' OR email LIKE '%example%' OR email LIKE '%dummy%'
    OR duplicate_email_count > 1
ORDER BY severity DESC, provider_id;

-- Query 7: validation_summary
SELECT 
    'validation_summary' as rule_name,
    'SUMMARY' as provider_id,
    'Validation Summary Statistics' as full_name,
    printf('Total Providers: %d, Total Facilities: %d, Total Affiliations: %d', 
           provider_count, facility_count, affiliation_count) as issue_description,
    'INFO' as severity
FROM (
    SELECT 
        (SELECT COUNT(*) FROM healthcare_providers) as provider_count,
        (SELECT COUNT(*) FROM healthcare_facilities) as facility_count,
        (SELECT COUNT(*) FROM provider_facility_affiliations) as affiliation_count
);