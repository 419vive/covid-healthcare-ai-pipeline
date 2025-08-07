"""
Data quality calculation utilities
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Union, Tuple
from dataclasses import dataclass
from datetime import datetime, date
import re
import logging

logger = logging.getLogger(__name__)


@dataclass
class QualityMetrics:
    """Container for data quality metrics"""
    completeness: float
    consistency: float
    accuracy: float
    timeliness: float
    uniqueness: float
    validity: float
    overall_score: float
    
    def to_dict(self) -> Dict[str, float]:
        """Convert metrics to dictionary"""
        return {
            'completeness': self.completeness,
            'consistency': self.consistency,
            'accuracy': self.accuracy,
            'timeliness': self.timeliness,
            'uniqueness': self.uniqueness,
            'validity': self.validity,
            'overall_score': self.overall_score
        }
    
    def get_grade(self) -> str:
        """Get letter grade based on overall score"""
        if self.overall_score >= 95:
            return 'A'
        elif self.overall_score >= 85:
            return 'B'
        elif self.overall_score >= 75:
            return 'C'
        elif self.overall_score >= 65:
            return 'D'
        else:
            return 'F'


class DataQualityCalculator:
    """
    Advanced data quality calculation engine
    Implements multiple quality dimensions with configurable weights
    """
    
    def __init__(self, 
                 weights: Optional[Dict[str, float]] = None,
                 thresholds: Optional[Dict[str, float]] = None):
        """
        Initialize data quality calculator
        
        Args:
            weights: Quality dimension weights (completeness, consistency, etc.)
            thresholds: Quality thresholds for scoring
        """
        self.weights = weights or {
            'completeness': 0.25,
            'consistency': 0.20,
            'accuracy': 0.25,
            'timeliness': 0.10,
            'uniqueness': 0.15,
            'validity': 0.05
        }
        
        self.thresholds = thresholds or {
            'excellent': 95.0,
            'good': 85.0,
            'fair': 75.0,
            'poor': 65.0
        }
        
        # Validate weights sum to 1.0
        total_weight = sum(self.weights.values())
        if abs(total_weight - 1.0) > 0.01:
            logger.warning(f"Quality dimension weights sum to {total_weight:.3f}, not 1.0")
    
    def calculate_completeness(self, df: pd.DataFrame, 
                             required_columns: Optional[List[str]] = None) -> float:
        """
        Calculate data completeness score
        
        Args:
            df: DataFrame to analyze
            required_columns: List of required columns (default: all columns)
            
        Returns:
            Completeness score (0-100)
        """
        if df.empty:
            return 0.0
        
        columns_to_check = required_columns or df.columns.tolist()
        
        total_cells = len(df) * len(columns_to_check)
        if total_cells == 0:
            return 100.0
        
        # Count non-null, non-empty values
        non_empty_cells = 0
        for col in columns_to_check:
            if col in df.columns:
                # Consider null, empty string, and whitespace-only as missing
                non_empty = df[col].notna() & (df[col].astype(str).str.strip() != '')
                non_empty_cells += non_empty.sum()
        
        completeness_score = (non_empty_cells / total_cells) * 100
        return round(completeness_score, 2)
    
    def calculate_consistency(self, df: pd.DataFrame, 
                            consistency_rules: Optional[Dict[str, Any]] = None) -> float:
        """
        Calculate data consistency score based on various consistency rules
        
        Args:
            df: DataFrame to analyze
            consistency_rules: Dictionary of consistency rules to apply
            
        Returns:
            Consistency score (0-100)
        """
        if df.empty:
            return 100.0
        
        consistency_rules = consistency_rules or {}
        total_records = len(df)
        consistent_records = total_records
        
        # Rule 1: Format consistency (e.g., phone numbers, emails)
        if 'phone_format' in consistency_rules and 'phone_number' in df.columns:
            # Check phone number format consistency
            phone_pattern = r'^\d{3}-\d{3}-\d{4}|\(\d{3}\)\s\d{3}-\d{4}|\d{10}$'
            valid_phones = df['phone_number'].notna()
            if valid_phones.any():
                consistent_phones = df.loc[valid_phones, 'phone_number'].str.match(phone_pattern, na=False).sum()
                total_phones = valid_phones.sum()
                if total_phones > 0:
                    phone_consistency = consistent_phones / total_phones
                    consistent_records = int(consistent_records * phone_consistency)
        
        # Rule 2: Name format consistency
        if 'name_format' in consistency_rules and 'full_name' in df.columns:
            # Check name format patterns
            name_patterns = [
                r'^[A-Za-z\s\.\,\-\']+$',  # Letters, spaces, common punctuation
            ]
            valid_names = df['full_name'].notna()
            if valid_names.any():
                consistent_names = 0
                for pattern in name_patterns:
                    consistent_names += df.loc[valid_names, 'full_name'].str.match(pattern, na=False).sum()
                
                total_names = valid_names.sum()
                if total_names > 0:
                    name_consistency = min(consistent_names / total_names, 1.0)
                    consistent_records = int(consistent_records * name_consistency)
        
        # Rule 3: Date format consistency  
        if 'date_format' in consistency_rules:
            date_columns = [col for col in df.columns if 'date' in col.lower()]
            for date_col in date_columns:
                if date_col in df.columns:
                    valid_dates = df[date_col].notna()
                    if valid_dates.any():
                        # Check if dates are in consistent format
                        try:
                            pd.to_datetime(df.loc[valid_dates, date_col])
                            # If successful, dates are consistently parseable
                        except:
                            # Reduce consistency score for unparseable dates
                            consistent_records = int(consistent_records * 0.9)
        
        # Rule 4: Categorical value consistency
        if 'categorical_consistency' in consistency_rules:
            categorical_cols = consistency_rules['categorical_consistency']
            for col, expected_values in categorical_cols.items():
                if col in df.columns:
                    valid_values = df[col].notna()
                    if valid_values.any():
                        consistent_values = df.loc[valid_values, col].isin(expected_values).sum()
                        total_values = valid_values.sum()
                        if total_values > 0:
                            cat_consistency = consistent_values / total_values
                            consistent_records = int(consistent_records * cat_consistency)
        
        consistency_score = (consistent_records / total_records) * 100
        return round(consistency_score, 2)
    
    def calculate_accuracy(self, df: pd.DataFrame,
                         accuracy_rules: Optional[Dict[str, Any]] = None) -> float:
        """
        Calculate data accuracy score based on validation rules
        
        Args:
            df: DataFrame to analyze  
            accuracy_rules: Dictionary of accuracy validation rules
            
        Returns:
            Accuracy score (0-100)
        """
        if df.empty:
            return 100.0
        
        accuracy_rules = accuracy_rules or {}
        total_records = len(df)
        accurate_records = total_records
        
        # Rule 1: Email format validation
        if 'email' in df.columns:
            valid_emails = df['email'].notna()
            if valid_emails.any():
                email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
                accurate_emails = df.loc[valid_emails, 'email'].str.match(email_pattern, na=False).sum()
                total_emails = valid_emails.sum()
                if total_emails > 0:
                    email_accuracy = accurate_emails / total_emails
                    accurate_records = int(accurate_records * email_accuracy)
        
        # Rule 2: NPI number validation (10 digits)
        if 'npi_number' in df.columns:
            valid_npis = df['npi_number'].notna()
            if valid_npis.any():
                npi_pattern = r'^\d{10}$'
                accurate_npis = df.loc[valid_npis, 'npi_number'].str.match(npi_pattern, na=False).sum()
                total_npis = valid_npis.sum()
                if total_npis > 0:
                    npi_accuracy = accurate_npis / total_npis
                    accurate_records = int(accurate_records * npi_accuracy)
        
        # Rule 3: Date range validation
        if 'birth_year' in df.columns:
            valid_years = df['birth_year'].notna()
            if valid_years.any():
                current_year = datetime.now().year
                reasonable_years = ((df.loc[valid_years, 'birth_year'] >= 1920) & 
                                  (df.loc[valid_years, 'birth_year'] <= current_year - 18)).sum()
                total_years = valid_years.sum()
                if total_years > 0:
                    year_accuracy = reasonable_years / total_years
                    accurate_records = int(accurate_records * year_accuracy)
        
        # Rule 4: State code validation
        if 'license_state' in df.columns:
            valid_states = df['license_state'].notna()
            if valid_states.any():
                # US state codes (2 characters)
                state_pattern = r'^[A-Z]{2}$'
                accurate_states = df.loc[valid_states, 'license_state'].str.match(state_pattern, na=False).sum()
                total_states = valid_states.sum()
                if total_states > 0:
                    state_accuracy = accurate_states / total_states
                    accurate_records = int(accurate_records * state_accuracy)
        
        accuracy_score = (accurate_records / total_records) * 100
        return round(accuracy_score, 2)
    
    def calculate_timeliness(self, df: pd.DataFrame,
                           timeliness_column: str = 'last_updated',
                           max_age_days: int = 90) -> float:
        """
        Calculate data timeliness score
        
        Args:
            df: DataFrame to analyze
            timeliness_column: Column containing timestamps
            max_age_days: Maximum acceptable age in days
            
        Returns:
            Timeliness score (0-100)
        """
        if df.empty or timeliness_column not in df.columns:
            return 100.0
        
        valid_timestamps = df[timeliness_column].notna()
        if not valid_timestamps.any():
            return 50.0  # Default score if no timestamps
        
        try:
            # Convert to datetime if needed
            timestamps = pd.to_datetime(df.loc[valid_timestamps, timeliness_column])
            current_time = datetime.now()
            
            # Calculate age in days
            ages_days = (current_time - timestamps).dt.days
            
            # Score based on age distribution
            fresh_records = (ages_days <= max_age_days).sum()
            total_records_with_timestamp = len(timestamps)
            
            if total_records_with_timestamp == 0:
                return 100.0
            
            # Linear scoring: 100% for fresh, declining with age
            avg_age = ages_days.mean()
            if avg_age <= max_age_days:
                timeliness_score = 100.0 - (avg_age / max_age_days) * 20  # Max 20 point deduction
            else:
                timeliness_score = max(0, 100.0 - (avg_age / max_age_days) * 50)
            
            return round(timeliness_score, 2)
            
        except Exception as e:
            logger.warning(f"Error calculating timeliness: {e}")
            return 50.0
    
    def calculate_uniqueness(self, df: pd.DataFrame,
                           key_columns: Optional[List[str]] = None) -> float:
        """
        Calculate data uniqueness score
        
        Args:
            df: DataFrame to analyze
            key_columns: Columns that should be unique (default: all columns)
            
        Returns:
            Uniqueness score (0-100)
        """
        if df.empty:
            return 100.0
        
        key_columns = key_columns or ['provider_id', 'npi_number', 'email']
        
        total_records = len(df)
        uniqueness_scores = []
        
        for col in key_columns:
            if col in df.columns:
                non_null_values = df[col].notna()
                if non_null_values.any():
                    unique_values = df.loc[non_null_values, col].nunique()
                    total_values = non_null_values.sum()
                    
                    if total_values > 0:
                        col_uniqueness = (unique_values / total_values) * 100
                        uniqueness_scores.append(col_uniqueness)
        
        if uniqueness_scores:
            overall_uniqueness = np.mean(uniqueness_scores)
        else:
            # Check overall record uniqueness
            unique_records = len(df.drop_duplicates())
            overall_uniqueness = (unique_records / total_records) * 100
        
        return round(overall_uniqueness, 2)
    
    def calculate_validity(self, df: pd.DataFrame,
                         validity_rules: Optional[Dict[str, Any]] = None) -> float:
        """
        Calculate data validity score based on business rules
        
        Args:
            df: DataFrame to analyze
            validity_rules: Dictionary of business validity rules
            
        Returns:
            Validity score (0-100)
        """
        if df.empty:
            return 100.0
        
        validity_rules = validity_rules or {}
        total_records = len(df)
        valid_records = total_records
        
        # Rule 1: Required field combinations
        if 'required_combinations' in validity_rules:
            for combo in validity_rules['required_combinations']:
                if all(col in df.columns for col in combo):
                    # All fields in combination must be present
                    valid_combo = df[combo].notna().all(axis=1).sum()
                    combo_validity = valid_combo / total_records
                    valid_records = int(valid_records * combo_validity)
        
        # Rule 2: Value ranges
        if 'value_ranges' in validity_rules:
            for col, (min_val, max_val) in validity_rules['value_ranges'].items():
                if col in df.columns:
                    valid_range = df[col].notna()
                    if valid_range.any():
                        in_range = ((df.loc[valid_range, col] >= min_val) & 
                                  (df.loc[valid_range, col] <= max_val)).sum()
                        total_values = valid_range.sum()
                        if total_values > 0:
                            range_validity = in_range / total_values
                            valid_records = int(valid_records * range_validity)
        
        # Rule 3: Cross-field validation
        if 'cross_field_rules' in validity_rules:
            # Example: graduation_year should be after birth_year + 22
            if ('birth_year' in df.columns and 'graduation_year' in df.columns):
                both_present = df[['birth_year', 'graduation_year']].notna().all(axis=1)
                if both_present.any():
                    valid_graduation = ((df.loc[both_present, 'graduation_year'] - 
                                       df.loc[both_present, 'birth_year']) >= 22).sum()
                    total_graduates = both_present.sum()
                    if total_graduates > 0:
                        graduation_validity = valid_graduation / total_graduates
                        valid_records = int(valid_records * graduation_validity)
        
        validity_score = (valid_records / total_records) * 100
        return round(validity_score, 2)
    
    def calculate_overall_quality(self, df: pd.DataFrame,
                                **kwargs) -> QualityMetrics:
        """
        Calculate comprehensive data quality metrics
        
        Args:
            df: DataFrame to analyze
            **kwargs: Additional parameters for individual quality calculations
            
        Returns:
            QualityMetrics object with all quality scores
        """
        logger.info(f"Calculating quality metrics for {len(df)} records")
        
        # Calculate individual quality dimensions
        completeness = self.calculate_completeness(df, kwargs.get('required_columns'))
        consistency = self.calculate_consistency(df, kwargs.get('consistency_rules'))
        accuracy = self.calculate_accuracy(df, kwargs.get('accuracy_rules'))
        timeliness = self.calculate_timeliness(df, 
                                             kwargs.get('timeliness_column', 'last_updated'),
                                             kwargs.get('max_age_days', 90))
        uniqueness = self.calculate_uniqueness(df, kwargs.get('key_columns'))
        validity = self.calculate_validity(df, kwargs.get('validity_rules'))
        
        # Calculate weighted overall score
        overall_score = (
            completeness * self.weights['completeness'] +
            consistency * self.weights['consistency'] +
            accuracy * self.weights['accuracy'] +
            timeliness * self.weights['timeliness'] +
            uniqueness * self.weights['uniqueness'] +
            validity * self.weights['validity']
        )
        
        metrics = QualityMetrics(
            completeness=completeness,
            consistency=consistency,
            accuracy=accuracy,
            timeliness=timeliness,
            uniqueness=uniqueness,
            validity=validity,
            overall_score=round(overall_score, 2)
        )
        
        logger.info(f"Quality assessment complete: {metrics.overall_score}% overall score ({metrics.get_grade()} grade)")
        
        return metrics
    
    def generate_quality_report(self, metrics: QualityMetrics) -> Dict[str, Any]:
        """
        Generate comprehensive quality report
        
        Args:
            metrics: QualityMetrics object
            
        Returns:
            Dictionary containing detailed quality report
        """
        report = {
            'summary': {
                'overall_score': metrics.overall_score,
                'grade': metrics.get_grade(),
                'assessment_date': datetime.now().isoformat(),
                'meets_threshold': metrics.overall_score >= self.thresholds['good']
            },
            'dimensions': metrics.to_dict(),
            'recommendations': self._generate_recommendations(metrics),
            'weights_used': self.weights.copy(),
            'thresholds_used': self.thresholds.copy()
        }
        
        return report
    
    def _generate_recommendations(self, metrics: QualityMetrics) -> List[Dict[str, str]]:
        """Generate improvement recommendations based on quality scores"""
        recommendations = []
        
        if metrics.completeness < 90:
            recommendations.append({
                'dimension': 'completeness',
                'priority': 'HIGH',
                'recommendation': 'Focus on data collection processes to reduce missing values',
                'action': 'Implement required field validation and data entry training'
            })
        
        if metrics.consistency < 85:
            recommendations.append({
                'dimension': 'consistency',
                'priority': 'MEDIUM',
                'recommendation': 'Standardize data formats and validation rules',
                'action': 'Implement data transformation and normalization procedures'
            })
        
        if metrics.accuracy < 90:
            recommendations.append({
                'dimension': 'accuracy',
                'priority': 'HIGH',
                'recommendation': 'Strengthen data validation and verification processes',
                'action': 'Implement real-time validation rules and periodic data audits'
            })
        
        if metrics.timeliness < 80:
            recommendations.append({
                'dimension': 'timeliness',
                'priority': 'MEDIUM',
                'recommendation': 'Improve data refresh frequency and update processes',
                'action': 'Implement automated data refresh schedules and monitoring'
            })
        
        if metrics.uniqueness < 95:
            recommendations.append({
                'dimension': 'uniqueness',
                'priority': 'HIGH',
                'recommendation': 'Address duplicate records and improve deduplication',
                'action': 'Implement advanced matching algorithms and duplicate resolution workflows'
            })
        
        if metrics.validity < 85:
            recommendations.append({
                'dimension': 'validity',
                'priority': 'MEDIUM',
                'recommendation': 'Enhance business rule validation and cross-field checks',
                'action': 'Review and update business rules, implement cross-validation logic'
            })
        
        return recommendations