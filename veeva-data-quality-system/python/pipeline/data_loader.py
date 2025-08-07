"""
Module: data_loader.py
Purpose: Data loading pipeline for CORD-19 to healthcare provider transformation
Author: Claude Code + Cursor AI
Created: 2025-08-07
Description: Transforms CORD-19 author data into simulated healthcare provider records
"""

import sqlite3
import pandas as pd
import numpy as np
import json
import hashlib
import uuid
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional, Tuple
from pathlib import Path
import random
import re

class HealthcareDataTransformer:
    """Transform CORD-19 data into realistic healthcare provider records"""
    
    def __init__(self, cord19_path: str, output_db_path: str):
        self.cord19_path = Path(cord19_path)
        self.output_db_path = Path(output_db_path)
        self.db_connection = None
        
        # Healthcare-specific data for realistic simulation
        self.medical_specialties = [
            'Internal Medicine', 'Family Medicine', 'Cardiology', 'Oncology',
            'Pulmonology', 'Infectious Disease', 'Emergency Medicine', 'Radiology',
            'Pathology', 'Anesthesiology', 'Surgery', 'Neurology', 'Psychiatry',
            'Dermatology', 'Ophthalmology', 'Orthopedics', 'Pediatrics', 'Obstetrics',
            'Endocrinology', 'Gastroenterology', 'Nephrology', 'Rheumatology'
        ]
        
        self.degree_types = ['MD', 'DO', 'PhD', 'MD/PhD', 'PharmD', 'NP', 'PA-C', 'RN']
        
        self.facility_types = [
            'Academic Medical Center', 'Community Hospital', 'Private Practice',
            'Outpatient Clinic', 'Research Institute', 'Surgery Center', 
            'Rehabilitation Center', 'Urgent Care'
        ]
        
        self.us_states = [
            'CA', 'NY', 'TX', 'FL', 'PA', 'IL', 'OH', 'GA', 'NC', 'MI',
            'NJ', 'VA', 'WA', 'AZ', 'MA', 'TN', 'IN', 'MO', 'MD', 'WI'
        ]
        
        # Set random seed for reproducible results
        random.seed(42)
        np.random.seed(42)

    def connect_database(self):
        """Establish database connection and execute schema"""
        self.db_connection = sqlite3.connect(str(self.output_db_path))
        
        # Execute schema creation
        schema_path = self.output_db_path.parent.parent / 'sql' / '01_schema' / 'create_tables.sql'
        if schema_path.exists():
            with open(schema_path, 'r') as f:
                schema_sql = f.read()
                # Execute schema in chunks to handle complex statements
                statements = schema_sql.split(';')
                for statement in statements:
                    if statement.strip():
                        try:
                            self.db_connection.execute(statement)
                        except sqlite3.Error as e:
                            if 'already exists' not in str(e):
                                print(f"Schema error: {e}")
                                print(f"Statement: {statement[:100]}...")
        
        self.db_connection.commit()
        print(f"Database connection established: {self.output_db_path}")

    def generate_npi(self, provider_id: str) -> str:
        """Generate realistic NPI number (10 digits)"""
        # Use hash of provider_id to ensure consistency
        hash_obj = hashlib.md5(provider_id.encode())
        hash_digits = ''.join([c for c in hash_obj.hexdigest() if c.isdigit()])
        
        if len(hash_digits) >= 10:
            return hash_digits[:10]
        else:
            # Pad with random digits if needed
            padding = ''.join([str(random.randint(0, 9)) for _ in range(10 - len(hash_digits))])
            return hash_digits + padding

    def generate_license_number(self, state: str, provider_id: str) -> str:
        """Generate realistic medical license number"""
        hash_obj = hashlib.md5(f"{state}{provider_id}".encode())
        hash_hex = hash_obj.hexdigest()[:8].upper()
        return f"{state}{hash_hex}"

    def parse_author_name(self, full_name: str) -> Dict[str, str]:
        """Parse full name into components"""
        if pd.isna(full_name) or not full_name:
            return {'first_name': None, 'last_name': None, 'middle_initial': None}
        
        # Clean the name
        name = re.sub(r'[^\w\s\-\']', '', str(full_name).strip())
        parts = name.split()
        
        if len(parts) == 0:
            return {'first_name': None, 'last_name': None, 'middle_initial': None}
        elif len(parts) == 1:
            return {'first_name': parts[0], 'last_name': parts[0], 'middle_initial': None}
        elif len(parts) == 2:
            return {'first_name': parts[0], 'last_name': parts[1], 'middle_initial': None}
        else:
            # More than 2 parts
            first = parts[0]
            last = parts[-1]
            middle = parts[1][0] if len(parts[1]) > 0 else None
            return {'first_name': first, 'last_name': last, 'middle_initial': middle}

    def generate_email(self, first_name: str, last_name: str, facility_name: str = None) -> str:
        """Generate realistic email address"""
        if not first_name or not last_name:
            return None
        
        domains = ['gmail.com', 'yahoo.com', 'outlook.com', 'hospital.org', 'clinic.org', 'medical.edu']
        if facility_name:
            # Try to use facility-based email
            clean_facility = re.sub(r'[^\w]', '', facility_name.lower())[:10]
            domains.insert(0, f"{clean_facility}.org")
        
        first_clean = re.sub(r'[^\w]', '', first_name.lower())
        last_clean = re.sub(r'[^\w]', '', last_name.lower())
        
        email_formats = [
            f"{first_clean}.{last_clean}",
            f"{first_clean[0]}{last_clean}",
            f"{first_clean}_{last_clean}",
            f"{first_clean}{last_clean[0]}"
        ]
        
        email_prefix = random.choice(email_formats)
        domain = random.choice(domains)
        return f"{email_prefix}@{domain}"

    def load_cord19_data(self, sample_size: int = 50000) -> pd.DataFrame:
        """Load and sample CORD-19 author data"""
        print(f"Loading CORD-19 data from {self.cord19_path}")
        
        # Try different possible file structures in the CORD-19 data
        possible_files = [
            'metadata.csv',
            'cord19_authors.csv',
            'authors.csv'
        ]
        
        df = None
        for filename in possible_files:
            filepath = self.cord19_path / filename
            if filepath.exists():
                print(f"Found data file: {filepath}")
                try:
                    df = pd.read_csv(filepath)
                    break
                except Exception as e:
                    print(f"Error reading {filepath}: {e}")
                    continue
        
        if df is None:
            # Create synthetic data if CORD-19 not available
            print("CORD-19 data not found, creating synthetic author data")
            df = self.create_synthetic_authors(sample_size)
        
        # Sample the data
        if len(df) > sample_size:
            df = df.sample(n=sample_size, random_state=42)
        
        print(f"Loaded {len(df)} author records")
        return df

    def create_synthetic_authors(self, count: int) -> pd.DataFrame:
        """Create synthetic author data for testing"""
        first_names = ['John', 'Mary', 'David', 'Sarah', 'Michael', 'Lisa', 'Robert', 'Jennifer',
                      'William', 'Patricia', 'James', 'Linda', 'Richard', 'Elizabeth', 'Charles']
        last_names = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis',
                     'Rodriguez', 'Martinez', 'Hernandez', 'Lopez', 'Gonzalez', 'Wilson', 'Anderson']
        
        synthetic_data = []
        for i in range(count):
            first = random.choice(first_names)
            last = random.choice(last_names)
            full_name = f"{first} {last}"
            
            synthetic_data.append({
                'author_id': f"SYNTH_{i:06d}",
                'full_name': full_name,
                'email': f"{first.lower()}.{last.lower()}@email.com",
                'affiliation': f"{random.choice(['University', 'Hospital', 'Medical Center', 'Institute'])} of {random.choice(['California', 'Texas', 'New York', 'Florida'])}"
            })
        
        return pd.DataFrame(synthetic_data)

    def transform_to_healthcare_providers(self, authors_df: pd.DataFrame) -> pd.DataFrame:
        """Transform author data into healthcare provider records"""
        print("Transforming authors to healthcare providers...")
        
        providers = []
        
        for idx, row in authors_df.iterrows():
            # Generate unique provider ID
            if 'author_id' in row and pd.notna(row['author_id']):
                provider_id = f"PROV_{str(row['author_id']).replace(' ', '_')[:20]}"
            else:
                provider_id = f"PROV_{idx:06d}"
            
            # Parse name
            full_name = row.get('full_name', '') or row.get('authors', '') or f"Provider {idx}"
            name_parts = self.parse_author_name(full_name)
            
            # Generate NPI and license
            npi_number = self.generate_npi(provider_id)
            license_state = random.choice(self.us_states)
            license_number = self.generate_license_number(license_state, provider_id)
            
            # Assign medical specialty and degree
            specialty_primary = random.choice(self.medical_specialties)
            degree = random.choice(self.degree_types)
            
            # Generate other attributes
            gender = random.choice(['Male', 'Female'])
            birth_year = random.randint(1950, 1990)
            years_practice = max(0, 2025 - birth_year - 25)  # Assuming practice starts at 25
            
            # Generate email
            email = self.generate_email(
                name_parts['first_name'], 
                name_parts['last_name']
            )
            
            provider_data = {
                'provider_id': provider_id,
                'npi_number': npi_number,
                'full_name': full_name,
                'first_name': name_parts['first_name'],
                'last_name': name_parts['last_name'],
                'middle_initial': name_parts['middle_initial'],
                'degree': degree,
                'specialty_primary': specialty_primary,
                'specialty_secondary': random.choice(self.medical_specialties) if random.random() < 0.3 else None,
                'email': email,
                'phone_number': f"({random.randint(200,999)}) {random.randint(100,999)}-{random.randint(1000,9999)}",
                'license_number': license_number,
                'license_state': license_state,
                'license_expiry_date': date.today() + timedelta(days=random.randint(30, 1095)),
                'years_in_practice': years_practice,
                'gender': gender,
                'birth_year': birth_year,
                'medical_school': f"University of {random.choice(['California', 'Texas', 'Pennsylvania', 'Michigan'])} Medical School",
                'graduation_year': birth_year + 25 + random.randint(-2, 2),
                'data_source': 'CORD19_TRANSFORMED',
                'source_confidence': round(random.uniform(0.75, 0.95), 2),
                'last_updated': datetime.now(),
                'record_status': 'ACTIVE',
                'is_golden_record': True
            }
            
            providers.append(provider_data)
        
        providers_df = pd.DataFrame(providers)
        print(f"Generated {len(providers_df)} healthcare provider records")
        return providers_df

    def generate_healthcare_facilities(self, count: int = 500) -> pd.DataFrame:
        """Generate healthcare facility records"""
        print(f"Generating {count} healthcare facility records...")
        
        facilities = []
        facility_names = [
            "General Hospital", "Medical Center", "Community Hospital", "Regional Medical Center",
            "University Hospital", "Children's Hospital", "Cancer Center", "Heart Institute",
            "Orthopedic Clinic", "Family Practice", "Urgent Care Center", "Surgery Center"
        ]
        
        cities = [
            "New York", "Los Angeles", "Chicago", "Houston", "Phoenix", "Philadelphia", 
            "San Antonio", "San Diego", "Dallas", "San Jose", "Austin", "Jacksonville"
        ]
        
        for i in range(count):
            city = random.choice(cities)
            state = random.choice(self.us_states)
            facility_base = random.choice(facility_names)
            
            facility_name = f"{city} {facility_base}"
            facility_id = f"FAC_{i:06d}"
            
            facility_data = {
                'facility_id': facility_id,
                'facility_name': facility_name,
                'facility_type': random.choice(self.facility_types),
                'organization_type': random.choice(['Non-profit', 'For-profit', 'Government']),
                'address_line1': f"{random.randint(100, 9999)} {random.choice(['Main', 'Oak', 'Pine', 'Elm'])} Street",
                'city': city,
                'state_province': state,
                'postal_code': f"{random.randint(10000, 99999)}",
                'country': 'USA',
                'phone': f"({random.randint(200,999)}) {random.randint(100,999)}-{random.randint(1000,9999)}",
                'website': f"www.{facility_name.replace(' ', '').lower()[:15]}.org",
                'bed_count': random.randint(50, 800) if 'Hospital' in facility_base else None,
                'employee_count': random.randint(100, 5000),
                'data_source': 'GENERATED',
                'source_confidence': 0.90,
                'validation_status': 'VERIFIED',
                'last_updated': datetime.now()
            }
            
            facilities.append(facility_data)
        
        facilities_df = pd.DataFrame(facilities)
        print(f"Generated {len(facilities_df)} facility records")
        return facilities_df

    def generate_affiliations(self, providers_df: pd.DataFrame, facilities_df: pd.DataFrame) -> pd.DataFrame:
        """Generate provider-facility affiliation records"""
        print("Generating provider-facility affiliations...")
        
        affiliations = []
        provider_ids = providers_df['provider_id'].tolist()
        facility_ids = facilities_df['facility_id'].tolist()
        
        position_titles = [
            'Attending Physician', 'Chief of Staff', 'Department Head', 'Senior Physician',
            'Resident', 'Fellow', 'Consulting Physician', 'Staff Physician', 'Medical Director'
        ]
        
        departments = [
            'Internal Medicine', 'Emergency Department', 'Surgery', 'Cardiology',
            'Oncology', 'Pediatrics', 'Radiology', 'Pathology', 'Administration'
        ]
        
        # Each provider gets 1-3 affiliations
        for provider_id in provider_ids:
            num_affiliations = random.choices([1, 2, 3], weights=[0.6, 0.3, 0.1])[0]
            selected_facilities = random.sample(facility_ids, min(num_affiliations, len(facility_ids)))
            
            for i, facility_id in enumerate(selected_facilities):
                start_date = date.today() - timedelta(days=random.randint(30, 1825))  # 1 month to 5 years ago
                end_date = None if random.random() < 0.8 else start_date + timedelta(days=random.randint(90, 1095))
                
                affiliation_data = {
                    'provider_id': provider_id,
                    'facility_id': facility_id,
                    'start_date': start_date,
                    'end_date': end_date,
                    'position_title': random.choice(position_titles),
                    'department': random.choice(departments),
                    'is_primary_affiliation': (i == 0),  # First affiliation is primary
                    'employment_type': random.choice(['Full-time', 'Part-time', 'Consulting']),
                    'admitting_privileges': random.random() < 0.7,
                    'data_source': 'GENERATED',
                    'confidence_score': round(random.uniform(0.8, 0.95), 2)
                }
                
                affiliations.append(affiliation_data)
        
        affiliations_df = pd.DataFrame(affiliations)
        print(f"Generated {len(affiliations_df)} affiliation records")
        return affiliations_df

    def load_to_database(self, providers_df: pd.DataFrame, facilities_df: pd.DataFrame, affiliations_df: pd.DataFrame):
        """Load all data into the database"""
        print("Loading data into database...")
        
        # Load providers
        providers_df.to_sql('healthcare_providers', self.db_connection, if_exists='append', index=False)
        print(f"Loaded {len(providers_df)} providers")
        
        # Load facilities
        facilities_df.to_sql('healthcare_facilities', self.db_connection, if_exists='append', index=False)
        print(f"Loaded {len(facilities_df)} facilities")
        
        # Load affiliations
        affiliations_df.to_sql('provider_facility_affiliations', self.db_connection, if_exists='append', index=False)
        print(f"Loaded {len(affiliations_df)} affiliations")
        
        self.db_connection.commit()
        print("All data loaded successfully!")

    def run_transformation(self, sample_size: int = 50000):
        """Execute the complete data transformation pipeline"""
        print("=== Starting Healthcare Data Transformation Pipeline ===")
        
        # Connect to database
        self.connect_database()
        
        # Load CORD-19 data
        authors_df = self.load_cord19_data(sample_size)
        
        # Transform to healthcare providers
        providers_df = self.transform_to_healthcare_providers(authors_df)
        
        # Generate facilities
        facilities_df = self.generate_healthcare_facilities(count=min(500, len(providers_df) // 10))
        
        # Generate affiliations
        affiliations_df = self.generate_affiliations(providers_df, facilities_df)
        
        # Load to database
        self.load_to_database(providers_df, facilities_df, affiliations_df)
        
        # Generate summary report
        self.generate_load_summary()
        
        print("=== Data Transformation Pipeline Complete ===")

    def generate_load_summary(self):
        """Generate a summary of the loaded data"""
        cursor = self.db_connection.cursor()
        
        # Count records
        tables = ['healthcare_providers', 'healthcare_facilities', 'provider_facility_affiliations']
        summary = {}
        
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            summary[table] = count
        
        print("\n=== DATA LOAD SUMMARY ===")
        for table, count in summary.items():
            print(f"{table}: {count:,} records")
        
        # Additional stats
        cursor.execute("SELECT COUNT(DISTINCT specialty_primary) FROM healthcare_providers")
        specialties = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(DISTINCT license_state) FROM healthcare_providers")
        states = cursor.fetchone()[0]
        
        print(f"\nDistinct medical specialties: {specialties}")
        print(f"Distinct license states: {states}")
        print("Ready for data quality analysis!")

if __name__ == "__main__":
    # Configuration
    CORD19_PATH = Path("../../../target_tables")  # Adjust path as needed
    OUTPUT_DB = Path("../../data/database/veeva_opendata.db")
    
    # Ensure output directory exists
    OUTPUT_DB.parent.mkdir(parents=True, exist_ok=True)
    
    # Run transformation
    transformer = HealthcareDataTransformer(
        cord19_path=CORD19_PATH,
        output_db_path=OUTPUT_DB
    )
    
    transformer.run_transformation(sample_size=50000)