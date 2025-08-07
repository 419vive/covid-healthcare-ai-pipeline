#!/usr/bin/env python3
"""
COVID-19 Research Data Analysis Pipeline

A comprehensive analytics framework for analyzing COVID-19 research findings
across multiple categories including population management, risk factors,
patient descriptions, therapeutics, diagnostics, and more.

Author: Data Analytics Team
Date: August 2025
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import warnings
import os
from pathlib import Path
import re
from collections import Counter, defaultdict
from datetime import datetime
import json

# Suppress warnings for cleaner output
warnings.filterwarnings('ignore')

class COVID19ResearchAnalyzer:
    """
    Main class for analyzing COVID-19 research data across multiple categories
    """
    
    def __init__(self, base_path):
        """
        Initialize the analyzer with base data path
        
        Args:
            base_path (str): Path to the target_tables directory
        """
        self.base_path = Path(base_path)
        self.categories = {
            '1_population': 'Population Management',
            '2_relevant_factors': 'Relevant Factors',
            '3_patient_descriptions': 'Patient Descriptions',
            '4_models_and_open_questions': 'Models and Open Questions',
            '5_materials': 'Materials Research',
            '6_diagnostics': 'Diagnostics',
            '7_therapeutics_interventions_and_clinical_studies': 'Therapeutics & Clinical Studies',
            '8_risk_factors': 'Risk Factors'
        }
        
        # Initialize data containers
        self.category_data = {}
        self.summary_stats = {}
        self.insights = {}
        
        # Load column definitions
        self._load_column_definitions()
    
    def _load_column_definitions(self):
        """Load column definitions from the metadata files"""
        try:
            col_def_path = self.base_path / "0_table_formats_and_column_definitions" / "column_definitions_extended.csv"
            self.column_definitions = pd.read_csv(col_def_path)
            print("✓ Column definitions loaded successfully")
        except Exception as e:
            print(f"⚠ Warning: Could not load column definitions: {e}")
            self.column_definitions = None
    
    def load_all_data(self):
        """
        Load all CSV files from each category directory
        """
        print("📊 Loading COVID-19 research data...")
        
        for category_folder, category_name in self.categories.items():
            category_path = self.base_path / category_folder
            
            if not category_path.exists():
                print(f"⚠ Warning: Category folder {category_folder} not found")
                continue
            
            print(f"📁 Loading {category_name}...")
            category_data = {}
            
            # Get all CSV files in the category
            csv_files = list(category_path.glob("*.csv"))
            
            for csv_file in csv_files:
                try:
                    df = pd.read_csv(csv_file, encoding='utf-8')
                    
                    # Clean up column names
                    df.columns = df.columns.str.strip()
                    
                    # Store with filename as key
                    table_name = csv_file.stem
                    category_data[table_name] = df
                    
                    print(f"  ✓ {table_name}: {len(df)} records")
                    
                except Exception as e:
                    print(f"  ✗ Error loading {csv_file}: {e}")
            
            self.category_data[category_folder] = category_data
        
        print(f"✅ Data loading complete. Loaded {len(self.category_data)} categories")
    
    def generate_category_summary(self, category_folder):
        """
        Generate summary statistics for a specific category
        
        Args:
            category_folder (str): Category folder name
        
        Returns:
            dict: Summary statistics for the category
        """
        if category_folder not in self.category_data:
            return None
        
        category_data = self.category_data[category_folder]
        category_name = self.categories[category_folder]
        
        summary = {
            'category_name': category_name,
            'total_tables': len(category_data),
            'total_records': sum(len(df) for df in category_data.values()),
            'table_details': {},
            'date_range': {'earliest': None, 'latest': None},
            'study_types': Counter(),
            'journals': Counter(),
            'key_insights': []
        }
        
        all_dates = []
        
        for table_name, df in category_data.items():
            table_info = {
                'records': len(df),
                'columns': list(df.columns),
                'date_range': None,
                'key_metrics': {}
            }
            
            # Analyze date information
            if 'Date' in df.columns:
                try:
                    dates = pd.to_datetime(df['Date'], errors='coerce')
                    valid_dates = dates.dropna()
                    if not valid_dates.empty:
                        table_info['date_range'] = {
                            'earliest': valid_dates.min(),
                            'latest': valid_dates.max()
                        }
                        all_dates.extend(valid_dates.tolist())
                except:
                    pass
            
            # Analyze study types
            if 'Study Type' in df.columns:
                summary['study_types'].update(df['Study Type'].value_counts().to_dict())
            
            # Analyze journals
            if 'Journal' in df.columns:
                summary['journals'].update(df['Journal'].value_counts().head(10).to_dict())
            
            # Category-specific analysis
            if category_folder == '8_risk_factors':
                self._analyze_risk_factors(df, table_info, table_name)
            elif category_folder == '3_patient_descriptions':
                self._analyze_patient_descriptions(df, table_info)
            elif category_folder == '2_relevant_factors':
                self._analyze_relevant_factors(df, table_info)
            elif category_folder == '6_diagnostics':
                self._analyze_diagnostics(df, table_info)
            elif category_folder == '7_therapeutics_interventions_and_clinical_studies':
                self._analyze_therapeutics(df, table_info)
            
            summary['table_details'][table_name] = table_info
        
        # Overall date range
        if all_dates:
            summary['date_range'] = {
                'earliest': min(all_dates),
                'latest': max(all_dates)
            }
        
        return summary
    
    def _analyze_risk_factors(self, df, table_info, risk_factor_name):
        """Analyze risk factor specific metrics"""
        metrics = {}
        
        # Odds ratios and hazard ratios
        if 'Severe' in df.columns:
            severe_values = df['Severe'].dropna()
            if not severe_values.empty:
                metrics['severe_outcomes'] = len(severe_values)
        
        if 'Fatality' in df.columns:
            fatality_values = df['Fatality'].dropna()
            if not fatality_values.empty:
                metrics['fatality_outcomes'] = len(fatality_values)
        
        # Sample sizes
        if 'Sample Size' in df.columns:
            sample_sizes = df['Sample Size'].dropna()
            if not sample_sizes.empty:
                # Extract numeric values from sample size strings
                numeric_samples = []
                for sample in sample_sizes:
                    try:
                        # Extract numbers from strings like "patients: 1317"
                        numbers = re.findall(r'\d+', str(sample))
                        if numbers:
                            numeric_samples.extend([int(n) for n in numbers])
                    except:
                        pass
                
                if numeric_samples:
                    metrics['sample_size_stats'] = {
                        'total_studies': len(sample_sizes),
                        'total_patients': sum(numeric_samples),
                        'avg_sample_size': np.mean(numeric_samples),
                        'median_sample_size': np.median(numeric_samples)
                    }
        
        table_info['key_metrics'] = metrics
    
    def _analyze_patient_descriptions(self, df, table_info):
        """Analyze patient description specific metrics"""
        metrics = {}
        
        # Sample sizes
        if 'Sample Size' in df.columns:
            sample_data = df['Sample Size'].dropna()
            if not sample_data.empty:
                metrics['total_studies'] = len(sample_data)
        
        # Age analysis
        if 'Age' in df.columns:
            age_data = df['Age'].dropna()
            if not age_data.empty:
                metrics['studies_with_age'] = len(age_data)
        
        # Asymptomatic rates (if applicable)
        if 'Asymptomatic' in df.columns:
            asymptomatic_data = df['Asymptomatic'].dropna()
            if not asymptomatic_data.empty:
                # Extract percentages
                percentages = []
                for value in asymptomatic_data:
                    try:
                        # Extract percentage values
                        pct = re.findall(r'(\d+(?:\.\d+)?)%', str(value))
                        if pct:
                            percentages.extend([float(p) for p in pct])
                    except:
                        pass
                
                if percentages:
                    metrics['asymptomatic_rates'] = {
                        'mean': np.mean(percentages),
                        'median': np.median(percentages),
                        'range': [min(percentages), max(percentages)],
                        'studies': len(percentages)
                    }
        
        table_info['key_metrics'] = metrics
    
    def _analyze_relevant_factors(self, df, table_info):
        """Analyze relevant factors metrics"""
        metrics = {}
        
        # Influential factors
        if 'Influential' in df.columns:
            influential_data = df['Influential'].value_counts()
            metrics['influential_factors'] = influential_data.to_dict()
        
        # Factor types
        if 'Factors' in df.columns:
            factors = df['Factors'].dropna()
            metrics['unique_factors'] = len(factors.unique())
            metrics['total_factor_studies'] = len(factors)
        
        table_info['key_metrics'] = metrics
    
    def _analyze_diagnostics(self, df, table_info):
        """Analyze diagnostics specific metrics"""
        metrics = {}
        
        # Detection methods
        if 'Detection Method' in df.columns:
            methods = df['Detection Method'].dropna()
            metrics['detection_methods'] = methods.value_counts().head(10).to_dict()
        
        # FDA approval status
        if 'FDA approval' in df.columns:
            fda_status = df['FDA approval'].value_counts()
            metrics['fda_approval_status'] = fda_status.to_dict()
        
        # Test accuracy metrics
        if 'Measure of Testing Accuracy' in df.columns:
            accuracy_data = df['Measure of Testing Accuracy'].dropna()
            metrics['studies_with_accuracy'] = len(accuracy_data)
        
        table_info['key_metrics'] = metrics
    
    def _analyze_therapeutics(self, df, table_info):
        """Analyze therapeutics specific metrics"""
        metrics = {}
        
        # Clinical improvement rates
        if 'Clinical Improvement (Y/N)' in df.columns:
            improvement = df['Clinical Improvement (Y/N)'].value_counts()
            metrics['clinical_improvement'] = improvement.to_dict()
        
        # Therapeutic methods
        if 'Therapeutic method(s) utilized/assessed' in df.columns:
            methods = df['Therapeutic method(s) utilized/assessed'].dropna()
            metrics['therapeutic_methods'] = len(methods.unique())
        
        # Severity analysis
        if 'Severity of Disease' in df.columns:
            severity = df['Severity of Disease'].value_counts()
            metrics['severity_distribution'] = severity.to_dict()
        
        table_info['key_metrics'] = metrics
    
    def generate_comprehensive_report(self):
        """
        Generate a comprehensive analysis report across all categories
        """
        print("📋 Generating comprehensive research analysis report...")
        
        # Generate summaries for each category
        for category_folder in self.categories.keys():
            self.summary_stats[category_folder] = self.generate_category_summary(category_folder)
        
        # Create comprehensive insights
        self._generate_cross_category_insights()
        
        # Generate visualizations
        self._create_summary_visualizations()
        
        print("✅ Comprehensive report generation complete")
    
    def _generate_cross_category_insights(self):
        """Generate insights across categories"""
        insights = {
            'research_timeline': {},
            'study_type_distribution': Counter(),
            'journal_impact': Counter(),
            'sample_size_analysis': {},
            'key_findings': []
        }
        
        all_dates = []
        total_studies = 0
        total_patients = 0
        
        for category_folder, summary in self.summary_stats.items():
            if not summary:
                continue
            
            total_studies += summary['total_tables']
            
            # Aggregate study types
            insights['study_type_distribution'].update(summary['study_types'])
            
            # Aggregate journals
            insights['journal_impact'].update(summary['journals'])
            
            # Collect dates
            if summary['date_range']['earliest']:
                all_dates.append(summary['date_range']['earliest'])
                all_dates.append(summary['date_range']['latest'])
        
        # Timeline analysis
        if all_dates:
            insights['research_timeline'] = {
                'earliest_study': min(all_dates),
                'latest_study': max(all_dates),
                'time_span_days': (max(all_dates) - min(all_dates)).days
            }
        
        insights['total_studies'] = total_studies
        self.insights = insights
    
    def _create_summary_visualizations(self):
        """Create summary visualizations"""
        
        # Set style
        plt.style.use('default')
        sns.set_palette("husl")
        
        # Create figure with subplots
        fig = plt.figure(figsize=(20, 15))
        
        # 1. Studies by Category
        ax1 = plt.subplot(2, 3, 1)
        categories = []
        study_counts = []
        
        for category_folder, summary in self.summary_stats.items():
            if summary:
                categories.append(self.categories[category_folder][:20] + '...' if len(self.categories[category_folder]) > 20 else self.categories[category_folder])
                study_counts.append(summary['total_tables'])
        
        bars = ax1.barh(categories, study_counts, color=plt.cm.Set3(range(len(categories))))
        ax1.set_xlabel('Number of Research Tables')
        ax1.set_title('Research Tables by Category', fontweight='bold')
        
        # Add value labels on bars
        for i, bar in enumerate(bars):
            width = bar.get_width()
            ax1.text(width + 0.1, bar.get_y() + bar.get_height()/2, 
                    f'{int(width)}', ha='left', va='center')
        
        # 2. Total Records by Category
        ax2 = plt.subplot(2, 3, 2)
        record_counts = []
        
        for category_folder, summary in self.summary_stats.items():
            if summary:
                record_counts.append(summary['total_records'])
        
        bars2 = ax2.barh(categories, record_counts, color=plt.cm.Pastel1(range(len(categories))))
        ax2.set_xlabel('Total Research Records')
        ax2.set_title('Research Records by Category', fontweight='bold')
        
        for i, bar in enumerate(bars2):
            width = bar.get_width()
            ax2.text(width + max(record_counts)*0.01, bar.get_y() + bar.get_height()/2, 
                    f'{int(width)}', ha='left', va='center')
        
        # 3. Study Type Distribution
        ax3 = plt.subplot(2, 3, 3)
        if self.insights['study_type_distribution']:
            study_types = list(self.insights['study_type_distribution'].keys())[:10]
            counts = [self.insights['study_type_distribution'][st] for st in study_types]
            
            ax3.pie(counts, labels=study_types, autopct='%1.1f%%', startangle=90)
            ax3.set_title('Study Type Distribution (Top 10)', fontweight='bold')
        
        # 4. Top Journals
        ax4 = plt.subplot(2, 3, 4)
        if self.insights['journal_impact']:
            top_journals = list(self.insights['journal_impact'].most_common(10))
            journal_names = [j[0][:30] + '...' if len(j[0]) > 30 else j[0] for j in top_journals]
            journal_counts = [j[1] for j in top_journals]
            
            bars3 = ax4.barh(journal_names, journal_counts, color=plt.cm.viridis(np.linspace(0, 1, len(journal_names))))
            ax4.set_xlabel('Number of Studies')
            ax4.set_title('Top 10 Publishing Journals', fontweight='bold')
            
            for i, bar in enumerate(bars3):
                width = bar.get_width()
                ax4.text(width + 0.1, bar.get_y() + bar.get_height()/2, 
                        f'{int(width)}', ha='left', va='center', fontsize=8)
        
        # 5. Research Timeline
        ax5 = plt.subplot(2, 3, 5)
        
        # Collect monthly publication data
        monthly_data = defaultdict(int)
        
        for category_folder, summary in self.summary_stats.items():
            if not summary or not summary['date_range']['earliest']:
                continue
                
            category_data = self.category_data.get(category_folder, {})
            for table_name, df in category_data.items():
                if 'Date' in df.columns:
                    try:
                        dates = pd.to_datetime(df['Date'], errors='coerce')
                        for date in dates.dropna():
                            month_key = date.strftime('%Y-%m')
                            monthly_data[month_key] += 1
                    except:
                        pass
        
        if monthly_data:
            months = sorted(monthly_data.keys())[-12:]  # Last 12 months with data
            counts = [monthly_data[month] for month in months]
            
            ax5.plot(months, counts, marker='o', linewidth=2, markersize=6)
            ax5.set_xlabel('Month')
            ax5.set_ylabel('Number of Studies Published')
            ax5.set_title('Research Publication Timeline', fontweight='bold')
            ax5.tick_params(axis='x', rotation=45)
        
        # 6. Category Insights Summary
        ax6 = plt.subplot(2, 3, 6)
        ax6.axis('off')
        
        # Create summary text
        summary_text = f"""
KEY RESEARCH INSIGHTS

Total Categories Analyzed: {len([s for s in self.summary_stats.values() if s])}
Total Research Tables: {sum(s['total_tables'] for s in self.summary_stats.values() if s)}
Total Research Records: {sum(s['total_records'] for s in self.summary_stats.values() if s)}

Most Active Research Area:
{max(self.categories.values(), key=lambda x: self.summary_stats.get([k for k, v in self.categories.items() if v == x][0], {'total_records': 0})['total_records'])}

Top Study Type:
{self.insights['study_type_distribution'].most_common(1)[0][0] if self.insights['study_type_distribution'] else 'N/A'}
({self.insights['study_type_distribution'].most_common(1)[0][1] if self.insights['study_type_distribution'] else 0} studies)

Research Time Span:
{self.insights.get('research_timeline', {}).get('time_span_days', 'N/A')} days
"""
        
        ax6.text(0.05, 0.95, summary_text, transform=ax6.transAxes, fontsize=10,
                verticalalignment='top', fontfamily='monospace',
                bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.8))
        
        plt.tight_layout()
        plt.savefig('/Users/jerrylaivivemachi/DS PROJECT/project5/covid19_research_summary.png', 
                    dpi=300, bbox_inches='tight')
        plt.show()
        
        print("📊 Summary visualizations saved to covid19_research_summary.png")
    
    def create_risk_factor_analysis(self):
        """Create detailed risk factor analysis"""
        if '8_risk_factors' not in self.category_data:
            print("⚠ Risk factors data not available")
            return
        
        print("🎯 Creating detailed risk factor analysis...")
        
        risk_factors_data = self.category_data['8_risk_factors']
        
        # Combine all risk factor data
        all_risk_data = []
        for risk_factor_name, df in risk_factors_data.items():
            df_copy = df.copy()
            df_copy['Risk_Factor'] = risk_factor_name.replace('_', ' ').title()
            all_risk_data.append(df_copy)
        
        combined_rf_data = pd.concat(all_risk_data, ignore_index=True)
        
        # Create risk factor visualization
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        
        # 1. Risk factors by study count
        rf_counts = combined_rf_data['Risk_Factor'].value_counts().head(15)
        
        axes[0, 0].barh(rf_counts.index, rf_counts.values, color=plt.cm.viridis(np.linspace(0, 1, len(rf_counts))))
        axes[0, 0].set_xlabel('Number of Studies')
        axes[0, 0].set_title('Risk Factors by Study Count (Top 15)', fontweight='bold')
        
        # 2. Significant vs Non-significant findings
        if 'Severe Significant' in combined_rf_data.columns:
            sig_counts = combined_rf_data['Severe Significant'].value_counts()
            axes[0, 1].pie(sig_counts.values, labels=sig_counts.index, autopct='%1.1f%%')
            axes[0, 1].set_title('Severe Outcome Significance Distribution', fontweight='bold')
        
        # 3. Study types in risk factor research
        if 'Study Type' in combined_rf_data.columns:
            study_types = combined_rf_data['Study Type'].value_counts().head(8)
            axes[1, 0].bar(range(len(study_types)), study_types.values, 
                          color=plt.cm.Set3(range(len(study_types))))
            axes[1, 0].set_xticks(range(len(study_types)))
            axes[1, 0].set_xticklabels(study_types.index, rotation=45, ha='right')
            axes[1, 0].set_ylabel('Number of Studies')
            axes[1, 0].set_title('Study Types in Risk Factor Research', fontweight='bold')
        
        # 4. Sample size distribution
        axes[1, 1].axis('off')
        
        # Extract sample sizes for analysis
        sample_size_data = []
        if 'Sample Size' in combined_rf_data.columns:
            for sample in combined_rf_data['Sample Size'].dropna():
                try:
                    numbers = re.findall(r'patients:\s*(\d+)', str(sample))
                    if numbers:
                        sample_size_data.extend([int(n) for n in numbers])
                except:
                    pass
        
        if sample_size_data:
            sample_stats = f"""
RISK FACTOR RESEARCH SAMPLE STATISTICS

Total Studies with Sample Data: {len(sample_size_data)}
Total Patients Across Studies: {sum(sample_size_data):,}

Sample Size Distribution:
• Mean: {np.mean(sample_size_data):.0f} patients
• Median: {np.median(sample_size_data):.0f} patients  
• Range: {min(sample_size_data):,} - {max(sample_size_data):,} patients

Largest Studies:
"""
            
            # Add top 5 largest studies
            largest_samples = sorted(sample_size_data, reverse=True)[:5]
            for i, size in enumerate(largest_samples, 1):
                sample_stats += f"• #{i}: {size:,} patients\n"
            
            axes[1, 1].text(0.05, 0.95, sample_stats, transform=axes[1, 1].transAxes,
                           fontsize=10, verticalalignment='top', fontfamily='monospace',
                           bbox=dict(boxstyle='round', facecolor='lightgreen', alpha=0.8))
        
        plt.tight_layout()
        plt.savefig('/Users/jerrylaivivemachi/DS PROJECT/project5/risk_factors_analysis.png', 
                    dpi=300, bbox_inches='tight')
        plt.show()
        
        print("📊 Risk factor analysis saved to risk_factors_analysis.png")
    
    def create_patient_outcomes_dashboard(self):
        """Create patient outcomes dashboard"""
        
        # Combine relevant categories for patient outcomes
        relevant_categories = ['3_patient_descriptions', '7_therapeutics_interventions_and_clinical_studies', '8_risk_factors']
        
        print("🏥 Creating patient outcomes dashboard...")
        
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=('Asymptomatic Rates by Study', 'Therapeutic Effectiveness', 
                          'Sample Size Distribution', 'Study Timeline'),
            specs=[[{"type": "bar"}, {"type": "pie"}],
                   [{"type": "histogram"}, {"type": "scatter"}]]
        )
        
        # 1. Asymptomatic rates (if available)
        if '3_patient_descriptions' in self.category_data:
            patient_data = self.category_data['3_patient_descriptions']
            
            # Look for asymptomatic data
            asymptomatic_file = None
            for filename, df in patient_data.items():
                if 'asymptomatic' in filename.lower():
                    asymptomatic_file = df
                    break
            
            if asymptomatic_file is not None and 'Asymptomatic' in asymptomatic_file.columns:
                # Extract asymptomatic percentages
                async_rates = []
                study_names = []
                
                for idx, row in asymptomatic_file.iterrows():
                    if pd.notna(row['Asymptomatic']):
                        try:
                            # Extract percentage
                            pct_match = re.search(r'(\d+(?:\.\d+)?)%', str(row['Asymptomatic']))
                            if pct_match:
                                async_rates.append(float(pct_match.group(1)))
                                study_names.append(f"Study {idx+1}")
                        except:
                            pass
                
                if async_rates:
                    fig.add_trace(
                        go.Bar(x=study_names[:15], y=async_rates[:15], 
                               name="Asymptomatic Rate (%)",
                               marker_color='lightblue'),
                        row=1, col=1
                    )
        
        # 2. Therapeutic effectiveness
        if '7_therapeutics_interventions_and_clinical_studies' in self.category_data:
            therapeutic_data = self.category_data['7_therapeutics_interventions_and_clinical_studies']
            
            improvement_counts = Counter()
            for filename, df in therapeutic_data.items():
                if 'Clinical Improvement (Y/N)' in df.columns:
                    improvement_counts.update(df['Clinical Improvement (Y/N)'].value_counts().to_dict())
            
            if improvement_counts:
                fig.add_trace(
                    go.Pie(labels=list(improvement_counts.keys()), 
                           values=list(improvement_counts.values()),
                           name="Clinical Improvement"),
                    row=1, col=2
                )
        
        # 3. Sample size distribution across all studies
        all_sample_sizes = []
        for category_folder in relevant_categories:
            if category_folder in self.category_data:
                for filename, df in self.category_data[category_folder].items():
                    if 'Sample Size' in df.columns:
                        for sample in df['Sample Size'].dropna():
                            try:
                                numbers = re.findall(r'(\d+)', str(sample))
                                if numbers:
                                    all_sample_sizes.extend([int(n) for n in numbers if int(n) < 10000])  # Filter outliers
                            except:
                                pass
        
        if all_sample_sizes:
            fig.add_trace(
                go.Histogram(x=all_sample_sizes, nbinsx=30, name="Sample Sizes",
                            marker_color='lightcoral'),
                row=2, col=1
            )
        
        # 4. Study timeline
        all_dates = []
        study_counts_by_month = defaultdict(int)
        
        for category_folder in relevant_categories:
            if category_folder in self.category_data:
                for filename, df in self.category_data[category_folder].items():
                    if 'Date' in df.columns:
                        try:
                            dates = pd.to_datetime(df['Date'], errors='coerce')
                            for date in dates.dropna():
                                month_key = date.strftime('%Y-%m')
                                study_counts_by_month[month_key] += 1
                        except:
                            pass
        
        if study_counts_by_month:
            months = sorted(study_counts_by_month.keys())
            counts = [study_counts_by_month[month] for month in months]
            
            fig.add_trace(
                go.Scatter(x=months, y=counts, mode='lines+markers',
                          name="Studies per Month", line=dict(color='green')),
                row=2, col=2
            )
        
        fig.update_layout(height=800, showlegend=True, 
                         title_text="COVID-19 Patient Outcomes Dashboard")
        
        fig.write_html('/Users/jerrylaivivemachi/DS PROJECT/project5/patient_outcomes_dashboard.html')
        fig.show()
        
        print("📊 Patient outcomes dashboard saved to patient_outcomes_dashboard.html")
    
    def export_summary_report(self):
        """Export detailed summary report to JSON and text files"""
        
        print("📤 Exporting comprehensive summary report...")
        
        # Prepare comprehensive report data
        report_data = {
            'analysis_metadata': {
                'analysis_date': datetime.now().isoformat(),
                'total_categories': len(self.categories),
                'categories_analyzed': len([s for s in self.summary_stats.values() if s])
            },
            'category_summaries': self.summary_stats,
            'cross_category_insights': self.insights,
            'key_findings': []
        }
        
        # Generate key findings
        key_findings = []
        
        # Finding 1: Most researched area
        if self.summary_stats:
            max_records_category = max(
                [(k, v) for k, v in self.summary_stats.items() if v],
                key=lambda x: x[1]['total_records']
            )
            key_findings.append({
                'finding': 'Most Researched Area',
                'category': self.categories[max_records_category[0]],
                'total_records': max_records_category[1]['total_records'],
                'significance': 'This category has the highest volume of research data, indicating significant scientific interest and investment.'
            })
        
        # Finding 2: Study type distribution
        if self.insights['study_type_distribution']:
            top_study_type = self.insights['study_type_distribution'].most_common(1)[0]
            key_findings.append({
                'finding': 'Dominant Study Type',
                'study_type': top_study_type[0],
                'count': top_study_type[1],
                'significance': f'This represents the most common research methodology used in COVID-19 studies, accounting for {top_study_type[1]} studies.'
            })
        
        # Finding 3: Research timeline
        if 'research_timeline' in self.insights and self.insights['research_timeline']:
            timeline = self.insights['research_timeline']
            key_findings.append({
                'finding': 'Research Timeline',
                'earliest_study': timeline.get('earliest_study', '').strftime('%Y-%m-%d') if timeline.get('earliest_study') else 'N/A',
                'latest_study': timeline.get('latest_study', '').strftime('%Y-%m-%d') if timeline.get('latest_study') else 'N/A',
                'time_span_days': timeline.get('time_span_days', 0),
                'significance': 'Shows the temporal span of research efforts and research momentum over time.'
            })
        
        report_data['key_findings'] = key_findings
        
        # Export JSON report
        with open('/Users/jerrylaivivemachi/DS PROJECT/project5/covid19_research_report.json', 'w') as f:
            json.dump(report_data, f, indent=2, default=str)
        
        # Export text summary
        with open('/Users/jerrylaivivemachi/DS PROJECT/project5/covid19_research_summary.txt', 'w') as f:
            f.write("COVID-19 RESEARCH DATA ANALYSIS SUMMARY REPORT\n")
            f.write("=" * 60 + "\n\n")
            
            f.write(f"Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Total Categories Analyzed: {len([s for s in self.summary_stats.values() if s])}\n\n")
            
            f.write("CATEGORY BREAKDOWN\n")
            f.write("-" * 30 + "\n")
            
            for category_folder, summary in self.summary_stats.items():
                if summary:
                    f.write(f"\n{summary['category_name']}:\n")
                    f.write(f"  • Research Tables: {summary['total_tables']}\n")
                    f.write(f"  • Total Records: {summary['total_records']}\n")
                    
                    if summary['study_types']:
                        top_study_type = max(summary['study_types'].items(), key=lambda x: x[1])
                        f.write(f"  • Top Study Type: {top_study_type[0]} ({top_study_type[1]} studies)\n")
            
            f.write("\n\nKEY FINDINGS\n")
            f.write("-" * 20 + "\n")
            
            for i, finding in enumerate(key_findings, 1):
                f.write(f"\n{i}. {finding['finding']}:\n")
                for key, value in finding.items():
                    if key != 'finding':
                        f.write(f"   {key.title().replace('_', ' ')}: {value}\n")
        
        print("✅ Summary report exported to:")
        print("  • covid19_research_report.json (detailed JSON)")
        print("  • covid19_research_summary.txt (readable summary)")
    
    def get_actionable_insights(self):
        """Generate actionable insights for researchers and policymakers"""
        
        print("\n🎯 ACTIONABLE INSIGHTS FOR COVID-19 RESEARCH")
        print("=" * 60)
        
        insights = []
        
        # Research Gap Analysis
        if self.summary_stats:
            # Find categories with least research
            category_records = [(self.categories[k], v['total_records']) 
                              for k, v in self.summary_stats.items() if v]
            category_records.sort(key=lambda x: x[1])
            
            print(f"\n🔍 RESEARCH GAP ANALYSIS:")
            print(f"   Under-researched areas:")
            for category, count in category_records[:3]:
                print(f"   • {category}: {count} records")
                insights.append(f"Increase research focus in {category} - currently only {count} records")
        
        # Study Quality Recommendations
        if self.insights.get('study_type_distribution'):
            observational_studies = sum(count for study_type, count in self.insights['study_type_distribution'].items() 
                                      if 'observational' in study_type.lower() or 'retrospective' in study_type.lower())
            total_studies = sum(self.insights['study_type_distribution'].values())
            
            if observational_studies / total_studies > 0.6:
                print(f"\n📊 STUDY QUALITY RECOMMENDATIONS:")
                print(f"   • {observational_studies/total_studies*100:.1f}% of studies are observational")
                print(f"   • Recommendation: Increase randomized controlled trials")
                insights.append("Need more randomized controlled trials - currently dominated by observational studies")
        
        # Sample Size Analysis
        all_sample_sizes = []
        small_study_count = 0
        
        for category_folder, category_data in self.category_data.items():
            for filename, df in category_data.items():
                if 'Sample Size' in df.columns:
                    for sample in df['Sample Size'].dropna():
                        try:
                            numbers = re.findall(r'(\d+)', str(sample))
                            if numbers:
                                sizes = [int(n) for n in numbers if int(n) < 100000]  # Filter outliers
                                all_sample_sizes.extend(sizes)
                                small_study_count += sum(1 for s in sizes if s < 100)
                        except:
                            pass
        
        if all_sample_sizes:
            avg_sample_size = np.mean(all_sample_sizes)
            print(f"\n📈 SAMPLE SIZE RECOMMENDATIONS:")
            print(f"   • Average sample size: {avg_sample_size:.0f} patients")
            print(f"   • Studies with <100 patients: {small_study_count}")
            if avg_sample_size < 500:
                print(f"   • Recommendation: Conduct larger multi-center studies")
                insights.append(f"Increase sample sizes - current average is only {avg_sample_size:.0f} patients")
        
        # Publication Timeline Analysis
        if 'research_timeline' in self.insights and self.insights['research_timeline']:
            timeline = self.insights['research_timeline']
            if timeline.get('time_span_days', 0) > 0:
                print(f"\n📅 RESEARCH TIMELINE INSIGHTS:")
                print(f"   • Research span: {timeline['time_span_days']} days")
                print(f"   • Latest research: {timeline.get('latest_study', 'N/A')}")
                
                # Check if research is recent
                if timeline.get('latest_study'):
                    latest_date = timeline['latest_study']
                    days_since_latest = (datetime.now() - latest_date).days
                    if days_since_latest > 180:
                        print(f"   • Recommendation: Update research - latest study is {days_since_latest} days old")
                        insights.append(f"Research may be outdated - latest study is {days_since_latest} days old")
        
        # Risk Factor Insights
        if '8_risk_factors' in self.category_data:
            risk_data = self.category_data['8_risk_factors']
            risk_factor_count = len(risk_data)
            
            print(f"\n🎯 RISK FACTOR RESEARCH INSIGHTS:")
            print(f"   • Total risk factors studied: {risk_factor_count}")
            
            # Identify most studied risk factors
            risk_records = [(name.replace('_', ' ').title(), len(df)) 
                           for name, df in risk_data.items()]
            risk_records.sort(key=lambda x: x[1], reverse=True)
            
            print(f"   • Most studied risk factors:")
            for risk_factor, count in risk_records[:5]:
                print(f"     - {risk_factor}: {count} studies")
        
        print(f"\n✅ Generated {len(insights)} actionable insights")
        
        return insights


def main():
    """
    Main execution function
    """
    
    # Initialize the analyzer
    base_path = "/Users/jerrylaivivemachi/DS PROJECT/project5/target_tables"
    analyzer = COVID19ResearchAnalyzer(base_path)
    
    print("🔬 COVID-19 Research Data Analysis Pipeline")
    print("=" * 50)
    
    try:
        # Load all data
        analyzer.load_all_data()
        
        # Generate comprehensive report
        analyzer.generate_comprehensive_report()
        
        # Create specialized visualizations
        analyzer.create_risk_factor_analysis()
        analyzer.create_patient_outcomes_dashboard()
        
        # Export summary reports
        analyzer.export_summary_report()
        
        # Generate actionable insights
        insights = analyzer.get_actionable_insights()
        
        print("\n🎉 Analysis Complete!")
        print("📊 Generated files:")
        print("  • covid19_research_summary.png")
        print("  • risk_factors_analysis.png") 
        print("  • patient_outcomes_dashboard.html")
        print("  • covid19_research_report.json")
        print("  • covid19_research_summary.txt")
        
    except Exception as e:
        print(f"❌ Error during analysis: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()