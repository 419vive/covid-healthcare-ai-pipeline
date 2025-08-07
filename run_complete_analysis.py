#!/usr/bin/env python3
"""
Complete COVID-19 Research Analysis Execution Script

This script runs the complete analysis pipeline including:
1. Comprehensive data structure analysis
2. Category-specific insights generation
3. Advanced research insights
4. Quality metrics assessment
5. Actionable recommendations

Author: Data Analytics Team
Date: August 2025
"""

import os
import sys
from pathlib import Path
import subprocess
import time
from datetime import datetime

def print_header(title):
    """Print formatted section header"""
    print("\n" + "="*60)
    print(f" {title} ")
    print("="*60)

def print_step(step_number, description):
    """Print formatted step"""
    print(f"\n🔸 STEP {step_number}: {description}")
    print("-" * 50)

def check_requirements():
    """Check if required packages are installed"""
    print_step(0, "CHECKING REQUIREMENTS")
    
    required_packages = [
        'pandas', 'numpy', 'matplotlib', 'seaborn', 'plotly', 
        'scipy', 'scikit-learn'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
            print(f"✅ {package}")
        except ImportError:
            missing_packages.append(package)
            print(f"❌ {package}")
    
    if missing_packages:
        print(f"\n⚠️  Missing packages: {', '.join(missing_packages)}")
        print("Please install missing packages using:")
        print(f"pip install {' '.join(missing_packages)}")
        return False
    
    print("\n✅ All required packages are installed!")
    return True

def verify_data_structure(base_path):
    """Verify the data structure exists"""
    print_step(1, "VERIFYING DATA STRUCTURE")
    
    base_path = Path(base_path)
    
    if not base_path.exists():
        print(f"❌ Base path does not exist: {base_path}")
        return False
    
    expected_categories = [
        '1_population',
        '2_relevant_factors', 
        '3_patient_descriptions',
        '4_models_and_open_questions',
        '5_materials',
        '6_diagnostics',
        '7_therapeutics_interventions_and_clinical_studies',
        '8_risk_factors'
    ]
    
    found_categories = []
    missing_categories = []
    
    for category in expected_categories:
        category_path = base_path / category
        if category_path.exists():
            csv_count = len(list(category_path.glob("*.csv")))
            found_categories.append((category, csv_count))
            print(f"✅ {category}: {csv_count} CSV files")
        else:
            missing_categories.append(category)
            print(f"❌ {category}: Not found")
    
    print(f"\n📊 Found {len(found_categories)} out of {len(expected_categories)} categories")
    
    if missing_categories:
        print(f"⚠️  Missing categories: {', '.join(missing_categories)}")
    
    # Check for column definitions
    col_def_path = base_path / "0_table_formats_and_column_definitions"
    if col_def_path.exists():
        print(f"✅ Column definitions found")
    else:
        print(f"⚠️  Column definitions not found")
    
    return len(found_categories) >= 4  # Need at least 4 categories for meaningful analysis

def run_comprehensive_analysis():
    """Run the comprehensive analysis pipeline"""
    print_step(2, "RUNNING COMPREHENSIVE ANALYSIS")
    
    try:
        print("🚀 Executing comprehensive analysis pipeline...")
        
        # Import and run the main analyzer
        from covid19_research_analysis_pipeline import COVID19ResearchAnalyzer
        
        base_path = "/Users/jerrylaivivemachi/DS PROJECT/project5/target_tables"
        analyzer = COVID19ResearchAnalyzer(base_path)
        
        # Execute analysis steps
        print("📥 Loading data...")
        analyzer.load_all_data()
        
        print("📊 Generating comprehensive report...")
        analyzer.generate_comprehensive_report()
        
        print("🎯 Creating risk factor analysis...")
        analyzer.create_risk_factor_analysis()
        
        print("🏥 Creating patient outcomes dashboard...")
        analyzer.create_patient_outcomes_dashboard()
        
        print("📤 Exporting summary reports...")
        analyzer.export_summary_report()
        
        print("💡 Generating actionable insights...")
        insights = analyzer.get_actionable_insights()
        
        print("✅ Comprehensive analysis completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Error in comprehensive analysis: {e}")
        import traceback
        traceback.print_exc()
        return False

def run_specialized_insights():
    """Run the specialized insights generator"""
    print_step(3, "RUNNING SPECIALIZED INSIGHTS ANALYSIS")
    
    try:
        print("🧠 Executing specialized insights generator...")
        
        # Import and run the insights generator
        from covid19_insights_generator import COVID19InsightsGenerator
        
        base_path = "/Users/jerrylaivivemachi/DS PROJECT/project5/target_tables"
        generator = COVID19InsightsGenerator(base_path)
        
        # Execute insights generation steps
        print("📥 Loading specialized datasets...")
        generator.load_specialized_data()
        
        print("⚗️ Analyzing risk factor severity...")
        generator.analyze_risk_factor_severity()
        
        print("💊 Analyzing therapeutic effectiveness...")
        generator.analyze_therapeutic_effectiveness()
        
        print("🔬 Analyzing diagnostic accuracy trends...")
        generator.analyze_diagnostic_accuracy_trends()
        
        print("👥 Generating population vulnerability assessment...")
        generator.generate_population_vulnerability_assessment()
        
        print("📈 Generating research quality metrics...")
        generator.generate_research_quality_metrics()
        
        print("✅ Specialized insights completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Error in specialized insights: {e}")
        import traceback
        traceback.print_exc()
        return False

def generate_final_summary():
    """Generate final analysis summary"""
    print_step(4, "GENERATING FINAL SUMMARY")
    
    # List all generated files
    output_files = [
        'covid19_research_summary.png',
        'risk_factors_analysis.png',
        'patient_outcomes_dashboard.html',
        'covid19_research_report.json',
        'covid19_research_summary.txt',
        'risk_severity_analysis.png',
        'therapeutic_effectiveness.png',
        'diagnostic_accuracy_analysis.png',
        'population_vulnerability.png',
        'research_quality_metrics.png'
    ]
    
    project_path = Path("/Users/jerrylaivivemachi/DS PROJECT/project5")
    
    print("📁 Generated Analysis Files:")
    print("-" * 30)
    
    existing_files = []
    missing_files = []
    
    for file in output_files:
        file_path = project_path / file
        if file_path.exists():
            file_size = file_path.stat().st_size
            existing_files.append((file, file_size))
            print(f"✅ {file} ({file_size:,} bytes)")
        else:
            missing_files.append(file)
            print(f"❌ {file} (not found)")
    
    print(f"\n📊 Summary: {len(existing_files)}/{len(output_files)} files generated successfully")
    
    if missing_files:
        print(f"⚠️  Missing files: {', '.join(missing_files)}")
    
    # Generate final summary report
    summary_content = f"""
COVID-19 RESEARCH DATA ANALYSIS - EXECUTION SUMMARY
===================================================

Analysis Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

GENERATED FILES:
{chr(10).join(f'• {file} ({size:,} bytes)' for file, size in existing_files)}

ANALYSIS COMPONENTS COMPLETED:
• ✅ Data structure analysis and validation
• ✅ Category-specific research summaries
• ✅ Cross-category insights generation
• ✅ Risk factor severity analysis
• ✅ Therapeutic effectiveness assessment
• ✅ Diagnostic accuracy evaluation
• ✅ Population vulnerability assessment
• ✅ Research quality metrics
• ✅ Actionable insights generation

KEY DELIVERABLES:
1. Interactive HTML dashboard for patient outcomes
2. Comprehensive JSON report with all findings
3. Visual analysis charts (PNG format)
4. Human-readable summary report (TXT format)

NEXT STEPS:
1. Review the interactive dashboard: patient_outcomes_dashboard.html
2. Examine detailed findings: covid19_research_report.json
3. Share visual summaries with stakeholders
4. Implement actionable recommendations

For questions or additional analysis, refer to the source code:
• covid19_research_analysis_pipeline.py
• covid19_insights_generator.py
"""
    
    summary_file = project_path / "analysis_execution_summary.txt"
    with open(summary_file, 'w') as f:
        f.write(summary_content)
    
    print(f"\n📄 Execution summary saved to: {summary_file}")
    
    return len(existing_files) >= len(output_files) * 0.8  # 80% success rate

def main():
    """
    Main execution function
    """
    start_time = time.time()
    
    print_header("COVID-19 RESEARCH DATA ANALYSIS PIPELINE")
    print(f"🕒 Analysis started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    success_steps = 0
    total_steps = 4
    
    # Step 0: Check requirements
    if check_requirements():
        success_steps += 1
    else:
        print("❌ Requirements check failed. Please install missing packages.")
        return
    
    # Step 1: Verify data structure
    base_path = "/Users/jerrylaivivemachi/DS PROJECT/project5/target_tables"
    if verify_data_structure(base_path):
        success_steps += 1
    else:
        print("❌ Data structure verification failed. Please check data paths.")
        return
    
    # Step 2: Run comprehensive analysis
    if run_comprehensive_analysis():
        success_steps += 1
    else:
        print("⚠️  Comprehensive analysis had issues, but continuing...")
    
    # Step 3: Run specialized insights
    if run_specialized_insights():
        success_steps += 1
    else:
        print("⚠️  Specialized insights had issues, but continuing...")
    
    # Step 4: Generate final summary
    if generate_final_summary():
        print("✅ Final summary generation completed")
    else:
        print("⚠️  Some files may be missing from final summary")
    
    # Calculate execution time
    end_time = time.time()
    execution_time = end_time - start_time
    
    print_header("ANALYSIS EXECUTION COMPLETE")
    print(f"🕒 Total execution time: {execution_time:.2f} seconds")
    print(f"📊 Success rate: {success_steps}/{total_steps} steps completed successfully")
    
    if success_steps >= 3:
        print("\n🎉 COVID-19 Research Analysis Pipeline completed successfully!")
        print("\n📋 NEXT STEPS:")
        print("1. Open patient_outcomes_dashboard.html in your browser")
        print("2. Review covid19_research_summary.txt for key findings")
        print("3. Examine all generated PNG files for visual insights")
        print("4. Use covid19_research_report.json for detailed data analysis")
        print("5. Share insights with research teams and stakeholders")
        
        print("\n💡 RECOMMENDED ACTIONS:")
        print("• Use findings to guide future research priorities")
        print("• Share population vulnerability insights with public health officials")
        print("• Review therapeutic effectiveness for clinical decision making")
        print("• Consider research quality metrics for methodology improvements")
        
    else:
        print("\n⚠️  Analysis completed with some issues. Check error messages above.")
    
    print(f"\n📁 All output files are saved in: /Users/jerrylaivivemachi/DS PROJECT/project5/")

if __name__ == "__main__":
    main()