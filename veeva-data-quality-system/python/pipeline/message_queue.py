"""
Message queue implementation for async job processing
"""

import asyncio
import json
import uuid
from typing import Dict, List, Any, Optional, Callable, AsyncIterator
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from enum import Enum
import aioredis
from contextlib import asynccontextmanager

from ..utils.logging_config import get_logger

logger = get_logger(__name__)


class JobStatus(Enum):
    """Job status enumeration"""
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class JobMessage:
    """Standard job message format"""
    job_id: str
    job_type: str
    payload: Dict[str, Any]
    priority: int = 0
    created_at: Optional[datetime] = None
    callback_url: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)
        if self.metadata is None:
            self.metadata = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        data = asdict(self)
        data['created_at'] = self.created_at.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'JobMessage':
        """Create from dictionary"""
        if 'created_at' in data and isinstance(data['created_at'], str):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        return cls(**data)


class MessageQueue:
    """
    Redis-based message queue for async job processing with:
    - Priority queues
    - Dead letter queues
    - Retry logic
    - Job persistence
    - Consumer groups
    """
    
    def __init__(self,
                 redis_url: str = "redis://localhost:6379",
                 default_queue: str = "default",
                 consumer_group: str = "workers"):
        """
        Initialize message queue
        
        Args:
            redis_url: Redis connection URL
            default_queue: Default queue name
            consumer_group: Consumer group name
        """
        self.redis_url = redis_url
        self.default_queue = default_queue
        self.consumer_group = consumer_group
        self.consumer_id = f"worker_{uuid.uuid4().hex[:8]}"
        
        self._redis = None
        self._subscribers = {}
        self._running = False
        self._consumer_tasks = []
    
    async def connect(self) -> None:
        """Connect to Redis"""
        try:
            self._redis = await aioredis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
                max_connections=20,
                retry_on_timeout=True
            )
            
            # Test connection
            await self._redis.ping()
            
            logger.info("Message queue connected to Redis")
            
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise
    
    async def disconnect(self) -> None:
        """Disconnect from Redis"""
        try:
            self._running = False
            
            # Cancel consumer tasks
            for task in self._consumer_tasks:
                task.cancel()
            
            if self._consumer_tasks:
                await asyncio.gather(*self._consumer_tasks, return_exceptions=True)
            
            if self._redis:
                await self._redis.close()
            
            logger.info("Message queue disconnected")
            
        except Exception as e:
            logger.error(f"Error disconnecting from Redis: {e}")
    
    async def publish(self,
                     queue_name: str,
                     message: JobMessage,
                     delay: Optional[int] = None) -> str:
        """
        Publish job message to queue
        
        Args:
            queue_name: Queue to publish to
            message: Job message
            delay: Delay in seconds before job becomes available
            
        Returns:
            Message ID
        """
        if not self._redis:
            raise RuntimeError("Message queue not connected")
        
        try:
            # Serialize message
            message_data = json.dumps(message.to_dict())
            
            if delay:
                # Use delayed processing
                score = (datetime.now(timezone.utc).timestamp() + delay) * 1000
                await self._redis.zadd(f"{queue_name}:delayed", {message.job_id: score})
                await self._redis.hset(f"{queue_name}:messages", message.job_id, message_data)
            else:
                # Add to priority queue (higher priority = lower score)
                priority_score = -message.priority
                await self._redis.zadd(f"{queue_name}:priority", {message.job_id: priority_score})
                await self._redis.hset(f"{queue_name}:messages", message.job_id, message_data)
            
            # Track job status
            await self._redis.hset(f"jobs:{message.job_id}", mapping={
                "status": JobStatus.QUEUED.value,
                "queue": queue_name,
                "created_at": message.created_at.isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat()
            })
            
            logger.debug(f"Published job {message.job_id} to queue {queue_name}")
            return message.job_id
            
        except Exception as e:
            logger.error(f"Error publishing message: {e}")
            raise
    
    async def subscribe(self,
                       queue_name: str,
                       handler: Callable[[JobMessage], Any],
                       max_concurrent: int = 5) -> None:
        """
        Subscribe to queue with message handler
        
        Args:
            queue_name: Queue to subscribe to
            handler: Async message handler function
            max_concurrent: Maximum concurrent messages
        """
        if not self._redis:
            raise RuntimeError("Message queue not connected")
        
        self._subscribers[queue_name] = {
            "handler": handler,
            "max_concurrent": max_concurrent,
            "semaphore": asyncio.Semaphore(max_concurrent)
        }
        
        # Create consumer group if it doesn't exist
        try:
            await self._redis.xgroup_create(
                f"{queue_name}:stream",
                self.consumer_group,
                id="0",
                mkstream=True
            )
        except Exception:
            # Group already exists
            pass
        
        logger.info(f"Subscribed to queue {queue_name} with max_concurrent={max_concurrent}")
    
    async def start_consumers(self) -> None:
        """Start consumer tasks for all subscribed queues"""
        if self._running:
            return
        
        self._running = True
        
        for queue_name, config in self._subscribers.items():
            # Start priority queue consumer
            task = asyncio.create_task(
                self._consume_priority_queue(queue_name, config)
            )
            self._consumer_tasks.append(task)
            
            # Start delayed queue processor
            task = asyncio.create_task(
                self._process_delayed_queue(queue_name)
            )
            self._consumer_tasks.append(task)
        
        logger.info(f"Started {len(self._consumer_tasks)} consumer tasks")
    
    async def _consume_priority_queue(self, queue_name: str, config: Dict[str, Any]) -> None:
        """Consume messages from priority queue"""
        handler = config["handler"]
        semaphore = config["semaphore"]
        
        while self._running:
            try:
                # Get highest priority job
                result = await self._redis.zpopmin(f"{queue_name}:priority")
                
                if not result:
                    await asyncio.sleep(1)
                    continue
                
                job_id = result[0][0]  # (job_id, score) tuple
                
                # Get message data
                message_data = await self._redis.hget(f"{queue_name}:messages", job_id)
                if not message_data:
                    continue
                
                # Parse message
                message_dict = json.loads(message_data)
                message = JobMessage.from_dict(message_dict)
                
                # Process with concurrency control
                async with semaphore:
                    await self._process_message(queue_name, message, handler)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in priority queue consumer: {e}")
                await asyncio.sleep(5)
    
    async def _process_delayed_queue(self, queue_name: str) -> None:
        """Process delayed messages that are ready"""
        while self._running:
            try:
                current_time = datetime.now(timezone.utc).timestamp() * 1000
                
                # Get ready delayed jobs
                ready_jobs = await self._redis.zrangebyscore(
                    f"{queue_name}:delayed",
                    0,
                    current_time,
                    withscores=True
                )
                
                if ready_jobs:
                    for job_id, score in ready_jobs:
                        # Move to priority queue
                        message_data = await self._redis.hget(f"{queue_name}:messages", job_id)
                        if message_data:
                            message_dict = json.loads(message_data)
                            message = JobMessage.from_dict(message_dict)
                            
                            # Add to priority queue
                            priority_score = -message.priority
                            await self._redis.zadd(f"{queue_name}:priority", {job_id: priority_score})
                        
                        # Remove from delayed queue
                        await self._redis.zrem(f"{queue_name}:delayed", job_id)
                
                await asyncio.sleep(1)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error processing delayed queue: {e}")
                await asyncio.sleep(5)
    
    async def _process_message(self,
                              queue_name: str,
                              message: JobMessage,
                              handler: Callable[[JobMessage], Any]) -> None:
        """Process individual message with error handling"""
        job_id = message.job_id
        
        try:
            # Update job status to running
            await self._update_job_status(job_id, JobStatus.RUNNING)
            
            logger.debug(f"Processing job {job_id}")
            
            # Call handler
            await handler(message)
            
            # Update job status to completed
            await self._update_job_status(job_id, JobStatus.COMPLETED)
            
            # Clean up message
            await self._redis.hdel(f"{queue_name}:messages", job_id)
            
            logger.debug(f"Job {job_id} completed successfully")
            
        except Exception as e:
            logger.error(f"Error processing job {job_id}: {e}")
            
            # Handle retry logic
            message.retry_count += 1
            
            if message.retry_count <= message.max_retries:
                logger.info(f"Retrying job {job_id} (attempt {message.retry_count}/{message.max_retries})")
                
                # Retry with exponential backoff
                delay = 2 ** message.retry_count  # 2, 4, 8 seconds
                await self.publish(queue_name, message, delay=delay)
            else:
                # Move to dead letter queue
                await self._move_to_dead_letter_queue(queue_name, message, str(e))
                await self._update_job_status(job_id, JobStatus.FAILED, error=str(e))
    
    async def _move_to_dead_letter_queue(self,
                                       queue_name: str,
                                       message: JobMessage,
                                       error: str) -> None:
        """Move failed message to dead letter queue"""
        dlq_name = f"{queue_name}:dlq"
        
        dlq_message = {
            **message.to_dict(),
            "failed_at": datetime.now(timezone.utc).isoformat(),
            "error": error
        }
        
        await self._redis.lpush(dlq_name, json.dumps(dlq_message))
        
        logger.warning(f"Job {message.job_id} moved to dead letter queue after {message.retry_count} retries")
    
    async def _update_job_status(self,
                               job_id: str,
                               status: JobStatus,
                               error: Optional[str] = None) -> None:
        """Update job status in Redis"""
        status_data = {
            "status": status.value,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        if error:
            status_data["error"] = error
        
        await self._redis.hset(f"jobs:{job_id}", mapping=status_data)
    
    async def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job status"""
        if not self._redis:
            return None
        
        status_data = await self._redis.hgetall(f"jobs:{job_id}")
        return status_data if status_data else None
    
    async def cancel_job(self, job_id: str) -> bool:
        """Cancel queued job"""
        if not self._redis:
            return False
        
        try:
            # Remove from all queues
            removed = 0
            
            for queue_name in self._subscribers.keys():
                removed += await self._redis.zrem(f"{queue_name}:priority", job_id)
                removed += await self._redis.zrem(f"{queue_name}:delayed", job_id)
                await self._redis.hdel(f"{queue_name}:messages", job_id)
            
            if removed > 0:
                await self._update_job_status(job_id, JobStatus.CANCELLED)
                logger.info(f"Job {job_id} cancelled successfully")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error cancelling job {job_id}: {e}")
            return False
    
    async def get_queue_info(self, queue_name: str) -> Dict[str, Any]:
        """Get queue statistics"""
        if not self._redis:
            return {}
        
        try:
            priority_count = await self._redis.zcard(f"{queue_name}:priority")
            delayed_count = await self._redis.zcard(f"{queue_name}:delayed")
            dlq_count = await self._redis.llen(f"{queue_name}:dlq")
            
            return {
                "queue_name": queue_name,
                "priority_jobs": priority_count,
                "delayed_jobs": delayed_count,
                "dead_letter_jobs": dlq_count,
                "total_jobs": priority_count + delayed_count
            }
            
        except Exception as e:
            logger.error(f"Error getting queue info: {e}")
            return {"error": str(e)}
    
    async def purge_queue(self, queue_name: str) -> int:
        """Purge all messages from queue"""
        if not self._redis:
            return 0
        
        try:
            pipeline = self._redis.pipeline()
            
            # Delete all queue structures
            pipeline.delete(f"{queue_name}:priority")
            pipeline.delete(f"{queue_name}:delayed")
            pipeline.delete(f"{queue_name}:messages")
            
            await pipeline.execute()
            
            logger.info(f"Queue {queue_name} purged")
            return 1
            
        except Exception as e:
            logger.error(f"Error purging queue: {e}")
            return 0
    
    async def requeue_dead_letters(self, queue_name: str, max_items: int = 100) -> int:
        """Requeue messages from dead letter queue"""
        if not self._redis:
            return 0
        
        try:
            dlq_name = f"{queue_name}:dlq"
            requeued = 0
            
            for _ in range(max_items):
                dlq_data = await self._redis.rpop(dlq_name)
                if not dlq_data:
                    break
                
                try:
                    dlq_message = json.loads(dlq_data)
                    # Reset retry count
                    dlq_message["retry_count"] = 0
                    
                    message = JobMessage.from_dict(dlq_message)
                    await self.publish(queue_name, message)
                    requeued += 1
                    
                except Exception as e:
                    logger.error(f"Error requeuing dead letter: {e}")
                    # Put it back
                    await self._redis.lpush(dlq_name, dlq_data)
                    break
            
            logger.info(f"Requeued {requeued} messages from dead letter queue")
            return requeued
            
        except Exception as e:
            logger.error(f"Error requeuing dead letters: {e}")
            return 0