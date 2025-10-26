# LangGraph Integration Architecture

## Overview

The Recommender_v2 system now uses **LangGraph** for workflow orchestration with **LangSmith** observability integration. This architecture provides:

- ✅ **Stateful Workflow Management** - LangGraph StateGraph for S1→S7 progression
- ✅ **Session Persistence** - Redis checkpointing for hot data (24hr TTL)
- ✅ **Long-term Archival** - PostgreSQL for completed sessions
- ✅ **Observability** - LangSmith @traceable decorators for workflow monitoring
- ✅ **Graceful Degradation** - System continues if Redis/PostgreSQL unavailable

---

## Architecture Layers

### 1. Database Layer

#### Redis (Hot Session Data)
- **Purpose**: Fast session state storage with checkpointing
- **TTL**: 24 hours (configurable via `REDIS_TTL_SECONDS`)
- **Configuration**: `.env` variables (REDIS_URL, REDIS_HOST, REDIS_PORT)
- **Manager**: `RedisManager` in `backend/app/database/database.py`
- **Initialization**: Async startup in `main.py` lifespan()

```python
# Redis Configuration
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_TTL_SECONDS=86400  # 24 hours
```

**Features**:
- Connection pooling with `redis.asyncio.Redis`
- Health check integration
- Graceful degradation (app continues without Redis)

#### PostgreSQL (Long-term Archival)
- **Purpose**: Archive completed sessions for analytics
- **Driver**: `asyncpg` for high-performance async operations
- **ORM**: SQLAlchemy 2.0 with async support
- **Configuration**: `.env` variables (POSTGRES_HOST, POSTGRES_PORT, POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB)
- **Manager**: `PostgreSQLManager` in `backend/app/database/database.py`

```python
# PostgreSQL Configuration
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=pconfig
POSTGRES_PASSWORD=your_password
POSTGRES_DB=pconfig
```

**Schema**:
```sql
CREATE TABLE archived_sessions (
    session_id VARCHAR(255) PRIMARY KEY,
    master_parameters JSONB NOT NULL,
    response_json JSONB NOT NULL,
    conversation_messages JSONB NOT NULL,
    agent_actions JSONB,
    current_state VARCHAR(100),
    user_selected_products JSONB,
    compatibility_check_results JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE INDEX idx_archived_sessions_created ON archived_sessions(created_at);
CREATE INDEX idx_archived_sessions_state ON archived_sessions(current_state);
```

**Archival Service**: `PostgresArchivalService` in `backend/app/database/postgres_archival.py`

---

### 2. LangGraph State Models

#### ConfiguratorGraphState (TypedDict)
Bridge between Pydantic `ConversationState` and LangGraph's TypedDict requirements.

**Location**: `backend/app/models/graph_state.py`

```python
class ConfiguratorGraphState(TypedDict, total=False):
    # Session & State
    session_id: str
    thread_id: str
    current_state: str

    # Core Data
    master_parameters: Dict[str, Any]
    response_json: Dict[str, Any]

    # Communication
    messages: Annotated[List[Dict[str, str]], operator.add]

    # Observability
    agent_actions: Annotated[List[Dict[str, Any]], operator.add]
    llm_extractions: List[Dict[str, Any]]
    neo4j_queries: List[Dict[str, Any]]
    state_transitions: List[Dict[str, Any]]
```

**Key Features**:
- `Annotated[List, operator.add]` for append-only lists (messages, agent_actions)
- Conversion functions: `conversation_state_to_graph_state()` and `graph_state_to_conversation_state()`
- Pydantic models for observability: `AgentAction`, `Neo4jQuery`, `LLMExtraction`, `StateTransition`

---

### 3. LangGraph Workflow

#### ConfiguratorGraph
4-node workflow orchestrating the S1→S7 configurator.

**Location**: `backend/app/services/graph/configurator_graph.py`

**Nodes**:
1. **extract_parameters** - LLM parameter extraction with schema-driven MasterParameterJSON
2. **search_products** - Neo4j product search based on extracted parameters
3. **generate_response** - Conversational response generation
4. **determine_next_state** - State machine logic for S1→S7 progression

**Workflow**:
```
START → extract_parameters → search_products → generate_response → determine_next_state → END
```

**Code Structure**:
```python
class ConfiguratorGraph:
    def __init__(
        self,
        parameter_extractor: ParameterExtractor,
        product_search: Neo4jProductSearch,
        message_generator: MessageGenerator,
        component_applicability_config: Dict,
        redis_url: str = None
    ):
        self.graph = self._build_graph()

        # Redis checkpointing
        checkpointer = RedisSaver.from_conn_string(redis_url)
        self.app = self.graph.compile(checkpointer=checkpointer)

    @traceable(name="extract_parameters", run_type="llm")
    async def extract_parameters_node(self, state: ConfiguratorGraphState):
        # LLM parameter extraction
        # Returns updated state with master_parameters

    @traceable(name="search_products", run_type="chain")
    async def search_products_node(self, state: ConfiguratorGraphState):
        # Neo4j product search
        # Returns updated state with products

    @traceable(name="generate_response", run_type="llm")
    async def generate_response_node(self, state: ConfiguratorGraphState):
        # Conversational response generation
        # Returns updated state with message

    @traceable(name="determine_next_state", run_type="tool")
    async def determine_next_state_node(self, state: ConfiguratorGraphState):
        # State machine logic
        # Returns updated state with current_state
```

**LangSmith Integration**:
- Each node decorated with `@traceable` for run tracking
- Captures inputs, outputs, and execution time
- Enables LangSmith UI visualization

---

### 4. Observability Service

#### LangSmithService
Centralized observability service for workflow tracking.

**Location**: `backend/app/services/observability/langsmith_service.py`

**Configuration**:
```python
# .env
LANGSMITH_API_KEY=your_api_key
LANGSMITH_PROJECT=Recommender  # Optional, defaults to "Recommender"
```

**Features**:
- `track_workflow_execution()` - Track complete workflow runs
- `log_agent_action()` - Log individual agent actions
- `log_performance_metrics()` - Log performance data
- `log_error()` - Centralized error logging

**Usage**:
```python
from .services.observability.langsmith_service import langsmith_service

# Check if enabled
if langsmith_service.is_enabled():
    # Track workflow
    await langsmith_service.track_workflow_execution(
        session_id="abc123",
        user_message="I need a 500A power source",
        current_state="power_source_selection",
        result={"message": "Response text"}
    )
```

---

## Integration Points

### FastAPI Application (main.py)

**Lifespan Management**:
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting Recommender_v2 application...")

    # Initialize databases
    try:
        await init_redis()
        logger.info("✓ Redis initialized")
    except Exception as e:
        logger.warning(f"Redis initialization failed: {e}. Continuing without Redis caching.")

    try:
        init_postgresql()
        logger.info("✓ PostgreSQL initialized")

        # Create database tables
        async with postgresql_manager.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("✓ Database tables created/verified")
    except Exception as e:
        logger.warning(f"PostgreSQL initialization failed: {e}. Continuing without archival.")

    # Initialize LangSmith
    if langsmith_service.is_enabled():
        logger.info("✓ LangSmith observability enabled")
    else:
        logger.info("LangSmith observability disabled")

    # Initialize orchestrator and other services...

    yield

    # Shutdown
    await close_redis()
    await close_postgresql()
    logger.info("Shutdown complete")
```

**Health Check**:
```python
@app.get("/health")
async def health_check():
    from .database.database import redis_manager, postgresql_manager

    health_status = {
        "status": "healthy",
        "services": {
            "parameter_extractor": parameter_extractor is not None,
            "neo4j_search": neo4j_search is not None,
            "message_generator": message_generator is not None,
            "orchestrator": orchestrator is not None,
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
```

---

## Session Lifecycle

### 1. Session Creation
```
User Request → Create Session → Initialize ConversationState → Store in Redis
```

### 2. Message Processing
```
User Message → LangGraph Workflow → Update State → Redis Checkpoint
```

**LangGraph Workflow Steps**:
1. **Extract Parameters** - LLM extracts MasterParameterJSON from user message
2. **Search Products** - Neo4j searches based on extracted parameters
3. **Generate Response** - Creates conversational response
4. **Determine Next State** - Updates state machine (S1→S7)

### 3. Session Archival
```
Session Complete → PostgreSQL Archive → Remove from Redis
```

**Archival Trigger**: Manual or automatic based on business logic

---

## Configuration

### Environment Variables

**Redis**:
```bash
REDIS_URL=redis://localhost:6379  # Optional full URL
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_TTL_SECONDS=86400  # 24 hours
```

**PostgreSQL**:
```bash
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=pconfig
POSTGRES_PASSWORD=your_password
POSTGRES_DB=pconfig
```

**LangSmith**:
```bash
LANGSMITH_API_KEY=your_api_key
LANGSMITH_PROJECT=Recommender  # Optional
```

**OpenAI** (for LLM):
```bash
OPENAI_API_KEY=your_openai_key
```

**Neo4j** (for product search):
```bash
NEO4J_URI=neo4j+s://your_instance.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_password
```

---

## Deployment

### Local Development
```bash
# Start servers
./start_servers.sh

# Backend: http://localhost:8001
# Frontend: http://localhost:3001
# API Docs: http://localhost:8001/docs
# Health: http://localhost:8001/health

# Stop servers
./stop_servers.sh
```

### Docker Deployment
```yaml
# docker-compose.yml
version: '3.8'

services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: pconfig
      POSTGRES_PASSWORD: your_password
      POSTGRES_DB: pconfig
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  backend:
    build: ./backend
    ports:
      - "8001:8001"
    environment:
      - REDIS_HOST=redis
      - POSTGRES_HOST=postgres
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - NEO4J_URI=${NEO4J_URI}
      - NEO4J_USERNAME=${NEO4J_USERNAME}
      - NEO4J_PASSWORD=${NEO4J_PASSWORD}
      - LANGSMITH_API_KEY=${LANGSMITH_API_KEY}
    depends_on:
      - redis
      - postgres

volumes:
  redis_data:
  postgres_data:
```

---

## Monitoring & Observability

### LangSmith Dashboard
- **Workflow Visualization**: See complete S1→S7 progression
- **Node Performance**: Track execution time per node
- **Error Tracking**: Centralized error logging
- **Run History**: Search and filter past executions

**Access**: https://smith.langchain.com/ (requires LANGSMITH_API_KEY)

### Health Checks
```bash
# Check system health
curl http://localhost:8001/health

# Expected response
{
  "status": "healthy",
  "services": {
    "parameter_extractor": true,
    "neo4j_search": true,
    "message_generator": true,
    "orchestrator": true,
    "redis": true,
    "postgresql": true,
    "langsmith": false  # true if LANGSMITH_API_KEY set
  }
}
```

### Database Monitoring
```bash
# Redis
redis-cli ping
redis-cli info

# PostgreSQL
psql -h localhost -U pconfig -d pconfig -c "\dt"
psql -h localhost -U pconfig -d pconfig -c "SELECT COUNT(*) FROM archived_sessions;"
```

---

## Testing

### Unit Tests
```bash
cd backend
source venv/bin/activate
pytest tests/
```

### Integration Tests
```bash
# Test API endpoint
curl -X POST http://localhost:8001/api/v1/configurator/message \
  -H "Content-Type: application/json" \
  -d '{"message": "I need a 500A power source", "session_id": null}'

# Expected: Session creation + parameter extraction
```

### Frontend Testing
1. Navigate to http://localhost:3001/test_extraction.html
2. Enter query: "I need a 500A power source"
3. Click "Extract Parameters"
4. Verify extraction results in output section

---

## Troubleshooting

### Redis Connection Issues
```bash
# Check Redis is running
redis-cli ping

# Check logs
tail -f backend.log | grep -i redis

# Common fixes
# 1. Ensure Redis is installed and running
# 2. Check firewall rules
# 3. Verify .env configuration
```

### PostgreSQL Connection Issues
```bash
# Check PostgreSQL is running
pg_isready -h localhost -p 5432

# Check logs
tail -f backend.log | grep -i postgresql

# Common fixes
# 1. Ensure PostgreSQL is installed and running
# 2. Verify credentials in .env
# 3. Create database: createdb -U pconfig pconfig
```

### LangSmith Not Enabled
```bash
# Check configuration
echo $LANGSMITH_API_KEY

# Verify in health check
curl http://localhost:8001/health | jq '.services.langsmith'

# Enable LangSmith
export LANGSMITH_API_KEY=your_api_key
# Restart backend
```

---

## Performance Considerations

### Redis Performance
- **Connection Pooling**: Enabled by default with `redis.asyncio.Redis`
- **TTL Optimization**: 24hr default, adjust based on usage patterns
- **Memory Management**: Monitor Redis memory usage, configure maxmemory policies

### PostgreSQL Performance
- **Indexing**: Created on `created_at` and `current_state` columns
- **JSONB Storage**: Efficient storage for master_parameters and response_json
- **Connection Pooling**: SQLAlchemy async engine with pool size management

### LangSmith Performance
- **Async Logging**: Non-blocking observability calls
- **Batch Operations**: Consider batching for high-volume scenarios
- **Selective Tracing**: Enable only for critical workflows in production

---

## Future Enhancements

### Planned Features
1. **LangGraph Visualization**: Real-time workflow visualization in frontend
2. **Session Analytics**: PostgreSQL-based analytics dashboard
3. **Multi-tenancy**: Support for multiple users with isolated sessions
4. **Workflow Variants**: A/B testing different workflow configurations
5. **Advanced Checkpointing**: Branching and rollback capabilities

### Scalability Improvements
1. **Redis Cluster**: Horizontal scaling for high-volume scenarios
2. **PostgreSQL Read Replicas**: Separate analytics workload from archival writes
3. **Load Balancing**: Multiple backend instances with shared state
4. **Caching Layer**: Additional caching for Neo4j query results

---

## References

- **LangGraph Documentation**: https://langchain-ai.github.io/langgraph/
- **LangSmith Documentation**: https://docs.smith.langchain.com/
- **Redis Documentation**: https://redis.io/docs/
- **PostgreSQL Documentation**: https://www.postgresql.org/docs/
- **SQLAlchemy 2.0**: https://docs.sqlalchemy.org/en/20/
- **FastAPI Lifespan**: https://fastapi.tiangolo.com/advanced/events/

---

## Support

For issues or questions:
1. Check this documentation
2. Review backend.log for error messages
3. Verify health endpoint status
4. Check database connectivity
5. Consult LangSmith dashboard for workflow issues

**Last Updated**: 2025-10-25
**Version**: 2.0.0
