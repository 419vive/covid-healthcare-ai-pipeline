"""
Logging configuration for Veeva Data Quality System
"""

import os
import sys
import logging
import logging.handlers
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime


def setup_logging(
    log_level: str = "INFO",
    log_file: Optional[str] = None,
    console_output: bool = True,
    max_file_size_mb: int = 10,
    backup_count: int = 5,
    log_format: Optional[str] = None
) -> logging.Logger:
    """
    Setup comprehensive logging configuration
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file (optional)
        console_output: Whether to output to console
        max_file_size_mb: Maximum log file size before rotation
        backup_count: Number of backup log files to keep
        log_format: Custom log format string
        
    Returns:
        Configured logger instance
    """
    
    # Create main logger
    logger = logging.getLogger('veeva_dq')
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # Clear existing handlers
    logger.handlers.clear()
    
    # Default format
    if log_format is None:
        log_format = "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s"
    
    formatter = logging.Formatter(
        log_format,
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, log_level.upper()))
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    # File handler with rotation
    if log_file:
        # Ensure log directory exists
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=max_file_size_mb * 1024 * 1024,  # Convert MB to bytes
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(getattr(logging, log_level.upper()))
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    # Add custom filter for sensitive data
    logger.addFilter(SensitiveDataFilter())
    
    return logger


class SensitiveDataFilter(logging.Filter):
    """Filter to remove sensitive data from log messages"""
    
    SENSITIVE_PATTERNS = [
        # Common sensitive patterns
        r'password["\s]*[:=]["\s]*[^"\s]+',
        r'api[_-]?key["\s]*[:=]["\s]*[^"\s]+',
        r'secret["\s]*[:=]["\s]*[^"\s]+',
        r'token["\s]*[:=]["\s]*[^"\s]+',
        # Database connection strings
        r'sqlite:///.+',
        r'postgresql://[^@]+@[^/]+/',
        r'mysql://[^@]+@[^/]+/',
    ]
    
    def filter(self, record):
        """Filter sensitive data from log records"""
        import re
        
        message = str(record.getMessage())
        
        for pattern in self.SENSITIVE_PATTERNS:
            message = re.sub(pattern, '[REDACTED]', message, flags=re.IGNORECASE)
        
        # Update the record message
        record.msg = message
        record.args = ()
        
        return True


class PerformanceLogger:
    """Context manager for performance logging"""
    
    def __init__(self, operation_name: str, logger: Optional[logging.Logger] = None):
        self.operation_name = operation_name
        self.logger = logger or logging.getLogger('veeva_dq.performance')
        self.start_time = None
        
    def __enter__(self):
        self.start_time = datetime.now()
        self.logger.info(f"Starting operation: {self.operation_name}")
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            duration = (datetime.now() - self.start_time).total_seconds()
            
            if exc_type is None:
                self.logger.info(f"Operation completed: {self.operation_name} ({duration:.2f}s)")
            else:
                self.logger.error(f"Operation failed: {self.operation_name} ({duration:.2f}s) - {exc_val}")


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the specified name under the veeva_dq namespace"""
    return logging.getLogger(f'veeva_dq.{name}')


def log_system_info():
    """Log system information for debugging"""
    logger = get_logger('system')
    
    import platform
    import psutil
    
    logger.info(f"Python version: {platform.python_version()}")
    logger.info(f"Platform: {platform.platform()}")
    logger.info(f"CPU count: {psutil.cpu_count()}")
    logger.info(f"Memory: {psutil.virtual_memory().total // (1024**3)} GB")
    logger.info(f"Working directory: {os.getcwd()}")


def configure_third_party_loggers(level: str = "WARNING"):
    """Configure third-party library loggers to reduce noise"""
    third_party_loggers = [
        'urllib3',
        'requests',
        'sqlalchemy.engine',
        'sqlalchemy.pool',
        'pandas.io.common',
    ]
    
    for logger_name in third_party_loggers:
        logging.getLogger(logger_name).setLevel(getattr(logging, level.upper()))