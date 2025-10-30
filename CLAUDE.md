# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Recommender_v2** is a state-by-state welding equipment configurator using LangGraph for multi-agent orchestration. It implements an S1→S7 sequential flow where users are guided through component selection with real-time compatibility validation against a Neo4j graph database.

**Key Distinction from V1**: This is a clean-room implementation that runs on port 8001 (V1 uses 8000) and implements sequential state-machine-based configuration instead of V1's all-at-once recommendation approach.

## Development Commands

### Backend Setup
```bash
cd backend
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Running the Application
```bash
# From backend directory
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload

# Or using main.py directly
python -m app.main
```

### Redis Monitoring
```bash
# Start Redis monitor dashboard (port 8002)
./scripts/redis_monitor.sh start

# Check Redis status
./scripts/redis_monitor.sh status

# View dashboard
open http://localhost:8002

# Stop monitor
./scripts/redis_monitor.sh stop

# Python-based Redis inspection
python scripts/inspect_redis.py [session_id]
```

### Testing & Debugging
```bash
# Check application health
curl http://localhost:8001/health

# Test configurator endpoint
curl -X POST http://localhost:8001/api/v1/configurator/message \
  -H 'Content-Type: application/json' \
  -d '{"message": "I need a MIG welder", "language": "en"}'

# Monitor Redis sessions
redis-cli KEYS "session:*"
redis-cli GET "session:<uuid>"
```

## Architecture Overview

### State Machine Flow (S1→S7)

The system implements a **mandatory sequential flow**:

1. **S1 (PowerSource)**: MANDATORY - cannot be skipped, user must provide details
2. **S2 (Feeder)**: Optional - compatibility validated against S1
3. **S3 (Cooler)**: Optional - compatibility validated against S1+S2
4. **S4 (Interconnector)**: Optional - compatibility validated against S1+S2+S3
5. **S5 (Torch)**: Optional - compatibility validated against S2+S3
6. **S6 (Accessories)**: Optional - category-specific compatibility
7. **S7 (Finalize)**: Validates ≥3 real components selected

**Component Applicability**: Each PowerSource has a Y/N configuration (`component_applicability.json`) that determines which subsequent states are active. Components marked "N" are auto-filled with NA products.

### Core Data Structures

**Master Parameter JSON**: Tracks all user requirements across states. LLM extracts parameters per component using structured prompts. Latest value wins if user changes mind.

**Response JSON**: Acts as shopping cart storing selected products. Structure:
```python
{
  "PowerSource": ComponentSelection | None,
  "Feeder": ComponentSelection | None,
  "Cooler": ComponentSelection | None,
  "Interconnector": ComponentSelection | None,
  "Torch": ComponentSelection | None,
  "Accessories": List[ComponentSelection]
}
```

**Conversation State**: Session management with Redis caching (1-hour TTL) and PostgreSQL archival.

### Service Architecture

**StateByStateOrchestrator** (`app/services/orchestrator/state_orchestrator.py`):
- Central coordinator for S1→S7 flow
- Manages state transitions and validation
- Coordinates between extraction, search, and response services

**ParameterExtractor** (`app/services/intent/parameter_extractor.py`):
- LLM-based entity extraction using OpenAI
- Structured prompts per component type
- Updates Master Parameter JSON incrementally

**Neo4jProductSearch** (`app/services/neo4j/product_search.py`):
- Graph database queries with compatibility validation
- Uses COMPATIBLE_WITH bidirectional relationships
- Component-specific search logic (see compatibility rules below)

**MessageGenerator** (`app/services/response/message_generator.py`):
- Multilingual response generation (12 languages)
- Expertise-level adaptation (expert/advanced/basic)
- User-friendly product presentation

### Multilingual Support

**Supported Languages**: en, es, fr, de, pt, it, zh, ja, ko, ru, ar, hi

**Flow**:
1. Language detection via keyword matching in ParameterExtractor
2. Translation to English for Neo4j queries
3. Response generation in user's native language
4. Expertise-level adaptation (technical terms vs simple explanations)

**Configuration**: `app/services/multilingual/` contains translation dictionaries and language-specific formatting.

### Session Management

**Redis** (port 6379, DB 0):
- Hot session storage with key pattern: `session:{uuid}`
- 1-hour TTL (3600 seconds)
- Stores serialized ConversationState objects

**PostgreSQL**:
- Long-term archival of completed sessions
- LangGraph checkpoint storage
- Observability data (LangSmith integration)

**Session Lifecycle**:
1. User sends message → API creates/retrieves session by UUID
2. ConversationState loaded from Redis
3. Orchestrator processes message and updates state
4. Updated state saved back to Redis with TTL reset
5. Optional archival to PostgreSQL on completion

## Key Implementation Rules

### Compatibility Validation

**Per-Component Rules** (from spec Section 9):

- **Feeder**: Must be compatible with PowerSource (bidirectional COMPATIBLE_WITH)
- **Cooler**: Must be compatible with PowerSource AND Feeder
- **Interconnector**: Must be compatible with PowerSource, Feeder, AND Cooler
- **Torch**: Must be compatible with Feeder AND Cooler (NOT PowerSource)
- **Accessories**: Category-specific compatibility checks

**Neo4j Query Pattern**:
```cypher
MATCH (component:ComponentType)-[:COMPATIBLE_WITH]-(existing:SelectedComponent)
WHERE component.property = value
RETURN component
```

### State Progression Logic

**Applicability Check** (before each state):
```python
# Load component_applicability.json
config = component_applicability_config[power_source_gin]

# If component marked "N", auto-fill NA and skip
if config["Feeder"] == "N":
    response_json.Feeder = NA_PRODUCT
    move_to_next_Y_state()
```

**Parameter Threshold**: Neo4j search only triggered when Master JSON has ≥1 parameter for current component OR user mentions specific product name.

**User Progression**: System waits for explicit user action (selection, skip, or more details) before advancing to next state.

### Error Handling & Edge Cases

**Renegade Products**: Products like "Renegade ES300" with all components marked "N" skip S2-S4 entirely and jump directly to S5 (Torch).

**Session Expiry**: If Redis session expires, API returns 404. User must restart configuration flow.

**Neo4j Connection Failures**: System logs error and returns friendly message. Core services health check will show degraded status.

**LLM Extraction Failures**: System falls back to asking user for more specific details.

## Configuration Files

**`component_applicability.json`**: Maps PowerSource GINs to Y/N configuration for Feeder, Cooler, Interconnector, Torch. Used to determine state skipping.

**`master_parameter_schema.json`**: Defines parameter structure for Master JSON. Includes all possible fields with types and descriptions.

**`product_names.json`**: Product name dictionary for fuzzy matching and normalization. Helps LLM recognize product mentions.

**`.env`**: Environment configuration:
```env
OPENAI_API_KEY=...
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=...
REDIS_HOST=localhost
REDIS_PORT=6379
POSTGRES_HOST=localhost
POSTGRES_DB=configurator
LANGCHAIN_API_KEY=... (optional)
```

## Observability

**LangSmith Integration**: Enabled when `LANGCHAIN_API_KEY` is set. Traces:
- LLM extraction calls
- Neo4j query execution
- State transitions
- Response generation

**Logging**: Structured logging via Python's logging module. Levels: INFO (default), DEBUG, WARNING, ERROR.

**Health Endpoint**: `/health` returns service status for all components (parameter_extractor, neo4j_search, redis, postgresql, langsmith).

## Important Implementation Notes

**PowerSource Mandatory Rule**: S1 cannot be skipped under any circumstances. The orchestrator will keep prompting user until valid PowerSource parameters or product selection is provided.

**Session State Immutability**: Each state update creates a new snapshot. Previous states can be revisited but not modified retroactively.

**Compatibility Caching**: Neo4j compatibility queries are expensive. Consider implementing result caching if performance issues arise with large product catalogs.

**LLM Token Management**: Parameter extraction prompts are designed to minimize token usage. Avoid adding unnecessary context to extraction calls.

**Redis Memory Management**: With 1-hour TTL and expected 20-25 concurrent users, Redis memory should stay under 50MB. Monitor with `redis_monitor.sh` dashboard.

## Documentation

Comprehensive architecture documentation in `/docs`:
- `CORRECTED_STATE_FLOW_ARCHITECTURE.md`: Complete S1→S7 flow specification
- `MASTER_PARAMETER_JSON_ARCHITECTURE.md`: Parameter tracking system
- `LLM_ENTITY_EXTRACTION_ARCHITECTURE.md`: Prompt engineering approach
- `MULTILINGUAL_FLOW.md`: Multilingual support details
- `REDIS_INSPECTION.md`: Redis monitoring guide
- `REDIS_MONITOR_DASHBOARD.md`: Web dashboard documentation

## V1 vs V2 Comparison

| Aspect | V1 (Recommender) | V2 (Recommender_v2) |
|--------|------------------|---------------------|
| Port | 8000 | 8001 |
| Flow | All-at-once | S1→S7 sequential |
| PowerSource | Optional | MANDATORY |
| Output | TrinityPackage list | Response JSON cart |
| Validation | Trinity-based | Per-component compatibility |
| Interaction | Single query | Multi-turn conversation |
| Session | In-memory | Redis + PostgreSQL |

**Isolation**: Both systems can run simultaneously without conflicts. They use separate databases connections, ports, and codebases.
