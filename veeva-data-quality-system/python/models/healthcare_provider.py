"""
Healthcare Provider model
"""

from sqlalchemy import Column, String, Integer, Boolean, DateTime, Numeric, Date, Text
from sqlalchemy.orm import relationship
from .base import BaseModel


class HealthcareProvider(BaseModel):
    """Healthcare Provider model - Core provider information"""
    
    __tablename__ = 'healthcare_providers'
    
    # Primary identifier
    provider_id = Column(String(50), primary_key=True)
    
    # National Provider Identifier 
    npi_number = Column(String(10), unique=True, index=True)
    
    # Name information
    full_name = Column(String(200), nullable=False, index=True)
    first_name = Column(String(100))
    last_name = Column(String(100), nullable=False, index=True)
    middle_initial = Column(String(10))
    name_suffix = Column(String(20))  # Jr., Sr., III, etc.
    
    # Professional information
    degree = Column(String(50))  # MD, DO, NP, PA, etc.
    specialty_primary = Column(String(100), index=True)
    specialty_secondary = Column(String(100))
    sub_specialty = Column(String(100))
    
    # Contact information
    email = Column(String(100), index=True)
    phone_number = Column(String(20))
    
    # License information
    license_number = Column(String(50), index=True)
    license_state = Column(String(2), index=True)
    license_expiry_date = Column(Date)
    dea_number = Column(String(20))  # Drug Enforcement Administration number
    
    # Professional details
    board_certification = Column(String(200))
    years_in_practice = Column(Integer)
    medical_school = Column(String(200))
    graduation_year = Column(Integer)
    
    # Demographics
    gender = Column(String(10))
    birth_year = Column(Integer)
    
    # Data quality and lineage fields
    data_source = Column(String(50), nullable=False, default='UNKNOWN', index=True)
    source_confidence = Column(Numeric(3, 2), default=0.50)
    last_updated = Column(DateTime, nullable=False, index=True)
    last_verified = Column(Date)
    is_golden_record = Column(Boolean, default=False, index=True)
    record_status = Column(String(20), default='ACTIVE', index=True)
    
    # Audit fields  
    created_by = Column(String(50), default='SYSTEM')
    updated_by = Column(String(50), default='SYSTEM')
    
    # Relationships
    affiliations = relationship("ProviderFacilityAffiliation", back_populates="provider")
    activities = relationship("MedicalActivity", back_populates="provider")
    
    def __repr__(self) -> str:
        return f"<HealthcareProvider(id={self.provider_id}, name={self.full_name}, specialty={self.specialty_primary})>"
    
    @property
    def is_active(self) -> bool:
        """Check if provider record is active"""
        return self.record_status == 'ACTIVE'
    
    @property
    def has_valid_npi(self) -> bool:
        """Check if provider has valid NPI format"""
        if not self.npi_number:
            return False
        return len(self.npi_number) == 10 and self.npi_number.isdigit()
    
    @property
    def name_completeness_score(self) -> float:
        """Calculate name completeness score"""
        fields = [self.full_name, self.first_name, self.last_name]
        filled_fields = sum(1 for field in fields if field and field.strip())
        return (filled_fields / len(fields)) * 100
    
    @property
    def contact_completeness_score(self) -> float:
        """Calculate contact information completeness score"""
        fields = [self.email, self.phone_number]
        filled_fields = sum(1 for field in fields if field and field.strip())
        return (filled_fields / len(fields)) * 100
    
    @property
    def license_completeness_score(self) -> float:
        """Calculate license information completeness score"""
        fields = [self.license_number, self.license_state]
        filled_fields = sum(1 for field in fields if field and field.strip())
        return (filled_fields / len(fields)) * 100
    
    def get_overall_completeness_score(self) -> float:
        """Calculate overall data completeness score"""
        # Core required fields
        core_fields = [
            self.full_name, self.first_name, self.last_name,
            self.specialty_primary, self.license_number, self.license_state
        ]
        
        # Optional but important fields
        optional_fields = [
            self.npi_number, self.email, self.phone_number,
            self.degree, self.years_in_practice
        ]
        
        core_filled = sum(1 for field in core_fields if field and str(field).strip())
        optional_filled = sum(1 for field in optional_fields if field and str(field).strip())
        
        # Weight core fields more heavily
        core_weight = 0.7
        optional_weight = 0.3
        
        core_score = (core_filled / len(core_fields)) * core_weight
        optional_score = (optional_filled / len(optional_fields)) * optional_weight
        
        return (core_score + optional_score) * 100
    
    def validate_data_quality(self) -> dict:
        """Validate provider data quality and return issues"""
        issues = []
        
        # Name validation
        if not self.full_name or not self.full_name.strip():
            issues.append("Missing or empty full name")
        
        if not self.last_name or not self.last_name.strip():
            issues.append("Missing or empty last name")
        
        # NPI validation
        if self.npi_number and not self.has_valid_npi:
            issues.append("Invalid NPI number format")
        
        # License validation
        if self.license_state and len(self.license_state) != 2:
            issues.append("Invalid license state format")
        
        # Email validation (basic)
        if self.email and '@' not in self.email:
            issues.append("Invalid email format")
        
        # Birth year validation
        if self.birth_year:
            current_year = 2024  # Or use datetime.now().year
            if self.birth_year < 1920 or self.birth_year > 2005:
                issues.append("Unrealistic birth year")
        
        # Years in practice validation
        if self.years_in_practice is not None:
            if self.years_in_practice < 0 or self.years_in_practice > 60:
                issues.append("Invalid years in practice")
        
        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "completeness_score": self.get_overall_completeness_score()
        }