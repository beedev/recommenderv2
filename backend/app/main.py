"""
Recommender_v2 - S1→S7 State-by-State Configurator
FastAPI Application Entry Point
"""

import logging
import json
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from .api.v1.configurator import router as configurator_router
from .services.intent.parameter_extractor import ParameterExtractor
from .services.neo4j.product_search import Neo4jProductSearch
from .services.response.message_generator import MessageGenerator
from .services.orchestrator.state_orchestrator import StateByStateOrchestrator

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global instances
parameter_extractor = None
neo4j_search = None
message_generator = None
orchestrator = None
component_applicability_config = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager - startup and shutdown"""

    # Startup
    logger.info("Starting Recommender_v2 application...")

    global parameter_extractor, neo4j_search, message_generator, orchestrator, component_applicability_config

    # Load environment variables
    openai_api_key = os.getenv("OPENAI_API_KEY")
    neo4j_uri = os.getenv("NEO4J_URI")
    neo4j_username = os.getenv("NEO4J_USERNAME")
    neo4j_password = os.getenv("NEO4J_PASSWORD")

    if not all([openai_api_key, neo4j_uri, neo4j_username, neo4j_password]):
        raise ValueError("Missing required environment variables")

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

    logger.info("All services initialized successfully")

    yield

    # Shutdown
    logger.info("Shutting down Recommender_v2 application...")

    if neo4j_search:
        await neo4j_search.close()

    logger.info("Shutdown complete")


# Create FastAPI application
app = FastAPI(
    title="Recommender_v2 - S1→S7 Configurator",
    description="State-by-state welding equipment configurator with compatibility validation",
    version="2.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Dependency injection for orchestrator
def get_orchestrator() -> StateByStateOrchestrator:
    """Get orchestrator instance for dependency injection"""
    return orchestrator


# Include routers
app.include_router(configurator_router)

# Override dependency in app (not router)
from .api.v1.configurator import get_orchestrator_dep
app.dependency_overrides[get_orchestrator_dep] = get_orchestrator


@app.get("/")
async def root():
    """Root endpoint - health check"""
    return {
        "service": "Recommender_v2",
        "version": "2.0.0",
        "description": "S1→S7 State-by-State Welding Equipment Configurator",
        "endpoints": {
            "configurator": "/api/v1/configurator/message",
            "docs": "/docs"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""

    health_status = {
        "status": "healthy",
        "services": {
            "parameter_extractor": parameter_extractor is not None,
            "neo4j_search": neo4j_search is not None,
            "message_generator": message_generator is not None,
            "orchestrator": orchestrator is not None
        }
    }

    all_healthy = all(health_status["services"].values())

    if not all_healthy:
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
