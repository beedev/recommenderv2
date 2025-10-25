# Welding Product Configurator - V2 (S1→S7 State-by-State Flow)

**Version**: 2.0
**Status**: Clean Implementation
**Architecture**: State Machine with Sequential Component Selection

---

## Overview

Recommender_v2 is a **clean room implementation** of the S1→S7 state-by-state configurator flow.
This is a **completely separate project** from Recommender v1 to ensure zero risk to the existing working system.

### Key Differences from V1

| Feature | V1 (Recommender) | V2 (Recommender_v2) |
|---------|------------------|---------------------|
| **Flow** | All-at-once recommendations | State-by-state (S1→S7) |
| **Output** | TrinityPackage list | Response JSON (selected products) |
| **PowerSource** | Optional | **Mandatory** |
| **Compatibility** | Trinity-based | Per-component validation |
| **User Interaction** | Single query | Multi-turn conversation |
| **Port** | 8000 | 8001 |

---

## Architecture

### S1→S7 Sequential Flow

```
S1: PowerSource (MANDATORY)
  ↓ Get Component Applicability
  ↓ Auto-fill NA components
S2: Feeder (if Y)
  ↓ Validate compatibility with S1
S3: Cooler (if Y)
  ↓ Validate compatibility with S1 + S2
S4: Interconnector (if Y)
  ↓ Validate compatibility with S1 + S2 + S3
S5: Torch (if Y)
  ↓ Validate compatibility with S2 + S3
S6: Accessories (optional)
  ↓ Category-specific compatibility
S7: Finalize
  ↓ Validate ≥3 components
  ↓ Generate packages
```

### Core Components

1. **Master Parameter JSON** - User requirements tracking
2. **Response JSON** - Selected products (cart)
3. **Component Applicability** - Y/N configuration per power source
4. **LLM Entity Extractor** - Prompt-based parameter extraction
5. **State Machine** - S1→S7 orchestration
6. **Compatibility Validator** - COMPATIBLE_WITH relationship checks

---

## Directory Structure

```
Recommender_v2/
├── backend/
│   ├── app/
│   │   ├── api/v1/configurator/    # S1→S7 endpoints
│   │   ├── services/
│   │   │   ├── intent/             # Agent 1 - Simplified
│   │   │   ├── neo4j/              # Agent 2 - Simplified
│   │   │   ├── response/           # Agent 3 - Simplified
│   │   │   ├── extraction/         # NEW - Master JSON + LLM
│   │   │   └── orchestrator/       # NEW - State machine
│   │   ├── models/
│   │   │   ├── master_parameter.py
│   │   │   ├── response_json.py
│   │   │   └── conversation.py
│   │   ├── database/repositories/
│   │   └── config/
│   │       └── component_applicability.json
│   ├── .env
│   ├── requirements.txt
│   └── main.py
├── docs/                           # Architecture documents
│   ├── CORRECTED_STATE_FLOW_ARCHITECTURE.md
│   ├── MASTER_PARAMETER_JSON_ARCHITECTURE.md
│   └── LLM_ENTITY_EXTRACTION_ARCHITECTURE.md
└── README.md
```

---

## Installation

```bash
# 1. Navigate to v2 backend
cd Recommender_v2/backend

# 2. Create virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy .env from v1 (or create new)
cp ../../Recommender/backend/.env .env

# 5. Run on port 8001
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

---

## API Endpoints

### New S1→S7 Configurator

```
POST /api/v1/configurator/message
Content-Type: application/json

{
  "session_id": "optional-session-id",
  "message": "I need a 500A MIG welder",
  "reset": false
}

Response:
{
  "session_id": "uuid",
  "message": "Great! I found the Aristo 500ix...",
  "current_state": "feeder_selection",
  "master_parameters": {...},
  "response_json": {...},
  "suggested_options": ["portable", "stationary"]
}
```

---

## Testing

### Run Both Systems Side-by-Side

```bash
# Terminal 1: V1 (Existing)
cd Recommender/backend
source venv/bin/activate
uvicorn app.main:app --port 8000

# Terminal 2: V2 (New S1→S7)
cd Recommender_v2/backend
source venv/bin/activate
uvicorn app.main:app --port 8001
```

### Test V1
```bash
curl http://localhost:8000/api/v1/recommendations/enterprise
```

### Test V2
```bash
curl http://localhost:8001/api/v1/configurator/message
```

---

## Key Features

### 1. Mandatory PowerSource
- S1 cannot be skipped
- System keeps prompting until user provides details

### 2. Component Applicability
- Automatic NA assignment for incompatible components
- Dynamic state skipping (e.g., Renegade ES300 → skip S2, S3, S4)

### 3. Compatibility Validation
- Every search validates COMPATIBLE_WITH relationships
- Per-component compatibility rules (see docs)

### 4. Master Parameter JSON
- Tracks user requirements across all states
- LLM fills parameters via structured prompts
- Latest value wins (user can change mind)

### 5. Response JSON
- Selected products (cart)
- Used for final package generation
- Minimum 3 real components required

---

## Architecture Documents

See `/docs` for detailed architecture:

- `CORRECTED_STATE_FLOW_ARCHITECTURE.md` - Complete S1→S7 flow
- `MASTER_PARAMETER_JSON_ARCHITECTURE.md` - Parameter tracking
- `LLM_ENTITY_EXTRACTION_ARCHITECTURE.md` - Prompt-based extraction
- `PHASE1_ARCHITECTURE.md` - Implementation components
- `SYSTEM_ALIGNMENT_ANALYSIS.md` - Spec alignment

---

## Safety & Isolation

### Complete Isolation from V1

✅ **File System**: Separate `/Recommender_v2` directory
✅ **Runtime**: Different port (8001 vs 8000)
✅ **Database**: Separate connection pool
✅ **Dependencies**: Own virtual environment
✅ **No Shared Code**: All services copied and simplified

### Rollback Strategy

```bash
# If v2 has issues, just delete the folder
cd /Users/bharath/Desktop/AgenticAI
rm -rf Recommender_v2

# V1 continues running unaffected
```

---

## Development Status

- [x] Architecture design completed
- [x] Directory structure created
- [x] Config files copied
- [ ] Master Parameter JSON models
- [ ] LLM Entity Extractor
- [ ] State Machine orchestrator
- [ ] API endpoint
- [ ] Testing

---

## Next Steps

1. Implement Master Parameter JSON models
2. Create LLM Entity Extractor with prompt templates
3. Build State Machine orchestrator
4. Create FastAPI endpoint
5. Test S1→S7 flow
6. Compare with V1 output
7. Gradual migration or feature toggle

---

**Created**: 2025-10-24
**Author**: Claude + Bharath
**Purpose**: Safe S1→S7 implementation without affecting V1
