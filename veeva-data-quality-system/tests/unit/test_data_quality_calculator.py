"""
Unit tests for DataQualityCalculator class and QualityMetrics dataclass
Tests data quality calculation algorithms and metrics
"""

import unittest
import pandas as pd
import numpy as np
from pathlib import Path
import sys
from datetime import datetime, timedelta

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from python.utils.data_quality import DataQualityCalculator, QualityMetrics


class TestQualityMetrics(unittest.TestCase):
    """Test cases for QualityMetrics dataclass"""
    
    def test_quality_metrics_creation(self):
        """Test QualityMetrics creation and attributes"""
        metrics = QualityMetrics(
            completeness=95.5,
            consistency=88.2,
            accuracy=92.1,
            timeliness=75.0,
            uniqueness=98.7,
            validity=85.3,
            overall_score=89.1
        )
        
        self.assertEqual(metrics.completeness, 95.5)
        self.assertEqual(metrics.consistency, 88.2)
        self.assertEqual(metrics.accuracy, 92.1)
        self.assertEqual(metrics.timeliness, 75.0)
        self.assertEqual(metrics.uniqueness, 98.7)
        self.assertEqual(metrics.validity, 85.3)
        self.assertEqual(metrics.overall_score, 89.1)
    
    def test_to_dict(self):
        """Test converting QualityMetrics to dictionary"""
        metrics = QualityMetrics(
            completeness=90.0,
            consistency=85.0,
            accuracy=88.0,
            timeliness=80.0,
            uniqueness=95.0,
            validity=82.0,
            overall_score=87.0
        )
        
        metrics_dict = metrics.to_dict()
        
        self.assertIsInstance(metrics_dict, dict)
        self.assertEqual(metrics_dict['completeness'], 90.0)
        self.assertEqual(metrics_dict['consistency'], 85.0)
        self.assertEqual(metrics_dict['accuracy'], 88.0)
        self.assertEqual(metrics_dict['timeliness'], 80.0)
        self.assertEqual(metrics_dict['uniqueness'], 95.0)
        self.assertEqual(metrics_dict['validity'], 82.0)
        self.assertEqual(metrics_dict['overall_score'], 87.0)
    
    def test_get_grade(self):
        """Test grade assignment based on overall score"""
        # Test grade A
        metrics_a = QualityMetrics(90, 90, 90, 90, 90, 90, 96.0)
        self.assertEqual(metrics_a.get_grade(), 'A')
        
        # Test grade B
        metrics_b = QualityMetrics(80, 80, 80, 80, 80, 80, 87.0)
        self.assertEqual(metrics_b.get_grade(), 'B')
        
        # Test grade C
        metrics_c = QualityMetrics(70, 70, 70, 70, 70, 70, 78.0)
        self.assertEqual(metrics_c.get_grade(), 'C')
        
        # Test grade D
        metrics_d = QualityMetrics(60, 60, 60, 60, 60, 60, 67.0)
        self.assertEqual(metrics_d.get_grade(), 'D')
        
        # Test grade F
        metrics_f = QualityMetrics(50, 50, 50, 50, 50, 50, 55.0)
        self.assertEqual(metrics_f.get_grade(), 'F')
        
        # Test boundary conditions
        metrics_95 = QualityMetrics(95, 95, 95, 95, 95, 95, 95.0)
        self.assertEqual(metrics_95.get_grade(), 'A')
        
        metrics_94 = QualityMetrics(94, 94, 94, 94, 94, 94, 94.9)
        self.assertEqual(metrics_94.get_grade(), 'B')


class TestDataQualityCalculator(unittest.TestCase):
    """Test cases for DataQualityCalculator class"""
    
    def setUp(self):
        """Set up test data and calculator"""
        self.calculator = DataQualityCalculator()
        
        # Create test DataFrame
        self.test_data = pd.DataFrame({
            'id': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
            'name': ['John Doe', 'Jane Smith', '', 'Bob Johnson', 'Alice Brown', 
                    'Charlie Wilson', 'Diana Davis', None, 'Eve Miller', 'Frank Jones'],
            'email': ['john@email.com', 'jane@email.com', 'invalid-email', 
                     'bob@email.com', 'alice@email.com', 'charlie@email.com',
                     'diana@email.com', 'eve@email.com', 'eve@email.com', 'frank@email.com'],
            'phone': ['555-1234', '555-2345', '555-3456', '555-4567', '555-5678',
                     'invalid', '555-7890', '555-8901', '555-9012', '555-0123'],
            'created_date': [
                '2024-01-01', '2024-01-02', '2024-01-03', '2024-01-04', '2024-01-05',
                '2024-01-06', '2024-01-07', '2024-01-08', '2024-01-09', '2024-01-10'
            ],
            'score': [85.5, 90.2, 78.8, 92.1, 87.3, 82.6, 88.9, 91.4, 86.7, 89.1]
        })
        
        # Convert date column to datetime
        self.test_data['created_date'] = pd.to_datetime(self.test_data['created_date'])
    
    def test_initialization_default(self):
        """Test DataQualityCalculator initialization with defaults"""
        calculator = DataQualityCalculator()
        
        self.assertIsNotNone(calculator.weights)
        self.assertIsNotNone(calculator.thresholds)
        
        # Check default weights
        expected_weights = {
            'completeness': 0.25,
            'consistency': 0.20,
            'accuracy': 0.25,
            'timeliness': 0.10,
            'uniqueness': 0.15,
            'validity': 0.05
        }
        self.assertEqual(calculator.weights, expected_weights)
        
        # Check weights sum to 1.0
        total_weight = sum(calculator.weights.values())
        self.assertAlmostEqual(total_weight, 1.0, places=2)
    
    def test_initialization_custom_weights(self):
        """Test DataQualityCalculator initialization with custom weights"""
        custom_weights = {
            'completeness': 0.30,
            'consistency': 0.25,
            'accuracy': 0.30,
            'timeliness': 0.05,
            'uniqueness': 0.05,
            'validity': 0.05
        }
        
        calculator = DataQualityCalculator(weights=custom_weights)
        self.assertEqual(calculator.weights, custom_weights)
    
    def test_calculate_completeness_all_columns(self):
        """Test completeness calculation for all columns"""
        completeness = self.calculator.calculate_completeness(self.test_data)
        
        # Expected: 8 missing values out of 60 total values = 86.67% completeness
        # Missing: 1 empty string + 1 None in 'name' = 2/10 = 80% for name column
        # All other columns complete = 100%
        # Overall: (10+10+10+10+10+8)/60 = 58/60 = 96.67%
        
        self.assertGreater(completeness, 90.0)
        self.assertLessEqual(completeness, 100.0)
    
    def test_calculate_completeness_specific_columns(self):
        """Test completeness calculation for specific columns"""
        required_columns = ['id', 'email']
        completeness = self.calculator.calculate_completeness(
            self.test_data, 
            required_columns=required_columns
        )
        
        # Both columns are complete, should be 100%
        self.assertEqual(completeness, 100.0)
    
    def test_calculate_completeness_empty_dataframe(self):
        """Test completeness calculation with empty DataFrame"""
        empty_df = pd.DataFrame()
        completeness = self.calculator.calculate_completeness(empty_df)
        
        # Empty DataFrame should have 0% completeness
        self.assertEqual(completeness, 0.0)
    
    def test_calculate_consistency(self):
        """Test consistency calculation"""
        consistency = self.calculator.calculate_consistency(self.test_data)
        
        # Should detect format inconsistencies in phone and email fields
        self.assertGreater(consistency, 0.0)
        self.assertLessEqual(consistency, 100.0)
    
    def test_calculate_accuracy(self):
        """Test accuracy calculation"""
        accuracy = self.calculator.calculate_accuracy(self.test_data)
        
        # Should detect invalid email and phone formats
        self.assertGreater(accuracy, 0.0)
        self.assertLessEqual(accuracy, 100.0)
    
    def test_calculate_timeliness(self):
        """Test timeliness calculation"""
        timeliness = self.calculator.calculate_timeliness(self.test_data)
        
        # Recent dates should score high on timeliness
        self.assertGreater(timeliness, 0.0)
        self.assertLessEqual(timeliness, 100.0)
    
    def test_calculate_timeliness_with_date_column(self):
        """Test timeliness calculation with specific date column"""
        timeliness = self.calculator.calculate_timeliness(
            self.test_data, 
            date_columns=['created_date']
        )
        
        self.assertGreater(timeliness, 0.0)
        self.assertLessEqual(timeliness, 100.0)
    
    def test_calculate_uniqueness(self):
        """Test uniqueness calculation"""
        uniqueness = self.calculator.calculate_uniqueness(self.test_data)
        
        # Should detect duplicate email address
        self.assertGreater(uniqueness, 90.0)  # Most values are unique
        self.assertLess(uniqueness, 100.0)    # But there's one duplicate
    
    def test_calculate_uniqueness_specific_columns(self):
        """Test uniqueness calculation for specific columns"""
        uniqueness = self.calculator.calculate_uniqueness(
            self.test_data, 
            unique_columns=['id']
        )
        
        # ID column is completely unique
        self.assertEqual(uniqueness, 100.0)
    
    def test_calculate_validity(self):
        """Test validity calculation"""
        validity = self.calculator.calculate_validity(self.test_data)
        
        # Should detect invalid email and phone formats
        self.assertGreater(validity, 0.0)
        self.assertLess(validity, 100.0)
    
    def test_calculate_overall_quality(self):
        """Test overall quality calculation"""
        metrics = self.calculator.calculate_overall_quality(self.test_data)
        
        self.assertIsInstance(metrics, QualityMetrics)
        
        # All individual metrics should be between 0 and 100
        self.assertGreaterEqual(metrics.completeness, 0.0)
        self.assertLessEqual(metrics.completeness, 100.0)
        self.assertGreaterEqual(metrics.consistency, 0.0)
        self.assertLessEqual(metrics.consistency, 100.0)
        self.assertGreaterEqual(metrics.accuracy, 0.0)
        self.assertLessEqual(metrics.accuracy, 100.0)
        self.assertGreaterEqual(metrics.timeliness, 0.0)
        self.assertLessEqual(metrics.timeliness, 100.0)
        self.assertGreaterEqual(metrics.uniqueness, 0.0)
        self.assertLessEqual(metrics.uniqueness, 100.0)
        self.assertGreaterEqual(metrics.validity, 0.0)
        self.assertLessEqual(metrics.validity, 100.0)
        
        # Overall score should be weighted average
        self.assertGreaterEqual(metrics.overall_score, 0.0)
        self.assertLessEqual(metrics.overall_score, 100.0)
    
    def test_generate_quality_report(self):
        """Test quality report generation"""
        metrics = self.calculator.calculate_overall_quality(self.test_data)
        report = self.calculator.generate_quality_report(metrics)
        
        self.assertIsInstance(report, dict)
        self.assertIn('summary', report)
        self.assertIn('dimensions', report)
        self.assertIn('recommendations', report)
        
        # Check summary content
        summary = report['summary']
        self.assertIn('overall_score', summary)
        self.assertIn('grade', summary)
        self.assertIn('total_records', summary)
        
        # Check dimensions content
        dimensions = report['dimensions']
        quality_dimensions = ['completeness', 'consistency', 'accuracy', 
                            'timeliness', 'uniqueness', 'validity']
        for dimension in quality_dimensions:
            self.assertIn(dimension, dimensions)
    
    def test_validate_email_format(self):
        """Test email format validation"""
        # Valid emails
        self.assertTrue(self.calculator._validate_email_format('test@example.com'))
        self.assertTrue(self.calculator._validate_email_format('user.name@domain.co.uk'))
        
        # Invalid emails
        self.assertFalse(self.calculator._validate_email_format('invalid-email'))
        self.assertFalse(self.calculator._validate_email_format('user@'))
        self.assertFalse(self.calculator._validate_email_format('@domain.com'))
        self.assertFalse(self.calculator._validate_email_format('user.domain.com'))
    
    def test_validate_phone_format(self):
        """Test phone format validation"""
        # Valid phones
        self.assertTrue(self.calculator._validate_phone_format('555-1234'))
        self.assertTrue(self.calculator._validate_phone_format('(555) 123-4567'))
        self.assertTrue(self.calculator._validate_phone_format('555.123.4567'))
        self.assertTrue(self.calculator._validate_phone_format('5551234567'))
        
        # Invalid phones
        self.assertFalse(self.calculator._validate_phone_format('invalid'))
        self.assertFalse(self.calculator._validate_phone_format('123'))
        self.assertFalse(self.calculator._validate_phone_format('abc-defg'))
    
    def test_detect_outliers(self):
        """Test outlier detection"""
        # Create data with clear outliers
        data_with_outliers = pd.DataFrame({
            'values': [1, 2, 3, 4, 5, 100, 6, 7, 8, 9]  # 100 is an outlier
        })
        
        outliers = self.calculator._detect_outliers(data_with_outliers['values'])
        
        self.assertIsInstance(outliers, pd.Series)
        self.assertTrue(outliers.iloc[5])  # Index 5 (value 100) should be detected as outlier
        self.assertFalse(outliers.iloc[0])  # Index 0 (value 1) should not be outlier
    
    def test_calculate_data_freshness(self):
        """Test data freshness calculation"""
        # Create DataFrame with old and recent dates
        old_date = datetime.now() - timedelta(days=100)
        recent_date = datetime.now() - timedelta(days=1)
        
        test_dates = pd.DataFrame({
            'date_col': [old_date, recent_date, datetime.now()]
        })
        
        freshness = self.calculator._calculate_data_freshness(
            test_dates, 
            ['date_col']
        )
        
        self.assertGreater(freshness, 0.0)
        self.assertLessEqual(freshness, 100.0)
    
    def test_edge_case_all_null_column(self):
        """Test handling of column with all null values"""
        df_with_nulls = pd.DataFrame({
            'all_null': [None, None, None, None],
            'some_data': [1, 2, 3, 4]
        })
        
        completeness = self.calculator.calculate_completeness(df_with_nulls)
        self.assertEqual(completeness, 50.0)  # One column complete, one empty
    
    def test_edge_case_single_row(self):
        """Test handling of single row DataFrame"""
        single_row_df = pd.DataFrame({
            'col1': ['value1'],
            'col2': [42]
        })
        
        metrics = self.calculator.calculate_overall_quality(single_row_df)
        
        self.assertIsInstance(metrics, QualityMetrics)
        self.assertGreaterEqual(metrics.overall_score, 0.0)
        self.assertLessEqual(metrics.overall_score, 100.0)
    
    def test_custom_validation_rules(self):
        """Test custom validation rules"""
        # Test with custom validation patterns
        custom_patterns = {
            'email': r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
            'phone': r'^\d{3}-\d{4}$'
        }
        
        calculator_custom = DataQualityCalculator()
        
        # Override validation patterns
        calculator_custom.validation_patterns = custom_patterns
        
        validity = calculator_custom.calculate_validity(self.test_data)
        
        self.assertGreater(validity, 0.0)
        self.assertLessEqual(validity, 100.0)
    
    def test_weights_validation(self):
        """Test validation of custom weights"""
        # Test with weights that don't sum to 1.0
        invalid_weights = {
            'completeness': 0.5,
            'consistency': 0.5,
            'accuracy': 0.5,  # Total > 1.0
            'timeliness': 0.1,
            'uniqueness': 0.1,
            'validity': 0.1
        }
        
        # Should still create calculator but log warning
        calculator = DataQualityCalculator(weights=invalid_weights)
        self.assertEqual(calculator.weights, invalid_weights)


if __name__ == '__main__':
    unittest.main()