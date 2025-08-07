#!/usr/bin/env python3
"""
COVID-19 Research Insights Generator

Advanced analytics for extracting specific insights from COVID-19 research data:
- Risk factor correlation analysis
- Treatment effectiveness patterns  
- Diagnostic accuracy trends
- Population vulnerability assessments
- Research quality metrics

Author: Data Analytics Team
Date: August 2025
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import re
from collections import defaultdict, Counter
import warnings
from scipy import stats
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA

warnings.filterwarnings('ignore')

class COVID19InsightsGenerator:
    """
    Advanced insights generator for COVID-19 research data
    """
    
    def __init__(self, base_path):
        self.base_path = Path(base_path)
        self.risk_factors_data = {}
        self.therapeutics_data = {}
        self.diagnostics_data = {}
        self.patient_data = {}
        
    def load_specialized_data(self):
        """Load data for specialized analysis"""
        
        print("📊 Loading specialized datasets for insights generation...")
        
        # Load risk factors data
        risk_path = self.base_path / "8_risk_factors"
        if risk_path.exists():
            for csv_file in risk_path.glob("*.csv"):
                try:
                    df = pd.read_csv(csv_file)
                    risk_name = csv_file.stem.replace('_', ' ').title()
                    self.risk_factors_data[risk_name] = df
                except Exception as e:
                    print(f"Error loading {csv_file}: {e}")
        
        # Load therapeutics data
        therapeutics_path = self.base_path / "7_therapeutics_interventions_and_clinical_studies"
        if therapeutics_path.exists():
            for csv_file in therapeutics_path.glob("*.csv"):
                try:
                    df = pd.read_csv(csv_file)
                    self.therapeutics_data[csv_file.stem] = df
                except Exception as e:
                    print(f"Error loading {csv_file}: {e}")
        
        # Load diagnostics data
        diagnostics_path = self.base_path / "6_diagnostics"
        if diagnostics_path.exists():
            for csv_file in diagnostics_path.glob("*.csv"):
                try:
                    df = pd.read_csv(csv_file)
                    self.diagnostics_data[csv_file.stem] = df
                except Exception as e:
                    print(f"Error loading {csv_file}: {e}")
        
        # Load patient descriptions data
        patient_path = self.base_path / "3_patient_descriptions"
        if patient_path.exists():
            for csv_file in patient_path.glob("*.csv"):
                try:
                    df = pd.read_csv(csv_file)
                    self.patient_data[csv_file.stem] = df
                except Exception as e:
                    print(f"Error loading {csv_file}: {e}")
        
        print(f"✅ Loaded {len(self.risk_factors_data)} risk factor datasets")
        print(f"✅ Loaded {len(self.therapeutics_data)} therapeutic datasets")
        print(f"✅ Loaded {len(self.diagnostics_data)} diagnostic datasets")
        print(f"✅ Loaded {len(self.patient_data)} patient description datasets")
    
    def analyze_risk_factor_severity(self):
        """
        Analyze risk factors by their association with severe outcomes
        """
        print("\n🎯 RISK FACTOR SEVERITY ANALYSIS")
        print("-" * 40)
        
        risk_severity_data = []
        
        for risk_factor_name, df in self.risk_factors_data.items():
            if 'Severe' in df.columns and 'Severe Significant' in df.columns:
                
                # Extract odds ratios and hazard ratios
                severe_values = df['Severe'].dropna()
                significance = df['Severe Significant'].dropna()
                
                for idx, (severe_val, sig_val) in enumerate(zip(severe_values, significance)):
                    try:
                        # Extract numeric values from severe column
                        if pd.notna(severe_val) and 'OR' in str(severe_val):
                            # Extract odds ratio
                            or_match = re.search(r'OR[:\s]*(\d+\.?\d*)', str(severe_val))
                            if or_match:
                                odds_ratio = float(or_match.group(1))
                                
                                risk_severity_data.append({
                                    'Risk_Factor': risk_factor_name,
                                    'Odds_Ratio': odds_ratio,
                                    'Significant': sig_val,
                                    'Effect_Size': 'High' if odds_ratio > 2.0 else 'Moderate' if odds_ratio > 1.5 else 'Low',
                                    'Direction': 'Protective' if odds_ratio < 1.0 else 'Risk'
                                })
                    except Exception as e:
                        continue
        
        if risk_severity_data:
            severity_df = pd.DataFrame(risk_severity_data)
            
            # Create visualization
            fig, axes = plt.subplots(2, 2, figsize=(16, 12))
            
            # 1. Risk factors ranked by odds ratio
            top_risks = severity_df.nlargest(15, 'Odds_Ratio')
            axes[0, 0].barh(top_risks['Risk_Factor'], top_risks['Odds_Ratio'], 
                           color=['red' if x == 'Significant' else 'orange' for x in top_risks['Significant']])
            axes[0, 0].axvline(x=1, color='black', linestyle='--', alpha=0.7)
            axes[0, 0].set_xlabel('Odds Ratio')
            axes[0, 0].set_title('Top Risk Factors by Odds Ratio\n(Red = Significant)', fontweight='bold')
            
            # 2. Effect size distribution
            effect_counts = severity_df['Effect_Size'].value_counts()
            axes[0, 1].pie(effect_counts.values, labels=effect_counts.index, autopct='%1.1f%%')
            axes[0, 1].set_title('Risk Effect Size Distribution', fontweight='bold')
            
            # 3. Significant vs Non-significant
            sig_counts = severity_df['Significant'].value_counts()
            axes[1, 0].bar(sig_counts.index, sig_counts.values, 
                          color=['green', 'gray'])
            axes[1, 0].set_ylabel('Number of Studies')
            axes[1, 0].set_title('Statistical Significance Distribution', fontweight='bold')
            
            # 4. Protective vs Risk factors
            direction_counts = severity_df['Direction'].value_counts()
            axes[1, 1].pie(direction_counts.values, labels=direction_counts.index, 
                          autopct='%1.1f%%', colors=['lightcoral', 'lightblue'])
            axes[1, 1].set_title('Risk Direction Distribution', fontweight='bold')
            
            plt.tight_layout()
            plt.savefig('/Users/jerrylaivivemachi/DS PROJECT/project5/risk_severity_analysis.png', 
                       dpi=300, bbox_inches='tight')
            plt.show()
            
            # Generate insights
            print("\n📊 KEY FINDINGS:")
            
            # Highest risk factors
            highest_risk = severity_df.loc[severity_df['Odds_Ratio'].idxmax()]
            print(f"• Highest Risk Factor: {highest_risk['Risk_Factor']} (OR: {highest_risk['Odds_Ratio']:.2f})")
            
            # Most significant findings
            significant_factors = severity_df[severity_df['Significant'] == 'Significant']
            print(f"• Significant Risk Factors: {len(significant_factors)} out of {len(severity_df)} ({len(significant_factors)/len(severity_df)*100:.1f}%)")
            
            # Protective factors
            protective_factors = severity_df[severity_df['Direction'] == 'Protective']
            if not protective_factors.empty:
                print(f"• Protective Factors Found: {len(protective_factors)}")
                for _, factor in protective_factors.iterrows():
                    print(f"  - {factor['Risk_Factor']}: OR = {factor['Odds_Ratio']:.2f}")
            
            return severity_df
        
        else:
            print("❌ No suitable risk factor data found for severity analysis")
            return None
    
    def analyze_therapeutic_effectiveness(self):
        """
        Analyze therapeutic interventions by effectiveness
        """
        print("\n💊 THERAPEUTIC EFFECTIVENESS ANALYSIS")
        print("-" * 40)
        
        therapeutic_results = []
        
        for study_name, df in self.therapeutics_data.items():
            if 'Clinical Improvement (Y/N)' in df.columns and 'Therapeutic method(s) utilized/assessed' in df.columns:
                
                for _, row in df.iterrows():
                    if pd.notna(row['Clinical Improvement (Y/N)']) and pd.notna(row['Therapeutic method(s) utilized/assessed']):
                        
                        # Extract sample size
                        sample_size = 0
                        if 'Sample Size' in df.columns and pd.notna(row['Sample Size']):
                            sample_match = re.search(r'patients:\s*(\d+)', str(row['Sample Size']))
                            if sample_match:
                                sample_size = int(sample_match.group(1))
                        
                        therapeutic_results.append({
                            'Treatment': str(row['Therapeutic method(s) utilized/assessed'])[:50],
                            'Effective': row['Clinical Improvement (Y/N)'],
                            'Sample_Size': sample_size,
                            'Study': study_name
                        })
        
        if therapeutic_results:
            therapeutics_df = pd.DataFrame(therapeutic_results)
            
            # Create effectiveness analysis
            fig, axes = plt.subplots(2, 2, figsize=(16, 12))
            
            # 1. Overall effectiveness rate
            effectiveness_rate = therapeutics_df['Effective'].value_counts()
            axes[0, 0].pie(effectiveness_rate.values, labels=effectiveness_rate.index, 
                          autopct='%1.1f%%', colors=['lightgreen', 'lightcoral'])
            axes[0, 0].set_title('Overall Therapeutic Effectiveness', fontweight='bold')
            
            # 2. Top treatments by frequency
            treatment_counts = therapeutics_df['Treatment'].value_counts().head(10)
            axes[0, 1].barh(treatment_counts.index, treatment_counts.values)
            axes[0, 1].set_xlabel('Number of Studies')
            axes[0, 1].set_title('Most Studied Treatments', fontweight='bold')
            
            # 3. Effectiveness by treatment (for treatments with multiple studies)
            treatment_effectiveness = therapeutics_df.groupby('Treatment')['Effective'].agg(['count', lambda x: sum(x == 'Y')])
            treatment_effectiveness.columns = ['Total_Studies', 'Effective_Studies']
            treatment_effectiveness['Effectiveness_Rate'] = treatment_effectiveness['Effective_Studies'] / treatment_effectiveness['Total_Studies']
            
            # Filter for treatments with at least 2 studies
            multi_study_treatments = treatment_effectiveness[treatment_effectiveness['Total_Studies'] >= 2]
            
            if not multi_study_treatments.empty:
                top_effective = multi_study_treatments.nlargest(10, 'Effectiveness_Rate')
                axes[1, 0].barh(top_effective.index, top_effective['Effectiveness_Rate']*100)
                axes[1, 0].set_xlabel('Effectiveness Rate (%)')
                axes[1, 0].set_title('Treatment Effectiveness Rates\n(≥2 studies)', fontweight='bold')
            
            # 4. Sample size vs effectiveness
            effective_studies = therapeutics_df[therapeutics_df['Effective'] == 'Y']
            ineffective_studies = therapeutics_df[therapeutics_df['Effective'] == 'N']
            
            if not effective_studies.empty and not ineffective_studies.empty:
                axes[1, 1].hist([effective_studies['Sample_Size'], ineffective_studies['Sample_Size']], 
                               bins=20, alpha=0.7, label=['Effective', 'Not Effective'],
                               color=['green', 'red'])
                axes[1, 1].set_xlabel('Sample Size')
                axes[1, 1].set_ylabel('Frequency')
                axes[1, 1].set_title('Sample Size Distribution by Effectiveness', fontweight='bold')
                axes[1, 1].legend()
            
            plt.tight_layout()
            plt.savefig('/Users/jerrylaivivemachi/DS PROJECT/project5/therapeutic_effectiveness.png', 
                       dpi=300, bbox_inches='tight')
            plt.show()
            
            # Generate insights
            print("\n📊 KEY FINDINGS:")
            
            total_effective = len(therapeutics_df[therapeutics_df['Effective'] == 'Y'])
            total_studies = len(therapeutics_df)
            overall_rate = total_effective / total_studies * 100
            
            print(f"• Overall Effectiveness Rate: {overall_rate:.1f}% ({total_effective}/{total_studies} studies)")
            
            # Most promising treatments
            if not multi_study_treatments.empty:
                best_treatment = multi_study_treatments.loc[multi_study_treatments['Effectiveness_Rate'].idxmax()]
                print(f"• Most Promising Treatment: {best_treatment.name}")
                print(f"  - Effectiveness: {best_treatment['Effectiveness_Rate']*100:.1f}% ({best_treatment['Effective_Studies']}/{best_treatment['Total_Studies']} studies)")
            
            # Sample size insights
            if not effective_studies.empty:
                avg_effective_sample = effective_studies['Sample_Size'].mean()
                avg_ineffective_sample = ineffective_studies['Sample_Size'].mean()
                print(f"• Average Sample Size - Effective studies: {avg_effective_sample:.0f}")
                print(f"• Average Sample Size - Ineffective studies: {avg_ineffective_sample:.0f}")
            
            return therapeutics_df
        
        else:
            print("❌ No suitable therapeutic data found for effectiveness analysis")
            return None
    
    def analyze_diagnostic_accuracy_trends(self):
        """
        Analyze diagnostic test accuracy and approval trends
        """
        print("\n🔬 DIAGNOSTIC ACCURACY ANALYSIS")
        print("-" * 35)
        
        diagnostic_results = []
        
        for test_name, df in self.diagnostics_data.items():
            
            for _, row in df.iterrows():
                accuracy_data = {
                    'Test_Type': test_name.replace('_', ' ').title(),
                    'Detection_Method': None,
                    'Sensitivity': None,
                    'Specificity': None,
                    'FDA_Approved': None,
                    'Speed': None
                }
                
                # Extract detection method
                if 'Detection Method' in df.columns and pd.notna(row['Detection Method']):
                    accuracy_data['Detection_Method'] = str(row['Detection Method'])
                
                # Extract accuracy measures
                if 'Measure of Testing Accuracy' in df.columns and pd.notna(row['Measure of Testing Accuracy']):
                    accuracy_text = str(row['Measure of Testing Accuracy'])
                    
                    # Extract sensitivity
                    sens_match = re.search(r'sensitivity[:\s]*(\d+(?:\.\d+)?)', accuracy_text, re.IGNORECASE)
                    if sens_match:
                        accuracy_data['Sensitivity'] = float(sens_match.group(1))
                    
                    # Extract specificity  
                    spec_match = re.search(r'specificity[:\s]*(\d+(?:\.\d+)?)', accuracy_text, re.IGNORECASE)
                    if spec_match:
                        accuracy_data['Specificity'] = float(spec_match.group(1))
                
                # Extract FDA approval
                if 'FDA approval' in df.columns and pd.notna(row['FDA approval']):
                    accuracy_data['FDA_Approved'] = row['FDA approval']
                
                # Extract speed
                if 'Speed of assay' in df.columns and pd.notna(row['Speed of assay']):
                    accuracy_data['Speed'] = str(row['Speed of assay'])
                
                diagnostic_results.append(accuracy_data)
        
        if diagnostic_results:
            diagnostics_df = pd.DataFrame(diagnostic_results)
            
            # Create diagnostic analysis visualization
            fig, axes = plt.subplots(2, 2, figsize=(16, 12))
            
            # 1. Test types distribution
            test_counts = diagnostics_df['Test_Type'].value_counts()
            axes[0, 0].pie(test_counts.values, labels=test_counts.index, autopct='%1.1f%%')
            axes[0, 0].set_title('Diagnostic Test Types Distribution', fontweight='bold')
            
            # 2. FDA approval status
            if diagnostics_df['FDA_Approved'].notna().any():
                fda_counts = diagnostics_df['FDA_Approved'].value_counts()
                axes[0, 1].bar(fda_counts.index, fda_counts.values, 
                              color=['green', 'red'])
                axes[0, 1].set_ylabel('Number of Tests')
                axes[0, 1].set_title('FDA Approval Status', fontweight='bold')
            
            # 3. Sensitivity vs Specificity scatter
            sens_spec_data = diagnostics_df[(diagnostics_df['Sensitivity'].notna()) & 
                                          (diagnostics_df['Specificity'].notna())]
            
            if not sens_spec_data.empty:
                scatter = axes[1, 0].scatter(sens_spec_data['Sensitivity'], 
                                           sens_spec_data['Specificity'],
                                           c=['green' if x == 'Y' else 'red' for x in sens_spec_data['FDA_Approved']],
                                           alpha=0.7, s=60)
                axes[1, 0].set_xlabel('Sensitivity (%)')
                axes[1, 0].set_ylabel('Specificity (%)')
                axes[1, 0].set_title('Test Accuracy: Sensitivity vs Specificity\n(Green=FDA Approved)', fontweight='bold')
                axes[1, 0].plot([0, 100], [0, 100], 'k--', alpha=0.5)
            
            # 4. Detection methods
            if diagnostics_df['Detection_Method'].notna().any():
                method_counts = diagnostics_df['Detection_Method'].value_counts().head(8)
                axes[1, 1].barh(method_counts.index, method_counts.values)
                axes[1, 1].set_xlabel('Number of Studies')
                axes[1, 1].set_title('Detection Methods Used', fontweight='bold')
            
            plt.tight_layout()
            plt.savefig('/Users/jerrylaivivemachi/DS PROJECT/project5/diagnostic_accuracy_analysis.png', 
                       dpi=300, bbox_inches='tight')
            plt.show()
            
            # Generate insights
            print("\n📊 KEY FINDINGS:")
            
            # Test accuracy statistics
            if not sens_spec_data.empty:
                avg_sensitivity = sens_spec_data['Sensitivity'].mean()
                avg_specificity = sens_spec_data['Specificity'].mean()
                print(f"• Average Test Sensitivity: {avg_sensitivity:.1f}%")
                print(f"• Average Test Specificity: {avg_specificity:.1f}%")
                
                # Best performing tests
                sens_spec_data['Combined_Accuracy'] = (sens_spec_data['Sensitivity'] + sens_spec_data['Specificity']) / 2
                best_test_idx = sens_spec_data['Combined_Accuracy'].idxmax()
                best_test = sens_spec_data.loc[best_test_idx]
                print(f"• Best Overall Accuracy: {best_test['Test_Type']} "
                     f"(Sens: {best_test['Sensitivity']:.1f}%, Spec: {best_test['Specificity']:.1f}%)")
            
            # FDA approval insights
            if diagnostics_df['FDA_Approved'].notna().any():
                fda_approved = len(diagnostics_df[diagnostics_df['FDA_Approved'] == 'Y'])
                total_tests = len(diagnostics_df[diagnostics_df['FDA_Approved'].notna()])
                approval_rate = fda_approved / total_tests * 100
                print(f"• FDA Approval Rate: {approval_rate:.1f}% ({fda_approved}/{total_tests} tests)")
            
            return diagnostics_df
        
        else:
            print("❌ No suitable diagnostic data found for accuracy analysis")
            return None
    
    def generate_population_vulnerability_assessment(self):
        """
        Generate vulnerability assessment based on patient descriptions and risk factors
        """
        print("\n👥 POPULATION VULNERABILITY ASSESSMENT")
        print("-" * 42)
        
        vulnerability_data = []
        
        # Analyze age-related vulnerability
        age_risk_data = self.risk_factors_data.get('Age')
        if age_risk_data is not None:
            # Extract age-related risk information
            for _, row in age_risk_data.iterrows():
                if pd.notna(row.get('Severe')) and 'OR' in str(row['Severe']):
                    or_match = re.search(r'OR[:\s]*(\d+\.?\d*)', str(row['Severe']))
                    if or_match:
                        vulnerability_data.append({
                            'Factor': 'Age',
                            'Risk_Level': float(or_match.group(1)),
                            'Category': 'Demographic'
                        })
        
        # Analyze comorbidity risks
        comorbidities = ['Diabetes', 'Hypertension', 'Heart Disease', 'COPD', 'Cancer']
        
        for comorbidity in comorbidities:
            comorbidity_data = self.risk_factors_data.get(comorbidity)
            if comorbidity_data is not None:
                # Extract risk ratios
                severe_values = comorbidity_data['Severe'].dropna()
                for severe_val in severe_values:
                    if 'OR' in str(severe_val):
                        or_match = re.search(r'OR[:\s]*(\d+\.?\d*)', str(severe_val))
                        if or_match:
                            vulnerability_data.append({
                                'Factor': comorbidity,
                                'Risk_Level': float(or_match.group(1)),
                                'Category': 'Comorbidity'
                            })
                            break  # Take first valid value per comorbidity
        
        # Analyze demographic risks
        demographic_factors = ['Male Gender', 'Race Black Vs White', 'Race Asian Vs White']
        
        for demo_factor in demographic_factors:
            demo_data = self.risk_factors_data.get(demo_factor)
            if demo_data is not None:
                severe_values = demo_data['Severe'].dropna()
                for severe_val in severe_values:
                    if 'OR' in str(severe_val):
                        or_match = re.search(r'OR[:\s]*(\d+\.?\d*)', str(severe_val))
                        if or_match:
                            vulnerability_data.append({
                                'Factor': demo_factor.replace(' Vs ', ' vs '),
                                'Risk_Level': float(or_match.group(1)),
                                'Category': 'Demographic'
                            })
                            break
        
        if vulnerability_data:
            vuln_df = pd.DataFrame(vulnerability_data)
            
            # Create vulnerability assessment visualization
            fig, axes = plt.subplots(2, 2, figsize=(16, 12))
            
            # 1. Risk factors ranked by severity
            vuln_sorted = vuln_df.sort_values('Risk_Level', ascending=True)
            colors = ['red' if x > 2.0 else 'orange' if x > 1.5 else 'green' for x in vuln_sorted['Risk_Level']]
            
            axes[0, 0].barh(vuln_sorted['Factor'], vuln_sorted['Risk_Level'], color=colors)
            axes[0, 0].axvline(x=1, color='black', linestyle='--', alpha=0.7, label='No Effect')
            axes[0, 0].set_xlabel('Odds Ratio')
            axes[0, 0].set_title('Population Risk Factors\n(Red: High Risk, Orange: Moderate, Green: Low)', fontweight='bold')
            axes[0, 0].legend()
            
            # 2. Risk categories distribution
            category_counts = vuln_df['Category'].value_counts()
            axes[0, 1].pie(category_counts.values, labels=category_counts.index, 
                          autopct='%1.1f%%', colors=['lightblue', 'lightcoral'])
            axes[0, 1].set_title('Risk Factor Categories', fontweight='bold')
            
            # 3. High-risk population identification
            high_risk_factors = vuln_df[vuln_df['Risk_Level'] > 1.5]
            if not high_risk_factors.empty:
                axes[1, 0].bar(high_risk_factors['Factor'], high_risk_factors['Risk_Level'], 
                              color=['darkred' if x > 2.0 else 'red' for x in high_risk_factors['Risk_Level']])
                axes[1, 0].set_ylabel('Odds Ratio')
                axes[1, 0].set_title('High-Risk Population Factors (OR > 1.5)', fontweight='bold')
                axes[1, 0].tick_params(axis='x', rotation=45)
            
            # 4. Risk level distribution
            axes[1, 1].hist(vuln_df['Risk_Level'], bins=15, alpha=0.7, color='skyblue', edgecolor='black')
            axes[1, 1].axvline(x=1, color='red', linestyle='--', alpha=0.7, label='No Effect Line')
            axes[1, 1].set_xlabel('Odds Ratio')
            axes[1, 1].set_ylabel('Frequency')
            axes[1, 1].set_title('Risk Level Distribution', fontweight='bold')
            axes[1, 1].legend()
            
            plt.tight_layout()
            plt.savefig('/Users/jerrylaivivemachi/DS PROJECT/project5/population_vulnerability.png', 
                       dpi=300, bbox_inches='tight')
            plt.show()
            
            # Generate vulnerability insights
            print("\n📊 VULNERABILITY ASSESSMENT:")
            
            # Highest risk factors
            highest_risk = vuln_df.loc[vuln_df['Risk_Level'].idxmax()]
            print(f"• Highest Risk Factor: {highest_risk['Factor']} (OR: {highest_risk['Risk_Level']:.2f})")
            
            # High-risk population count
            high_risk_count = len(vuln_df[vuln_df['Risk_Level'] > 1.5])
            moderate_risk_count = len(vuln_df[(vuln_df['Risk_Level'] > 1.2) & (vuln_df['Risk_Level'] <= 1.5)])
            
            print(f"• High-Risk Factors (OR > 1.5): {high_risk_count}")
            print(f"• Moderate-Risk Factors (1.2 < OR ≤ 1.5): {moderate_risk_count}")
            
            # Category insights
            comorbidity_avg = vuln_df[vuln_df['Category'] == 'Comorbidity']['Risk_Level'].mean()
            demographic_avg = vuln_df[vuln_df['Category'] == 'Demographic']['Risk_Level'].mean()
            
            print(f"• Average Comorbidity Risk: OR = {comorbidity_avg:.2f}")
            print(f"• Average Demographic Risk: OR = {demographic_avg:.2f}")
            
            # Priority populations
            print("\n🚨 PRIORITY POPULATIONS FOR INTERVENTION:")
            priority_factors = vuln_df[vuln_df['Risk_Level'] > 2.0].sort_values('Risk_Level', ascending=False)
            for _, factor in priority_factors.iterrows():
                print(f"• {factor['Factor']}: {factor['Risk_Level']:.2f}x increased risk")
            
            return vuln_df
        
        else:
            print("❌ Insufficient data for vulnerability assessment")
            return None
    
    def generate_research_quality_metrics(self):
        """
        Generate research quality assessment metrics
        """
        print("\n📈 RESEARCH QUALITY METRICS")
        print("-" * 30)
        
        quality_metrics = {
            'sample_size_analysis': {},
            'study_type_quality': {},
            'temporal_coverage': {},
            'statistical_rigor': {}
        }
        
        all_sample_sizes = []
        study_types = []
        dates = []
        statistical_measures = []
        
        # Collect data from all categories
        all_datasets = {
            **self.risk_factors_data,
            **self.therapeutics_data, 
            **self.diagnostics_data,
            **self.patient_data
        }
        
        for dataset_name, df in all_datasets.items():
            
            # Sample size analysis
            if 'Sample Size' in df.columns:
                for sample in df['Sample Size'].dropna():
                    try:
                        numbers = re.findall(r'(\d+)', str(sample))
                        if numbers:
                            sample_sizes = [int(n) for n in numbers if 10 <= int(n) <= 100000]
                            all_sample_sizes.extend(sample_sizes)
                    except:
                        pass
            
            # Study type analysis
            if 'Study Type' in df.columns:
                study_types.extend(df['Study Type'].dropna().tolist())
            
            # Date analysis
            if 'Date' in df.columns:
                try:
                    date_series = pd.to_datetime(df['Date'], errors='coerce')
                    dates.extend(date_series.dropna().tolist())
                except:
                    pass
            
            # Statistical rigor analysis
            if 'Severe Significant' in df.columns:
                statistical_measures.extend(df['Severe Significant'].dropna().tolist())
            elif 'Clinical Improvement (Y/N)' in df.columns:
                statistical_measures.extend(['Statistical Test Used'] * len(df['Clinical Improvement (Y/N)'].dropna()))
        
        # Calculate quality metrics
        
        # 1. Sample Size Quality
        if all_sample_sizes:
            quality_metrics['sample_size_analysis'] = {
                'total_studies': len(all_sample_sizes),
                'mean_sample_size': np.mean(all_sample_sizes),
                'median_sample_size': np.median(all_sample_sizes),
                'small_studies_pct': len([s for s in all_sample_sizes if s < 100]) / len(all_sample_sizes) * 100,
                'large_studies_pct': len([s for s in all_sample_sizes if s > 1000]) / len(all_sample_sizes) * 100,
                'adequate_power_pct': len([s for s in all_sample_sizes if s > 400]) / len(all_sample_sizes) * 100
            }
        
        # 2. Study Type Quality
        if study_types:
            study_type_counts = Counter(study_types)
            total_studies = len(study_types)
            
            # Quality scoring (higher = better quality evidence)
            quality_scores = {
                'Randomized Controlled Trial': 5,
                'Systematic Review': 5,
                'Meta-analysis': 5,
                'Prospective Observational Study': 4,
                'Cohort Study': 4,
                'Case-Control Study': 3,
                'Retrospective Observational Study': 2,
                'Case Series': 2,
                'Expert Review': 1,
                'Editorial': 1
            }
            
            weighted_quality_score = 0
            for study_type, count in study_type_counts.items():
                score = 0
                for quality_type, quality_score in quality_scores.items():
                    if quality_type.lower() in study_type.lower():
                        score = quality_score
                        break
                weighted_quality_score += score * count
            
            avg_quality_score = weighted_quality_score / total_studies if total_studies > 0 else 0
            
            quality_metrics['study_type_quality'] = {
                'total_studies': total_studies,
                'unique_study_types': len(study_type_counts),
                'most_common_type': study_type_counts.most_common(1)[0],
                'avg_quality_score': avg_quality_score,
                'high_quality_pct': sum(count for study_type, count in study_type_counts.items() 
                                      if any(hq in study_type.lower() for hq in ['randomized', 'meta-analysis', 'systematic'])) / total_studies * 100
            }
        
        # 3. Temporal Coverage
        if dates:
            quality_metrics['temporal_coverage'] = {
                'earliest_study': min(dates),
                'latest_study': max(dates),
                'time_span_days': (max(dates) - min(dates)).days,
                'studies_per_month': len(dates) / max(1, (max(dates) - min(dates)).days) * 30,
                'recent_studies_pct': len([d for d in dates if (max(dates) - d).days <= 365]) / len(dates) * 100
            }
        
        # 4. Statistical Rigor
        if statistical_measures:
            significant_count = len([m for m in statistical_measures if 'significant' in str(m).lower()])
            quality_metrics['statistical_rigor'] = {
                'studies_with_stats': len(statistical_measures),
                'significant_findings_pct': significant_count / len(statistical_measures) * 100 if statistical_measures else 0,
                'statistical_testing_rate': len(statistical_measures) / len(all_datasets) * 100
            }
        
        # Create quality visualization
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        
        # 1. Sample size distribution
        if all_sample_sizes:
            axes[0, 0].hist(all_sample_sizes, bins=30, alpha=0.7, color='skyblue', edgecolor='black')
            axes[0, 0].axvline(x=np.mean(all_sample_sizes), color='red', linestyle='--', 
                              label=f'Mean: {np.mean(all_sample_sizes):.0f}')
            axes[0, 0].axvline(x=400, color='green', linestyle='--', 
                              label='Adequate Power Threshold')
            axes[0, 0].set_xlabel('Sample Size')
            axes[0, 0].set_ylabel('Frequency')
            axes[0, 0].set_title('Sample Size Distribution', fontweight='bold')
            axes[0, 0].legend()
            axes[0, 0].set_xlim(0, min(5000, max(all_sample_sizes)) if all_sample_sizes else 1000)
        
        # 2. Study type quality
        if study_types:
            study_type_counts = Counter(study_types)
            top_types = dict(study_type_counts.most_common(8))
            
            axes[0, 1].pie(top_types.values(), labels=top_types.keys(), autopct='%1.1f%%')
            axes[0, 1].set_title('Study Type Distribution', fontweight='bold')
        
        # 3. Temporal distribution
        if dates:
            monthly_counts = defaultdict(int)
            for date in dates:
                month_key = date.strftime('%Y-%m')
                monthly_counts[month_key] += 1
            
            months = sorted(monthly_counts.keys())[-24:]  # Last 24 months
            counts = [monthly_counts[month] for month in months]
            
            axes[1, 0].plot(months, counts, marker='o', linewidth=2)
            axes[1, 0].set_xlabel('Month')
            axes[1, 0].set_ylabel('Number of Studies')
            axes[1, 0].set_title('Research Publication Timeline', fontweight='bold')
            axes[1, 0].tick_params(axis='x', rotation=45)
        
        # 4. Quality metrics summary
        axes[1, 1].axis('off')
        
        quality_summary = f"""
RESEARCH QUALITY ASSESSMENT

Sample Size Quality:
• Mean Sample Size: {quality_metrics.get('sample_size_analysis', {}).get('mean_sample_size', 0):.0f}
• Studies with Adequate Power: {quality_metrics.get('sample_size_analysis', {}).get('adequate_power_pct', 0):.1f}%
• Small Studies (<100): {quality_metrics.get('sample_size_analysis', {}).get('small_studies_pct', 0):.1f}%

Study Design Quality:
• Average Quality Score: {quality_metrics.get('study_type_quality', {}).get('avg_quality_score', 0):.1f}/5
• High-Quality Studies: {quality_metrics.get('study_type_quality', {}).get('high_quality_pct', 0):.1f}%

Temporal Coverage:
• Research Span: {quality_metrics.get('temporal_coverage', {}).get('time_span_days', 0)} days
• Recent Studies: {quality_metrics.get('temporal_coverage', {}).get('recent_studies_pct', 0):.1f}%

Statistical Rigor:
• Studies with Statistical Tests: {quality_metrics.get('statistical_rigor', {}).get('statistical_testing_rate', 0):.1f}%
"""
        
        axes[1, 1].text(0.05, 0.95, quality_summary, transform=axes[1, 1].transAxes,
                        fontsize=10, verticalalignment='top', fontfamily='monospace',
                        bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.8))
        
        plt.tight_layout()
        plt.savefig('/Users/jerrylaivivemachi/DS PROJECT/project5/research_quality_metrics.png', 
                   dpi=300, bbox_inches='tight')
        plt.show()
        
        # Print quality assessment
        print("\n📊 OVERALL RESEARCH QUALITY ASSESSMENT:")
        
        # Calculate overall quality score
        quality_scores = []
        
        if 'sample_size_analysis' in quality_metrics:
            sample_score = min(5, quality_metrics['sample_size_analysis']['adequate_power_pct'] / 20)
            quality_scores.append(sample_score)
            print(f"• Sample Size Quality: {sample_score:.1f}/5")
        
        if 'study_type_quality' in quality_metrics:
            design_score = quality_metrics['study_type_quality']['avg_quality_score']
            quality_scores.append(design_score)
            print(f"• Study Design Quality: {design_score:.1f}/5")
        
        if 'temporal_coverage' in quality_metrics:
            temporal_score = min(5, quality_metrics['temporal_coverage']['recent_studies_pct'] / 20)
            quality_scores.append(temporal_score)
            print(f"• Temporal Relevance: {temporal_score:.1f}/5")
        
        if 'statistical_rigor' in quality_metrics:
            stats_score = min(5, quality_metrics['statistical_rigor']['statistical_testing_rate'] / 20)
            quality_scores.append(stats_score)
            print(f"• Statistical Rigor: {stats_score:.1f}/5")
        
        if quality_scores:
            overall_score = np.mean(quality_scores)
            print(f"\n🏆 OVERALL QUALITY SCORE: {overall_score:.1f}/5")
            
            if overall_score >= 4:
                print("   Quality Level: EXCELLENT")
            elif overall_score >= 3:
                print("   Quality Level: GOOD")
            elif overall_score >= 2:
                print("   Quality Level: MODERATE") 
            else:
                print("   Quality Level: NEEDS IMPROVEMENT")
        
        return quality_metrics


def main():
    """
    Main execution function for insights generation
    """
    print("🧠 COVID-19 Research Insights Generator")
    print("=" * 45)
    
    # Initialize the insights generator
    base_path = "/Users/jerrylaivivemachi/DS PROJECT/project5/target_tables"
    generator = COVID19InsightsGenerator(base_path)
    
    try:
        # Load specialized datasets
        generator.load_specialized_data()
        
        print("\n" + "="*60)
        print("GENERATING SPECIALIZED INSIGHTS")
        print("="*60)
        
        # Generate specialized analyses
        severity_results = generator.analyze_risk_factor_severity()
        therapeutic_results = generator.analyze_therapeutic_effectiveness()
        diagnostic_results = generator.analyze_diagnostic_accuracy_trends()
        vulnerability_results = generator.generate_population_vulnerability_assessment()
        quality_results = generator.generate_research_quality_metrics()
        
        print("\n🎉 INSIGHTS GENERATION COMPLETE!")
        print("\n📊 Generated Analysis Files:")
        print("  • risk_severity_analysis.png")
        print("  • therapeutic_effectiveness.png")
        print("  • diagnostic_accuracy_analysis.png")
        print("  • population_vulnerability.png")
        print("  • research_quality_metrics.png")
        
        # Summary of insights
        print("\n📋 EXECUTIVE SUMMARY:")
        print("-" * 25)
        
        if severity_results is not None:
            sig_risk_factors = len(severity_results[severity_results['Significant'] == 'Significant'])
            print(f"• Significant Risk Factors Identified: {sig_risk_factors}")
        
        if therapeutic_results is not None:
            effective_rate = len(therapeutic_results[therapeutic_results['Effective'] == 'Y']) / len(therapeutic_results) * 100
            print(f"• Therapeutic Success Rate: {effective_rate:.1f}%")
        
        if diagnostic_results is not None:
            fda_approved = len(diagnostic_results[diagnostic_results['FDA_Approved'] == 'Y'])
            print(f"• FDA-Approved Diagnostic Tests: {fda_approved}")
        
        if vulnerability_results is not None:
            high_risk_pops = len(vulnerability_results[vulnerability_results['Risk_Level'] > 2.0])
            print(f"• High-Risk Population Factors: {high_risk_pops}")
        
        if quality_results is not None and 'sample_size_analysis' in quality_results:
            avg_sample = quality_results['sample_size_analysis']['mean_sample_size']
            print(f"• Average Study Sample Size: {avg_sample:.0f} patients")
        
    except Exception as e:
        print(f"❌ Error during insights generation: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()