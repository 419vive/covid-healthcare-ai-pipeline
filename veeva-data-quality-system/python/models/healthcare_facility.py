"""
Healthcare Facility model
"""

from sqlalchemy import Column, String, Integer, DateTime, Numeric, Date, Text
from sqlalchemy.orm import relationship
from .base import BaseModel


class HealthcareFacility(BaseModel):
    """Healthcare Facility model - Medical facilities and institutions"""
    
    __tablename__ = 'healthcare_facilities'
    
    # Primary identifier
    facility_id = Column(String(50), primary_key=True)
    
    # Basic facility information
    facility_name = Column(String(300), nullable=False, index=True)
    facility_type = Column(String(50), index=True)  # Hospital, Clinic, Practice, etc.
    organization_type = Column(String(50))  # Non-profit, For-profit, Government
    
    # Address information
    address_line1 = Column(String(200))
    address_line2 = Column(String(200))
    city = Column(String(100), index=True)
    state_province = Column(String(100), index=True)
    postal_code = Column(String(20), index=True)
    country = Column(String(100), default='USA')
    
    # Contact information
    phone = Column(String(50))
    fax = Column(String(50))
    website = Column(String(200))
    email = Column(String(100))
    
    # Facility details
    bed_count = Column(Integer)
    employee_count = Column(Integer)
    specialties_offered = Column(Text)
    accreditation_status = Column(String(100))
    accreditation_date = Column(Date)
    medicare_provider_number = Column(String(20))
    
    # Geographic and administrative
    county = Column(String(100))
    msa_code = Column(String(20))  # Metropolitan Statistical Area
    cbsa_code = Column(String(20))  # Core Based Statistical Area
    network_affiliation = Column(String(200))
    ownership = Column(String(100))
    
    # Data quality fields
    data_source = Column(String(50), nullable=False, default='UNKNOWN', index=True)
    source_confidence = Column(Numeric(3, 2), default=0.50)
    last_updated = Column(DateTime, nullable=False, index=True)
    last_verified = Column(Date)
    validation_status = Column(String(20), default='PENDING', index=True)
    
    # Audit fields
    created_by = Column(String(50), default='SYSTEM')
    updated_by = Column(String(50), default='SYSTEM')
    
    # Relationships
    affiliations = relationship("ProviderFacilityAffiliation", back_populates="facility")
    activities = relationship("MedicalActivity", back_populates="facility")
    
    def __repr__(self) -> str:
        return f"<HealthcareFacility(id={self.facility_id}, name={self.facility_name}, type={self.facility_type})>"
    
    @property
    def is_validated(self) -> bool:
        """Check if facility has been validated"""
        return self.validation_status == 'VERIFIED'
    
    @property
    def full_address(self) -> str:
        """Get formatted full address"""
        address_parts = []
        
        if self.address_line1:
            address_parts.append(self.address_line1.strip())
        
        if self.address_line2:
            address_parts.append(self.address_line2.strip())
        
        city_state_zip = []
        if self.city:
            city_state_zip.append(self.city.strip())
        
        if self.state_province:
            city_state_zip.append(self.state_province.strip())
        
        if self.postal_code:
            city_state_zip.append(self.postal_code.strip())
        
        if city_state_zip:
            address_parts.append(', '.join(city_state_zip))
        
        if self.country and self.country != 'USA':
            address_parts.append(self.country.strip())
        
        return '\n'.join(address_parts)
    
    @property
    def address_completeness_score(self) -> float:
        """Calculate address completeness score"""
        required_fields = [self.address_line1, self.city, self.state_province, self.postal_code]
        filled_fields = sum(1 for field in required_fields if field and field.strip())
        return (filled_fields / len(required_fields)) * 100
    
    @property
    def contact_completeness_score(self) -> float:
        """Calculate contact information completeness score"""
        fields = [self.phone, self.email, self.website]
        filled_fields = sum(1 for field in fields if field and field.strip())
        return (filled_fields / len(fields)) * 100
    
    def get_overall_completeness_score(self) -> float:
        """Calculate overall facility data completeness score"""
        # Core required fields
        core_fields = [
            self.facility_name, self.facility_type,
            self.address_line1, self.city, self.state_province
        ]
        
        # Important but optional fields
        optional_fields = [
            self.postal_code, self.phone, self.email,
            self.bed_count, self.organization_type
        ]
        
        core_filled = sum(1 for field in core_fields if field and str(field).strip())
        optional_filled = sum(1 for field in optional_fields if field is not None and str(field).strip())
        
        # Weight core fields more heavily
        core_weight = 0.8
        optional_weight = 0.2
        
        core_score = (core_filled / len(core_fields)) * core_weight
        optional_score = (optional_filled / len(optional_fields)) * optional_weight
        
        return (core_score + optional_score) * 100
    
    def validate_data_quality(self) -> dict:
        """Validate facility data quality and return issues"""
        issues = []
        
        # Name validation
        if not self.facility_name or not self.facility_name.strip():
            issues.append("Missing or empty facility name")
        
        # Address validation
        if not self.address_line1 or not self.address_line1.strip():
            issues.append("Missing street address")
        
        if not self.city or not self.city.strip():
            issues.append("Missing city")
        
        if not self.state_province or not self.state_province.strip():
            issues.append("Missing state/province")
        
        # Postal code validation (basic US format)
        if self.postal_code:
            postal_clean = self.postal_code.replace('-', '').replace(' ', '')
            if not (len(postal_clean) == 5 or len(postal_clean) == 9) or not postal_clean.isdigit():
                issues.append("Invalid postal code format")
        
        # Email validation (basic)
        if self.email and '@' not in self.email:
            issues.append("Invalid email format")
        
        # Bed count validation
        if self.bed_count is not None and self.bed_count <= 0:
            issues.append("Invalid bed count")
        
        # Facility type validation
        valid_facility_types = [
            'Hospital', 'Outpatient Clinic', 'Urgent Care', 'Surgery Center',
            'Diagnostic Center', 'Rehabilitation Center', 'Nursing Home',
            'Private Practice', 'Community Health Center', 'Academic Medical Center'
        ]
        
        if self.facility_type and self.facility_type not in valid_facility_types:
            issues.append(f"Unrecognized facility type: {self.facility_type}")
        
        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "completeness_score": self.get_overall_completeness_score()
        }
    
    def get_geographic_identifier(self) -> str:
        """Get geographic identifier for location matching"""
        parts = []
        
        if self.city:
            parts.append(self.city.upper().strip())
        
        if self.state_province:
            parts.append(self.state_province.upper().strip())
        
        if self.postal_code:
            # Use first 5 digits of postal code
            postal_clean = self.postal_code.replace('-', '').replace(' ', '')
            if len(postal_clean) >= 5:
                parts.append(postal_clean[:5])
        
        return '|'.join(parts)
    
    @classmethod
    def get_facility_types(cls) -> list:
        """Get list of valid facility types"""
        return [
            'Hospital', 'Outpatient Clinic', 'Urgent Care', 'Surgery Center',
            'Diagnostic Center', 'Rehabilitation Center', 'Nursing Home',
            'Private Practice', 'Community Health Center', 'Academic Medical Center'
        ]