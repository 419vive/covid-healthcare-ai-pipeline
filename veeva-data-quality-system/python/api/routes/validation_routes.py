"""
Validation API routes for data quality operations
"""

import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import pandas as pd

from ...pipeline.async_query_executor import AsyncQueryExecutor
from ...cache.cache_manager import CacheManager
from ..models.api_models import ValidationRequest, ValidationResponse, ValidationRuleInfo
from ..middleware.authentication import get_current_user
from ..middleware.rate_limiting import rate_limit
from ...utils.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter()


class ValidationJobRequest(BaseModel):
    """Request model for validation jobs"""
    rules: Optional[List[str]] = Field(None, description="Specific rules to execute")
    parallel: bool = Field(True, description="Execute queries in parallel")
    cache_results: bool = Field(True, description="Cache validation results")
    output_formats: List[str] = Field(["json"], description="Output formats")
    webhook_url: Optional[str] = Field(None, description="Webhook URL for completion notification")


class ValidationJobResponse(BaseModel):
    """Response model for validation jobs"""
    job_id: str
    status: str
    created_at: datetime
    estimated_completion: Optional[datetime] = None
    rules_count: int
    progress_url: str


class ValidationResultsResponse(BaseModel):
    """Response model for validation results"""
    job_id: str
    status: str
    total_rules: int
    completed_rules: int
    violations_found: int
    execution_time: float
    results: Dict[str, Any]
    created_at: datetime
    completed_at: Optional[datetime] = None


@router.get("/rules", response_model=List[ValidationRuleInfo])
@rate_limit("100/hour")
async def get_validation_rules(
    current_user = Depends(get_current_user)
) -> List[ValidationRuleInfo]:
    """
    Get list of available validation rules
    """
    try:
        # This would be injected via dependency injection in a real implementation
        query_executor = AsyncQueryExecutor()  # Placeholder
        
        rules_catalog = await query_executor.get_query_catalog()
        
        return [
            ValidationRuleInfo(
                rule_name=rule["rule_name"],
                enabled=rule["enabled"],
                severity=rule["severity"],
                description=rule["description"],
                category=rule.get("category", "general"),
                estimated_duration=rule.get("estimated_duration", 30)
            )
            for rule in rules_catalog
        ]
    
    except Exception as e:
        logger.error(f"Error getting validation rules: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve validation rules")


@router.post("/validate", response_model=ValidationResponse)
@rate_limit("50/hour")
async def execute_validation(
    request: ValidationRequest,
    background_tasks: BackgroundTasks,
    current_user = Depends(get_current_user)
) -> ValidationResponse:
    """
    Execute validation queries synchronously (for small datasets)
    """
    try:
        query_executor = AsyncQueryExecutor()  # Would be injected
        
        # Execute validation
        if request.rules:
            results = {}
            for rule_name in request.rules:
                result = await query_executor.execute_single_query(rule_name)
                if result:
                    results[rule_name] = result
        else:
            results = await query_executor.execute_all_queries(parallel=request.parallel)
        
        # Calculate summary statistics
        total_violations = sum(
            r.result.row_count for r in results.values() if r.result.success
        )
        
        critical_violations = sum(
            r.result.row_count for r in results.values() 
            if r.result.success and r.severity == "CRITICAL"
        )
        
        # Cache results if requested
        if request.cache_results:
            cache_manager = CacheManager()  # Would be injected
            await cache_manager.set(
                "validation_results", 
                f"sync_{datetime.now().timestamp()}", 
                results,
                ttl=3600
            )
        
        return ValidationResponse(
            job_id=f"sync_{datetime.now().timestamp()}",
            status="completed",
            total_rules=len(results),
            completed_rules=len([r for r in results.values() if r.result.success]),
            violations_found=total_violations,
            critical_violations=critical_violations,
            execution_time=sum(r.result.execution_time for r in results.values()),
            results={
                rule_name: {
                    "success": result.result.success,
                    "violations": result.result.row_count,
                    "severity": result.severity,
                    "execution_time": result.result.execution_time,
                    "sample_data": result.result.data.head(5).to_dict('records') if result.result.success else []
                }
                for rule_name, result in results.items()
            }
        )
    
    except Exception as e:
        logger.error(f"Validation execution error: {e}")
        raise HTTPException(status_code=500, detail=f"Validation failed: {str(e)}")


@router.post("/jobs", response_model=ValidationJobResponse)
@rate_limit("20/hour")
async def create_validation_job(
    request: ValidationJobRequest,
    background_tasks: BackgroundTasks,
    current_user = Depends(get_current_user)
) -> ValidationJobResponse:
    """
    Create asynchronous validation job (for large datasets)
    """
    try:
        job_id = f"job_{datetime.now().timestamp()}_{current_user.get('user_id', 'anonymous')}"
        
        # Store job in cache/database
        job_data = {
            "job_id": job_id,
            "status": "queued",
            "created_at": datetime.now(),
            "user_id": current_user.get("user_id"),
            "request": request.dict(),
            "progress": 0
        }
        
        # Add to background processing queue
        background_tasks.add_task(
            _process_validation_job,
            job_id,
            request,
            current_user
        )
        
        return ValidationJobResponse(
            job_id=job_id,
            status="queued",
            created_at=job_data["created_at"],
            rules_count=len(request.rules) if request.rules else 0,
            progress_url=f"/api/v1/validation/jobs/{job_id}/status"
        )
    
    except Exception as e:
        logger.error(f"Error creating validation job: {e}")
        raise HTTPException(status_code=500, detail="Failed to create validation job")


@router.get("/jobs/{job_id}/status")
@rate_limit("200/hour")
async def get_validation_job_status(
    job_id: str,
    current_user = Depends(get_current_user)
):
    """
    Get status of validation job
    """
    try:
        # Retrieve job status from cache/database
        cache_manager = CacheManager()  # Would be injected
        job_data = await cache_manager.get("validation_jobs", job_id)
        
        if not job_data:
            raise HTTPException(status_code=404, detail="Validation job not found")
        
        # Check user permissions
        if job_data.get("user_id") != current_user.get("user_id") and not current_user.get("is_admin", False):
            raise HTTPException(status_code=403, detail="Access denied to this job")
        
        return job_data
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting job status: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve job status")


@router.get("/jobs/{job_id}/results", response_model=ValidationResultsResponse)
@rate_limit("100/hour")
async def get_validation_results(
    job_id: str,
    format: str = Query("json", description="Response format: json, csv, excel"),
    download: bool = Query(False, description="Download as file attachment"),
    current_user = Depends(get_current_user)
):
    """
    Get validation job results
    """
    try:
        cache_manager = CacheManager()  # Would be injected
        
        # Get job data
        job_data = await cache_manager.get("validation_jobs", job_id)
        if not job_data:
            raise HTTPException(status_code=404, detail="Validation job not found")
        
        # Check permissions
        if job_data.get("user_id") != current_user.get("user_id") and not current_user.get("is_admin", False):
            raise HTTPException(status_code=403, detail="Access denied to this job")
        
        # Check if job is completed
        if job_data["status"] != "completed":
            raise HTTPException(status_code=409, detail="Job not completed yet")
        
        # Get results
        results = await cache_manager.get("validation_results", job_id)
        if not results:
            raise HTTPException(status_code=404, detail="Results not found or expired")
        
        if format == "json":
            return ValidationResultsResponse(**job_data, results=results)
        
        elif format == "csv":
            # Convert results to CSV
            csv_data = _convert_results_to_csv(results)
            
            if download:
                return StreamingResponse(
                    io.StringIO(csv_data),
                    media_type="text/csv",
                    headers={"Content-Disposition": f"attachment; filename=validation_results_{job_id}.csv"}
                )
            else:
                return {"format": "csv", "data": csv_data}
        
        elif format == "excel":
            # Convert results to Excel
            excel_data = _convert_results_to_excel(results)
            
            if download:
                return StreamingResponse(
                    io.BytesIO(excel_data),
                    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f"attachment; filename=validation_results_{job_id}.xlsx"}
                )
            else:
                return {"format": "excel", "size": len(excel_data)}
        
        else:
            raise HTTPException(status_code=400, detail="Unsupported format")
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting validation results: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve results")


@router.delete("/jobs/{job_id}")
@rate_limit("50/hour")
async def cancel_validation_job(
    job_id: str,
    current_user = Depends(get_current_user)
):
    """
    Cancel running validation job
    """
    try:
        cache_manager = CacheManager()  # Would be injected
        
        job_data = await cache_manager.get("validation_jobs", job_id)
        if not job_data:
            raise HTTPException(status_code=404, detail="Validation job not found")
        
        # Check permissions
        if job_data.get("user_id") != current_user.get("user_id") and not current_user.get("is_admin", False):
            raise HTTPException(status_code=403, detail="Access denied to this job")
        
        # Update job status
        job_data["status"] = "cancelled"
        job_data["cancelled_at"] = datetime.now()
        
        await cache_manager.set("validation_jobs", job_id, job_data)
        
        return {"message": "Validation job cancelled successfully"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling job: {e}")
        raise HTTPException(status_code=500, detail="Failed to cancel job")


@router.get("/statistics")
@rate_limit("100/hour") 
async def get_validation_statistics(
    days: int = Query(7, ge=1, le=90, description="Number of days to include"),
    current_user = Depends(get_current_user)
):
    """
    Get validation statistics and trends
    """
    try:
        # This would query historical validation data
        stats = {
            "period_days": days,
            "total_validations": 150,
            "total_violations": 2340,
            "critical_violations": 45,
            "average_execution_time": 12.5,
            "most_frequent_violations": [
                {"rule": "npi_validation", "count": 450, "trend": "increasing"},
                {"rule": "name_inconsistency", "count": 320, "trend": "stable"},
                {"rule": "address_validation", "count": 280, "trend": "decreasing"}
            ],
            "performance_metrics": {
                "avg_response_time": 2.1,
                "cache_hit_rate": 85.3,
                "database_query_time": 1.8
            }
        }
        
        return stats
    
    except Exception as e:
        logger.error(f"Error getting validation statistics: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve statistics")


async def _process_validation_job(
    job_id: str,
    request: ValidationJobRequest,
    user: Dict[str, Any]
) -> None:
    """
    Background task to process validation job
    """
    cache_manager = CacheManager()  # Would be injected
    
    try:
        # Update job status to running
        job_data = await cache_manager.get("validation_jobs", job_id)
        job_data["status"] = "running" 
        job_data["started_at"] = datetime.now()
        await cache_manager.set("validation_jobs", job_id, job_data)
        
        # Execute validation
        query_executor = AsyncQueryExecutor()  # Would be injected
        
        if request.rules:
            results = {}
            total_rules = len(request.rules)
            
            for i, rule_name in enumerate(request.rules):
                result = await query_executor.execute_single_query(rule_name)
                if result:
                    results[rule_name] = result
                
                # Update progress
                progress = int((i + 1) / total_rules * 100)
                job_data["progress"] = progress
                await cache_manager.set("validation_jobs", job_id, job_data)
        else:
            results = await query_executor.execute_all_queries(parallel=request.parallel)
        
        # Store results
        await cache_manager.set("validation_results", job_id, results, ttl=86400)  # 24 hours
        
        # Update job completion
        job_data["status"] = "completed"
        job_data["completed_at"] = datetime.now()
        job_data["progress"] = 100
        job_data["violations_found"] = sum(r.result.row_count for r in results.values() if r.result.success)
        
        await cache_manager.set("validation_jobs", job_id, job_data)
        
        # Send webhook notification if provided
        if request.webhook_url:
            await _send_webhook_notification(request.webhook_url, job_id, job_data)
        
        logger.info(f"Validation job {job_id} completed successfully")
        
    except Exception as e:
        logger.error(f"Error processing validation job {job_id}: {e}")
        
        # Update job status to failed
        job_data = await cache_manager.get("validation_jobs", job_id)
        if job_data:
            job_data["status"] = "failed"
            job_data["error"] = str(e)
            job_data["failed_at"] = datetime.now()
            await cache_manager.set("validation_jobs", job_id, job_data)


async def _send_webhook_notification(webhook_url: str, job_id: str, job_data: Dict[str, Any]) -> None:
    """Send webhook notification for job completion"""
    try:
        import aiohttp
        
        payload = {
            "job_id": job_id,
            "status": job_data["status"],
            "completed_at": job_data.get("completed_at"),
            "violations_found": job_data.get("violations_found", 0)
        }
        
        async with aiohttp.ClientSession() as session:
            await session.post(webhook_url, json=payload, timeout=30)
        
        logger.info(f"Webhook notification sent for job {job_id}")
        
    except Exception as e:
        logger.error(f"Failed to send webhook notification: {e}")


def _convert_results_to_csv(results: Dict[str, Any]) -> str:
    """Convert validation results to CSV format"""
    import io
    
    # Flatten results into tabular format
    rows = []
    for rule_name, result in results.items():
        if result.result.success:
            for _, violation in result.result.data.iterrows():
                row = {
                    "rule_name": rule_name,
                    "severity": result.severity,
                    "execution_time": result.result.execution_time,
                    **violation.to_dict()
                }
                rows.append(row)
    
    if rows:
        df = pd.DataFrame(rows)
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False)
        return csv_buffer.getvalue()
    else:
        return "No violations found"


def _convert_results_to_excel(results: Dict[str, Any]) -> bytes:
    """Convert validation results to Excel format"""
    import io
    
    excel_buffer = io.BytesIO()
    
    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
        # Summary sheet
        summary_data = []
        for rule_name, result in results.items():
            summary_data.append({
                "Rule": rule_name,
                "Severity": result.severity,
                "Success": result.result.success,
                "Violations": result.result.row_count,
                "Execution Time": result.result.execution_time
            })
        
        summary_df = pd.DataFrame(summary_data)
        summary_df.to_excel(writer, sheet_name="Summary", index=False)
        
        # Individual sheets for each rule with violations
        for rule_name, result in results.items():
            if result.result.success and result.result.row_count > 0:
                sheet_name = rule_name[:31]  # Excel limit
                result.result.data.to_excel(writer, sheet_name=sheet_name, index=False)
    
    excel_buffer.seek(0)
    return excel_buffer.getvalue()