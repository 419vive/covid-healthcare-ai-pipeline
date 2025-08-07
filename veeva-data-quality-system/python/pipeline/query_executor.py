"""
SQL Query execution engine for data validation
Executes Claude Code's designed AI-enhanced validation queries
"""

import os
import time
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
import pandas as pd
import logging
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed

from ..utils.database import DatabaseManager, QueryResult
from ..config.pipeline_config import PipelineConfig
from ..utils.query_cache import QueryResultCache, CACHE_CONFIGS


logger = logging.getLogger(__name__)


@dataclass
class ValidationQueryResult:
    """Container for validation query results"""
    rule_name: str
    query_path: str
    result: QueryResult
    severity: str
    enabled: bool
    execution_timestamp: pd.Timestamp
    summary: Optional[Dict[str, Any]] = None


class QueryExecutor:
    """
    SQL Query execution engine that loads and executes 
    Claude Code's AI-enhanced validation queries
    """
    
    def __init__(self, 
                 db_manager: DatabaseManager,
                 config: PipelineConfig,
                 sql_queries_dir: Optional[str] = None,
                 enable_caching: bool = True,
                 performance_monitor=None):
        """
        Initialize query executor
        
        Args:
            db_manager: Database manager instance
            config: Pipeline configuration
            sql_queries_dir: Directory containing SQL query files
            enable_caching: Enable query result caching for performance
            performance_monitor: Performance monitor for tracking query metrics
        """
        self.db_manager = db_manager
        self.config = config
        self.sql_queries_dir = sql_queries_dir or self._get_default_sql_dir()
        self.performance_monitor = performance_monitor
        
        # Initialize query cache for performance optimization
        if enable_caching:
            cache_dir = Path(self.sql_queries_dir).parent / "cache"
            self.query_cache = QueryResultCache(
                cache_dir=str(cache_dir),
                default_ttl_minutes=60,
                max_memory_entries=50
            )
        else:
            self.query_cache = None
        
        # Load validation queries
        self.validation_queries = self._load_validation_queries()
        
        # Load optimized queries if available
        self._load_optimized_queries()
        
        logger.info(f"QueryExecutor initialized with {len(self.validation_queries)} validation queries (caching: {enable_caching})")
    
    def _get_default_sql_dir(self) -> str:
        """Get default SQL queries directory"""
        project_root = Path(__file__).parent.parent.parent
        return str(project_root / "sql")
    
    def _load_validation_queries(self) -> Dict[str, str]:
        """Load validation queries from SQL files"""
        queries = {}
        
        # Load queries from validation directory
        validation_dir = Path(self.sql_queries_dir) / "02_validation"
        
        if not validation_dir.exists():
            logger.warning(f"Validation queries directory not found: {validation_dir}")
            return queries
        
        # Load AI-enhanced validation queries
        ai_queries_file = validation_dir / "ai_enhanced_validation_queries.sql"
        if ai_queries_file.exists():
            logger.info(f"Loading AI-enhanced validation queries from: {ai_queries_file}")
            queries.update(self._parse_sql_file(ai_queries_file))
        
        # Load other validation query files
        for sql_file in validation_dir.glob("*.sql"):
            if sql_file.name != "ai_enhanced_validation_queries.sql":
                logger.info(f"Loading validation queries from: {sql_file}")
                queries.update(self._parse_sql_file(sql_file))
        
        logger.info(f"Loaded {len(queries)} validation queries total")
        return queries
    
    def _parse_sql_file(self, file_path: Path) -> Dict[str, str]:
        """
        Parse SQL file and extract individual queries
        Expects queries to be separated by specific comment patterns
        """
        queries = {}
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # For the AI-enhanced queries, extract individual query blocks
            if "ai_enhanced_validation_queries.sql" in file_path.name:
                queries = self._extract_ai_enhanced_queries(content, file_path)
            else:
                # For other files, treat the entire content as one query
                query_name = file_path.stem.replace("_checks", "").replace("_", "_")
                queries[query_name] = content
        
        except Exception as e:
            logger.error(f"Error parsing SQL file {file_path}: {e}")
        
        return queries
    
    def _extract_ai_enhanced_queries(self, content: str, file_path: Path) -> Dict[str, str]:
        """Extract individual AI-enhanced queries from the SQL file"""
        queries = {}
        
        # Split content by query separators (looking for "Query N:" patterns)
        sections = content.split("-- Query ")
        
        if len(sections) <= 1:
            # If no query separators found, try different patterns
            sections = content.split("-- =====")
            if len(sections) <= 1:
                # Fallback: treat as single query
                queries["ai_enhanced_validation"] = content
                return queries
        
        for i, section in enumerate(sections[1:], 1):  # Skip first empty section
            lines = section.strip().split('\n')
            
            # Extract query name from first line
            if lines:
                first_line = lines[0].strip()
                # Try to extract a meaningful name
                if ':' in first_line:
                    # Get the part after the colon
                    query_name_part = first_line.split(':', 1)[1].strip()
                    # Clean up the name
                    query_name = query_name_part.lower().replace(' ', '_').replace('-', '_')
                else:
                    query_name = f"validation_{i:02d}"
                
                # Extract the actual SQL (skip header and comment lines)
                sql_lines = []
                in_sql = False
                
                for line in lines[1:]:  # Skip the first line (it's the header)
                    line_stripped = line.strip()
                    if line_stripped.startswith('--'):
                        if in_sql:  # Include inline comments if we're in SQL
                            sql_lines.append(line)
                        continue  # Skip leading comments
                    elif line_stripped and not in_sql:
                        in_sql = True  # Start of SQL content
                    
                    if in_sql:
                        sql_lines.append(line)
                
                if sql_lines:
                    queries[query_name] = '\n'.join(sql_lines).strip()
        
        logger.info(f"Extracted {len(queries)} AI-enhanced queries from {file_path}")
        return queries
    
    def _load_optimized_queries(self):
        """Load performance-optimized queries if available"""
        optimized_dir = Path(self.sql_queries_dir) / "02_validation"
        optimized_file = optimized_dir / "optimized_validation_queries.sql"
        
        if optimized_file.exists():
            logger.info(f"Loading optimized validation queries from: {optimized_file}")
            optimized_queries = self._parse_sql_file(optimized_file)
            
            # Replace existing queries with optimized versions
            for query_name, query_sql in optimized_queries.items():
                if query_name in self.validation_queries:
                    logger.info(f"Replacing query with optimized version: {query_name}")
                    self.validation_queries[query_name] = query_sql
                else:
                    self.validation_queries[query_name] = query_sql
            
            logger.info(f"Loaded {len(optimized_queries)} optimized queries")
        else:
            logger.info("No optimized queries found - using standard queries")
    
    def execute_single_query(self, rule_name: str) -> Optional[ValidationQueryResult]:
        """
        Execute a single validation query by name
        
        Args:
            rule_name: Name of the validation rule/query to execute
            
        Returns:
            ValidationQueryResult or None if query not found
        """
        if rule_name not in self.validation_queries:
            logger.error(f"Validation query not found: {rule_name}")
            return None
        
        # Check if rule is enabled in configuration
        rule_config = self.config.get_validation_rule_config(rule_name)
        enabled = rule_config.enabled if rule_config else True
        severity = rule_config.severity if rule_config else "MEDIUM"
        
        if not enabled:
            logger.info(f"Skipping disabled validation rule: {rule_name}")
            return ValidationQueryResult(
                rule_name=rule_name,
                query_path="",
                result=QueryResult(
                    data=pd.DataFrame(),
                    execution_time=0,
                    row_count=0,
                    columns=[],
                    query="",
                    success=True,
                    error_message="Rule disabled in configuration"
                ),
                severity=severity,
                enabled=False,
                execution_timestamp=pd.Timestamp.now()
            )
        
        logger.info(f"Executing validation query: {rule_name}")
        
        # Check cache first if caching is enabled
        query_sql = self.validation_queries[rule_name]
        
        if self.query_cache:
            cached_result = self.query_cache.get(rule_name, query_sql)
            if cached_result:
                logger.info(f"Using cached result for {rule_name}")
                result = QueryResult(
                    data=cached_result.result_data,
                    execution_time=0.001,  # Cache retrieval time
                    row_count=cached_result.row_count,
                    columns=cached_result.result_data.columns.tolist(),
                    query=query_sql,
                    success=True
                )
            else:
                # Execute the query and cache result
                result = self.db_manager.execute_query(query_sql)
                if result.success and result.row_count < 50000:  # Don't cache huge results
                    cache_config = CACHE_CONFIGS.get(rule_name, {})
                    ttl_minutes = cache_config.get('ttl_minutes')
                    self.query_cache.set(
                        rule_name=rule_name,
                        query_sql=query_sql,
                        result_data=result.data,
                        execution_time=result.execution_time,
                        ttl_minutes=ttl_minutes
                    )
        else:
            # Execute the query without caching
            result = self.db_manager.execute_query(query_sql)
        
        # Track performance metrics if monitor is available
        if self.performance_monitor and result:
            cache_hit = False
            if self.query_cache:
                cached_result = self.query_cache.get(rule_name, query_sql)
                cache_hit = cached_result is not None
            
            self.performance_monitor.track_query_performance(
                query_name=rule_name,
                execution_time=result.execution_time,
                row_count=result.row_count,
                cache_hit=cache_hit,
                error_message=result.error_message if not result.success else None
            )
        
        # Create validation result
        validation_result = ValidationQueryResult(
            rule_name=rule_name,
            query_path=self.sql_queries_dir,
            result=result,
            severity=severity,
            enabled=enabled,
            execution_timestamp=pd.Timestamp.now()
        )
        
        # Generate summary if query succeeded
        if result.success and result.row_count > 0:
            validation_result.summary = self._generate_query_summary(result.data, rule_name)
        
        logger.info(f"Query {rule_name} completed: {result.row_count} violations found in {result.execution_time:.2f}s")
        
        return validation_result
    
    def execute_all_queries(self, parallel: bool = True) -> Dict[str, ValidationQueryResult]:
        """
        Execute all validation queries
        
        Args:
            parallel: Whether to execute queries in parallel
            
        Returns:
            Dictionary of rule names to ValidationQueryResult objects
        """
        logger.info(f"Starting execution of {len(self.validation_queries)} validation queries")
        start_time = time.time()
        
        if parallel and len(self.validation_queries) > 1:
            results = self._execute_queries_parallel()
        else:
            results = self._execute_queries_sequential()
        
        total_time = time.time() - start_time
        successful_queries = sum(1 for r in results.values() if r.result.success)
        total_violations = sum(r.result.row_count for r in results.values() if r.result.success)
        
        logger.info(f"Query execution completed: {successful_queries}/{len(results)} successful, "
                   f"{total_violations} total violations found in {total_time:.2f}s")
        
        return results
    
    def _execute_queries_sequential(self) -> Dict[str, ValidationQueryResult]:
        """Execute queries sequentially"""
        results = {}
        
        for rule_name in self.validation_queries:
            result = self.execute_single_query(rule_name)
            if result:
                results[rule_name] = result
        
        return results
    
    def _execute_queries_parallel(self) -> Dict[str, ValidationQueryResult]:
        """Execute queries in parallel"""
        results = {}
        max_workers = self.config.performance.max_workers
        
        logger.info(f"Executing queries in parallel with {max_workers} workers")
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all queries
            future_to_rule = {
                executor.submit(self.execute_single_query, rule_name): rule_name
                for rule_name in self.validation_queries
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_rule):
                rule_name = future_to_rule[future]
                try:
                    result = future.result()
                    if result:
                        results[rule_name] = result
                except Exception as e:
                    logger.error(f"Query {rule_name} failed with exception: {e}")
                    # Create error result
                    results[rule_name] = ValidationQueryResult(
                        rule_name=rule_name,
                        query_path=self.sql_queries_dir,
                        result=QueryResult(
                            data=pd.DataFrame(),
                            execution_time=0,
                            row_count=0,
                            columns=[],
                            query="",
                            success=False,
                            error_message=str(e)
                        ),
                        severity="ERROR",
                        enabled=True,
                        execution_timestamp=pd.Timestamp.now()
                    )
        
        return results
    
    def _generate_query_summary(self, df: pd.DataFrame, rule_name: str) -> Dict[str, Any]:
        """Generate summary statistics for query results"""
        summary = {
            "total_violations": len(df),
            "rule_name": rule_name
        }
        
        # Add severity distribution if available
        if 'severity_level' in df.columns:
            severity_counts = df['severity_level'].value_counts().to_dict()
            summary["severity_distribution"] = severity_counts
            summary["critical_violations"] = severity_counts.get("CRITICAL", 0)
            summary["high_violations"] = severity_counts.get("HIGH", 0)
        
        # Add confidence distribution if available  
        if 'confidence_level' in df.columns:
            confidence_counts = df['confidence_level'].value_counts().to_dict()
            summary["confidence_distribution"] = confidence_counts
        
        # Add entity information if available
        if 'entity_id' in df.columns:
            summary["unique_entities_affected"] = df['entity_id'].nunique()
        
        if 'provider_id' in df.columns:
            summary["unique_providers_affected"] = df['provider_id'].nunique()
        
        if 'facility_id' in df.columns:
            summary["unique_facilities_affected"] = df['facility_id'].nunique()
        
        # Add top violations if available
        if len(df) > 0:
            summary["sample_violations"] = df.head(5).to_dict('records')
        
        return summary
    
    def get_cache_statistics(self) -> Optional[Dict[str, Any]]:
        """Get query cache performance statistics"""
        if self.query_cache:
            return self.query_cache.get_statistics()
        return None
    
    def clear_cache(self, rule_name: Optional[str] = None):
        """Clear query cache"""
        if self.query_cache:
            if rule_name:
                self.query_cache.invalidate_rule(rule_name)
            else:
                self.query_cache.clear_all()
    
    def optimize_cache(self):
        """Optimize query cache performance"""
        if self.query_cache:
            self.query_cache.optimize_cache()
    
    def get_query_catalog(self) -> List[Dict[str, Any]]:
        """Get catalog of available validation queries"""
        catalog = []
        
        for rule_name in self.validation_queries:
            rule_config = self.config.get_validation_rule_config(rule_name)
            
            catalog.append({
                "rule_name": rule_name,
                "enabled": rule_config.enabled if rule_config else True,
                "severity": rule_config.severity if rule_config else "MEDIUM",
                "query_length": len(self.validation_queries[rule_name]),
                "description": self._extract_query_description(rule_name)
            })
        
        return catalog
    
    def _extract_query_description(self, rule_name: str) -> str:
        """Extract description from query comments"""
        query_sql = self.validation_queries.get(rule_name, "")
        lines = query_sql.split('\n')
        
        # Look for description in comments
        for line in lines[:10]:  # Check first 10 lines
            if line.strip().startswith('--') and ('purpose' in line.lower() or 'description' in line.lower()):
                return line.strip('- ').strip()
        
        # Fallback to rule name formatting
        return rule_name.replace('_', ' ').title()
    
    def export_query_results(self, 
                           results: Dict[str, ValidationQueryResult], 
                           output_dir: str,
                           formats: List[str] = None) -> Dict[str, str]:
        """
        Export query results to various formats
        
        Args:
            results: Dictionary of validation results
            output_dir: Output directory path
            formats: List of formats to export ('xlsx', 'csv', 'json')
            
        Returns:
            Dictionary of format to file path mappings
        """
        formats = formats or ['xlsx', 'csv']
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        exported_files = {}
        
        # Combine all results into summary DataFrame
        all_violations = []
        
        for rule_name, validation_result in results.items():
            if validation_result.result.success and validation_result.result.row_count > 0:
                df = validation_result.result.data.copy()
                df['validation_rule'] = rule_name
                df['severity'] = validation_result.severity
                df['execution_time'] = validation_result.result.execution_time
                df['check_timestamp'] = validation_result.execution_timestamp
                all_violations.append(df)
        
        if all_violations:
            combined_df = pd.concat(all_violations, ignore_index=True)
        else:
            combined_df = pd.DataFrame()
        
        timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
        
        # Export in requested formats
        for format_type in formats:
            if format_type == 'xlsx':
                file_path = output_dir / f"validation_results_{timestamp}.xlsx"
                with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                    # Summary sheet
                    summary_df = self._create_summary_dataframe(results)
                    summary_df.to_excel(writer, sheet_name='Summary', index=False)
                    
                    # Combined violations
                    if not combined_df.empty:
                        combined_df.to_excel(writer, sheet_name='All_Violations', index=False)
                    
                    # Individual rule results
                    for rule_name, validation_result in results.items():
                        if validation_result.result.success and validation_result.result.row_count > 0:
                            sheet_name = rule_name[:31]  # Excel sheet name limit
                            validation_result.result.data.to_excel(writer, sheet_name=sheet_name, index=False)
                
                exported_files['xlsx'] = str(file_path)
            
            elif format_type == 'csv':
                file_path = output_dir / f"validation_results_{timestamp}.csv"
                if not combined_df.empty:
                    combined_df.to_csv(file_path, index=False)
                else:
                    # Create empty CSV with headers
                    pd.DataFrame({"message": ["No violations found"]}).to_csv(file_path, index=False)
                
                exported_files['csv'] = str(file_path)
            
            elif format_type == 'json':
                file_path = output_dir / f"validation_results_{timestamp}.json"
                export_data = {
                    "execution_timestamp": pd.Timestamp.now().isoformat(),
                    "summary": self._create_summary_dict(results),
                    "results": {
                        rule_name: {
                            "rule_name": rule_name,
                            "severity": validation_result.severity,
                            "enabled": validation_result.enabled,
                            "success": validation_result.result.success,
                            "violation_count": validation_result.result.row_count,
                            "execution_time": validation_result.result.execution_time,
                            "violations": validation_result.result.data.to_dict('records') if validation_result.result.success else []
                        }
                        for rule_name, validation_result in results.items()
                    }
                }
                
                with open(file_path, 'w') as f:
                    import json
                    json.dump(export_data, f, indent=2, default=str)
                
                exported_files['json'] = str(file_path)
        
        logger.info(f"Query results exported to: {list(exported_files.values())}")
        return exported_files
    
    def _create_summary_dataframe(self, results: Dict[str, ValidationQueryResult]) -> pd.DataFrame:
        """Create summary DataFrame from validation results"""
        summary_data = []
        
        for rule_name, validation_result in results.items():
            summary_data.append({
                "rule_name": rule_name,
                "enabled": validation_result.enabled,
                "severity": validation_result.severity,
                "success": validation_result.result.success,
                "violation_count": validation_result.result.row_count,
                "execution_time_seconds": validation_result.result.execution_time,
                "execution_timestamp": validation_result.execution_timestamp,
                "error_message": validation_result.result.error_message or ""
            })
        
        return pd.DataFrame(summary_data)
    
    def _create_summary_dict(self, results: Dict[str, ValidationQueryResult]) -> Dict[str, Any]:
        """Create summary dictionary from validation results"""
        total_queries = len(results)
        successful_queries = sum(1 for r in results.values() if r.result.success)
        total_violations = sum(r.result.row_count for r in results.values() if r.result.success)
        
        severity_counts = {}
        for validation_result in results.values():
            if validation_result.result.success:
                severity = validation_result.severity
                severity_counts[severity] = severity_counts.get(severity, 0) + validation_result.result.row_count
        
        summary = {
            "total_queries": total_queries,
            "successful_queries": successful_queries,
            "failed_queries": total_queries - successful_queries,
            "total_violations": total_violations,
            "severity_distribution": severity_counts
        }
        
        # Add cache statistics if available
        if self.query_cache:
            cache_stats = self.query_cache.get_statistics()
            summary["cache_performance"] = {
                "hit_rate": cache_stats.get("hit_rate", 0),
                "total_hits": cache_stats.get("hits", 0),
                "memory_entries": cache_stats.get("memory_entries", 0),
                "disk_entries": cache_stats.get("disk_entries", 0)
            }
        
        return summary