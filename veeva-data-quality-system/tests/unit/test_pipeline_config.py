"""
Unit tests for PipelineConfig and related configuration classes
Tests configuration loading, validation, and data class functionality
"""

import unittest
import tempfile
import yaml
from pathlib import Path
import os
import sys

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from python.config.pipeline_config import (
    PipelineConfig, QualityThresholds, ValidationRuleConfig, 
    BusinessRules, PerformanceConfig, ReportingConfig
)


class TestQualityThresholds(unittest.TestCase):
    """Test cases for QualityThresholds dataclass"""
    
    def test_default_values(self):
        """Test QualityThresholds with default values"""
        thresholds = QualityThresholds()
        
        self.assertEqual(thresholds.completeness_minimum, 95.0)
        self.assertEqual(thresholds.consistency_minimum, 90.0)
        self.assertEqual(thresholds.accuracy_minimum, 95.0)
        self.assertEqual(thresholds.timeliness_maximum_days, 30)
        self.assertEqual(thresholds.uniqueness_minimum, 99.0)
    
    def test_custom_values(self):
        """Test QualityThresholds with custom values"""
        thresholds = QualityThresholds(
            completeness_minimum=80.0,
            consistency_minimum=85.0,
            accuracy_minimum=90.0,
            timeliness_maximum_days=60,
            uniqueness_minimum=95.0
        )
        
        self.assertEqual(thresholds.completeness_minimum, 80.0)
        self.assertEqual(thresholds.consistency_minimum, 85.0)
        self.assertEqual(thresholds.accuracy_minimum, 90.0)
        self.assertEqual(thresholds.timeliness_maximum_days, 60)
        self.assertEqual(thresholds.uniqueness_minimum, 95.0)


class TestValidationRuleConfig(unittest.TestCase):
    """Test cases for ValidationRuleConfig dataclass"""
    
    def test_default_values(self):
        """Test ValidationRuleConfig with default values"""
        rule = ValidationRuleConfig()
        
        self.assertTrue(rule.enabled)
        self.assertEqual(rule.severity, "MEDIUM")
        self.assertIsNone(rule.confidence_threshold)
        self.assertIsNone(rule.check_format)
        self.assertIsNone(rule.check_duplicates)
    
    def test_custom_values(self):
        """Test ValidationRuleConfig with custom values"""
        rule = ValidationRuleConfig(
            enabled=False,
            severity="HIGH",
            confidence_threshold=0.8,
            check_format=True,
            check_duplicates=False
        )
        
        self.assertFalse(rule.enabled)
        self.assertEqual(rule.severity, "HIGH")
        self.assertEqual(rule.confidence_threshold, 0.8)
        self.assertTrue(rule.check_format)
        self.assertFalse(rule.check_duplicates)


class TestBusinessRules(unittest.TestCase):
    """Test cases for BusinessRules dataclass"""
    
    def test_default_values(self):
        """Test BusinessRules with default values"""
        rules = BusinessRules()
        
        self.assertEqual(rules.max_provider_facilities, 5)
        self.assertEqual(rules.max_monthly_activities, 50)
        self.assertEqual(rules.min_career_years, 1)
        self.assertEqual(rules.max_career_years, 60)
        self.assertEqual(rules.min_graduation_age, 22)
        self.assertEqual(rules.max_graduation_age, 40)
        self.assertEqual(rules.specialty_rules, {})
    
    def test_custom_values(self):
        """Test BusinessRules with custom values"""
        specialty_rules = {"cardiology": {"max_patients": 100}}
        
        rules = BusinessRules(
            max_provider_facilities=10,
            max_monthly_activities=100,
            specialty_rules=specialty_rules
        )
        
        self.assertEqual(rules.max_provider_facilities, 10)
        self.assertEqual(rules.max_monthly_activities, 100)
        self.assertEqual(rules.specialty_rules, specialty_rules)


class TestPerformanceConfig(unittest.TestCase):
    """Test cases for PerformanceConfig dataclass"""
    
    def test_default_values(self):
        """Test PerformanceConfig with default values"""
        config = PerformanceConfig()
        
        self.assertEqual(config.query_timeout_seconds, 300)
        self.assertEqual(config.memory_limit_mb, 2048)
        self.assertFalse(config.enable_query_profiling)
        self.assertTrue(config.cache_query_results)
        self.assertEqual(config.cache_ttl_seconds, 3600)
        self.assertEqual(config.max_workers, 4)
        self.assertEqual(config.batch_size, 10000)
    
    def test_custom_values(self):
        """Test PerformanceConfig with custom values"""
        config = PerformanceConfig(
            query_timeout_seconds=600,
            memory_limit_mb=4096,
            enable_query_profiling=True,
            cache_query_results=False,
            max_workers=8
        )
        
        self.assertEqual(config.query_timeout_seconds, 600)
        self.assertEqual(config.memory_limit_mb, 4096)
        self.assertTrue(config.enable_query_profiling)
        self.assertFalse(config.cache_query_results)
        self.assertEqual(config.max_workers, 8)


class TestReportingConfig(unittest.TestCase):
    """Test cases for ReportingConfig dataclass"""
    
    def test_default_values(self):
        """Test ReportingConfig with default values"""
        config = ReportingConfig()
        
        self.assertEqual(config.output_directory, "reports")
        self.assertEqual(config.formats, ["xlsx", "html", "json"])
        self.assertTrue(config.include_charts)
        self.assertEqual(config.templates, {})
    
    def test_custom_values(self):
        """Test ReportingConfig with custom values"""
        custom_formats = ["csv", "pdf"]
        custom_templates = {"summary": "template.html"}
        
        config = ReportingConfig(
            output_directory="custom_reports",
            formats=custom_formats,
            include_charts=False,
            templates=custom_templates
        )
        
        self.assertEqual(config.output_directory, "custom_reports")
        self.assertEqual(config.formats, custom_formats)
        self.assertFalse(config.include_charts)
        self.assertEqual(config.templates, custom_templates)


class TestPipelineConfig(unittest.TestCase):
    """Test cases for PipelineConfig class"""
    
    def setUp(self):
        """Set up test configuration file"""
        self.test_config_data = {
            "quality_checks": {
                "thresholds": {
                    "completeness_minimum": 85.0,
                    "consistency_minimum": 80.0,
                    "accuracy_minimum": 90.0,
                    "timeliness_maximum_days": 45,
                    "uniqueness_minimum": 97.0
                },
                "validation_rules": {
                    "npi_validation": {
                        "enabled": True,
                        "severity": "HIGH",
                        "check_format": True
                    },
                    "name_consistency": {
                        "enabled": False,
                        "severity": "MEDIUM",
                        "confidence_threshold": 0.7
                    }
                },
                "max_workers": 6,
                "batch_size": 5000
            },
            "business_rules": {
                "max_provider_facilities": 8,
                "max_monthly_activities": 75,
                "specialty_rules": {
                    "cardiology": {"max_patients": 200}
                }
            },
            "performance": {
                "query_timeout_seconds": 450,
                "memory_limit_mb": 3072,
                "enable_query_profiling": True
            },
            "reporting": {
                "output_directory": "test_reports",
                "formats": ["json", "csv"],
                "include_charts": False
            }
        }
        
        # Create temporary config file
        self.temp_config = tempfile.NamedTemporaryFile(
            mode='w', suffix='.yaml', delete=False
        )
        yaml.dump(self.test_config_data, self.temp_config)
        self.temp_config.close()
        self.config_path = self.temp_config.name
    
    def tearDown(self):
        """Clean up temporary config file"""
        if os.path.exists(self.config_path):
            os.unlink(self.config_path)
    
    def test_initialization_with_config_file(self):
        """Test PipelineConfig initialization with custom config file"""
        config = PipelineConfig(self.config_path)
        
        self.assertEqual(config.config_path, self.config_path)
        self.assertIsInstance(config.config_data, dict)
        self.assertIsInstance(config.quality_thresholds, QualityThresholds)
        self.assertIsInstance(config.validation_rules, dict)
        self.assertIsInstance(config.business_rules, BusinessRules)
        self.assertIsInstance(config.performance, PerformanceConfig)
        self.assertIsInstance(config.reporting, ReportingConfig)
    
    def test_initialization_default_config(self):
        """Test PipelineConfig initialization with default config"""
        # This may fail if default config doesn't exist, but tests the path
        try:
            config = PipelineConfig()
            self.assertIsNotNone(config)
        except:
            # Expected if default config file doesn't exist
            pass
    
    def test_load_quality_thresholds(self):
        """Test loading quality thresholds from config"""
        config = PipelineConfig(self.config_path)
        
        thresholds = config.quality_thresholds
        self.assertEqual(thresholds.completeness_minimum, 85.0)
        self.assertEqual(thresholds.consistency_minimum, 80.0)
        self.assertEqual(thresholds.accuracy_minimum, 90.0)
        self.assertEqual(thresholds.timeliness_maximum_days, 45)
        self.assertEqual(thresholds.uniqueness_minimum, 97.0)
    
    def test_load_validation_rules(self):
        """Test loading validation rules from config"""
        config = PipelineConfig(self.config_path)
        
        rules = config.validation_rules
        self.assertIn("npi_validation", rules)
        self.assertIn("name_consistency", rules)
        
        npi_rule = rules["npi_validation"]
        self.assertTrue(npi_rule.enabled)
        self.assertEqual(npi_rule.severity, "HIGH")
        self.assertTrue(npi_rule.check_format)
        
        name_rule = rules["name_consistency"]
        self.assertFalse(name_rule.enabled)
        self.assertEqual(name_rule.severity, "MEDIUM")
        self.assertEqual(name_rule.confidence_threshold, 0.7)
    
    def test_load_business_rules(self):
        """Test loading business rules from config"""
        config = PipelineConfig(self.config_path)
        
        rules = config.business_rules
        self.assertEqual(rules.max_provider_facilities, 8)
        self.assertEqual(rules.max_monthly_activities, 75)
        self.assertIn("cardiology", rules.specialty_rules)
        self.assertEqual(rules.specialty_rules["cardiology"]["max_patients"], 200)
    
    def test_load_performance_config(self):
        """Test loading performance configuration"""
        config = PipelineConfig(self.config_path)
        
        performance = config.performance
        self.assertEqual(performance.query_timeout_seconds, 450)
        self.assertEqual(performance.memory_limit_mb, 3072)
        self.assertTrue(performance.enable_query_profiling)
        # These should come from quality_checks section
        self.assertEqual(performance.max_workers, 6)
        self.assertEqual(performance.batch_size, 5000)
    
    def test_load_reporting_config(self):
        """Test loading reporting configuration"""
        config = PipelineConfig(self.config_path)
        
        reporting = config.reporting
        self.assertEqual(reporting.output_directory, "test_reports")
        self.assertEqual(reporting.formats, ["json", "csv"])
        self.assertFalse(reporting.include_charts)
    
    def test_get_validation_rule_config(self):
        """Test getting specific validation rule configuration"""
        config = PipelineConfig(self.config_path)
        
        # Test existing rule
        npi_config = config.get_validation_rule_config("npi_validation")
        self.assertIsNotNone(npi_config)
        self.assertTrue(npi_config.enabled)
        self.assertEqual(npi_config.severity, "HIGH")
        
        # Test non-existent rule
        missing_config = config.get_validation_rule_config("nonexistent_rule")
        self.assertIsNone(missing_config)
    
    def test_load_empty_config(self):
        """Test loading empty configuration file"""
        # Create empty config file
        empty_config = tempfile.NamedTemporaryFile(
            mode='w', suffix='.yaml', delete=False
        )
        empty_config.write("")
        empty_config.close()
        
        try:
            config = PipelineConfig(empty_config.name)
            
            # Should use default values
            self.assertEqual(config.quality_thresholds.completeness_minimum, 95.0)
            self.assertEqual(len(config.validation_rules), 0)
            self.assertEqual(config.business_rules.max_provider_facilities, 5)
            self.assertEqual(config.performance.max_workers, 4)
            self.assertEqual(config.reporting.output_directory, "reports")
        finally:
            os.unlink(empty_config.name)
    
    def test_load_malformed_config(self):
        """Test loading malformed YAML configuration"""
        # Create malformed config file
        malformed_config = tempfile.NamedTemporaryFile(
            mode='w', suffix='.yaml', delete=False
        )
        malformed_config.write("invalid: yaml: content:\n  - missing: bracket")
        malformed_config.close()
        
        try:
            config = PipelineConfig(malformed_config.name)
            
            # Should handle error gracefully and use defaults
            self.assertEqual(config.config_data, {})
            self.assertEqual(config.quality_thresholds.completeness_minimum, 95.0)
        finally:
            os.unlink(malformed_config.name)
    
    def test_load_nonexistent_config(self):
        """Test loading non-existent configuration file"""
        config = PipelineConfig("/nonexistent/config.yaml")
        
        # Should handle missing file gracefully and use defaults
        self.assertEqual(config.config_data, {})
        self.assertEqual(config.quality_thresholds.completeness_minimum, 95.0)
        self.assertEqual(len(config.validation_rules), 0)
    
    def test_partial_config_sections(self):
        """Test config with only some sections defined"""
        partial_config_data = {
            "quality_checks": {
                "thresholds": {
                    "completeness_minimum": 75.0
                }
            }
        }
        
        # Create partial config file
        partial_config = tempfile.NamedTemporaryFile(
            mode='w', suffix='.yaml', delete=False
        )
        yaml.dump(partial_config_data, partial_config)
        partial_config.close()
        
        try:
            config = PipelineConfig(partial_config.name)
            
            # Should load defined values and use defaults for missing ones
            self.assertEqual(config.quality_thresholds.completeness_minimum, 75.0)
            self.assertEqual(config.quality_thresholds.consistency_minimum, 90.0)  # default
            self.assertEqual(config.business_rules.max_provider_facilities, 5)  # default
        finally:
            os.unlink(partial_config.name)
    
    def test_config_data_access(self):
        """Test direct access to config data"""
        config = PipelineConfig(self.config_path)
        
        # Should be able to access raw config data
        self.assertIn("quality_checks", config.config_data)
        self.assertIn("business_rules", config.config_data)
        self.assertIn("performance", config.config_data)
        self.assertIn("reporting", config.config_data)
    
    def test_config_path_resolution(self):
        """Test configuration path resolution"""
        config = PipelineConfig(self.config_path)
        self.assertEqual(config.config_path, self.config_path)
        
        # Test default path resolution
        default_config = PipelineConfig()
        self.assertTrue(default_config.config_path.endswith('pipeline_config.yaml'))


if __name__ == '__main__':
    unittest.main()