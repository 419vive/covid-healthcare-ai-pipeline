"""
Pipeline configuration management
"""

import os
import yaml
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, List, Any, Optional


@dataclass
class QualityThresholds:
    """Data quality threshold configuration"""
    completeness_minimum: float = 95.0
    consistency_minimum: float = 90.0
    accuracy_minimum: float = 95.0
    timeliness_maximum_days: int = 30
    uniqueness_minimum: float = 99.0


@dataclass  
class ValidationRuleConfig:
    """Individual validation rule configuration"""
    enabled: bool = True
    severity: str = "MEDIUM"
    confidence_threshold: Optional[float] = None
    check_format: Optional[bool] = None
    check_duplicates: Optional[bool] = None
    max_facilities_p95: Optional[bool] = None
    multi_state_flag: Optional[bool] = None
    check_age_ranges: Optional[bool] = None
    check_career_timeline: Optional[bool] = None
    check_orphaned_records: Optional[bool] = None


@dataclass
class BusinessRules:
    """Business rules configuration"""
    max_provider_facilities: int = 5
    max_monthly_activities: int = 50
    min_career_years: int = 1
    max_career_years: int = 60
    min_graduation_age: int = 22
    max_graduation_age: int = 40
    specialty_rules: Dict[str, Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.specialty_rules is None:
            self.specialty_rules = {}


@dataclass
class PerformanceConfig:
    """Performance and resource configuration"""
    query_timeout_seconds: int = 300
    memory_limit_mb: int = 2048
    enable_query_profiling: bool = False
    cache_query_results: bool = True
    cache_ttl_seconds: int = 3600
    max_workers: int = 4
    batch_size: int = 10000


@dataclass
class ReportingConfig:
    """Reporting configuration"""
    output_directory: str = "reports"
    formats: List[str] = None
    include_charts: bool = True
    templates: Dict[str, str] = None
    
    def __post_init__(self):
        if self.formats is None:
            self.formats = ["xlsx", "html", "json"]
        if self.templates is None:
            self.templates = {}


class PipelineConfig:
    """Main pipeline configuration manager"""
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize configuration from YAML file"""
        self.config_path = config_path or self._get_default_config_path()
        self.config_data = self._load_config()
        
        # Initialize configuration sections
        self.quality_thresholds = self._load_quality_thresholds()
        self.validation_rules = self._load_validation_rules()
        self.business_rules = self._load_business_rules()
        self.performance = self._load_performance_config()
        self.reporting = self._load_reporting_config()
    
    def _get_default_config_path(self) -> str:
        """Get default configuration file path"""
        return str(Path(__file__).parent / "pipeline_config.yaml")
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as file:
                return yaml.safe_load(file)
        except FileNotFoundError:
            print(f"Config file not found: {self.config_path}")
            return {}
        except yaml.YAMLError as e:
            print(f"Error parsing config file: {e}")
            return {}
    
    def _load_quality_thresholds(self) -> QualityThresholds:
        """Load quality thresholds configuration"""
        thresholds_data = self.config_data.get("quality_checks", {}).get("thresholds", {})
        return QualityThresholds(**thresholds_data)
    
    def _load_validation_rules(self) -> Dict[str, ValidationRuleConfig]:
        """Load validation rules configuration"""
        rules_data = self.config_data.get("quality_checks", {}).get("validation_rules", {})
        validation_rules = {}
        
        for rule_name, rule_config in rules_data.items():
            validation_rules[rule_name] = ValidationRuleConfig(**rule_config)
        
        return validation_rules
    
    def _load_business_rules(self) -> BusinessRules:
        """Load business rules configuration"""
        rules_data = self.config_data.get("business_rules", {})
        return BusinessRules(**rules_data)
    
    def _load_performance_config(self) -> PerformanceConfig:
        """Load performance configuration"""
        perf_data = self.config_data.get("performance", {})
        quality_checks = self.config_data.get("quality_checks", {})
        
        # Merge performance data with quality checks performance settings
        merged_data = {
            **perf_data,
            "max_workers": quality_checks.get("max_workers", 4),
            "batch_size": quality_checks.get("batch_size", 10000)
        }
        
        return PerformanceConfig(**merged_data)
    
    def _load_reporting_config(self) -> ReportingConfig:
        """Load reporting configuration"""
        reporting_data = self.config_data.get("reporting", {})
        return ReportingConfig(**reporting_data)
    
    def get_validation_rule_config(self, rule_name: str) -> Optional[ValidationRuleConfig]:
        """Get configuration for specific validation rule"""
        return self.validation_rules.get(rule_name)
    
    def is_rule_enabled(self, rule_name: str) -> bool:
        """Check if validation rule is enabled"""
        rule_config = self.get_validation_rule_config(rule_name)
        return rule_config.enabled if rule_config else False
    
    def get_rule_severity(self, rule_name: str) -> str:
        """Get severity level for validation rule"""
        rule_config = self.get_validation_rule_config(rule_name)
        return rule_config.severity if rule_config else "MEDIUM"
    
    def get_specialty_rules(self, specialty: str) -> Dict[str, Any]:
        """Get business rules for specific specialty"""
        return self.business_rules.specialty_rules.get(specialty, {})
    
    def get_database_path(self) -> str:
        """Get database path from configuration"""
        return self.config_data.get("database", {}).get("path", "data/database/veeva_opendata.db")
    
    def get_logging_config(self) -> Dict[str, Any]:
        """Get logging configuration"""
        return self.config_data.get("logging", {
            "level": "INFO",
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            "file_path": "logs/veeva_dq.log",
            "console_output": True
        })
    
    def update_config(self, updates: Dict[str, Any]) -> None:
        """Update configuration with new values"""
        self._deep_update(self.config_data, updates)
        self._reload_configurations()
    
    def _deep_update(self, base_dict: Dict[str, Any], update_dict: Dict[str, Any]) -> None:
        """Deep update dictionary with nested values"""
        for key, value in update_dict.items():
            if isinstance(value, dict) and key in base_dict and isinstance(base_dict[key], dict):
                self._deep_update(base_dict[key], value)
            else:
                base_dict[key] = value
    
    def _reload_configurations(self) -> None:
        """Reload all configuration sections after update"""
        self.quality_thresholds = self._load_quality_thresholds()
        self.validation_rules = self._load_validation_rules()
        self.business_rules = self._load_business_rules()
        self.performance = self._load_performance_config()
        self.reporting = self._load_reporting_config()
    
    def save_config(self, output_path: Optional[str] = None) -> None:
        """Save current configuration to YAML file"""
        output_path = output_path or self.config_path
        try:
            with open(output_path, 'w', encoding='utf-8') as file:
                yaml.dump(self.config_data, file, default_flow_style=False, indent=2)
            print(f"Configuration saved to: {output_path}")
        except Exception as e:
            print(f"Error saving configuration: {e}")
    
    @classmethod
    def create_default_config(cls, output_path: str) -> 'PipelineConfig':
        """Create default configuration file"""
        default_config = {
            "database": {"path": "data/database/veeva_opendata.db", "echo_sql": False},
            "quality_checks": {
                "enabled": True,
                "thresholds": {
                    "completeness_minimum": 95.0,
                    "consistency_minimum": 90.0,
                    "accuracy_minimum": 95.0
                }
            },
            "business_rules": {"max_provider_facilities": 5},
            "performance": {"query_timeout_seconds": 300},
            "reporting": {"output_directory": "reports"}
        }
        
        with open(output_path, 'w', encoding='utf-8') as file:
            yaml.dump(default_config, file, default_flow_style=False, indent=2)
        
        return cls(output_path)