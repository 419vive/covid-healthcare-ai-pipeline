"""
Asynchronous query executor for high-performance data validation
"""

import asyncio
import time
from typing import Dict, List, Any, Optional, AsyncIterator, Callable
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import pandas as pd
from pathlib import Path

from ..database.abstract_database import AbstractDatabaseManager, QueryResult
from ..cache.cache_manager import CacheManager
from ..config.pipeline_config import PipelineConfig
from ..utils.logging_config import get_logger
from .message_queue import MessageQueue, JobMessage
from .job_scheduler import JobScheduler

logger = get_logger(__name__)


@dataclass
class AsyncValidationResult:
    """Container for async validation results"""
    rule_name: str
    query_path: str
    result: QueryResult
    severity: str
    enabled: bool
    execution_timestamp: pd.Timestamp
    summary: Optional[Dict[str, Any]] = None
    cached: bool = False
    shard_info: Optional[Dict[str, Any]] = None


class AsyncQueryExecutor:
    """
    High-performance asynchronous query executor with:
    - Async/await pattern throughout
    - Message queue integration
    - Intelligent caching
    - Load balancing across database replicas
    - Background job processing
    """
    
    def __init__(self,
                 db_manager: AbstractDatabaseManager,
                 cache_manager: CacheManager,
                 config: PipelineConfig,
                 message_queue: Optional[MessageQueue] = None):
        """
        Initialize async query executor
        
        Args:
            db_manager: Database manager instance
            cache_manager: Cache manager instance  
            config: Pipeline configuration
            message_queue: Optional message queue for job processing
        """
        self.db_manager = db_manager
        self.cache_manager = cache_manager
        self.config = config
        self.message_queue = message_queue
        
        # Load validation queries
        self.validation_queries = {}
        self._load_validation_queries()
        
        # Job tracking
        self._active_jobs = {}
        self._job_scheduler = JobScheduler() if message_queue else None
        
        logger.info(f"AsyncQueryExecutor initialized with {len(self.validation_queries)} queries")
    
    async def initialize(self) -> None:
        """Initialize async components"""
        if self.message_queue:
            await self.message_queue.connect()
            await self._setup_job_processing()
        
        # Warm caches if configured
        if self.config.performance.cache_query_results:
            await self._warm_query_cache()
    
    async def close(self) -> None:
        """Close async resources"""
        if self.message_queue:
            await self.message_queue.disconnect()
        
        # Cancel active jobs
        for job_id in list(self._active_jobs.keys()):
            await self.cancel_job(job_id)
    
    def _load_validation_queries(self) -> None:
        """Load validation queries from SQL files"""
        sql_dir = Path(__file__).parent.parent.parent / "sql" / "02_validation"
        
        if not sql_dir.exists():
            logger.warning(f"Validation queries directory not found: {sql_dir}")
            return
        
        for sql_file in sql_dir.glob("*.sql"):
            queries = self._parse_sql_file(sql_file)
            self.validation_queries.update(queries)
        
        logger.info(f"Loaded {len(self.validation_queries)} validation queries")
    
    def _parse_sql_file(self, file_path: Path) -> Dict[str, str]:
        """Parse SQL file and extract queries"""
        queries = {}
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if "ai_enhanced_validation_queries.sql" in file_path.name:
                queries = self._extract_ai_enhanced_queries(content, file_path)
            else:
                query_name = file_path.stem
                queries[query_name] = content
        
        except Exception as e:
            logger.error(f"Error parsing SQL file {file_path}: {e}")
        
        return queries
    
    def _extract_ai_enhanced_queries(self, content: str, file_path: Path) -> Dict[str, str]:
        """Extract individual AI-enhanced queries"""
        queries = {}
        sections = content.split("-- Query ")
        
        for i, section in enumerate(sections[1:], 1):
            lines = section.strip().split('\n')
            
            if lines:
                first_line = lines[0].strip()
                if ':' in first_line:
                    query_name_part = first_line.split(':', 1)[1].strip()
                    query_name = query_name_part.lower().replace(' ', '_').replace('-', '_')
                else:
                    query_name = f"validation_{i:02d}"
                
                # Extract SQL content
                sql_lines = []
                in_sql = False
                
                for line in lines[1:]:
                    line_stripped = line.strip()
                    if line_stripped.startswith('--'):
                        if in_sql:
                            sql_lines.append(line)
                        continue
                    elif line_stripped and not in_sql:
                        in_sql = True
                    
                    if in_sql:
                        sql_lines.append(line)
                
                if sql_lines:
                    queries[query_name] = '\n'.join(sql_lines).strip()
        
        return queries
    
    async def execute_single_query(self, 
                                 rule_name: str,
                                 use_cache: bool = True,
                                 cache_ttl: Optional[int] = None) -> Optional[AsyncValidationResult]:
        """
        Execute single validation query asynchronously
        
        Args:
            rule_name: Name of validation rule
            use_cache: Whether to use cached results
            cache_ttl: Cache time-to-live override
            
        Returns:
            AsyncValidationResult or None if not found
        """
        if rule_name not in self.validation_queries:
            logger.error(f"Validation query not found: {rule_name}")
            return None
        
        # Check cache first
        if use_cache:
            cached_result = await self._get_cached_result(rule_name)
            if cached_result:
                return cached_result
        
        # Get rule configuration
        rule_config = self.config.get_validation_rule_config(rule_name)
        enabled = rule_config.enabled if rule_config else True
        severity = rule_config.severity if rule_config else "MEDIUM"
        
        if not enabled:
            logger.info(f"Skipping disabled validation rule: {rule_name}")
            return self._create_disabled_result(rule_name, severity)
        
        try:
            # Execute query
            query_sql = self.validation_queries[rule_name]
            
            # Use read-only routing for validation queries
            result = await self.db_manager.execute_query(query_sql, read_only=True)
            
            # Create validation result
            validation_result = AsyncValidationResult(
                rule_name=rule_name,
                query_path="",
                result=result,
                severity=severity,
                enabled=enabled,
                execution_timestamp=pd.Timestamp.now(),
                cached=False
            )
            
            # Generate summary if successful
            if result.success and result.row_count > 0:
                validation_result.summary = await self._generate_query_summary(
                    result.data, rule_name
                )
            
            # Cache result if configured
            if use_cache and result.success:
                await self._cache_result(rule_name, validation_result, cache_ttl)
            
            logger.info(f"Query {rule_name} completed: {result.row_count} violations in {result.execution_time:.2f}s")
            return validation_result
        
        except Exception as e:
            logger.error(f"Error executing query {rule_name}: {e}")
            return self._create_error_result(rule_name, severity, str(e))
    
    async def execute_all_queries(self,
                                parallel: bool = True,
                                max_concurrency: int = None,
                                use_cache: bool = True) -> Dict[str, AsyncValidationResult]:
        """
        Execute all validation queries asynchronously
        
        Args:
            parallel: Execute queries in parallel
            max_concurrency: Maximum concurrent queries
            use_cache: Use cached results
            
        Returns:
            Dictionary of rule names to results
        """
        logger.info(f"Starting async execution of {len(self.validation_queries)} queries")
        start_time = time.time()
        
        if parallel:
            results = await self._execute_queries_concurrent(max_concurrency, use_cache)
        else:
            results = await self._execute_queries_sequential(use_cache)
        
        # Log execution summary
        total_time = time.time() - start_time
        successful_queries = sum(1 for r in results.values() if r.result.success)
        total_violations = sum(r.result.row_count for r in results.values() if r.result.success)
        
        logger.info(f"Async query execution completed: {successful_queries}/{len(results)} successful, "
                   f"{total_violations} violations found in {total_time:.2f}s")
        
        return results
    
    async def _execute_queries_concurrent(self,
                                        max_concurrency: Optional[int],
                                        use_cache: bool) -> Dict[str, AsyncValidationResult]:
        """Execute queries concurrently with controlled concurrency"""
        max_concurrency = max_concurrency or self.config.performance.max_workers
        
        # Create semaphore to control concurrency
        semaphore = asyncio.Semaphore(max_concurrency)
        
        async def execute_with_semaphore(rule_name: str) -> tuple[str, AsyncValidationResult]:
            async with semaphore:
                result = await self.execute_single_query(rule_name, use_cache=use_cache)
                return rule_name, result
        
        # Create tasks for all queries
        tasks = [
            execute_with_semaphore(rule_name)
            for rule_name in self.validation_queries
        ]
        
        # Wait for all tasks to complete
        results = {}
        completed_tasks = await asyncio.gather(*tasks, return_exceptions=True)
        
        for task_result in completed_tasks:
            if isinstance(task_result, Exception):
                logger.error(f"Query task failed: {task_result}")
            else:
                rule_name, validation_result = task_result
                if validation_result:
                    results[rule_name] = validation_result
        
        return results
    
    async def _execute_queries_sequential(self, use_cache: bool) -> Dict[str, AsyncValidationResult]:
        """Execute queries sequentially"""
        results = {}
        
        for rule_name in self.validation_queries:
            result = await self.execute_single_query(rule_name, use_cache=use_cache)
            if result:
                results[rule_name] = result
        
        return results
    
    async def submit_job(self,
                        rules: Optional[List[str]] = None,
                        job_priority: int = 0,
                        callback_url: Optional[str] = None,
                        metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Submit validation job to message queue
        
        Args:
            rules: Specific rules to execute
            job_priority: Job priority (higher = more priority)
            callback_url: URL to notify on completion
            metadata: Additional job metadata
            
        Returns:
            Job ID
        """
        if not self.message_queue:
            raise RuntimeError("Message queue not configured")
        
        job_id = f"job_{int(time.time() * 1000)}"
        
        job_message = JobMessage(
            job_id=job_id,
            job_type="validation",
            payload={
                "rules": rules or list(self.validation_queries.keys()),
                "use_cache": True,
                "parallel": True
            },
            priority=job_priority,
            callback_url=callback_url,
            metadata=metadata or {}
        )
        
        # Submit to queue
        await self.message_queue.publish("validation_jobs", job_message)
        
        # Track job
        self._active_jobs[job_id] = {
            "status": "queued",
            "created_at": pd.Timestamp.now(),
            "message": job_message
        }
        
        logger.info(f"Validation job {job_id} submitted to queue")
        return job_id
    
    async def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get status of submitted job"""
        if job_id in self._active_jobs:
            return self._active_jobs[job_id]
        
        # Check cache for completed jobs
        cached_status = await self.cache_manager.get("job_status", job_id)
        return cached_status
    
    async def cancel_job(self, job_id: str) -> bool:
        """Cancel active job"""
        if job_id not in self._active_jobs:
            return False
        
        # Update status
        self._active_jobs[job_id]["status"] = "cancelled"
        self._active_jobs[job_id]["cancelled_at"] = pd.Timestamp.now()
        
        # Cache final status
        await self.cache_manager.set(
            "job_status", 
            job_id, 
            self._active_jobs[job_id],
            ttl=86400  # 24 hours
        )
        
        # Remove from active jobs
        del self._active_jobs[job_id]
        
        logger.info(f"Job {job_id} cancelled")
        return True
    
    async def _setup_job_processing(self) -> None:
        """Setup background job processing"""
        if not self.message_queue:
            return
        
        async def process_job(message: JobMessage) -> None:
            """Process individual validation job"""
            job_id = message.job_id
            
            try:
                # Update job status
                if job_id in self._active_jobs:
                    self._active_jobs[job_id]["status"] = "running"
                    self._active_jobs[job_id]["started_at"] = pd.Timestamp.now()
                
                # Execute validation
                rules = message.payload.get("rules", [])
                use_cache = message.payload.get("use_cache", True)
                parallel = message.payload.get("parallel", True)
                
                if rules:
                    results = {}
                    for rule_name in rules:
                        result = await self.execute_single_query(rule_name, use_cache=use_cache)
                        if result:
                            results[rule_name] = result
                else:
                    results = await self.execute_all_queries(
                        parallel=parallel, 
                        use_cache=use_cache
                    )
                
                # Cache results
                await self.cache_manager.set(
                    "validation_results",
                    job_id,
                    results,
                    ttl=86400  # 24 hours
                )
                
                # Update job status
                job_status = {
                    "status": "completed",
                    "completed_at": pd.Timestamp.now(),
                    "results_count": len(results),
                    "violations_found": sum(r.result.row_count for r in results.values() if r.result.success)
                }
                
                if job_id in self._active_jobs:
                    self._active_jobs[job_id].update(job_status)
                    final_status = self._active_jobs[job_id]
                    del self._active_jobs[job_id]
                else:
                    final_status = job_status
                
                # Cache final status
                await self.cache_manager.set("job_status", job_id, final_status, ttl=86400)
                
                # Send callback notification
                if message.callback_url:
                    await self._send_job_callback(message.callback_url, job_id, final_status)
                
                logger.info(f"Validation job {job_id} completed successfully")
            
            except Exception as e:
                logger.error(f"Error processing validation job {job_id}: {e}")
                
                # Update job status to failed
                error_status = {
                    "status": "failed",
                    "failed_at": pd.Timestamp.now(),
                    "error": str(e)
                }
                
                if job_id in self._active_jobs:
                    self._active_jobs[job_id].update(error_status)
                    final_status = self._active_jobs[job_id]
                    del self._active_jobs[job_id]
                else:
                    final_status = error_status
                
                await self.cache_manager.set("job_status", job_id, final_status, ttl=86400)
        
        # Subscribe to validation jobs queue
        await self.message_queue.subscribe("validation_jobs", process_job)
        
        logger.info("Job processing setup completed")
    
    async def _get_cached_result(self, rule_name: str) -> Optional[AsyncValidationResult]:
        """Get cached validation result"""
        if not self.config.performance.cache_query_results:
            return None
        
        cached_data = await self.cache_manager.get("validation_queries", rule_name)
        
        if cached_data:
            # Convert cached data back to AsyncValidationResult
            cached_result = AsyncValidationResult(**cached_data)
            cached_result.cached = True
            return cached_result
        
        return None
    
    async def _cache_result(self,
                          rule_name: str,
                          result: AsyncValidationResult,
                          ttl: Optional[int] = None) -> None:
        """Cache validation result"""
        if not self.config.performance.cache_query_results:
            return
        
        cache_ttl = ttl or self.config.performance.cache_ttl_seconds
        
        # Convert to dict for caching
        cache_data = {
            "rule_name": result.rule_name,
            "query_path": result.query_path,
            "result": {
                "data": result.result.data,
                "execution_time": result.result.execution_time,
                "row_count": result.result.row_count,
                "columns": result.result.columns,
                "query": result.result.query,
                "success": result.result.success,
                "error_message": result.result.error_message
            },
            "severity": result.severity,
            "enabled": result.enabled,
            "execution_timestamp": result.execution_timestamp,
            "summary": result.summary,
            "cached": False
        }
        
        await self.cache_manager.set(
            "validation_queries",
            rule_name,
            cache_data,
            ttl=cache_ttl
        )
    
    async def _warm_query_cache(self) -> None:
        """Warm cache with frequently used queries"""
        # Identify high-priority queries for cache warming
        priority_queries = [
            rule_name for rule_name, query in self.validation_queries.items()
            if any(keyword in query.lower() for keyword in ['critical', 'high', 'npi', 'name'])
        ]
        
        if priority_queries:
            logger.info(f"Warming cache for {len(priority_queries)} priority queries")
            
            warming_tasks = [
                self.execute_single_query(rule_name, use_cache=False)
                for rule_name in priority_queries[:5]  # Limit to top 5
            ]
            
            await asyncio.gather(*warming_tasks, return_exceptions=True)
    
    async def _generate_query_summary(self, df: pd.DataFrame, rule_name: str) -> Dict[str, Any]:
        """Generate async summary statistics"""
        # Run summary generation in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        
        def generate_summary():
            summary = {
                "total_violations": len(df),
                "rule_name": rule_name
            }
            
            # Add severity distribution
            if 'severity_level' in df.columns:
                severity_counts = df['severity_level'].value_counts().to_dict()
                summary["severity_distribution"] = severity_counts
            
            # Add sample violations
            if len(df) > 0:
                summary["sample_violations"] = df.head(5).to_dict('records')
            
            return summary
        
        with ThreadPoolExecutor() as executor:
            return await loop.run_in_executor(executor, generate_summary)
    
    def _create_disabled_result(self, rule_name: str, severity: str) -> AsyncValidationResult:
        """Create result for disabled rule"""
        return AsyncValidationResult(
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
    
    def _create_error_result(self, rule_name: str, severity: str, error_msg: str) -> AsyncValidationResult:
        """Create result for failed query"""
        return AsyncValidationResult(
            rule_name=rule_name,
            query_path="",
            result=QueryResult(
                data=pd.DataFrame(),
                execution_time=0,
                row_count=0,
                columns=[],
                query="",
                success=False,
                error_message=error_msg
            ),
            severity="ERROR",
            enabled=True,
            execution_timestamp=pd.Timestamp.now()
        )
    
    async def _send_job_callback(self, callback_url: str, job_id: str, status: Dict[str, Any]) -> None:
        """Send job completion callback"""
        try:
            import aiohttp
            
            payload = {
                "job_id": job_id,
                "status": status["status"],
                "completed_at": status.get("completed_at"),
                "violations_found": status.get("violations_found", 0)
            }
            
            async with aiohttp.ClientSession() as session:
                await session.post(callback_url, json=payload, timeout=30)
            
            logger.info(f"Callback sent for job {job_id}")
            
        except Exception as e:
            logger.error(f"Failed to send callback for job {job_id}: {e}")
    
    async def get_query_catalog(self) -> List[Dict[str, Any]]:
        """Get catalog of available queries"""
        catalog = []
        
        for rule_name in self.validation_queries:
            rule_config = self.config.get_validation_rule_config(rule_name)
            
            catalog.append({
                "rule_name": rule_name,
                "enabled": rule_config.enabled if rule_config else True,
                "severity": rule_config.severity if rule_config else "MEDIUM",
                "description": self._extract_query_description(rule_name),
                "estimated_duration": self._estimate_query_duration(rule_name)
            })
        
        return catalog
    
    def _extract_query_description(self, rule_name: str) -> str:
        """Extract description from query comments"""
        query_sql = self.validation_queries.get(rule_name, "")
        lines = query_sql.split('\n')
        
        for line in lines[:10]:
            if line.strip().startswith('--') and ('purpose' in line.lower() or 'description' in line.lower()):
                return line.strip('- ').strip()
        
        return rule_name.replace('_', ' ').title()
    
    def _estimate_query_duration(self, rule_name: str) -> int:
        """Estimate query duration in seconds"""
        query_sql = self.validation_queries.get(rule_name, "")
        
        # Simple heuristic based on query complexity
        complexity_score = 0
        complexity_score += query_sql.lower().count('join') * 2
        complexity_score += query_sql.lower().count('group by') * 1
        complexity_score += query_sql.lower().count('order by') * 1
        complexity_score += query_sql.lower().count('like') * 1
        complexity_score += len(query_sql) // 500  # Character count factor
        
        # Map to estimated seconds
        if complexity_score <= 2:
            return 5
        elif complexity_score <= 5:
            return 15
        elif complexity_score <= 10:
            return 30
        else:
            return 60