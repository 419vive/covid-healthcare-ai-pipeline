"""
Base model class and common database setup
"""

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, String, DateTime, func
from datetime import datetime
from typing import Dict, Any


Base = declarative_base()


class BaseModel(Base):
    """Base model class with common fields and methods"""
    
    __abstract__ = True
    
    # Common audit fields
    created_at = Column(DateTime, default=func.current_timestamp())
    updated_at = Column(DateTime, default=func.current_timestamp(), onupdate=func.current_timestamp())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model instance to dictionary"""
        return {
            column.name: getattr(self, column.name)
            for column in self.__table__.columns
        }
    
    def update_from_dict(self, data: Dict[str, Any]) -> None:
        """Update model instance from dictionary"""
        for key, value in data.items():
            if hasattr(self, key):
                setattr(self, key, value)
    
    @classmethod
    def get_column_names(cls) -> list[str]:
        """Get list of column names for the model"""
        return [column.name for column in cls.__table__.columns]
    
    def __repr__(self) -> str:
        """String representation of the model"""
        class_name = self.__class__.__name__
        primary_key = getattr(self, self.__table__.primary_key.columns.keys()[0])
        return f"<{class_name}(id={primary_key})>"