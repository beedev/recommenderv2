# Agentic AI Welding Recommender System

🚀 **Langraph-based 3-Agent Enterprise Framework** for intelligent welding equipment recommendations with Neo4j graph database, multilingual support, and real-time observability.

## 🎯 System Overview

This is a production-ready agentic AI system that provides intelligent welding equipment recommendations through a sophisticated 3-agent architecture. The system handles realistic user queries like "I want to form a package with Aristo 500 ix" and returns optimized Trinity packages (PowerSource + Feeder + Cooler) with compatibility validation.

### Key Capabilities
- **🤖 3-Agent Architecture**: Intent Processing → Neo4j Recommendations → Response Generation
- **🧠 LLM-Powered Intelligence**: Product extraction, multilingual processing, expertise detection
- **📊 Graph Database**: Neo4j with vector embeddings for semantic search and compatibility
- **🌐 Multilingual Support**: 10+ languages with cultural adaptation
- **📈 Real-time Observability**: LangSmith integration with performance tracking
- **🎯 Guided Flow**: Realistic user scenarios with step-by-step assistance
- **⚡ Trinity Compliance**: Automatic package formation with business rule validation

## 🏗️ Architecture

### System Components

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Agent 1:      │    │   Agent 2:      │    │   Agent 3:      │
│ Intent          │───▶│ Neo4j           │───▶│ Response        │
│ Processing      │    │ Recommendations │    │ Generation      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ • LLM Analysis  │    │ • Graph Queries │    │ • Multilingual  │
│ • Language Det. │    │ • Vector Search │    │ • Cultural      │
│ • Expertise Det.│    │ • Compatibility │    │ • Explanations  │
│ • Product Ext.  │    │ • Sales History │    │ • Guidance      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Technology Stack

**Backend (✅ Working)**
- **Framework**: FastAPI + Python 3.11+
- **Database**: Neo4j 5.13+ (Graph + Vector), PostgreSQL (User data)
- **AI/ML**: OpenAI GPT-4, Sentence Transformers (embeddings)
- **Orchestration**: Langraph (Agentic framework)
- **Observability**: LangSmith (Real-time monitoring)

**Frontend (🚧 WIP)**
- **Framework**: React 18 + TypeScript + Vite
- **Styling**: TailwindCSS + Design System
- **State**: Redux Toolkit + RTK Query
- **WebSocket**: Real-time conversation updates

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Neo4j 5.13+
- PostgreSQL 14+
- Node.js 18+ (for frontend)

### 1. Backend Setup

```bash
# Clone and setup
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Environment configuration
cp .env.example .env
# Edit .env with your database credentials and OpenAI API key
```

### 2. Database Setup

```bash
# Start databases
# Neo4j: Start Neo4j Desktop or Docker
# PostgreSQL: Start PostgreSQL service

# Load data (one-time setup)
bash scripts/load_data.sh
```

### 3. Start Backend Server

```bash
cd backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 4. Frontend Setup (Optional)

```bash
cd frontend
npm install
npm run dev
```

## 🧪 Testing

### Expert Mode Testing
Test the enterprise recommendation system with technical scenarios:

```bash
# Run all expert scenarios
python scripts/test_recommendations.py

# Verbose output
python scripts/test_recommendations.py --verbose

# Specific scenario
python scripts/test_recommendations.py --scenario mig_aluminum

# Export results
python scripts/test_recommendations.py --export results.json
```

### Guided Flow Testing
Test realistic user scenarios with guided assistance:

```bash
# Run all guided flow scenarios
python scripts/test_guided_flow.py

# Verbose output with detailed flow analysis
python scripts/test_guided_flow.py --verbose

# Test specific guided flow scenario
python scripts/test_guided_flow.py --scenario package_formation_aristo

# Export guided flow results
python scripts/test_guided_flow.py --export guided_flow_results.json
```

### Health Check
```bash
curl http://localhost:8000/api/v1/health
```

## 📡 API Endpoints

### Core Recommendation API
```http
POST /api/v1/enterprise/recommendations
Content-Type: application/json

{
  "query": "I want to form a package with Aristo 500 ix",
  "user_context": {
    "user_id": "user123",
    "experience_level": "expert",
    "preferences": {
      "budget_range": "premium",
      "preferred_brands": ["ESAB"]
    }
  },
  "session_id": "session_456",
  "language": "en"
}
```

### Example Queries

**Expert Mode Queries:**
- `"I need MIG welding equipment for aluminum, 300 amps, 1/4 inch thickness"`
- `"High current TIG welding for stainless steel, aerospace application"`
- `"Multi-process welding for both aluminum and steel, 400 amps maximum"`

**Guided Flow Queries:**
- `"I want to form a package with Aristo 500 ix"`
- `"I need complete welding equipment for my garage"`
- `"What goes with my existing Warrior 400i?"`
- `"I'm looking for a multi process welding machine"`

## 🔧 Configuration

### Mode Detection
The system automatically detects user expertise and routing strategy via `/backend/config/mode_detection.yaml`:

- **Expert Mode**: Technical parameters, process acronyms, specific models
- **Guided Mode**: Beginner indicators, learning questions, package requests
- **Hybrid Mode**: Mixed expertise scenarios

### Guided Flow Scenarios
Realistic user scenarios configured in `mode_detection.yaml`:

```yaml
guided_flow_scenarios:
  package_formation:
    - "form a package with"
    - "create a package with"
    - "what goes with"
    
  multi_process_queries:
    - "multi process"
    - "versatile welding"
    
  beginner_package_requests:
    - "complete welding setup"
    - "welding starter kit"
```

## 📊 System Features

### 🎯 Intelligent Intent Processing (Agent 1)
- **LLM-Powered Analysis**: Extract products, requirements, and context
- **Language Detection**: Auto-detect and process 10+ languages
- **Expertise Classification**: Expert, Guided, or Hybrid mode detection
- **Product Recognition**: "Aristo 500 ix", "Warrior 400i", "Renegade 300"

### 🧠 Neo4j Recommendations (Agent 2)
- **Graph Traversal**: Compatibility relationships and sales patterns
- **Vector Search**: Semantic similarity with 384-dimensional embeddings
- **Trinity Formation**: PowerSource + Feeder + Cooler packages
- **Business Rules**: Sales frequency, compatibility validation, pricing

### 🌐 Response Generation (Agent 3)
- **Multilingual Output**: Localized responses with cultural adaptation
- **Expertise-Aware**: Technical details for experts, guidance for beginners
- **Structured Results**: Package details, compatibility scores, explanations
- **User Guidance**: Next steps, related questions, learning paths

## 📈 Performance & Observability

### Performance Targets
- **Response Time**: <3s for standard queries, <5s for complex analysis
- **Accuracy**: >90% for product recognition, >85% for recommendations
- **Availability**: 99.9% uptime target with health monitoring

### Monitoring
- **LangSmith Integration**: Real-time agent performance tracking
- **Health Endpoints**: Database connections, system status
- **Performance Metrics**: Response times, success rates, error tracking
- **Quality Gates**: Validation cycles, compatibility verification

## 📚 Documentation

### Architecture Documentation
- [Data Pipeline Architecture](./docs/DATA_PIPELINE_ARCHITECTURE.md)
- [Technical Implementation Guide](./docs/TECHNICAL_IMPLEMENTATION_GUIDE.md)
- [Neo4j Schema Analysis](./docs/NEO4J_SCHEMA_ANALYSIS.md)
- [Agentic Architecture Analysis](./docs/AGENTIC_ARCHITECTURE_ANALYSIS.md)

### Development Documentation
- [Vector Embedding Design](./docs/VECTOR_EMBEDDING_DESIGN.md)
- [LangSmith Configuration](./docs/LANGSMITH_CONFIGURATION_VERIFICATION.md)
- [Implementation Plan](./docs/IMPLEMENTATION_PLAN.md)

## 🛠️ Development

### Project Structure
```
├── backend/                 # FastAPI backend with 3-agent system
│   ├── app/
│   │   ├── agents/         # Langraph agents
│   │   ├── services/       # Enterprise services
│   │   ├── api/            # REST API endpoints
│   │   └── database/       # Neo4j + PostgreSQL
│   ├── config/             # YAML configuration
│   ├── data/               # ETL tools and loaders
│   └── tests/              # Unit and integration tests
├── frontend/               # React TypeScript frontend
├── scripts/                # Testing and deployment scripts
├── docs/                   # Comprehensive documentation
└── neo4j_datasets/         # Graph-ready JSON data
```

### Key Services
- **EnterpriseOrchestratorService**: Main 3-agent coordinator
- **IntelligentIntentService**: LLM-based intent processing
- **SmartNeo4jService**: Graph queries and Trinity formation
- **MultilingualResponseService**: Localized response generation

## 🚀 Deployment

### Production Deployment
```bash
# Deploy data pipeline
bash scripts/deploy_data.sh

# Transform and load data
bash scripts/transform_data.sh
bash scripts/load_data.sh

# Start production server
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Docker Deployment (Coming Soon)
```bash
docker-compose up -d
```

## 🤝 Contributing

This system is designed and orchestrated by **Bharath Devanathan** with a focus on:
- **Quality-First Development**: Comprehensive testing and validation
- **Enterprise Architecture**: Scalable, maintainable, observable systems
- **User-Centric Design**: Realistic scenarios and intelligent assistance

### Development Workflow
1. **Analysis Phase**: Understand requirements and design approach
2. **Implementation Phase**: Code with comprehensive testing
3. **Validation Phase**: Quality gates and performance verification
4. **Documentation Phase**: Complete documentation and examples

## 📄 License

Proprietary software - All rights reserved.

---

**🤖 Designed and orchestrated by Bharath Devanathan**

*Enterprise-grade agentic AI system for intelligent welding equipment recommendations*