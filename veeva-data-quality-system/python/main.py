#!/usr/bin/env python3
"""
Veeva Data Quality System - Main Command Line Interface
Author: Cursor (based on Claude Code architecture)
Created: 2025-08-07
"""

import os
import sys
import click
import json
from pathlib import Path
from typing import Optional, List
from datetime import datetime
import pandas as pd

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from python.config.database_config import DatabaseConfig
from python.config.pipeline_config import PipelineConfig
from python.utils.database import DatabaseManager
from python.utils.logging_config import setup_logging, get_logger, log_system_info
from python.utils.monitoring import SystemMonitor, create_monitoring_dashboard
from python.pipeline.query_executor import QueryExecutor


# Initialize logging
logger = get_logger('main')


@click.group()
@click.option('--config', '-c', type=click.Path(exists=True), 
              help='Path to configuration file')
@click.option('--log-level', '-l', default='INFO',
              type=click.Choice(['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']),
              help='Logging level')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose output')
@click.pass_context
def cli(ctx, config, log_level, verbose):
    """
    Veeva Data Quality System - AI-Enhanced Healthcare Data Validation
    
    This system implements Claude Code's designed architecture for comprehensive
    healthcare provider data quality monitoring and validation.
    """
    # Ensure the context object exists
    ctx.ensure_object(dict)
    
    # Setup logging
    log_file = "logs/veeva_dq.log"
    setup_logging(
        log_level=log_level,
        log_file=log_file,
        console_output=True
    )
    
    if verbose:
        log_system_info()
    
    # Load configuration
    try:
        pipeline_config = PipelineConfig(config) if config else PipelineConfig()
        db_config = DatabaseConfig.from_env()
        
        # Store in context
        ctx.obj['pipeline_config'] = pipeline_config
        ctx.obj['db_config'] = db_config
        
        logger.info("Veeva Data Quality System initialized")
        
    except Exception as e:
        logger.error(f"Failed to initialize system: {e}")
        sys.exit(1)


@cli.command()
@click.pass_context
def status(ctx):
    """Check system status and database connectivity"""
    logger.info("Checking system status...")
    
    try:
        db_config = ctx.obj['db_config']
        db_manager = DatabaseManager(db_config)
        
        # Database health check
        health_status = db_manager.health_check()
        
        click.echo("=== Veeva Data Quality System Status ===")
        click.echo(f"Database Path: {db_config.db_path}")
        click.echo(f"Database Accessible: {'✅ Yes' if health_status['database_accessible'] else '❌ No'}")
        click.echo(f"Overall Status: {health_status['overall_status']}")
        
        if health_status.get('performance_test'):
            perf = health_status['performance_test']
            click.echo(f"Query Performance: {perf['query_time']:.2f}s ({'✅ Good' if perf['acceptable'] else '⚠️  Slow'})")
        
        # Table information
        overview = db_manager.get_database_overview()
        click.echo(f"\n=== Database Overview ===")
        click.echo(f"Total Records: {overview.get('total_records', 0):,}")
        
        for table_name, table_info in overview.get('tables', {}).items():
            row_count = table_info.get('row_count', 0)
            click.echo(f"  {table_name}: {row_count:,} records")
        
        logger.info("Status check completed successfully")
        
    except Exception as e:
        logger.error(f"Status check failed: {e}")
        click.echo(f"❌ Error: {e}")
        sys.exit(1)


@cli.command()
@click.option('--rule', '-r', multiple=True, help='Specific validation rule to run')
@click.option('--parallel', '-p', is_flag=True, default=True, help='Run queries in parallel')
@click.option('--output-dir', '-o', default='reports/validation',
              help='Output directory for results')
@click.option('--format', '-f', 'formats', multiple=True, 
              type=click.Choice(['xlsx', 'csv', 'json']),
              default=['xlsx'], help='Output format(s)')
@click.pass_context
def validate(ctx, rule, parallel, output_dir, formats):
    """
    Run AI-enhanced data validation queries
    
    This executes Claude Code's designed validation queries to identify
    data quality issues in the healthcare provider database.
    """
    logger.info("Starting data validation process...")
    
    try:
        db_config = ctx.obj['db_config']
        pipeline_config = ctx.obj['pipeline_config']
        
        db_manager = DatabaseManager(db_config)
        query_executor = QueryExecutor(db_manager, pipeline_config)
        
        # Show available queries if none specified
        if not rule:
            catalog = query_executor.get_query_catalog()
            click.echo("=== Available Validation Rules ===")
            for query_info in catalog:
                status_icon = "✅" if query_info['enabled'] else "❌"
                click.echo(f"{status_icon} {query_info['rule_name']} ({query_info['severity']})")
            
            if not click.confirm("\nRun all enabled validation queries?"):
                return
        
        # Execute validation queries
        if rule:
            # Execute specific rules
            results = {}
            for rule_name in rule:
                result = query_executor.execute_single_query(rule_name)
                if result:
                    results[rule_name] = result
        else:
            # Execute all queries
            results = query_executor.execute_all_queries(parallel=parallel)
        
        # Display results summary
        click.echo("\n=== Validation Results Summary ===")
        total_violations = 0
        critical_issues = 0
        
        for rule_name, validation_result in results.items():
            if validation_result.result.success:
                violation_count = validation_result.result.row_count
                total_violations += violation_count
                
                if validation_result.severity == 'CRITICAL':
                    critical_issues += violation_count
                
                severity_icon = {
                    'CRITICAL': '🔴',
                    'HIGH': '🟡', 
                    'MEDIUM': '🟠',
                    'LOW': '🔵'
                }.get(validation_result.severity, '⚪')
                
                click.echo(f"{severity_icon} {rule_name}: {violation_count} violations ({validation_result.result.execution_time:.2f}s)")
            else:
                click.echo(f"❌ {rule_name}: Failed - {validation_result.result.error_message}")
        
        click.echo(f"\nTotal Violations Found: {total_violations}")
        if critical_issues > 0:
            click.echo(f"🚨 Critical Issues: {critical_issues}")
        
        # Export results
        if results:
            exported_files = query_executor.export_query_results(
                results, output_dir, list(formats)
            )
            
            click.echo(f"\n=== Results Exported ===")
            for format_type, file_path in exported_files.items():
                click.echo(f"📄 {format_type.upper()}: {file_path}")
        
        logger.info(f"Validation completed: {total_violations} total violations found")
        
    except Exception as e:
        logger.error(f"Validation failed: {e}")
        click.echo(f"❌ Validation Error: {e}")
        sys.exit(1)


@cli.command()
@click.pass_context
def catalog(ctx):
    """List all available validation rules and their status"""
    try:
        db_config = ctx.obj['db_config']
        pipeline_config = ctx.obj['pipeline_config']
        
        db_manager = DatabaseManager(db_config)
        query_executor = QueryExecutor(db_manager, pipeline_config)
        
        catalog = query_executor.get_query_catalog()
        
        click.echo("=== Validation Rules Catalog ===")
        click.echo(f"{'Status':<8} {'Rule Name':<40} {'Severity':<10} {'Description'}")
        click.echo("-" * 80)
        
        for query_info in catalog:
            status_icon = "✅ ON " if query_info['enabled'] else "❌ OFF"
            rule_name = query_info['rule_name'][:38]
            severity = query_info['severity']
            description = query_info['description'][:25] + "..." if len(query_info['description']) > 25 else query_info['description']
            
            click.echo(f"{status_icon:<8} {rule_name:<40} {severity:<10} {description}")
        
        enabled_count = sum(1 for q in catalog if q['enabled'])
        click.echo(f"\nTotal Rules: {len(catalog)} | Enabled: {enabled_count}")
        
    except Exception as e:
        logger.error(f"Catalog failed: {e}")
        click.echo(f"❌ Error: {e}")


@cli.command()
@click.option('--optimize', '-opt', is_flag=True, help='Run database optimization')
@click.pass_context  
def maintenance(ctx, optimize):
    """Perform database maintenance tasks"""
    logger.info("Starting maintenance tasks...")
    
    try:
        db_config = ctx.obj['db_config']
        db_manager = DatabaseManager(db_config)
        
        if optimize:
            click.echo("Running database optimization...")
            results = db_manager.optimize_database()
            
            for operation, result in results.items():
                if result['status'] == 'SUCCESS':
                    click.echo(f"✅ {operation}: {result['execution_time']:.2f}s")
                else:
                    click.echo(f"❌ {operation}: {result['error']}")
        
        # Health check
        click.echo("\nRunning health check...")
        health_status = db_manager.health_check()
        click.echo(f"Overall Status: {health_status['overall_status']}")
        
        logger.info("Maintenance completed")
        
    except Exception as e:
        logger.error(f"Maintenance failed: {e}")
        click.echo(f"❌ Maintenance Error: {e}")


@cli.command()
@click.option('--output', '-o', default='config/current_config.yaml',
              help='Output path for configuration')
@click.pass_context
def config_export(ctx, output):
    """Export current configuration to file"""
    try:
        pipeline_config = ctx.obj['pipeline_config']
        
        # Ensure output directory exists
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        pipeline_config.save_config(str(output_path))
        click.echo(f"✅ Configuration exported to: {output_path}")
        
    except Exception as e:
        logger.error(f"Config export failed: {e}")
        click.echo(f"❌ Export Error: {e}")


@cli.command()
@click.option('--sample-size', '-n', default=10, help='Number of sample records to show')
@click.option('--table', '-t', type=click.Choice(['providers', 'facilities', 'affiliations']),
              default='providers', help='Table to explore')
@click.pass_context
def explore(ctx, sample_size, table):
    """Explore database content with sample data"""
    try:
        db_config = ctx.obj['db_config']
        db_manager = DatabaseManager(db_config)
        
        table_mapping = {
            'providers': 'healthcare_providers',
            'facilities': 'healthcare_facilities',
            'affiliations': 'provider_facility_affiliations'
        }
        
        table_name = table_mapping[table]
        
        query = f"SELECT * FROM {table_name} LIMIT {sample_size}"
        result = db_manager.execute_query(query)
        
        if result.success:
            click.echo(f"=== Sample Data from {table_name} ===")
            click.echo(f"Total columns: {len(result.columns)}")
            click.echo(f"Sample size: {len(result.data)} records")
            click.echo("\nColumn names:")
            for i, col in enumerate(result.columns, 1):
                click.echo(f"  {i:2d}. {col}")
            
            # Show first few records in a readable format
            if not result.data.empty:
                click.echo(f"\nFirst {min(3, len(result.data))} records:")
                for idx, row in result.data.head(3).iterrows():
                    click.echo(f"\n--- Record {idx + 1} ---")
                    for col in result.columns[:10]:  # Limit to first 10 columns
                        value = str(row[col])[:50] + "..." if len(str(row[col])) > 50 else str(row[col])
                        click.echo(f"  {col}: {value}")
                    if len(result.columns) > 10:
                        click.echo(f"  ... and {len(result.columns) - 10} more columns")
        else:
            click.echo(f"❌ Failed to query {table_name}: {result.error_message}")
            
    except Exception as e:
        logger.error(f"Explore failed: {e}")
        click.echo(f"❌ Explore Error: {e}")


@cli.command()
@click.option('--dashboard', is_flag=True, help='Generate HTML monitoring dashboard')
@click.option('--summary', is_flag=True, default=True, help='Show metrics summary')
@click.option('--hours', default=24, help='Hours of history to show in summary')
@click.option('--output', '-o', default='reports/monitoring_dashboard.html', 
              help='Output file for dashboard')
@click.pass_context
def monitor(ctx, dashboard, summary, hours, output):
    """System monitoring and health metrics"""
    try:
        db_config = ctx.obj['db_config']
        monitor = SystemMonitor(db_config.db_path)
        
        # Show current system health
        click.echo("=== System Health Status ===")
        health_status = monitor.get_system_health_status()
        
        status_color = {'HEALTHY': 'green', 'WARNING': 'yellow', 'CRITICAL': 'red'}
        click.echo(f"Overall Status: {health_status['overall_status']}", 
                  color=status_color.get(health_status['overall_status']))
        
        if health_status['issues']:
            click.echo("\n🚨 Issues:")
            for issue in health_status['issues']:
                click.echo(f"  • {issue}")
        
        if health_status['warnings']:
            click.echo("\n⚠️  Warnings:")
            for warning in health_status['warnings']:
                click.echo(f"  • {warning}")
        
        # Store current metrics
        system_metrics = monitor.collect_system_metrics()
        database_metrics = monitor.collect_database_metrics()
        
        if system_metrics and database_metrics:
            monitor.store_metrics(system_metrics, database_metrics)
            logger.info("Current metrics stored successfully")
        
        # Show summary if requested
        if summary:
            click.echo(f"\n=== {hours}-Hour Metrics Summary ===")
            metrics_summary = monitor.get_metrics_summary(hours)
            
            if 'system' in metrics_summary:
                sys_metrics = metrics_summary['system']
                click.echo(f"CPU Usage: {sys_metrics.get('avg_cpu_percent', 0):.1f}% avg, {sys_metrics.get('max_cpu_percent', 0):.1f}% peak")
                click.echo(f"Memory Usage: {sys_metrics.get('avg_memory_percent', 0):.1f}% avg, {sys_metrics.get('max_memory_percent', 0):.1f}% peak")
                click.echo(f"Minimum Disk Free: {sys_metrics.get('min_disk_free_gb', 0):.1f} GB")
            
            if 'database' in metrics_summary:
                db_metrics = metrics_summary['database']
                click.echo(f"Database Size: {db_metrics.get('avg_size_mb', 0):.1f} MB average")
                click.echo(f"Query Performance: {db_metrics.get('avg_query_time_ms', 0):.1f}ms avg, {db_metrics.get('max_query_time_ms', 0):.1f}ms peak")
                click.echo(f"Total Records: {db_metrics.get('avg_total_records', 0):,} average")
        
        # Generate dashboard if requested
        if dashboard:
            Path(output).parent.mkdir(parents=True, exist_ok=True)
            dashboard_file = create_monitoring_dashboard(monitor, output)
            if dashboard_file:
                click.echo(f"\n📊 Monitoring dashboard generated: {dashboard_file}")
                if sys.platform == 'darwin':  # macOS
                    click.echo(f"Open with: open {dashboard_file}")
                else:
                    click.echo(f"Open in browser: file://{Path(dashboard_file).absolute()}")
            else:
                click.echo("❌ Failed to generate monitoring dashboard")
        
        # Cleanup old metrics
        monitor.cleanup_old_metrics()
        
    except Exception as e:
        logger.error(f"Monitoring failed: {e}")
        click.echo(f"❌ Monitoring Error: {e}")


if __name__ == '__main__':
    cli()