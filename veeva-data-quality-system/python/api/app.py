"""
FastAPI application factory for Veeva Data Quality System
"""

import os
import asyncio
from typing import Dict, Any, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.openapi.utils import get_openapi
import uvicorn

from .routes.validation_routes import router as validation_router
from .routes.monitoring_routes import router as monitoring_router
from .routes.admin_routes import router as admin_router
from .middleware.authentication import AuthenticationMiddleware
from .middleware.rate_limiting import RateLimitMiddleware
from .middleware.request_validation import RequestValidationMiddleware
from ..database.database_factory import DatabaseFactory
from ..cache.cache_manager import CacheManager, CacheConfig
from ..utils.logging_config import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    try:
        # Initialize database manager
        db_config = DatabaseFactory.from_environment()
        db_manager = await DatabaseFactory.create_database_manager(db_config)
        app.state.db_manager = db_manager
        
        # Initialize cache manager
        cache_config = CacheConfig(
            redis_enabled=os.getenv('REDIS_ENABLED', 'true').lower() == 'true',
            redis_host=os.getenv('REDIS_HOST', 'localhost'),
            redis_port=int(os.getenv('REDIS_PORT', 6379)),
            redis_password=os.getenv('REDIS_PASSWORD'),
            redis_ttl=int(os.getenv('CACHE_TTL', 3600))
        )
        
        cache_manager = CacheManager(cache_config)
        await cache_manager.initialize()
        app.state.cache_manager = cache_manager
        
        logger.info("API application started successfully")
        
        yield
        
    except Exception as e:
        logger.error(f"Failed to start API application: {e}")
        raise
    
    finally:
        # Shutdown
        try:
            if hasattr(app.state, 'db_manager'):
                await app.state.db_manager.close()
            
            if hasattr(app.state, 'cache_manager'):
                await app.state.cache_manager.close()
            
            await DatabaseFactory.close_all_connections()
            logger.info("API application shutdown complete")
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")


def create_app(config: Optional[Dict[str, Any]] = None) -> FastAPI:
    """
    Create FastAPI application with all routes and middleware
    
    Args:
        config: Optional application configuration
        
    Returns:
        Configured FastAPI application
    """
    config = config or {}
    
    # Create FastAPI application
    app = FastAPI(
        title="Veeva Data Quality System API",
        description="RESTful API for healthcare provider data quality validation and monitoring",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan
    )
    
    # Add middleware
    _add_middleware(app, config)
    
    # Add routes
    _add_routes(app)
    
    # Add error handlers
    _add_error_handlers(app)
    
    # Customize OpenAPI schema
    _customize_openapi(app)
    
    return app


def _add_middleware(app: FastAPI, config: Dict[str, Any]) -> None:
    """Add middleware to the application"""
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.get('cors_origins', ["*"]),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
        allow_headers=["*"],
    )
    
    # Compression middleware
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    
    # Rate limiting middleware
    app.add_middleware(RateLimitMiddleware)
    
    # Authentication middleware
    app.add_middleware(AuthenticationMiddleware)
    
    # Request validation middleware
    app.add_middleware(RequestValidationMiddleware)


def _add_routes(app: FastAPI) -> None:
    """Add all route handlers to the application"""
    
    # Health check endpoint
    @app.get("/health", tags=["health"])
    async def health_check():
        """Basic health check endpoint"""
        return {
            "status": "healthy",
            "timestamp": pd.Timestamp.now().isoformat(),
            "version": "1.0.0"
        }
    
    # Include route modules
    app.include_router(
        validation_router, 
        prefix="/api/v1/validation", 
        tags=["validation"]
    )
    
    app.include_router(
        monitoring_router, 
        prefix="/api/v1/monitoring", 
        tags=["monitoring"]
    )
    
    app.include_router(
        admin_router, 
        prefix="/api/v1/admin", 
        tags=["admin"]
    )


def _add_error_handlers(app: FastAPI) -> None:
    """Add global error handlers"""
    
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        """Handle HTTP exceptions"""
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.status_code,
                    "message": exc.detail,
                    "path": str(request.url),
                    "timestamp": pd.Timestamp.now().isoformat()
                }
            }
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """Handle general exceptions"""
        logger.error(f"Unhandled exception: {exc}", exc_info=True)
        
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": 500,
                    "message": "Internal server error",
                    "path": str(request.url),
                    "timestamp": pd.Timestamp.now().isoformat()
                }
            }
        )


def _customize_openapi(app: FastAPI) -> None:
    """Customize OpenAPI schema"""
    
    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema
        
        openapi_schema = get_openapi(
            title="Veeva Data Quality System API",
            version="1.0.0",
            description="""
            Comprehensive RESTful API for healthcare provider data quality validation and monitoring.
            
            ## Features
            - **Data Validation**: Execute AI-enhanced validation queries
            - **Monitoring**: System health and performance metrics  
            - **Administration**: Configuration and maintenance operations
            - **Authentication**: JWT-based security
            - **Rate Limiting**: Request throttling and quotas
            - **Caching**: Multi-level caching for optimal performance
            
            ## Architecture
            - FastAPI framework with async/await pattern
            - Multi-database support (SQLite, PostgreSQL, MySQL)
            - Redis caching layer
            - Microservices-ready design
            
            ## Performance
            - Sub-5 second response times for most operations
            - Horizontal scaling support
            - Connection pooling and read replicas
            - Intelligent query optimization
            """,
            routes=app.routes,
        )
        
        # Add security schemes
        openapi_schema["components"]["securitySchemes"] = {
            "Bearer": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
            }
        }
        
        # Add rate limiting information
        openapi_schema["info"]["x-rateLimit"] = {
            "default": "1000 requests per hour per IP",
            "authenticated": "10000 requests per hour per user"
        }
        
        app.openapi_schema = openapi_schema
        return app.openapi_schema
    
    app.openapi = custom_openapi


async def start_server(
    host: str = "0.0.0.0",
    port: int = 8000,
    workers: int = 1,
    reload: bool = False,
    config: Optional[Dict[str, Any]] = None
) -> None:
    """
    Start the API server
    
    Args:
        host: Host to bind to
        port: Port to bind to
        workers: Number of worker processes
        reload: Enable auto-reload for development
        config: Application configuration
    """
    app = create_app(config)
    
    uvicorn_config = uvicorn.Config(
        app=app,
        host=host,
        port=port,
        workers=workers,
        reload=reload,
        log_level="info",
        access_log=True,
        use_colors=True
    )
    
    server = uvicorn.Server(uvicorn_config)
    
    try:
        logger.info(f"Starting API server on {host}:{port} with {workers} workers")
        await server.serve()
    except KeyboardInterrupt:
        logger.info("Server shutdown requested")
    except Exception as e:
        logger.error(f"Server error: {e}")
        raise


if __name__ == "__main__":
    import pandas as pd
    import argparse
    
    parser = argparse.ArgumentParser(description="Veeva Data Quality System API")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    parser.add_argument("--workers", type=int, default=1, help="Number of workers")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    
    args = parser.parse_args()
    
    asyncio.run(start_server(
        host=args.host,
        port=args.port,
        workers=args.workers,
        reload=args.reload
    ))