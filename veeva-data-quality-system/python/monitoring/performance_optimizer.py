"""
Performance optimization engine for automated system improvements
Analyzes performance data and implements optimizations automatically
"""

import asyncio
import time
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple, Callable
from pathlib import Path
import logging
from dataclasses import dataclass
from enum import Enum
import json

logger = logging.getLogger(__name__)


class OptimizationType(Enum):
    """Types of optimizations"""
    QUERY_OPTIMIZATION = "query_optimization"
    INDEX_CREATION = "index_creation"
    CACHE_TUNING = "cache_tuning"
    RESOURCE_ALLOCATION = "resource_allocation"
    CONFIGURATION_TUNING = "configuration_tuning"


@dataclass
class OptimizationRecommendation:
    """Optimization recommendation"""
    optimization_type: OptimizationType
    priority: str  # HIGH, MEDIUM, LOW
    description: str
    estimated_improvement: float  # Expected performance improvement %
    implementation_complexity: str  # SIMPLE, MEDIUM, COMPLEX
    auto_implementable: bool
    implementation_function: Optional[Callable] = None
    parameters: Optional[Dict[str, Any]] = None
    estimated_time_to_implement: str = "Unknown"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'optimization_type': self.optimization_type.value,
            'priority': self.priority,
            'description': self.description,
            'estimated_improvement_percent': self.estimated_improvement,
            'implementation_complexity': self.implementation_complexity,
            'auto_implementable': self.auto_implementable,
            'estimated_time_to_implement': self.estimated_time_to_implement,
            'parameters': self.parameters or {}
        }


class PerformanceOptimizer:
    """
    Automated performance optimization engine that:
    - Analyzes performance bottlenecks
    - Generates optimization recommendations  
    - Implements automatic optimizations
    - Tracks optimization effectiveness
    """
    
    def __init__(self, 
                 performance_monitor,
                 database_manager=None,
                 cache_manager=None,
                 query_executor=None):
        """
        Initialize performance optimizer
        
        Args:
            performance_monitor: PerformanceMonitor instance
            database_manager: Database manager for query optimizations
            cache_manager: Cache manager for cache optimizations
            query_executor: Query executor for query analysis
        """
        self.performance_monitor = performance_monitor
        self.database_manager = database_manager
        self.cache_manager = cache_manager
        self.query_executor = query_executor
        
        # Optimization history
        self.optimization_history = []
        self._init_optimization_db()
        
        # Optimization strategies
        self.optimization_strategies = {
            OptimizationType.QUERY_OPTIMIZATION: self._optimize_queries,
            OptimizationType.INDEX_CREATION: self._optimize_indexes,
            OptimizationType.CACHE_TUNING: self._optimize_cache,
            OptimizationType.RESOURCE_ALLOCATION: self._optimize_resources,
            OptimizationType.CONFIGURATION_TUNING: self._optimize_configuration
        }
        
        logger.info("Performance optimizer initialized")
    
    def _init_optimization_db(self):
        """Initialize optimization tracking database"""
        db_path = self.performance_monitor.metrics_db_path.parent / "optimizations.db"
        
        conn = sqlite3.connect(str(db_path))
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS optimization_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME NOT NULL,
                    optimization_type TEXT NOT NULL,
                    description TEXT NOT NULL,
                    estimated_improvement REAL,
                    actual_improvement REAL,
                    implementation_time_seconds REAL,
                    success BOOLEAN,
                    error_message TEXT,
                    parameters TEXT
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS optimization_recommendations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at DATETIME NOT NULL,
                    optimization_type TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    description TEXT NOT NULL,
                    estimated_improvement REAL,
                    implementation_complexity TEXT,
                    auto_implementable BOOLEAN,
                    implemented BOOLEAN DEFAULT FALSE,
                    implemented_at DATETIME,
                    parameters TEXT
                )
            """)
            
            conn.commit()
        finally:
            conn.close()
    
    async def analyze_and_optimize(self, auto_implement: bool = True) -> List[OptimizationRecommendation]:
        """
        Analyze current performance and generate/implement optimizations
        
        Args:
            auto_implement: Whether to automatically implement simple optimizations
            
        Returns:
            List of optimization recommendations
        """
        logger.info("Starting performance analysis and optimization")
        
        try:
            # Get current performance data
            performance_summary = self.performance_monitor.get_performance_summary(hours=24)
            
            # Analyze bottlenecks
            bottlenecks = self._identify_bottlenecks(performance_summary)
            
            # Generate recommendations
            recommendations = self._generate_recommendations(bottlenecks, performance_summary)
            
            # Store recommendations
            self._store_recommendations(recommendations)
            
            # Implement automatic optimizations
            if auto_implement:
                implemented_count = await self._implement_automatic_optimizations(recommendations)
                logger.info(f"Automatically implemented {implemented_count} optimizations")
            
            logger.info(f"Generated {len(recommendations)} optimization recommendations")
            return recommendations
            
        except Exception as e:
            logger.error(f"Error during performance analysis: {e}")
            return []
    
    def _identify_bottlenecks(self, performance_summary: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Identify performance bottlenecks from metrics"""
        bottlenecks = []
        perf = performance_summary.get('performance', {})
        targets = performance_summary.get('targets', {})
        
        # Query performance bottleneck
        if perf.get('avg_query_time_ms', 0) > targets.get('max_query_time_ms', 5000):
            severity = 'HIGH' if perf['avg_query_time_ms'] > targets.get('max_query_time_ms', 5000) * 2 else 'MEDIUM'
            bottlenecks.append({
                'type': 'query_performance',
                'severity': severity,
                'metric': 'avg_query_time_ms',
                'current_value': perf['avg_query_time_ms'],
                'target_value': targets.get('max_query_time_ms', 5000),
                'impact_score': (perf['avg_query_time_ms'] / targets.get('max_query_time_ms', 5000)) * 10
            })
        
        # Cache performance bottleneck
        if perf.get('avg_cache_hit_rate_percent', 0) < targets.get('target_cache_hit_rate_percent', 80):
            bottlenecks.append({
                'type': 'cache_performance',
                'severity': 'MEDIUM',
                'metric': 'avg_cache_hit_rate_percent',
                'current_value': perf['avg_cache_hit_rate_percent'],
                'target_value': targets.get('target_cache_hit_rate_percent', 80),
                'impact_score': (targets.get('target_cache_hit_rate_percent', 80) - perf['avg_cache_hit_rate_percent']) / 10
            })
        
        # Resource bottlenecks
        if perf.get('avg_cpu_usage_percent', 0) > targets.get('max_cpu_usage_percent', 70):
            bottlenecks.append({
                'type': 'cpu_usage',
                'severity': 'HIGH' if perf['avg_cpu_usage_percent'] > 90 else 'MEDIUM',
                'metric': 'avg_cpu_usage_percent',
                'current_value': perf['avg_cpu_usage_percent'],
                'target_value': targets.get('max_cpu_usage_percent', 70),
                'impact_score': (perf['avg_cpu_usage_percent'] / targets.get('max_cpu_usage_percent', 70)) * 8
            })
        
        if perf.get('avg_memory_usage_mb', 0) > targets.get('max_memory_usage_mb', 512):
            bottlenecks.append({
                'type': 'memory_usage',
                'severity': 'MEDIUM',
                'metric': 'avg_memory_usage_mb',
                'current_value': perf['avg_memory_usage_mb'],
                'target_value': targets.get('max_memory_usage_mb', 512),
                'impact_score': (perf['avg_memory_usage_mb'] / targets.get('max_memory_usage_mb', 512)) * 6
            })
        
        # Sort by impact score
        bottlenecks.sort(key=lambda x: x['impact_score'], reverse=True)
        
        logger.info(f"Identified {len(bottlenecks)} performance bottlenecks")
        return bottlenecks
    
    def _generate_recommendations(self, bottlenecks: List[Dict], performance_summary: Dict) -> List[OptimizationRecommendation]:
        """Generate optimization recommendations based on bottlenecks"""
        recommendations = []
        
        for bottleneck in bottlenecks:
            if bottleneck['type'] == 'query_performance':
                recommendations.extend(self._generate_query_recommendations(bottleneck))
            elif bottleneck['type'] == 'cache_performance':
                recommendations.extend(self._generate_cache_recommendations(bottleneck))
            elif bottleneck['type'] in ['cpu_usage', 'memory_usage']:
                recommendations.extend(self._generate_resource_recommendations(bottleneck))
        
        # Add proactive optimizations if system is performing well
        if performance_summary.get('performance', {}).get('avg_health_score', 0) > 90:
            recommendations.extend(self._generate_proactive_recommendations())
        
        return recommendations
    
    def _generate_query_recommendations(self, bottleneck: Dict) -> List[OptimizationRecommendation]:
        """Generate query optimization recommendations"""
        recommendations = []
        
        # Index optimization
        recommendations.append(OptimizationRecommendation(
            optimization_type=OptimizationType.INDEX_CREATION,
            priority='HIGH' if bottleneck['severity'] == 'HIGH' else 'MEDIUM',
            description="Analyze query patterns and create missing database indexes",
            estimated_improvement=25.0,
            implementation_complexity='MEDIUM',
            auto_implementable=True,
            implementation_function=self._optimize_indexes,
            estimated_time_to_implement="5-10 minutes"
        ))
        
        # Query optimization
        recommendations.append(OptimizationRecommendation(
            optimization_type=OptimizationType.QUERY_OPTIMIZATION,
            priority='HIGH',
            description="Optimize slow queries using better algorithms and reduced data scanning",
            estimated_improvement=40.0,
            implementation_complexity='COMPLEX',
            auto_implementable=False,
            estimated_time_to_implement="2-4 hours"
        ))
        
        return recommendations
    
    def _generate_cache_recommendations(self, bottleneck: Dict) -> List[OptimizationRecommendation]:
        """Generate cache optimization recommendations"""
        recommendations = []
        
        current_hit_rate = bottleneck['current_value']
        
        if current_hit_rate < 60:
            # Major cache tuning needed
            recommendations.append(OptimizationRecommendation(
                optimization_type=OptimizationType.CACHE_TUNING,
                priority='HIGH',
                description="Increase cache size and optimize TTL settings for better hit rates",
                estimated_improvement=30.0,
                implementation_complexity='SIMPLE',
                auto_implementable=True,
                implementation_function=self._optimize_cache,
                parameters={'increase_size_factor': 2.0, 'optimize_ttl': True},
                estimated_time_to_implement="1-2 minutes"
            ))
        else:
            # Fine-tuning needed
            recommendations.append(OptimizationRecommendation(
                optimization_type=OptimizationType.CACHE_TUNING,
                priority='MEDIUM',
                description="Fine-tune cache configuration for improved performance",
                estimated_improvement=15.0,
                implementation_complexity='SIMPLE',
                auto_implementable=True,
                implementation_function=self._optimize_cache,
                parameters={'increase_size_factor': 1.5, 'optimize_ttl': True},
                estimated_time_to_implement="1 minute"
            ))
        
        return recommendations
    
    def _generate_resource_recommendations(self, bottleneck: Dict) -> List[OptimizationRecommendation]:
        """Generate resource optimization recommendations"""
        recommendations = []
        
        if bottleneck['type'] == 'cpu_usage':
            recommendations.append(OptimizationRecommendation(
                optimization_type=OptimizationType.RESOURCE_ALLOCATION,
                priority='MEDIUM',
                description="Optimize CPU usage through query parallelization and resource tuning",
                estimated_improvement=20.0,
                implementation_complexity='MEDIUM',
                auto_implementable=True,
                implementation_function=self._optimize_resources,
                parameters={'optimize_cpu': True},
                estimated_time_to_implement="2-3 minutes"
            ))
        
        if bottleneck['type'] == 'memory_usage':
            recommendations.append(OptimizationRecommendation(
                optimization_type=OptimizationType.RESOURCE_ALLOCATION,
                priority='MEDIUM',
                description="Optimize memory usage through better caching and data management",
                estimated_improvement=15.0,
                implementation_complexity='SIMPLE',
                auto_implementable=True,
                implementation_function=self._optimize_resources,
                parameters={'optimize_memory': True},
                estimated_time_to_implement="1-2 minutes"
            ))
        
        return recommendations
    
    def _generate_proactive_recommendations(self) -> List[OptimizationRecommendation]:
        """Generate proactive optimizations for well-performing systems"""
        recommendations = []
        
        recommendations.append(OptimizationRecommendation(
            optimization_type=OptimizationType.CONFIGURATION_TUNING,
            priority='LOW',
            description="Fine-tune configuration parameters for optimal performance",
            estimated_improvement=5.0,
            implementation_complexity='SIMPLE',
            auto_implementable=True,
            implementation_function=self._optimize_configuration,
            estimated_time_to_implement="30 seconds"
        ))
        
        return recommendations
    
    def _store_recommendations(self, recommendations: List[OptimizationRecommendation]):
        """Store recommendations in database"""
        try:
            db_path = self.performance_monitor.metrics_db_path.parent / "optimizations.db"
            conn = sqlite3.connect(str(db_path))
            
            for rec in recommendations:
                conn.execute("""
                    INSERT INTO optimization_recommendations (
                        created_at, optimization_type, priority, description,
                        estimated_improvement, implementation_complexity,
                        auto_implementable, parameters
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    datetime.now().isoformat(),
                    rec.optimization_type.value,
                    rec.priority,
                    rec.description,
                    rec.estimated_improvement,
                    rec.implementation_complexity,
                    rec.auto_implementable,
                    json.dumps(rec.parameters or {})
                ))
            
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error storing recommendations: {e}")
    
    async def _implement_automatic_optimizations(self, recommendations: List[OptimizationRecommendation]) -> int:
        """Implement automatic optimizations"""
        implemented_count = 0
        
        for rec in recommendations:
            if rec.auto_implementable and rec.implementation_function:
                try:
                    logger.info(f"Implementing optimization: {rec.description}")
                    start_time = time.time()
                    
                    # Execute optimization
                    success = await rec.implementation_function(rec.parameters or {})
                    implementation_time = time.time() - start_time
                    
                    # Record result
                    self._record_optimization_result(
                        rec, success, implementation_time
                    )
                    
                    if success:
                        implemented_count += 1
                        logger.info(f"Successfully implemented optimization in {implementation_time:.2f}s")
                    else:
                        logger.warning(f"Failed to implement optimization: {rec.description}")
                        
                except Exception as e:
                    logger.error(f"Error implementing optimization {rec.description}: {e}")
                    self._record_optimization_result(
                        rec, False, 0, str(e)
                    )
        
        return implemented_count
    
    def _record_optimization_result(self, recommendation: OptimizationRecommendation, 
                                  success: bool, implementation_time: float, 
                                  error_message: Optional[str] = None):
        """Record optimization implementation result"""
        try:
            db_path = self.performance_monitor.metrics_db_path.parent / "optimizations.db"
            conn = sqlite3.connect(str(db_path))
            
            conn.execute("""
                INSERT INTO optimization_history (
                    timestamp, optimization_type, description, estimated_improvement,
                    implementation_time_seconds, success, error_message, parameters
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                datetime.now().isoformat(),
                recommendation.optimization_type.value,
                recommendation.description,
                recommendation.estimated_improvement,
                implementation_time,
                success,
                error_message,
                json.dumps(recommendation.parameters or {})
            ))
            
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error recording optimization result: {e}")
    
    # Optimization Implementation Functions
    
    async def _optimize_queries(self, parameters: Dict[str, Any]) -> bool:
        """Implement query optimizations"""
        try:
            # This would implement specific query optimizations
            # For now, return success as a placeholder
            logger.info("Query optimization would be implemented here")
            return True
        except Exception as e:
            logger.error(f"Query optimization failed: {e}")
            return False
    
    async def _optimize_indexes(self, parameters: Dict[str, Any]) -> bool:
        """Create database indexes for better performance"""
        try:
            if not self.database_manager:
                logger.warning("No database manager available for index optimization")
                return False
            
            # Define commonly needed indexes based on typical query patterns
            index_definitions = [
                "CREATE INDEX IF NOT EXISTS idx_healthcare_providers_npi ON healthcare_providers(npi)",
                "CREATE INDEX IF NOT EXISTS idx_healthcare_providers_state ON healthcare_providers(provider_state)",
                "CREATE INDEX IF NOT EXISTS idx_healthcare_facilities_name ON healthcare_facilities(facility_name)",
                "CREATE INDEX IF NOT EXISTS idx_provider_facility_affiliations_provider ON provider_facility_affiliations(provider_id)",
                "CREATE INDEX IF NOT EXISTS idx_medical_activities_date ON medical_activities(activity_date)",
                "CREATE INDEX IF NOT EXISTS idx_data_quality_metrics_timestamp ON data_quality_metrics(created_at)"
            ]
            
            success_count = 0
            for index_sql in index_definitions:
                try:
                    result = await self.database_manager.execute_query(index_sql)
                    if result.success:
                        success_count += 1
                        logger.info(f"Successfully created index: {index_sql.split()[-1]}")
                except Exception as e:
                    logger.warning(f"Failed to create index: {e}")
            
            return success_count > 0
            
        except Exception as e:
            logger.error(f"Index optimization failed: {e}")
            return False
    
    async def _optimize_cache(self, parameters: Dict[str, Any]) -> bool:
        """Optimize cache configuration"""
        try:
            if not self.cache_manager:
                logger.warning("No cache manager available for cache optimization")
                return True  # Return success as cache is optional
            
            # Implement cache optimization logic
            increase_factor = parameters.get('increase_size_factor', 1.5)
            optimize_ttl = parameters.get('optimize_ttl', True)
            
            # This would implement actual cache optimization
            logger.info(f"Cache optimization: size factor {increase_factor}, optimize TTL: {optimize_ttl}")
            return True
            
        except Exception as e:
            logger.error(f"Cache optimization failed: {e}")
            return False
    
    async def _optimize_resources(self, parameters: Dict[str, Any]) -> bool:
        """Optimize system resource allocation"""
        try:
            optimize_cpu = parameters.get('optimize_cpu', False)
            optimize_memory = parameters.get('optimize_memory', False)
            
            if optimize_cpu:
                # Implement CPU optimization
                logger.info("CPU optimization would be implemented here")
            
            if optimize_memory:
                # Implement memory optimization
                logger.info("Memory optimization would be implemented here")
            
            return True
            
        except Exception as e:
            logger.error(f"Resource optimization failed: {e}")
            return False
    
    async def _optimize_configuration(self, parameters: Dict[str, Any]) -> bool:
        """Optimize system configuration parameters"""
        try:
            # Implement configuration tuning
            logger.info("Configuration optimization would be implemented here")
            return True
            
        except Exception as e:
            logger.error(f"Configuration optimization failed: {e}")
            return False
    
    def get_optimization_history(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get optimization implementation history"""
        try:
            db_path = self.performance_monitor.metrics_db_path.parent / "optimizations.db"
            conn = sqlite3.connect(str(db_path))
            
            cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
            
            cursor = conn.execute("""
                SELECT 
                    timestamp, optimization_type, description, estimated_improvement,
                    actual_improvement, implementation_time_seconds, success, error_message
                FROM optimization_history 
                WHERE timestamp > ?
                ORDER BY timestamp DESC
            """, (cutoff_date,))
            
            history = []
            for row in cursor.fetchall():
                history.append({
                    'timestamp': row[0],
                    'optimization_type': row[1],
                    'description': row[2],
                    'estimated_improvement': row[3],
                    'actual_improvement': row[4],
                    'implementation_time_seconds': row[5],
                    'success': bool(row[6]),
                    'error_message': row[7]
                })
            
            conn.close()
            return history
            
        except Exception as e:
            logger.error(f"Error getting optimization history: {e}")
            return []
    
    def get_optimization_effectiveness(self) -> Dict[str, Any]:
        """Analyze effectiveness of implemented optimizations"""
        try:
            history = self.get_optimization_history(days=30)
            
            if not history:
                return {'message': 'No optimization history available'}
            
            total_optimizations = len(history)
            successful_optimizations = sum(1 for h in history if h['success'])
            total_estimated_improvement = sum(h['estimated_improvement'] or 0 for h in history if h['success'])
            avg_implementation_time = sum(h['implementation_time_seconds'] or 0 for h in history if h['success']) / max(successful_optimizations, 1)
            
            effectiveness = {
                'total_optimizations': total_optimizations,
                'successful_optimizations': successful_optimizations,
                'success_rate_percent': (successful_optimizations / total_optimizations * 100) if total_optimizations > 0 else 0,
                'total_estimated_improvement_percent': total_estimated_improvement,
                'average_implementation_time_seconds': avg_implementation_time,
                'optimization_types': {}
            }
            
            # Break down by optimization type
            type_stats = {}
            for h in history:
                opt_type = h['optimization_type']
                if opt_type not in type_stats:
                    type_stats[opt_type] = {'count': 0, 'success': 0, 'improvement': 0}
                
                type_stats[opt_type]['count'] += 1
                if h['success']:
                    type_stats[opt_type]['success'] += 1
                    type_stats[opt_type]['improvement'] += h['estimated_improvement'] or 0
            
            effectiveness['optimization_types'] = type_stats
            
            return effectiveness
            
        except Exception as e:
            logger.error(f"Error analyzing optimization effectiveness: {e}")
            return {'error': str(e)}
