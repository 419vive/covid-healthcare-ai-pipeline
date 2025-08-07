#!/usr/bin/env python3
"""
Setup and installation script for Veeva Data Quality System
"""

import os
import sys
import subprocess
from pathlib import Path


def install_dependencies():
    """Install required dependencies"""
    print("🔧 Installing dependencies...")
    
    try:
        # Install requirements
        requirements_file = Path(__file__).parent / "requirements.txt"
        subprocess.run([
            sys.executable, "-m", "pip", "install", "-r", str(requirements_file)
        ], check=True)
        
        print("✅ Dependencies installed successfully")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install dependencies: {e}")
        return False


def setup_directories():
    """Create necessary directories"""
    print("📁 Setting up directories...")
    
    directories = [
        "logs",
        "reports/validation",
        "reports/quality_metrics",
        "reports/reconciliation",
        "config"
    ]
    
    for directory in directories:
        dir_path = Path(__file__).parent / directory
        dir_path.mkdir(parents=True, exist_ok=True)
        print(f"  Created: {directory}")
    
    print("✅ Directory structure created")


def test_database_connection():
    """Test database connectivity"""
    print("🗄️ Testing database connection...")
    
    try:
        # Add project to Python path
        project_root = Path(__file__).parent
        sys.path.insert(0, str(project_root))
        
        from python.config.database_config import DatabaseConfig
        from python.utils.database import DatabaseManager
        
        db_config = DatabaseConfig()
        db_manager = DatabaseManager(db_config)
        
        # Test connection
        if db_config.test_connection():
            print("✅ Database connection successful")
            
            # Get database info
            table_info = db_config.get_table_info()
            print("📊 Database overview:")
            for table, info in table_info.items():
                print(f"  {table}: {info.get('row_count', 0):,} records")
            
            return True
        else:
            print("❌ Database connection failed")
            return False
            
    except Exception as e:
        print(f"❌ Database test failed: {e}")
        return False


def create_sample_config():
    """Create sample configuration file"""
    print("⚙️ Creating sample configuration...")
    
    config_dir = Path(__file__).parent / "config"
    sample_config = config_dir / "sample_config.yaml"
    
    if not sample_config.exists():
        try:
            # Add project to Python path
            project_root = Path(__file__).parent
            sys.path.insert(0, str(project_root))
            
            from python.config.pipeline_config import PipelineConfig
            
            # Create default config and save as sample
            pipeline_config = PipelineConfig()
            pipeline_config.save_config(str(sample_config))
            
            print(f"✅ Sample configuration created: {sample_config}")
            
        except Exception as e:
            print(f"❌ Failed to create sample configuration: {e}")
            return False
    
    return True


def run_basic_test():
    """Run basic system test"""
    print("🧪 Running basic system test...")
    
    try:
        # Add project to Python path
        project_root = Path(__file__).parent
        sys.path.insert(0, str(project_root))
        
        # Test CLI help command
        from python.main import cli
        from click.testing import CliRunner
        
        runner = CliRunner()
        result = runner.invoke(cli, ['--help'])
        
        if result.exit_code == 0:
            print("✅ CLI interface working correctly")
            return True
        else:
            print(f"❌ CLI test failed: {result.output}")
            return False
            
    except Exception as e:
        print(f"❌ Basic test failed: {e}")
        return False


def main():
    """Main setup process"""
    print("🚀 Veeva Data Quality System Setup")
    print("=" * 50)
    
    success = True
    
    # Step 1: Install dependencies
    if not install_dependencies():
        success = False
    
    # Step 2: Setup directories
    setup_directories()
    
    # Step 3: Create sample config
    if not create_sample_config():
        success = False
    
    # Step 4: Test database connection
    if not test_database_connection():
        print("⚠️  Warning: Database connection failed. Check database path.")
        # Don't fail setup for this - database might not be ready yet
    
    # Step 5: Run basic test
    if not run_basic_test():
        success = False
    
    print("=" * 50)
    
    if success:
        print("🎉 Setup completed successfully!")
        print("\nNext steps:")
        print("1. Run: python python/main.py status")
        print("2. Run: python python/main.py validate")
        print("3. Check reports in: reports/validation/")
    else:
        print("❌ Setup completed with errors. Please check the output above.")
        sys.exit(1)


if __name__ == "__main__":
    main()