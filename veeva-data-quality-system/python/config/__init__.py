"""
Configuration management for Veeva Data Quality System
"""

from .database_config import DatabaseConfig
from .pipeline_config import PipelineConfig

__all__ = ['DatabaseConfig', 'PipelineConfig']