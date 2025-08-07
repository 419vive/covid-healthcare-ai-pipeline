"""
Circuit breaker pattern implementation for fault tolerance
"""

import asyncio
import time
from enum import Enum
from typing import Any, Callable, Dict, Optional, TypeVar, Generic
from dataclasses import dataclass, field
from collections import defaultdict, deque
import statistics

from ..utils.logging_config import get_logger

logger = get_logger(__name__)

T = TypeVar('T')


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, calls blocked
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration"""
    failure_threshold: int = 5           # Failures before opening
    recovery_timeout: int = 60           # Seconds before trying half-open
    success_threshold: int = 3           # Successes in half-open to close
    timeout: float = 30.0               # Request timeout
    sliding_window_size: int = 100       # Size of metrics window
    minimum_requests: int = 10           # Minimum requests before evaluation
    failure_rate_threshold: float = 50.0 # Failure rate % threshold
    slow_call_duration: float = 5.0      # Slow call threshold
    slow_call_rate_threshold: float = 50.0 # Slow call rate % threshold


@dataclass
class CallResult:
    """Result of a circuit breaker call"""
    success: bool
    duration: float
    error: Optional[Exception] = None
    timestamp: float = field(default_factory=time.time)


class CircuitBreakerMetrics:
    """Metrics collector for circuit breaker"""
    
    def __init__(self, window_size: int = 100):
        self.window_size = window_size
        self.calls = deque(maxlen=window_size)
        self.total_calls = 0
        self.total_failures = 0
        self.total_successes = 0
        self.total_slow_calls = 0
    
    def record_call(self, result: CallResult) -> None:
        """Record a call result"""
        self.calls.append(result)
        self.total_calls += 1
        
        if result.success:
            self.total_successes += 1
        else:
            self.total_failures += 1
        
        # Check if call was slow
        slow_threshold = getattr(self, 'slow_call_duration', 5.0)
        if result.duration >= slow_threshold:
            self.total_slow_calls += 1
    
    def get_failure_rate(self) -> float:
        """Get current failure rate percentage"""
        if not self.calls:
            return 0.0
        
        failures = sum(1 for call in self.calls if not call.success)
        return (failures / len(self.calls)) * 100
    
    def get_slow_call_rate(self) -> float:
        """Get current slow call rate percentage"""
        if not self.calls:
            return 0.0
        
        slow_threshold = getattr(self, 'slow_call_duration', 5.0)
        slow_calls = sum(1 for call in self.calls if call.duration >= slow_threshold)
        return (slow_calls / len(self.calls)) * 100
    
    def get_average_duration(self) -> float:
        """Get average call duration"""
        if not self.calls:
            return 0.0
        
        return statistics.mean(call.duration for call in self.calls)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive metrics"""
        return {
            "total_calls": self.total_calls,
            "total_failures": self.total_failures,
            "total_successes": self.total_successes,
            "total_slow_calls": self.total_slow_calls,
            "current_window_size": len(self.calls),
            "failure_rate": self.get_failure_rate(),
            "slow_call_rate": self.get_slow_call_rate(),
            "average_duration": self.get_average_duration()
        }


class CircuitBreakerError(Exception):
    """Circuit breaker specific errors"""
    pass


class CircuitOpenError(CircuitBreakerError):
    """Raised when circuit is open"""
    pass


class CircuitBreaker(Generic[T]):
    """
    Circuit breaker implementation providing:
    - Automatic failure detection
    - Service degradation protection
    - Self-healing capabilities
    - Comprehensive metrics
    """
    
    def __init__(self, 
                 name: str,
                 config: Optional[CircuitBreakerConfig] = None):
        """
        Initialize circuit breaker
        
        Args:
            name: Circuit breaker identifier
            config: Configuration options
        """
        self.name = name
        self.config = config or CircuitBreakerConfig()
        
        # State management
        self._state = CircuitState.CLOSED
        self._last_failure_time = 0
        self._consecutive_failures = 0
        self._consecutive_successes = 0
        
        # Metrics
        self.metrics = CircuitBreakerMetrics(self.config.sliding_window_size)
        self.metrics.slow_call_duration = self.config.slow_call_duration
        
        # Synchronization
        self._lock = asyncio.Lock()
        
        logger.info(f"Circuit breaker '{name}' initialized")
    
    @property
    def state(self) -> CircuitState:
        """Get current circuit state"""
        return self._state
    
    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed (normal operation)"""
        return self._state == CircuitState.CLOSED
    
    @property
    def is_open(self) -> bool:
        """Check if circuit is open (failing)"""
        return self._state == CircuitState.OPEN
    
    @property
    def is_half_open(self) -> bool:
        """Check if circuit is half-open (testing)"""
        return self._state == CircuitState.HALF_OPEN
    
    async def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """
        Execute function with circuit breaker protection
        
        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            CircuitOpenError: When circuit is open
            Exception: Original function exceptions
        """
        async with self._lock:
            # Check if call should be allowed
            if not await self._should_allow_request():
                raise CircuitOpenError(f"Circuit breaker '{self.name}' is open")
            
            # If half-open, only allow limited calls
            if self._state == CircuitState.HALF_OPEN:
                return await self._execute_half_open_call(func, *args, **kwargs)
        
        # Execute call for closed circuit
        return await self._execute_call(func, *args, **kwargs)
    
    async def _should_allow_request(self) -> bool:
        """Determine if request should be allowed"""
        current_time = time.time()
        
        if self._state == CircuitState.CLOSED:
            return True
        
        elif self._state == CircuitState.OPEN:
            # Check if recovery timeout has passed
            if current_time - self._last_failure_time >= self.config.recovery_timeout:
                logger.info(f"Circuit breaker '{self.name}' transitioning to half-open")
                self._state = CircuitState.HALF_OPEN
                self._consecutive_successes = 0
                return True
            return False
        
        elif self._state == CircuitState.HALF_OPEN:
            return True
        
        return False
    
    async def _execute_call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Execute function call with timing and error handling"""
        start_time = time.time()
        
        try:
            # Add timeout if function supports it
            if asyncio.iscoroutinefunction(func):
                result = await asyncio.wait_for(
                    func(*args, **kwargs), 
                    timeout=self.config.timeout
                )
            else:
                # Run synchronous function in executor
                loop = asyncio.get_event_loop()
                result = await asyncio.wait_for(
                    loop.run_in_executor(None, func, *args, **kwargs),
                    timeout=self.config.timeout
                )
            
            duration = time.time() - start_time
            
            # Record successful call
            call_result = CallResult(success=True, duration=duration)
            await self._on_success(call_result)
            
            return result
            
        except Exception as e:
            duration = time.time() - start_time
            
            # Record failed call
            call_result = CallResult(success=False, duration=duration, error=e)
            await self._on_failure(call_result)
            
            raise
    
    async def _execute_half_open_call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Execute call in half-open state"""
        try:
            result = await self._execute_call(func, *args, **kwargs)
            
            # Count consecutive successes
            self._consecutive_successes += 1
            
            # If enough successes, close the circuit
            if self._consecutive_successes >= self.config.success_threshold:
                logger.info(f"Circuit breaker '{self.name}' closing after {self._consecutive_successes} successes")
                self._state = CircuitState.CLOSED
                self._consecutive_failures = 0
                self._consecutive_successes = 0
            
            return result
            
        except Exception as e:
            # Failure in half-open state opens the circuit immediately
            logger.warning(f"Circuit breaker '{self.name}' opening due to failure in half-open state")
            self._state = CircuitState.OPEN
            self._last_failure_time = time.time()
            self._consecutive_successes = 0
            raise
    
    async def _on_success(self, call_result: CallResult) -> None:
        """Handle successful call"""
        self.metrics.record_call(call_result)
        
        if self._state == CircuitState.CLOSED:
            self._consecutive_failures = 0
    
    async def _on_failure(self, call_result: CallResult) -> None:
        """Handle failed call"""
        self.metrics.record_call(call_result)
        self._consecutive_failures += 1
        self._last_failure_time = time.time()
        
        # Check if circuit should open
        if self._state == CircuitState.CLOSED and await self._should_trip():
            logger.warning(f"Circuit breaker '{self.name}' opening due to failures")
            self._state = CircuitState.OPEN
            self._consecutive_successes = 0
    
    async def _should_trip(self) -> bool:
        """Determine if circuit should trip (open)"""
        # Check consecutive failures threshold
        if self._consecutive_failures >= self.config.failure_threshold:
            return True
        
        # Check if we have enough data for statistical analysis
        if len(self.metrics.calls) < self.config.minimum_requests:
            return False
        
        # Check failure rate threshold
        failure_rate = self.metrics.get_failure_rate()
        if failure_rate >= self.config.failure_rate_threshold:
            logger.info(f"Circuit breaker '{self.name}' failure rate: {failure_rate:.1f}%")
            return True
        
        # Check slow call rate threshold
        slow_call_rate = self.metrics.get_slow_call_rate()
        if slow_call_rate >= self.config.slow_call_rate_threshold:
            logger.info(f"Circuit breaker '{self.name}' slow call rate: {slow_call_rate:.1f}%")
            return True
        
        return False
    
    async def force_open(self) -> None:
        """Manually open the circuit"""
        async with self._lock:
            logger.warning(f"Circuit breaker '{self.name}' manually opened")
            self._state = CircuitState.OPEN
            self._last_failure_time = time.time()
    
    async def force_close(self) -> None:
        """Manually close the circuit"""
        async with self._lock:
            logger.info(f"Circuit breaker '{self.name}' manually closed")
            self._state = CircuitState.CLOSED
            self._consecutive_failures = 0
            self._consecutive_successes = 0
    
    async def force_half_open(self) -> None:
        """Manually set circuit to half-open"""
        async with self._lock:
            logger.info(f"Circuit breaker '{self.name}' manually set to half-open")
            self._state = CircuitState.HALF_OPEN
            self._consecutive_successes = 0
    
    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive circuit breaker status"""
        return {
            "name": self.name,
            "state": self._state.value,
            "consecutive_failures": self._consecutive_failures,
            "consecutive_successes": self._consecutive_successes,
            "last_failure_time": self._last_failure_time,
            "config": {
                "failure_threshold": self.config.failure_threshold,
                "recovery_timeout": self.config.recovery_timeout,
                "success_threshold": self.config.success_threshold,
                "timeout": self.config.timeout
            },
            "metrics": self.metrics.get_stats()
        }


class CircuitBreakerManager:
    """
    Manager for multiple circuit breakers
    """
    
    def __init__(self):
        self._breakers: Dict[str, CircuitBreaker] = {}
        self._default_config = CircuitBreakerConfig()
    
    def get_breaker(self, 
                   name: str, 
                   config: Optional[CircuitBreakerConfig] = None) -> CircuitBreaker:
        """
        Get or create circuit breaker
        
        Args:
            name: Circuit breaker name
            config: Optional configuration
            
        Returns:
            CircuitBreaker instance
        """
        if name not in self._breakers:
            breaker_config = config or self._default_config
            self._breakers[name] = CircuitBreaker(name, breaker_config)
        
        return self._breakers[name]
    
    def remove_breaker(self, name: str) -> bool:
        """Remove circuit breaker"""
        if name in self._breakers:
            del self._breakers[name]
            return True
        return False
    
    def get_all_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all circuit breakers"""
        return {
            name: breaker.get_status()
            for name, breaker in self._breakers.items()
        }
    
    async def reset_all(self) -> None:
        """Reset all circuit breakers to closed state"""
        for breaker in self._breakers.values():
            await breaker.force_close()
    
    def set_default_config(self, config: CircuitBreakerConfig) -> None:
        """Set default configuration for new breakers"""
        self._default_config = config


# Global circuit breaker manager instance
circuit_breaker_manager = CircuitBreakerManager()