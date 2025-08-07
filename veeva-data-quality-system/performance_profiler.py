#!/usr/bin/env python3
"""
Veeva Data Quality System - Comprehensive Performance Profiler
Performance optimization analysis for Phase 3 optimization
"""

import sqlite3
import time
import pandas as pd
import cProfile
import pstats
import io
from pathlib import Path
import json
import sys
import os
from contextlib import contextmanager
from typing import Dict, List, Any, Tuple
import psutil
import gc

class PerformanceProfiler:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.results = {
            'database_overview': {},
            'query_performance': {},
            'index_analysis': {},
            'memory_analysis': {},
            'optimization_recommendations': []
        }
    
    @contextmanager
    def get_connection(self):
        """Get database connection with optimal settings"""
        conn = sqlite3.connect(self.db_path)
        # Set optimal SQLite performance parameters
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA cache_size = 10000")
        conn.execute("PRAGMA temp_store = MEMORY")
        conn.execute("PRAGMA mmap_size = 268435456")  # 256MB
        try:
            yield conn
        finally:
            conn.close()
    
    def analyze_database_overview(self):
        """Analyze database size and structure"""
        print("=== DATABASE OVERVIEW ANALYSIS ===")
        
        with self.get_connection() as conn:
            # Get database file size
            db_size = os.path.getsize(self.db_path) / (1024 * 1024)  # MB
            
            # Get table information
            tables_info = {}
            tables_query = """
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
            
            tables = pd.read_sql_query(tables_query, conn)['name'].tolist()
            
            total_records = 0
            for table in tables:
                try:
                    count_query = f"SELECT COUNT(*) as count FROM {table}"
                    count = pd.read_sql_query(count_query, conn).iloc[0]['count']
                    
                    # Get table size estimate
                    size_query = f"SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size() WHERE (SELECT COUNT(*) FROM {table}) > 0"
                    
                    tables_info[table] = {
                        'record_count': count,
                        'size_estimate_mb': 'N/A'  # Simplified for this analysis
                    }
                    total_records += count
                    print(f"{table}: {count:,} records")
                except Exception as e:
                    print(f"Error analyzing table {table}: {e}")
                    tables_info[table] = {'error': str(e)}
            
            self.results['database_overview'] = {
                'file_size_mb': db_size,
                'total_records': total_records,
                'table_count': len(tables),
                'tables': tables_info
            }
            
            print(f"Database size: {db_size:.1f} MB")
            print(f"Total records: {total_records:,}")
    
    def analyze_query_performance(self):
        """Analyze performance of key validation queries"""
        print("\n=== QUERY PERFORMANCE ANALYSIS ===")
        
        # Define test queries (simplified versions of validation queries)
        test_queries = {
            'simple_provider_count': {
                'query': 'SELECT COUNT(*) FROM healthcare_providers',
                'description': 'Simple count query baseline'
            },
            'provider_join_count': {
                'query': '''
                SELECT COUNT(*) 
                FROM healthcare_providers hp 
                JOIN provider_facility_affiliations pfa ON hp.provider_id = pfa.provider_id
                ''',
                'description': 'Basic join performance'
            },
            'affiliation_aggregation': {
                'query': '''
                SELECT 
                    pfa.provider_id,
                    COUNT(pfa.facility_id) as total_affiliations,
                    COUNT(CASE WHEN pfa.is_primary_affiliation = 1 THEN 1 END) as primary_affiliations,
                    COUNT(CASE WHEN pfa.end_date IS NULL THEN 1 END) as active_affiliations
                FROM provider_facility_affiliations pfa
                GROUP BY pfa.provider_id
                HAVING COUNT(pfa.facility_id) > 2
                LIMIT 100
                ''',
                'description': 'Affiliation aggregation (simplified)'
            },
            'npi_validation_check': {
                'query': '''
                SELECT provider_id, npi_number, full_name
                FROM healthcare_providers
                WHERE npi_number IS NULL 
                   OR LENGTH(npi_number) != 10 
                   OR npi_number NOT GLOB '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]'
                LIMIT 100
                ''',
                'description': 'NPI validation pattern matching'
            },
            'complex_name_search': {
                'query': '''
                SELECT provider_id, full_name, first_name, last_name
                FROM healthcare_providers
                WHERE (full_name IS NULL OR TRIM(full_name) = '') 
                   OR (first_name IS NULL AND last_name IS NULL)
                   OR (first_name IS NOT NULL AND full_name NOT LIKE '%' || first_name || '%')
                LIMIT 100
                ''',
                'description': 'Complex name consistency check'
            }
        }
        
        with self.get_connection() as conn:
            query_results = {}
            
            for query_name, query_info in test_queries.items():
                print(f"Testing {query_name}...")
                
                # Warm-up run
                pd.read_sql_query(query_info['query'], conn)
                
                # Actual performance test (3 runs)
                times = []
                for i in range(3):
                    start_time = time.time()
                    try:
                        result = pd.read_sql_query(query_info['query'], conn)
                        execution_time = time.time() - start_time
                        times.append(execution_time)
                        row_count = len(result)
                    except Exception as e:
                        execution_time = time.time() - start_time
                        times.append(execution_time)
                        row_count = 0
                        print(f"  Error in {query_name}: {e}")
                
                avg_time = sum(times) / len(times)
                min_time = min(times)
                max_time = max(times)
                
                query_results[query_name] = {
                    'description': query_info['description'],
                    'avg_execution_time': avg_time,
                    'min_execution_time': min_time,
                    'max_execution_time': max_time,
                    'result_count': row_count,
                    'performance_grade': self._grade_performance(avg_time)
                }
                
                print(f"  Average time: {avg_time:.3f}s (min: {min_time:.3f}s, max: {max_time:.3f}s)")
                print(f"  Results: {row_count} rows")
            
            self.results['query_performance'] = query_results
    
    def analyze_index_effectiveness(self):
        """Analyze index usage and effectiveness"""
        print("\n=== INDEX EFFECTIVENESS ANALYSIS ===")
        
        with self.get_connection() as conn:
            # Get all indexes
            indexes_query = """
            SELECT name, tbl_name, sql 
            FROM sqlite_master 
            WHERE type='index' AND name NOT LIKE 'sqlite_%'
            ORDER BY tbl_name, name
            """
            
            indexes = pd.read_sql_query(indexes_query, conn)
            
            print(f"Total indexes found: {len(indexes)}")
            
            # Analyze index distribution by table
            index_by_table = indexes.groupby('tbl_name').size().to_dict()
            
            # Test query plans for key operations
            query_plan_tests = {
                'provider_lookup_by_id': 'SELECT * FROM healthcare_providers WHERE provider_id = "PROV_SYNTH_000001"',
                'provider_lookup_by_name': 'SELECT * FROM healthcare_providers WHERE full_name LIKE "John%"',
                'affiliation_by_provider': 'SELECT * FROM provider_facility_affiliations WHERE provider_id = "PROV_SYNTH_000001"',
                'affiliation_join': '''
                    SELECT hp.full_name, pfa.facility_id 
                    FROM healthcare_providers hp 
                    JOIN provider_facility_affiliations pfa ON hp.provider_id = pfa.provider_id 
                    LIMIT 10
                '''
            }
            
            query_plans = {}
            for test_name, query in query_plan_tests.items():
                try:
                    plan = pd.read_sql_query(f'EXPLAIN QUERY PLAN {query}', conn)
                    uses_index = any('USING INDEX' in detail for detail in plan['detail'])
                    query_plans[test_name] = {
                        'uses_index': uses_index,
                        'plan': plan['detail'].tolist()
                    }
                except Exception as e:
                    query_plans[test_name] = {'error': str(e)}
            
            self.results['index_analysis'] = {
                'total_indexes': len(indexes),
                'indexes_by_table': index_by_table,
                'query_plans': query_plans
            }
            
            # Print summary
            for table, count in index_by_table.items():
                print(f"{table}: {count} indexes")
    
    def analyze_memory_usage(self):
        """Analyze memory usage patterns"""
        print("\n=== MEMORY USAGE ANALYSIS ===")
        
        process = psutil.Process()
        initial_memory = process.memory_info().rss / (1024 * 1024)  # MB
        
        print(f"Initial memory usage: {initial_memory:.1f} MB")
        
        # Test memory usage with large query
        with self.get_connection() as conn:
            gc.collect()
            
            start_memory = process.memory_info().rss / (1024 * 1024)
            
            # Load larger dataset
            large_query = "SELECT * FROM healthcare_providers LIMIT 10000"
            start_time = time.time()
            df = pd.read_sql_query(large_query, conn)
            query_time = time.time() - start_time
            
            peak_memory = process.memory_info().rss / (1024 * 1024)
            memory_increase = peak_memory - start_memory
            
            # Clean up
            del df
            gc.collect()
            
            final_memory = process.memory_info().rss / (1024 * 1024)
            
            self.results['memory_analysis'] = {
                'initial_memory_mb': initial_memory,
                'peak_memory_mb': peak_memory,
                'memory_increase_mb': memory_increase,
                'final_memory_mb': final_memory,
                'large_query_time': query_time,
                'memory_efficiency': 'GOOD' if memory_increase < 50 else 'NEEDS_OPTIMIZATION'
            }
            
            print(f"Peak memory usage: {peak_memory:.1f} MB (+{memory_increase:.1f} MB)")
            print(f"Large query time: {query_time:.3f} seconds")
    
    def generate_optimization_recommendations(self):
        """Generate specific optimization recommendations"""
        print("\n=== OPTIMIZATION RECOMMENDATIONS ===")
        
        recommendations = []
        
        # Analyze query performance results
        if 'query_performance' in self.results:
            for query_name, metrics in self.results['query_performance'].items():
                if metrics.get('performance_grade') == 'POOR':
                    recommendations.append({
                        'priority': 'HIGH',
                        'category': 'Query Optimization',
                        'issue': f"Slow query performance: {query_name}",
                        'current_time': f"{metrics['avg_execution_time']:.3f}s",
                        'target_time': '<0.1s',
                        'recommendation': f"Optimize {query_name} - consider adding indexes or rewriting query logic"
                    })
        
        # Database size recommendations
        if self.results['database_overview']['file_size_mb'] > 100:
            recommendations.append({
                'priority': 'MEDIUM',
                'category': 'Database Size',
                'issue': f"Large database file: {self.results['database_overview']['file_size_mb']:.1f} MB",
                'recommendation': "Consider implementing data archiving strategy for older records"
            })
        
        # Memory usage recommendations
        if self.results.get('memory_analysis', {}).get('memory_efficiency') == 'NEEDS_OPTIMIZATION':
            recommendations.append({
                'priority': 'MEDIUM',
                'category': 'Memory Usage',
                'issue': f"High memory usage: {self.results['memory_analysis']['memory_increase_mb']:.1f} MB increase",
                'recommendation': "Implement result streaming for large queries, optimize DataFrame operations"
            })
        
        # Index recommendations
        total_indexes = self.results.get('index_analysis', {}).get('total_indexes', 0)
        if total_indexes > 100:
            recommendations.append({
                'priority': 'LOW',
                'category': 'Index Management',
                'issue': f"High number of indexes: {total_indexes}",
                'recommendation': "Review and consolidate indexes to reduce maintenance overhead"
            })
        
        # Add performance-specific recommendations
        recommendations.extend([
            {
                'priority': 'HIGH',
                'category': 'Query Optimization',
                'issue': 'Affiliation anomaly query complexity',
                'recommendation': 'Implement query result caching and optimize GROUP BY operations'
            },
            {
                'priority': 'HIGH',
                'category': 'Database Configuration',
                'issue': 'SQLite performance settings',
                'recommendation': 'Optimize WAL mode, cache size, and mmap settings for concurrent access'
            },
            {
                'priority': 'MEDIUM',
                'category': 'Concurrent Processing',
                'issue': 'Parallel query execution failures',
                'recommendation': 'Implement connection pooling and optimize thread management'
            }
        ])
        
        self.results['optimization_recommendations'] = recommendations
        
        # Print recommendations by priority
        for priority in ['HIGH', 'MEDIUM', 'LOW']:
            priority_recs = [r for r in recommendations if r['priority'] == priority]
            if priority_recs:
                print(f"\n{priority} Priority Recommendations:")
                for i, rec in enumerate(priority_recs, 1):
                    print(f"  {i}. [{rec['category']}] {rec['issue']}")
                    print(f"     → {rec['recommendation']}")
    
    def _grade_performance(self, execution_time: float) -> str:
        """Grade query performance based on execution time"""
        if execution_time < 0.1:
            return 'EXCELLENT'
        elif execution_time < 0.5:
            return 'GOOD'
        elif execution_time < 2.0:
            return 'ACCEPTABLE'
        elif execution_time < 5.0:
            return 'NEEDS_IMPROVEMENT'
        else:
            return 'POOR'
    
    def run_comprehensive_analysis(self) -> Dict[str, Any]:
        """Run complete performance analysis"""
        print("VEEVA DATA QUALITY SYSTEM - PERFORMANCE PROFILER")
        print("=" * 55)
        
        self.analyze_database_overview()
        self.analyze_query_performance()
        self.analyze_index_effectiveness()
        self.analyze_memory_usage()
        self.generate_optimization_recommendations()
        
        return self.results
    
    def save_results(self, output_file: str):
        """Save analysis results to JSON file"""
        with open(output_file, 'w') as f:
            json.dump(self.results, f, indent=2, default=str)
        print(f"\nResults saved to: {output_file}")

def main():
    # Set up paths
    project_root = Path(__file__).parent
    db_path = project_root / "data/database/veeva_opendata.db"
    output_file = project_root / "reports/performance_analysis.json"
    
    if not db_path.exists():
        print(f"Error: Database not found at {db_path}")
        sys.exit(1)
    
    # Create reports directory if it doesn't exist
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Run performance analysis
    profiler = PerformanceProfiler(str(db_path))
    results = profiler.run_comprehensive_analysis()
    profiler.save_results(str(output_file))
    
    # Print executive summary
    print("\n" + "=" * 55)
    print("EXECUTIVE SUMMARY")
    print("=" * 55)
    print(f"Database Size: {results['database_overview']['file_size_mb']:.1f} MB")
    print(f"Total Records: {results['database_overview']['total_records']:,}")
    print(f"Total Indexes: {results.get('index_analysis', {}).get('total_indexes', 0)}")
    
    # Count recommendations by priority
    recs = results.get('optimization_recommendations', [])
    high_priority = len([r for r in recs if r['priority'] == 'HIGH'])
    medium_priority = len([r for r in recs if r['priority'] == 'MEDIUM'])
    
    print(f"High Priority Issues: {high_priority}")
    print(f"Medium Priority Issues: {medium_priority}")
    
    # Performance summary
    query_perfs = results.get('query_performance', {})
    slow_queries = [q for q, m in query_perfs.items() if m.get('avg_execution_time', 0) > 1.0]
    
    if slow_queries:
        print(f"\nSlow Queries (>1s): {len(slow_queries)}")
        for query in slow_queries:
            time_val = query_perfs[query]['avg_execution_time']
            print(f"  - {query}: {time_val:.3f}s")
    
    print(f"\nTarget: All queries <5s (Current status: {'ACHIEVED' if len(slow_queries) == 0 else 'NEEDS_WORK'})")

if __name__ == "__main__":
    main()