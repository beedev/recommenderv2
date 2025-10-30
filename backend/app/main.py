"""
Recommender_v2 - S1→S7 State-by-State Configurator
FastAPI Application Entry Point
"""

import logging
import json
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from dotenv import load_dotenv

from .api.v1.configurator import router as configurator_router
from .services.intent.parameter_extractor import ParameterExtractor
from .services.neo4j.product_search import Neo4jProductSearch
from .services.response.message_generator import MessageGenerator
from .services.orchestrator.state_orchestrator import StateByStateOrchestrator
from .services.graph.configurator_wrapper import ConfiguratorGraphWrapper

# Database and LangGraph imports
from .database.database import (
    init_redis,
    init_postgresql,
    close_redis,
    close_postgresql,
    get_redis_client,
    Base
)
from .database.redis_session_storage import init_redis_session_storage
from .database.postgres_archival import postgres_archival_service
from .services.observability.langsmith_service import get_langsmith_service

# Load environment variables
load_dotenv()

# Configure logging from environment
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
logger.info(f"Logging configured at {LOG_LEVEL} level")

# Configure rate limiting from environment
RATE_LIMIT_PER_MINUTE = os.getenv("RATE_LIMIT_PER_MINUTE", "60")
limiter = Limiter(key_func=get_remote_address, default_limits=[f"{RATE_LIMIT_PER_MINUTE}/minute"])
logger.info(f"Rate limiting configured: {RATE_LIMIT_PER_MINUTE} requests/minute")

# Global instances
parameter_extractor = None
neo4j_search = None
message_generator = None
orchestrator = None
graph_wrapper = None
component_applicability_config = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager - startup and shutdown"""

    # Startup
    logger.info("Starting Recommender_v2 application...")

    global parameter_extractor, neo4j_search, message_generator, orchestrator, graph_wrapper, component_applicability_config

    # Load environment variables
    openai_api_key = os.getenv("OPENAI_API_KEY")
    neo4j_uri = os.getenv("NEO4J_URI")
    neo4j_username = os.getenv("NEO4J_USERNAME")
    neo4j_password = os.getenv("NEO4J_PASSWORD")

    if not all([openai_api_key, neo4j_uri, neo4j_username, neo4j_password]):
        raise ValueError("Missing required environment variables")

    # Initialize databases
    logger.info("Initializing databases...")

    try:
        # Initialize Redis for hot session data
        await init_redis()
        logger.info("✓ Redis initialized")

        # Initialize Redis session storage
        redis_client = await get_redis_client()
        init_redis_session_storage(redis_client, ttl=3600)
        logger.info("✓ Redis session storage initialized")
    except Exception as e:
        logger.warning(f"Redis initialization failed: {e}. Continuing without Redis caching.")

    try:
        # Initialize PostgreSQL for archival
        init_postgresql()
        logger.info("✓ PostgreSQL initialized")

        # Create database tables
        from sqlalchemy.ext.asyncio import create_async_engine
        from .database.database import postgresql_manager

        async with postgresql_manager.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        logger.info("✓ Database tables created/verified")

    except Exception as e:
        logger.warning(f"PostgreSQL initialization failed: {e}. Continuing without archival.")

    # Initialize LangSmith observability
    langsmith_service = get_langsmith_service()
    if langsmith_service.is_enabled():
        logger.info("✓ LangSmith observability enabled")
    else:
        logger.info("LangSmith observability disabled")

    # Load component applicability config
    config_path = os.path.join(
        os.path.dirname(__file__),
        "config",
        "component_applicability.json"
    )

    with open(config_path, 'r') as f:
        component_applicability_config = json.load(f)

    logger.info("Loaded component applicability configuration")

    # Initialize services
    parameter_extractor = ParameterExtractor(openai_api_key)
    neo4j_search = Neo4jProductSearch(neo4j_uri, neo4j_username, neo4j_password)
    message_generator = MessageGenerator()

    # Initialize orchestrator
    orchestrator = StateByStateOrchestrator(
        parameter_extractor=parameter_extractor,
        product_search=neo4j_search,
        message_generator=message_generator,
        component_applicability_config=component_applicability_config
    )

    # Initialize LangGraph wrapper for observability
    graph_wrapper = ConfiguratorGraphWrapper(orchestrator)
    logger.info("✓ LangGraph wrapper initialized")

    logger.info("All services initialized successfully")

    yield

    # Shutdown
    logger.info("Shutting down Recommender_v2 application...")

    # Close databases
    try:
        await close_redis()
        logger.info("✓ Redis closed")
    except Exception as e:
        logger.error(f"Error closing Redis: {e}")

    try:
        await close_postgresql()
        logger.info("✓ PostgreSQL closed")
    except Exception as e:
        logger.error(f"Error closing PostgreSQL: {e}")

    # Close Neo4j
    if neo4j_search:
        await neo4j_search.close()
        logger.info("✓ Neo4j closed")

    logger.info("Shutdown complete")


# Create FastAPI application
app = FastAPI(
    title="Recommender_v2 - S1→S7 Configurator",
    description="State-by-state welding equipment configurator with compatibility validation",
    version="2.0.0",
    lifespan=lifespan
)

# Configure rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Configure CORS from environment
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:8001,http://localhost:3001").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in ALLOWED_ORIGINS],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
logger.info(f"CORS configured with origins: {ALLOWED_ORIGINS}")

# Add security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Add security headers to all responses"""
    response = await call_next(request)

    # Security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

    return response

logger.info("Security headers middleware configured")


# Dependency injection for orchestrator
def get_orchestrator() -> StateByStateOrchestrator:
    """Get orchestrator instance for dependency injection"""
    return orchestrator


def get_graph_wrapper() -> ConfiguratorGraphWrapper:
    """Get LangGraph wrapper instance for dependency injection"""
    return graph_wrapper


# Include routers
app.include_router(configurator_router)

# Override dependency in app (not router)
from .api.v1.configurator import get_orchestrator_dep, get_graph_wrapper_dep
app.dependency_overrides[get_orchestrator_dep] = get_orchestrator
app.dependency_overrides[get_graph_wrapper_dep] = get_graph_wrapper


@app.get("/")
async def root():
    """Root endpoint - health check"""
    return {
        "service": "Recommender_v2",
        "version": "2.0.0",
        "description": "S1→S7 State-by-State Welding Equipment Configurator",
        "endpoints": {
            "configurator": "/api/v1/configurator/message",
            "configurator_graph": "/api/v1/configurator/message-graph (LangGraph wrapper)",
            "docs": "/docs"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""

    from .database.database import redis_manager, postgresql_manager

    langsmith_service = get_langsmith_service()

    health_status = {
        "status": "healthy",
        "services": {
            "parameter_extractor": parameter_extractor is not None,
            "neo4j_search": neo4j_search is not None,
            "message_generator": message_generator is not None,
            "orchestrator": orchestrator is not None,
            "graph_wrapper": graph_wrapper is not None,
            "redis": redis_manager._initialized,
            "postgresql": postgresql_manager._initialized,
            "langsmith": langsmith_service.is_enabled()
        }
    }

    # Core services must be healthy
    core_services_healthy = all([
        health_status["services"]["parameter_extractor"],
        health_status["services"]["neo4j_search"],
        health_status["services"]["message_generator"],
        health_status["services"]["orchestrator"]
    ])

    if not core_services_healthy:
        health_status["status"] = "unhealthy"

    return health_status


if __name__ == "__main__":
    import uvicorn

    # Run on port 8001 (V1 uses 8000)
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
        log_level="info"
    )
