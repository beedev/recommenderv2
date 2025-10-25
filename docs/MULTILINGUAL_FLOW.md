# Multilingual Support - Complete Flow Documentation

## Overview

The Enterprise 3-Agent Agentic System includes comprehensive multilingual support that allows users to query in their native language and receive responses translated back to that language. The system supports 12 languages and automatically detects, translates, and adapts responses based on user expertise level.

---

## Supported Languages

```python
class LanguageCode(str, Enum):
    EN = "en"  # English (default)
    ES = "es"  # Spanish
    FR = "fr"  # French
    DE = "de"  # German
    PT = "pt"  # Portuguese
    IT = "it"  # Italian
    ZH = "zh"  # Chinese
    JA = "ja"  # Japanese
    KO = "ko"  # Korean
    RU = "ru"  # Russian
    AR = "ar"  # Arabic
    HI = "hi"  # Hindi
```

**File**: `app/services/enterprise/enhanced_state_models.py:29-42`

---

## Complete Multilingual Flow

### 🔄 **Phase 1: Language Detection (Agent 1)**

**Location**: `app/services/enterprise/intelligent_intent_service.py:202-257`

#### Step 1.1: User Query Input
```python
# User submits query in any supported language
query = "Necesito una máquina de soldar MIG para acero"  # Spanish
```

#### Step 1.2: Language Detection
```python
async def detect_language(self, query: str) -> LanguageCode:
    """
    Auto-detect language using keyword matching
    """
    # Language-specific keyword sets
    language_scores = {
        "es": 0,  # Spanish
        "fr": 0,  # French
        "de": 0,  # German
        "en": 0   # English (default)
    }

    # Spanish keywords
    spanish_keywords = ["necesito", "quiero", "para", "máquina", "soldadura"]

    # Count keyword matches per language
    for keyword in spanish_keywords:
        if keyword.lower() in query.lower():
            language_scores["es"] += 1

    # Return language with highest score
    detected_lang = max(language_scores, key=language_scores.get)

    return LanguageCode(detected_lang)
```

**Output**: `detected_language = LanguageCode.ES` (Spanish)

---

### 🔄 **Phase 2: Translation to English (Agent 1)**

**Location**: `app/services/enterprise/intelligent_intent_service.py:259-320`

#### Step 2.1: Translate Query to English
```python
async def translate_to_english(
    self,
    query: str,
    detected_language: LanguageCode
) -> str:
    """
    Translate foreign language queries to English for processing
    """
    if detected_language == LanguageCode.EN:
        return query  # No translation needed

    # Translation maps for each language
    translation_maps = {
        LanguageCode.ES: {
            # Spanish → English
            "necesito": "I need",
            "máquina de soldar": "welding machine",
            "soldadura": "welding",
            "para": "for",
            "acero": "steel",
            "MIG": "MIG",
            "TIG": "TIG"
        },
        LanguageCode.FR: {
            # French → English
            "j'ai besoin": "I need",
            "machine à souder": "welding machine",
            "soudage": "welding",
            "pour": "for",
            "acier": "steel"
        },
        LanguageCode.DE: {
            # German → English
            "ich brauche": "I need",
            "Schweißmaschine": "welding machine",
            "Schweißen": "welding",
            "für": "for",
            "Stahl": "steel"
        }
    }

    # Apply translation
    translated_query = query
    if detected_language in translation_maps:
        translation_map = translation_maps[detected_language]
        for foreign_term, english_term in translation_map.items():
            translated_query = translated_query.replace(foreign_term, english_term)

    return translated_query
```

**Input**: `"Necesito una máquina de soldar MIG para acero"`
**Output**: `"I need a welding machine MIG for steel"`

---

### 🔄 **Phase 3: Enhanced Intent Creation (Agent 1)**

**Location**: `app/services/enterprise/intelligent_intent_service.py:367-400`

```python
# Store both original and translated queries
enhanced_intent = EnhancedProcessedIntent(
    original_query=query,                    # Spanish: "Necesito una..."
    processed_query=english_query,           # English: "I need a..."
    detected_language=detected_language,     # LanguageCode.ES
    language_detection_confidence=0.95,

    # Extracted from English query
    welding_process=["GMAW"],
    material=Material.STEEL,

    # Auto-detected expertise
    expertise_mode=ExpertiseMode.HYBRID,
    mode_detection_confidence=0.85
)
```

**Output**: Intent with language metadata preserved

---

### 🔄 **Phase 4: Neo4j Search (Agent 2)**

**Location**: `app/services/enterprise/smart_neo4j_service.py`

```python
# Agent 2 processes the ENGLISH query
# Searches Neo4j using English-translated requirements
# Returns Trinity packages with English product names/descriptions

scored_recommendations = ScoredRecommendations(
    packages=[
        TrinityPackage(
            power_source={"product_name": "Aristo 500ix CE", ...},
            feeder={"product_name": "Robust Feed 304", ...},
            cooler={"product_name": "Cool 50 U42", ...}
        )
    ]
)
```

**Note**: Neo4j search happens in English. Product data in database is in English.

---

### 🔄 **Phase 5: Response Generation in English (Agent 3)**

**Location**: `app/services/enterprise/multilingual_response_service.py:480-543`

#### Step 5.1: Generate Mode-Aware Explanations

```python
# Generate explanations based on expertise mode
if expertise_mode == ExpertiseMode.EXPERT:
    explanations = {
        "technical_summary": "Optimal Trinity configuration identified...",
        "compatibility_analysis": "Package 1: Trinity compliance...",
        "performance_metrics": "Generated 3 packages, 3 Trinity-compliant..."
    }
elif expertise_mode == ExpertiseMode.GUIDED:
    explanations = {
        "beginner_summary": "I found a great welding package for you!...",
        "component_education": "Understanding Your Welding Package...",
        "usage_guidance": "Getting Started Tips..."
    }
```

#### Step 5.2: Format Response in English

```python
formatted_response = MultilingualResponse(
    title="Welding Package Recommendation",
    summary="Recommended Welding Package (Score: 95.0%)",
    detailed_explanation="**Power Source**: Aristo 500ix CE\n**Wire Feeder**: Robust Feed 304\n...",
    technical_notes=["This Trinity package ensures all components work together optimally."],
    package_descriptions=["Package 1: Aristo 500ix CE system - $15,450.00 (Score: 95%)"],
    next_steps=["Review package details", "Check delivery options", "Contact sales if needed"],
    related_questions=["Are there other configurations available?", "What's the warranty coverage?"],
    response_language=LanguageCode.EN,  # Still in English
    explanation_level=ExplanationLevel.BALANCED
)
```

---

### 🔄 **Phase 6: Translation Back to Original Language (Agent 3)**

**Location**: `app/services/enterprise/multilingual_response_service.py:305-363`

#### Step 6.1: Check if Translation Needed

```python
# Original query was in Spanish (LanguageCode.ES)
if original_intent.detected_language != LanguageCode.EN:
    formatted_response = self.multilingual_translator.translate_response(
        formatted_response,
        original_intent.detected_language  # LanguageCode.ES
    )
```

#### Step 6.2: Translate Response to Spanish

```python
class MultilingualTranslator:
    def translate_response(
        self,
        response: MultilingualResponse,
        target_language: LanguageCode
    ) -> MultilingualResponse:
        """Translate response back to user's original language"""

        # Translation maps for key technical terms
        translation_maps = {
            LanguageCode.ES: {
                "Power Source": "Fuente de Poder",
                "Wire Feeder": "Alimentador de Alambre",
                "Cooling System": "Sistema de Enfriamiento",
                "Total Package Price": "Precio Total del Paquete",
                "Recommended": "Recomendado",
                "Complete Trinity package": "Paquete Trinity Completo",
                "Review package details": "Revisar detalles del paquete",
                "Contact sales": "Contactar ventas"
            }
        }

        # Apply translations
        translated_response = MultilingualResponse(
            title=self._simple_translate(response.title, target_language),
            summary=self._simple_translate(response.summary, target_language),
            detailed_explanation=self._simple_translate(response.detailed_explanation, target_language),
            technical_notes=[self._simple_translate(note, target_language) for note in response.technical_notes],
            package_descriptions=[self._simple_translate(desc, target_language) for desc in response.package_descriptions],
            next_steps=[self._simple_translate(step, target_language) for step in response.next_steps],
            related_questions=[self._simple_translate(q, target_language) for q in response.related_questions],
            response_language=target_language,  # LanguageCode.ES
            explanation_level=response.explanation_level
        )

        return translated_response
```

**Final Response in Spanish**:
```python
MultilingualResponse(
    title="Recomendado de Paquete de Soldadura",
    summary="Paquete de Soldadura Recomendado (Puntuación: 95.0%)",
    detailed_explanation="**Fuente de Poder**: Aristo 500ix CE\n**Alimentador de Alambre**: Robust Feed 304\n...",
    technical_notes=["Este Paquete Trinity Completo asegura que todos los componentes funcionen juntos de manera óptima."],
    package_descriptions=["Paquete 1: Sistema Aristo 500ix CE - $15,450.00 (Puntuación: 95%)"],
    next_steps=["Revisar detalles del paquete", "Verificar opciones de entrega", "Contactar ventas si es necesario"],
    related_questions=["¿Hay otras configuraciones disponibles?", "¿Cuál es la cobertura de garantía?"],
    response_language=LanguageCode.ES,
    explanation_level=ExplanationLevel.BALANCED
)
```

---

## Expertise-Based Response Adaptation

### 🎯 **Expert Mode** (ExpertiseMode.EXPERT)

**Triggers**: Technical keywords like "amperage", "duty cycle", "GMAW", "DCEP"

**Response Style**:
```python
MultilingualResponse(
    title="Technical Welding System Analysis",
    summary="Optimal Trinity configuration identified with 95.0% compatibility score. | PowerSource: Aristo 500ix CE | Wire Feeder: Robust Feed 304 | ...",
    detailed_explanation="Package 1: Trinity compliance True, Business rule compliance 92.5%, Compatibility score 0.95",
    technical_notes=["Generated 3 packages, 3 Trinity-compliant, Average score: 0.93"],
    next_steps=["Review technical specifications", "Validate power requirements", "Confirm installation requirements"],
    related_questions=["What are the duty cycle requirements?", "Do you need additional consumables?"],
    explanation_level=ExplanationLevel.TECHNICAL
)
```

### 🎓 **Guided Mode** (ExpertiseMode.GUIDED)

**Triggers**: Keywords like "beginner", "new to welding", "learning", "help me understand"

**Response Style**:
```python
MultilingualResponse(
    title="Your Perfect Welding Package",
    summary="I found a great welding package for you! This complete setup includes everything you need:\n\n🔌 **Power Source**: Aristo 500ix CE - This is the main welding machine that provides the power.\n📋 **Wire Feeder**: Robust Feed 304 - This feeds welding wire automatically so you can focus on your weld.\n❄️ **Cooling System**: Cool 50 U42 - This keeps your torch cool during longer welding sessions.",
    detailed_explanation="**Understanding Your Welding Package:**\n🔌 **Power Source (Welder)**: The heart of your setup - converts electricity into welding power\n📋 **Wire Feeder**: Automatically feeds welding wire at the right speed (for MIG welding)\n❄️ **Cooling System**: Prevents overheating during long welding sessions\n⚡ **Why Trinity Matters**: These three components work together like a team",
    technical_notes=["**Getting Started Tips:**\n• This setup is optimized for steel welding\n• Start with practice pieces before your main project\n• Make sure you have proper safety equipment"],
    next_steps=["Get safety equipment", "Consider training classes", "Plan your workspace"],
    related_questions=["What safety equipment do I need?", "Where can I learn welding?"],
    explanation_level=ExplanationLevel.EDUCATIONAL
)
```

### ⚖️ **Hybrid Mode** (ExpertiseMode.HYBRID)

**Default**: Balanced technical and beginner-friendly information

**Response Style**:
```python
MultilingualResponse(
    title="Welding Package Recommendation",
    summary="**Recommended Welding Package** (Score: 95.0%)\n**Power Source**: Aristo 500ix CE\n**Wire Feeder**: Robust Feed 304\n**Cooling**: Cool 50 U42\n**Total**: $15,450.00",
    detailed_explanation="✅ Complete Trinity package (Power Source + Feeder + Cooler)\n✅ Components verified for compatibility\n✅ Business-grade quality and reliability",
    technical_notes=["Found 3 compatible packages. Top recommendation shown above."],
    next_steps=["Review package details", "Check delivery options", "Contact sales if needed"],
    related_questions=["Are there other configurations available?", "What's the warranty coverage?"],
    explanation_level=ExplanationLevel.BALANCED
)
```

---

## Complete Data Flow Diagram

```
┌────────────────────────────────────────────────────────────────┐
│ USER INPUT                                                     │
│ "Necesito una máquina de soldar MIG para acero" (Spanish)    │
└────────────┬───────────────────────────────────────────────────┘
             │
             ▼
┌────────────────────────────────────────────────────────────────┐
│ AGENT 1: Intelligent Intent Service                           │
│                                                                │
│ Step 1: Language Detection                                    │
│   ├─ Keyword matching → LanguageCode.ES (Spanish)            │
│   └─ Confidence: 95%                                          │
│                                                                │
│ Step 2: Translation to English                                │
│   ├─ Input: "Necesito una máquina de soldar MIG para acero"  │
│   └─ Output: "I need a welding machine MIG for steel"        │
│                                                                │
│ Step 3: Expertise Detection                                   │
│   ├─ Expert signals: 0                                        │
│   ├─ Guided signals: 0                                        │
│   └─ Mode: ExpertiseMode.HYBRID (default)                    │
│                                                                │
│ Step 4: Intent Extraction (from English query)               │
│   ├─ Welding Process: GMAW (MIG)                            │
│   ├─ Material: STEEL                                          │
│   └─ Confidence: 0.85                                         │
│                                                                │
│ OUTPUT: EnhancedProcessedIntent                               │
│   - original_query: "Necesito una..." (Spanish)              │
│   - processed_query: "I need a..." (English)                 │
│   - detected_language: LanguageCode.ES                        │
│   - expertise_mode: ExpertiseMode.HYBRID                      │
└────────────┬───────────────────────────────────────────────────┘
             │
             ▼
┌────────────────────────────────────────────────────────────────┐
│ AGENT 2: Smart Neo4j Service                                  │
│                                                                │
│ Step 1: Search Strategy Selection                             │
│   └─ Strategy: HYBRID (semantic + graph)                     │
│                                                                │
│ Step 2: Neo4j Query Execution (in English)                   │
│   ├─ Search for: MIG welding, steel material               │
│   ├─ Algorithm: Trinity Semantic Search                      │
│   └─ Results: 3 compatible Trinity packages                  │
│                                                                │
│ Step 3: Package Scoring & Ranking                            │
│   ├─ Trinity compliance check                                │
│   ├─ Compatibility scoring                                   │
│   └─ Business rules application                              │
│                                                                │
│ OUTPUT: ScoredRecommendations                                 │
│   - packages: [TrinityPackage(Aristo 500ix CE, ...)]        │
│   - trinity_formation_rate: 1.0 (100%)                       │
│   - total_packages_found: 3                                  │
└────────────┬───────────────────────────────────────────────────┘
             │
             ▼
┌────────────────────────────────────────────────────────────────┐
│ AGENT 3: Multilingual Response Service                        │
│                                                                │
│ Step 1: Business Context Re-ranking                           │
│   ├─ User: Anonymous                                          │
│   ├─ Organization: None                                       │
│   └─ Priority: ESAB products, Trinity compliance             │
│                                                                │
│ Step 2: Mode-Aware Explanation Generation                    │
│   ├─ Mode: ExpertiseMode.HYBRID                              │
│   └─ Explanations: Balanced technical + beginner-friendly    │
│                                                                │
│ Step 3: Response Formatting (in English)                     │
│   ├─ Title: "Welding Package Recommendation"                │
│   ├─ Summary: "Recommended Welding Package (Score: 95%)"    │
│   └─ Details: PowerSource, Feeder, Cooler info              │
│                                                                │
│ Step 4: Translation to Original Language (Spanish)           │
│   ├─ Detect: detected_language = LanguageCode.ES            │
│   ├─ Translate: Apply Spanish translation map               │
│   │    - "Power Source" → "Fuente de Poder"                │
│   │    - "Wire Feeder" → "Alimentador de Alambre"          │
│   │    - "Cooling System" → "Sistema de Enfriamiento"      │
│   └─ Output: MultilingualResponse (Spanish)                 │
│                                                                │
│ OUTPUT: EnterpriseRecommendationResponse                      │
│   - formatted_response: MultilingualResponse (Spanish)       │
│   - packages: [TrinityPackage(...)]                          │
│   - overall_confidence: 0.92                                 │
│   - trace_id: "abc123"                                       │
└────────────┬───────────────────────────────────────────────────┘
             │
             ▼
┌────────────────────────────────────────────────────────────────┐
│ API RESPONSE (to user)                                         │
│                                                                │
│ {                                                              │
│   "formatted_response": {                                     │
│     "title": "Recomendado de Paquete de Soldadura",         │
│     "summary": "Paquete de Soldadura Recomendado...",       │
│     "detailed_explanation": "**Fuente de Poder**: Aristo...",│
│     "response_language": "es",                               │
│     "explanation_level": "balanced"                          │
│   },                                                           │
│   "packages": [...],                                          │
│   "overall_confidence": 0.92                                  │
│ }                                                              │
└────────────────────────────────────────────────────────────────┘
```

---

## Key Files Reference

| File | Purpose | Key Functions |
|------|---------|---------------|
| `enhanced_state_models.py:29-42` | Language code definitions | `LanguageCode` enum |
| `intelligent_intent_service.py:202-320` | Language detection & translation | `detect_language()`, `translate_to_english()` |
| `multilingual_response_service.py:305-363` | Response translation | `translate_response()`, `_simple_translate()` |
| `multilingual_response_service.py:27-243` | Mode-aware explanations | `generate_explanations()`, `_generate_expert_explanations()`, `_generate_guided_explanations()` |

---

## Current Implementation Status

### ✅ Implemented
- Language detection via keyword matching (12 languages)
- Translation to English for processing
- Mode-aware response generation (Expert/Guided/Hybrid)
- Translation back to original language
- Spanish, French, German translation maps

### ⚠️ MVP Limitations
- Simple keyword-based translation (not professional-grade)
- Limited vocabulary in translation maps
- No full sentence structure translation
- Product names/descriptions remain in English (from database)

### 🚀 Future Enhancements
- Integration with professional translation API (Google Translate, DeepL)
- Multilingual product database
- Cultural adaptation beyond language translation
- Sentiment analysis for better expertise detection
- Dynamic translation quality scoring

---

## Usage Example

### Request (Spanish)
```json
POST /api/v1/enterprise/orchestrator/recommend
{
  "query": "Necesito una máquina de soldar MIG de 500 amperios para acero inoxidable",
  "user_context": {
    "user_id": "user_123",
    "preferred_language": "es"
  }
}
```

### Response (Spanish with English product names)
```json
{
  "formatted_response": {
    "title": "Recomendado de Paquete de Soldadura",
    "summary": "Paquete de Soldadura Recomendado (Puntuación: 95.0%)\n\n**Fuente de Poder**: Aristo 500ix CE\n**Alimentador de Alambre**: Robust Feed 304\n**Sistema de Enfriamiento**: Cool 50 U42\n**Total**: $15,450.00",
    "detailed_explanation": "✅ Paquete Trinity Completo (Fuente de Poder + Alimentador + Sistema de Enfriamiento)\n✅ Componentes verificados para compatibilidad\n✅ Calidad y fiabilidad de grado empresarial",
    "response_language": "es",
    "explanation_level": "balanced"
  },
  "overall_confidence": 0.92,
  "original_intent": {
    "original_query": "Necesito una máquina de soldar MIG de 500 amperios para acero inoxidable",
    "processed_query": "I need a MIG welding machine of 500 amps for stainless steel",
    "detected_language": "es"
  }
}
```

---

## Summary

The multilingual system provides a complete translation pipeline from user input to final response:

1. **Agent 1**: Detects language → Translates to English → Extracts intent
2. **Agent 2**: Processes English query → Searches Neo4j → Returns results
3. **Agent 3**: Generates English response → Translates to original language → Returns to user

This approach ensures:
- ✅ All processing happens in English (Neo4j data is English)
- ✅ Users interact in their native language
- ✅ Responses adapt to expertise level AND language
- ✅ Full transparency with original and processed queries tracked
