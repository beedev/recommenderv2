# Corrected State Flow Architecture - S1→S7 Deterministic Progression

**Version**: 2.0
**Date**: 2025-10-24
**Status**: Architecture Design - Spec-Compliant Flow with Compatibility Validation

---

## Executive Summary

This document corrects the implementation flow to match the v5.4 specification exactly:
- **Sequential state progression** S1→S7 (not all at once)
- **PowerSource (S1) is MANDATORY** - cannot be skipped
- **Collect parameters per state** before searching Neo4j
- **Search Neo4j only when ≥1 parameter** for that component
- **Compatibility validation** using COMPATIBLE_WITH relationships
- **User-driven progression** (user must confirm/skip to advance)
- **Component applicability** determines which states are active

**Spec Reference**: Section 2 - State Machine (S1→S7), Lines 217-286

---

## Critical Rules

### Rule 1: PowerSource is Mandatory
- S1 (PowerSource) **CANNOT** be skipped
- User must provide ≥1 parameter OR direct product mention
- System will keep prompting until PowerSource is selected
- All other states (S2-S6) can be skipped

### Rule 2: Compatibility Validation
- Every component search must validate compatibility with previously selected components
- Uses Neo4j `COMPATIBLE_WITH` relationships (bidirectional)
- Compatibility rules are component-specific (see Section 9)

---

## 1. Correct State Flow

### 1.1 State-by-State Progression

```
S1: PowerSource
    ↓ (user provides details OR says "skip")
    ↓
[Check Component Applicability JSON]
    ↓
S2: Feeder (if Y) OR skip to S3/S4/S5
    ↓ (user provides details OR says "skip")
    ↓
S3: Cooler (if Y) OR skip to S4/S5
    ↓ (user provides details OR says "skip")
    ↓
S4: Interconnect (if Y) OR skip to S5
    ↓ (user provides details OR says "skip")
    ↓
S5: Torch (if Y)
    ↓ (user provides details OR says "skip")
    ↓
S6: Accessories (optional)
    ↓ (user says "go ahead", "generate packages", or "skip all")
    ↓
S7: Finalize (check ≥3 components, get confirmation, call backend)
```

---

## 2. State Processing Logic

### 2.1 Per-State Processing Flow

**For Each State Sn (n = 1 to 6)**:

```
1. CHECK STATE APPLICABILITY
   - If current state marked "N" in Component Applicability JSON
   → Auto-fill as NA
   → Skip to next "Y" state

2. PROMPT USER FOR COMPONENT DETAILS
   - Generate user-friendly prompt based on component type
   - Example: "Tell me what you need in a Feeder:
     • Portability (portable or stationary)
     • Wire size (e.g., 0.035 inch, 0.045 inch)
     • Wire material (aluminum, steel, stainless)
     Or say 'skip' to continue without a feeder."

3. EXTRACT PARAMETERS USING LLM
   - User responds with details OR "skip"
   - LLM extracts parameters into Master JSON for THAT component only
   - Example: "I need a portable feeder with 0.035 wire"
   → Master JSON Feeder: {portability: "portable", wire_size: "0.035 inch"}

4. CHECK ELIGIBILITY FOR NEO4J SEARCH
   - If Master JSON has ≥1 parameter for this component (OR direct product mention)
   → Search Neo4j for matching products

   - If 0 parameters
   → Ask user for more details OR allow skip

5. NEO4J PRODUCT SEARCH
   - Use Master JSON parameters to search Neo4j
   - Return 1-5 matching products

6. PRESENT OPTIONS TO USER
   - If 1 product found: "I found the [Product Name]. Does this work for you?"

   - If >1 products found: "I found several options:
     1. [Product 1] - [Key Features]
     2. [Product 2] - [Key Features]
     3. [Product 3] - [Key Features]
     Which would you prefer, or would you like more details?"

7. USER SELECTION OR SKIP
   - User selects a product → Add to Response JSON (cart)
   - User says "skip" → Mark component as skipped (empty in Response JSON)
   - User asks for details → Show detailed product info

8. ADVANCE TO NEXT STATE
   - Move to next state in sequence
   - Check Component Applicability to determine next active state
   - Repeat steps 1-8 for next component
```

---

## 3. Detailed State Implementations

### 3.1 S1: PowerSource (MANDATORY - Cannot Skip)

**Mandatory Validation**:
- PowerSource is the ONLY mandatory component
- User CANNOT say "skip" for this state
- System must keep prompting until ≥1 parameter OR direct product mention
- Once selected, triggers Component Applicability configuration

**Prompt Template**:
```
"Welcome! Let's configure your welding package.

What power source do you need? (This is required to continue)

You can tell me:
• Amperage (e.g., 300A, 500A)
• Welding process (MIG, TIG, Stick)
• Material you'll be welding (aluminum, steel, stainless)
• Input voltage/phase (230V, 460V, 3-phase)

Or mention a specific model (e.g., 'Aristo 500ix', 'Renegade ES300')."
```

**User Response Examples**:
- "I need 500 amps for MIG welding" → Extract parameters
- "Aristo 500ix" → Direct product lookup
- "500A aluminum welding" → Extract parameters
- "skip" → **REJECTED**: "PowerSource is required. Please tell me what you need."

**LLM Extraction**:
```json
{
  "master_json_updates": {
    "PowerSource": {
      "current_output": "500 A",
      "process": "MIG (GMAW)",
      "material": "aluminum"
    }
  }
}
```

**Neo4j Search** (if ≥1 parameter):
```cypher
CALL db.index.vector.queryNodes('product_embeddings', 5, embedding_vector)
YIELD node, score
WHERE node.category = 'PowerSource'
  AND node.current_output CONTAINS '500'
  AND 'MIG (GMAW)' IN node.process
  AND node.material CONTAINS 'aluminum'
RETURN node
ORDER BY score DESC
LIMIT 5
```

**Present Options**:
```
"I found these power sources:

1. Aristo 500ix - 500A MIG/TIG, 3-phase, aluminum-ready
2. Warrior 500i - 500A MIG, 3-phase, multi-material

Which would you prefer?"
```

**After Selection**:
- Add to Response JSON: `{"PowerSource": {"gin": "0446200880", "description": "Aristo 500ix"}}`
- Check Component Applicability JSON for Aristo 500ix
- Auto-fill NA components if any marked "N"
- Advance to next "Y" state (e.g., Feeder if Y, or Torch if Feeder is N)

---

### 3.2 S2: Feeder

**Check Applicability First**:
```python
applicability = component_config.get_applicability("0446200880")  # Aristo 500ix

if applicability.Feeder == "N":
    # Auto-fill NA
    response_json["Feeder"] = {"gin": "NA", "description": "Not Applicable"}
    # Skip to S3
else:
    # Proceed with feeder selection
```

**Prompt Template** (if Y):
```
"Great choice! Now let's select a feeder.

For the Aristo 500ix, you'll need a feeder. Tell me your preferences:
• Portability (portable or stationary)
• Wire size (common: 0.030, 0.035, 0.045 inch)
• Wire material (aluminum, steel, stainless)

Or say 'skip' if you don't need a feeder right now."
```

**User Response Examples**:
- "I need a portable feeder with 0.035 wire" → Extract parameters
- "Python 450" → Direct product lookup
- "Skip" → Skip feeder (Response JSON Feeder remains empty)

**LLM Extraction**:
```json
{
  "master_json_updates": {
    "Feeder": {
      "portability": "portable",
      "wire_size": "0.035 inch",
      "process": "MIG (GMAW)"  // Inherited from PowerSource
    }
  }
}
```

**Compatibility Validation**:
- Feeder must be compatible with PowerSource
- Uses COMPATIBLE_WITH relationship in Neo4j

**Neo4j Search** (if ≥1 parameter):
```cypher
// Find feeders compatible with selected PowerSource
MATCH (ps:Product {gin: $power_source_gin})-[:COMPATIBLE_WITH]-(f:Product)
WHERE f.category = 'Feeder'
  AND ($portability IS NULL OR f.portability CONTAINS $portability)
  AND ($wire_size IS NULL OR f.wire_size CONTAINS $wire_size)
RETURN f
LIMIT 5

// Parameters from Master JSON:
// $power_source_gin = "0446200880" (from Response JSON)
// $portability = "portable" (from Master JSON Feeder)
// $wire_size = "0.035" (from Master JSON Feeder)
```

**Present Options**:
```
"I found these compatible feeders:

1. Python 450 - Portable, 0.030-0.045 inch wire, aluminum-ready
2. Wire Feeder 15A - Portable, 0.035 inch, steel/stainless

Which feeder works for you?"
```

**After Selection**:
- Add to Response JSON: `{"Feeder": {"gin": "K4331-1", "description": "Python 450"}}`
- Advance to S3 (Cooler)

---

### 3.3 S3: Cooler

**Prompt Template** (if Y):
```
"Excellent! Now for the cooling system.

For your Aristo 500ix and Python 450, you'll need a cooler.

What cooling do you prefer?
• Cooling type (water or air)
• Flow rate (e.g., 2 GPM, 4 GPM for water cooling)
• Tank capacity (e.g., 3 gallon, 5 gallon)

Or say 'skip' if you don't need a cooler."
```

**User Response Examples**:
- "Water cooling" → Extract cooling_type
- "I need 4 GPM water cooling" → Extract cooling_type + flow_rate
- "Cool Mate 3" → Direct product lookup
- "Skip" → Skip cooler

**LLM Extraction**:
```json
{
  "master_json_updates": {
    "Cooler": {
      "cooling_type": "water",
      "flow_rate": "4 GPM"
    }
  }
}
```

**Compatibility Validation**:
- Cooler must be compatible with PowerSource AND Feeder (if selected)

**Neo4j Search**:
```cypher
// Find coolers compatible with PowerSource AND Feeder
MATCH (ps:Product {gin: $power_source_gin})-[:COMPATIBLE_WITH]-(c:Product)
WHERE c.category = 'Cooler'
  AND ($cooling_type IS NULL OR c.cooling_type = $cooling_type)
  AND ($flow_rate IS NULL OR c.flow_rate CONTAINS $flow_rate)
  // If feeder was selected, validate compatibility
  AND (
    $feeder_gin IS NULL
    OR $feeder_gin = ''
    OR EXISTS((c)-[:COMPATIBLE_WITH]-(:Product {gin: $feeder_gin}))
  )
RETURN c
LIMIT 5

// Parameters:
// $power_source_gin = "0446200880" (from Response JSON)
// $feeder_gin = "K4331-1" (from Response JSON, if selected)
// $cooling_type = "water" (from Master JSON)
// $flow_rate = "4 GPM" (from Master JSON)
```

**After Selection**:
- Add to Response JSON: `{"Cooler": {"gin": "K2584-1", "description": "Cool Mate 3"}}`
- Advance to S4 (Interconnect)

---

### 3.4 S4: Interconnect

**Prompt Template** (if Y):
```
"Perfect! Now let's select the interconnector cable.

What cable length do you need?
• 3 meters (10 ft) - compact setup
• 5 meters (16 ft) - standard
• 10 meters (33 ft) - extended reach
• 15 meters (50 ft) - maximum reach

Or say 'skip'."
```

**User Response Examples**:
- "5 meters" → Extract length
- "I need 10m cable" → Extract length
- "Skip" → Skip interconnect

**LLM Extraction**:
```json
{
  "master_json_updates": {
    "Interconnect": {
      "length": "16 ft"
    }
  }
}
```

**Compatibility Validation**:
- Interconnector must be compatible with PowerSource, Feeder, and Cooler (if selected)

**Neo4j Search**:
```cypher
// Find interconnectors compatible with all selected components
MATCH (ps:Product {gin: $power_source_gin})-[:COMPATIBLE_WITH]-(ic:Product)
WHERE ic.category = 'Interconnector'
  AND ($length IS NULL OR ic.length CONTAINS $length)
  // Validate compatibility with Feeder (if selected)
  AND (
    $feeder_gin IS NULL OR $feeder_gin = ''
    OR EXISTS((ic)-[:COMPATIBLE_WITH]-(:Product {gin: $feeder_gin}))
  )
  // Validate compatibility with Cooler (if selected)
  AND (
    $cooler_gin IS NULL OR $cooler_gin = ''
    OR EXISTS((ic)-[:COMPATIBLE_WITH]-(:Product {gin: $cooler_gin}))
  )
RETURN ic
LIMIT 5

// Parameters:
// $power_source_gin, $feeder_gin, $cooler_gin from Response JSON
// $length from Master JSON
```

**After Selection**:
- Add to Response JSON: `{"Interconnect": {"gin": "...", "description": "Interconnector Cable 5m"}}`
- Advance to S5 (Torch)

---

### 3.5 S5: Torch

**Prompt Template** (if Y):
```
"Almost done! Now let's select your torch.

For your setup, what torch characteristics do you need?
• Amperage rating (should match your power source: 400A, 500A, 600A)
• Cooling type (water-cooled or air-cooled)
• Cable length (if different from interconnector)

Or mention a specific torch model, or say 'skip'."
```

**User Response Examples**:
- "500A water-cooled torch" → Extract parameters
- "Bernard Q400" → Direct product lookup
- "Skip" → Skip torch

**LLM Extraction**:
```json
{
  "master_json_updates": {
    "Torch": {
      "amperage_rating": "500 A",
      "cooling_type": "water",
      "process": "MIG (GMAW)"
    }
  }
}
```

**Compatibility Validation**:
- Torch must be compatible with Feeder AND Cooler (if selected)
- **Note**: Torch compatibility is with Feeder/Cooler, NOT PowerSource directly

**Neo4j Search**:
```cypher
// Find torches compatible with Feeder AND Cooler
// Start with Feeder if selected, otherwise PowerSource
MATCH (base:Product)
WHERE (
  ($feeder_gin IS NOT NULL AND $feeder_gin != '' AND base.gin = $feeder_gin)
  OR ($feeder_gin IS NULL OR $feeder_gin = '') AND base.gin = $power_source_gin
)
MATCH (base)-[:COMPATIBLE_WITH]-(t:Product)
WHERE t.category = 'Torch'
  AND ($amperage_rating IS NULL OR t.amperage_rating CONTAINS $amperage_rating)
  AND ($cooling_type IS NULL OR t.cooling_type = $cooling_type)
  // Validate compatibility with Cooler (if selected)
  AND (
    $cooler_gin IS NULL OR $cooler_gin = ''
    OR EXISTS((t)-[:COMPATIBLE_WITH]-(:Product {gin: $cooler_gin}))
  )
RETURN t
LIMIT 5

// Parameters:
// $feeder_gin, $cooler_gin, $power_source_gin from Response JSON
// $amperage_rating, $cooling_type from Master JSON
```

**After Selection**:
- Add to Response JSON: `{"Torch": {"gin": "...", "description": "Bernard Q400"}}`
- Advance to S6 (Accessories)

---

### 3.6 S6: Accessories (Optional)

**Prompt Template**:
```
"Great! Your core package is complete:
• PowerSource: Aristo 500ix
• Feeder: Python 450
• Cooler: Cool Mate 3
• Interconnect: 5m Cable
• Torch: Bernard Q400

Would you like to add any accessories, or shall we proceed to generate your complete package?

Say 'add accessories' to browse, or 'go ahead' / 'generate packages' to finalize."
```

**User Response**:
- "Go ahead" / "Generate packages" / "Finalize" → Advance to S7
- "Add accessories" → Show accessory options
- "Skip all" → Advance to S7

---

### 3.7 S7: Finalize

**Step 1: Validate Threshold**
```python
# Count real components in Response JSON
real_count = count_real_components(response_json)

if real_count < 3:
    return """
    You need at least 3 components to generate packages.
    Currently you have {real_count}:
    • PowerSource: Aristo 500ix
    • Feeder: Python 450

    Would you like to add more components?
    """
```

**Step 2: Get User Confirmation**
```
"Your configuration is ready with {component_count} components.

Ready to generate your complete packages?

Say 'confirm' or 'yes' to proceed."
```

**Step 3: Call Backend**
```python
if user_confirms:
    # Call Sparky + Standard package generation
    packages = await orchestrator.generate_packages(
        response_json=response_json,
        master_json=master_json
    )

    # Present both packages to user
    return format_package_presentation(packages)
```

---

## 4. Component Applicability Integration

### 4.1 Dynamic State Skipping

**After S1 (PowerSource Selection)**:

```python
async def _handle_power_source_selection(session, user_message):
    # ... user selects Aristo 500ix ...

    power_source_gin = "0446200880"  # Aristo 500ix

    # Get component applicability
    config_manager = get_component_config_manager()
    applicability = config_manager.get_applicability(power_source_gin)

    # AUTO-FILL NA COMPONENTS IMMEDIATELY
    na_service = get_na_autofill_service()
    filled_na = na_service.auto_fill_na_components(
        session.partial_package,
        applicability
    )

    # Example: Renegade ES300 has Feeder=N, Cooler=N, Interconnect=N
    if applicability.Feeder == "N":
        response_json["Feeder"] = {"gin": "NA", "description": "Not Applicable"}
    if applicability.Cooler == "N":
        response_json["Cooler"] = {"gin": "NA", "description": "Not Applicable"}
    if applicability.Interconnect == "N":
        response_json["Interconnect"] = {"gin": "NA", "description": "Not Applicable"}

    # Build confirmation message
    message = f"Great! Selected {power_source.name}.\n\n"

    if filled_na:
        message += "The following components are not needed for this power source:\n"
        for component in filled_na:
            message += f"• {component}: Not Applicable\n"
        message += "\n"

    # Determine next state
    next_state = state_machine.get_next_active_state(
        current_state=ConversationState.POWER_SOURCE,
        applicability=applicability
    )

    # Example: Renegade ES300 → skip to Torch (S5)
    # Example: Aristo 500ix → proceed to Feeder (S2)

    return message, [], next_state
```

---

## 5. Master JSON vs Response JSON

### 5.1 Clear Separation

**Master Parameter JSON** (User Requirements):
```json
{
  "PowerSource": {
    "process": "MIG (GMAW)",
    "current_output": "500 A",
    "material": "aluminum",
    "voltage": "230V",
    "phase": "3-phase"
  },
  "Feeder": {
    "portability": "portable",
    "wire_size": "0.035 inch",
    "process": "MIG (GMAW)"
  },
  "Cooler": {
    "cooling_type": "water",
    "flow_rate": "4 GPM"
  }
}
```

**Response JSON** (Selected Products - "Cart"):
```json
{
  "PowerSource": {
    "gin": "0446200880",
    "description": "Aristo 500ix"
  },
  "Feeder": {
    "gin": "K4331-1",
    "description": "Python 450"
  },
  "Cooler": {
    "gin": "K2584-1",
    "description": "Cool Mate 3"
  },
  "Interconnect": {
    "gin": "NA",
    "description": "Not Applicable"
  },
  "Torch": {
    "gin": "",
    "description": ""
  }
}
```

### 5.2 Usage

- **Master JSON**: Used for Neo4j search, parameter tracking, requirement validation
- **Response JSON**: Used for cart, package generation, backend API calls

---

## 6. Conversation Flow Example

### 6.1 Example: Aristo 500ix Configuration (All Y)

**Turn 1: S1 PowerSource**
```
System: "What power source do you need?"
User: "I need Aristo 500ix"

[LLM Extraction]
Master JSON PowerSource: {direct_product_mention: "Aristo 500ix"}

[Neo4j Direct Lookup]
Found: Aristo 500ix (0446200880)

[Check Applicability]
Feeder=Y, Cooler=Y, Interconnect=Y, Torch=Y

System: "Great! Selected Aristo 500ix (500A MIG/TIG).
Now let's select a feeder..."
```

**Turn 2: S2 Feeder**
```
System: "What feeder do you need? (portability, wire size, material)"
User: "Portable feeder with 0.035 wire"

[LLM Extraction]
Master JSON Feeder: {portability: "portable", wire_size: "0.035 inch"}

[Neo4j Search - COMPATIBLE_WITH Aristo]
Found:
1. Python 450 - Portable, 0.030-0.045 inch
2. Wire Feeder 15A - Portable, 0.035 inch

System: "I found these feeders:
1. Python 450 - Portable, 0.030-0.045 inch wire
2. Wire Feeder 15A - Portable, 0.035 inch

Which one?"

User: "Python 450"

[Add to Response JSON]
Response JSON Feeder: {gin: "K4331-1", description: "Python 450"}

System: "Excellent! Python 450 selected.
Now for the cooling system..."
```

**Turn 3: S3 Cooler**
```
System: "What cooling do you need?"
User: "Water cooling"

[LLM Extraction]
Master JSON Cooler: {cooling_type: "water"}

[Neo4j Search]
Found: Cool Mate 3 - 4 GPM water cooling

System: "I found Cool Mate 3 (4 GPM water cooling). Good for you?"
User: "Yes"

[Add to Response JSON]
System: "Great! Cool Mate 3 added. Now for interconnector cable..."
```

**Turn 4: S4 Interconnect**
```
System: "What cable length? (3m, 5m, 10m, 15m)"
User: "5 meters"

[Search & Add]
Response JSON Interconnect: {gin: "...", description: "5m Cable"}

System: "5m cable added. Now let's select your torch..."
```

**Turn 5: S5 Torch**
```
System: "What torch? (amperage, cooling)"
User: "500A water-cooled"

[Search & Add]
Response JSON Torch: {gin: "...", description: "Bernard Q400"}

System: "Bernard Q400 added!

Your package:
• PowerSource: Aristo 500ix
• Feeder: Python 450
• Cooler: Cool Mate 3
• Interconnect: 5m Cable
• Torch: Bernard Q400

Add accessories or generate packages?"
```

**Turn 6: S6 Accessories**
```
User: "Generate packages"

[Advance to S7]
```

**Turn 7: S7 Finalize**
```
[Validate Threshold]
Real components: 5 (≥3 ✓)

System: "Ready to generate packages with 5 components. Confirm?"
User: "Yes"

[Call Backend - Sparky + Standard]
[Present Packages]
```

---

### 6.2 Example: Renegade ES300 (Minimal Y)

**Turn 1: S1 PowerSource**
```
User: "Renegade ES300"

[Direct Lookup]
Found: Renegade ES300 (0445250880)

[Check Applicability]
Feeder=N, Cooler=N, Interconnect=N, Torch=Y

[Auto-Fill NA]
Response JSON:
- Feeder: {gin: "NA", description: "Not Applicable"}
- Cooler: {gin: "NA", description: "Not Applicable"}
- Interconnect: {gin: "NA", description: "Not Applicable"}

System: "Selected Renegade ES300!

This power source doesn't require:
• Feeder: Not Applicable
• Cooler: Not Applicable
• Interconnect: Not Applicable

Let's select your torch..."

[Skip directly to S5]
```

**Turn 2: S5 Torch**
```
User: "300A air-cooled"

[Search & Add]
Response JSON Torch: {gin: "...", description: "TIG Torch 300A"}

System: "Your package:
• PowerSource: Renegade ES300
• Torch: TIG Torch 300A

This has only 2 real components. You need at least 3 to generate packages.
Would you like to add accessories?"
```

**Turn 3: S6 Accessories**
```
User: "Yes, add accessories"

[Show accessory options]
User selects 2 accessories

Response JSON:
- Accessory1: {gin: "...", description: "Welding Helmet"}
- Accessory2: {gin: "...", description: "Gloves"}

Real components now: 4 (≥3 ✓)

System: "Ready to generate packages?"
```

---

## 7. Implementation Checklist

- [ ] Update ConversationalManager with state-by-state logic
- [ ] Implement per-state prompt templates
- [ ] Integrate Master JSON extraction per state
- [ ] Add Neo4j search after parameter collection
- [ ] Implement product list presentation (1 vs multiple)
- [ ] Add user selection handling
- [ ] Integrate Component Applicability checking
- [ ] Implement NA auto-fill after S1
- [ ] Add dynamic state skipping
- [ ] Implement threshold validation at S7
- [ ] Add user confirmation handling at S7
- [ ] Test Aristo 500ix flow (all Y)
- [ ] Test Renegade ES300 flow (minimal Y)
- [ ] Test skip functionality

---

## 8. Success Criteria

✅ **Sequential Progression**: States processed in order S1→S7
✅ **Parameter Collection**: Each state collects parameters before searching
✅ **Neo4j Search**: Only when ≥1 parameter for component
✅ **Product Selection**: User selects from list or direct match
✅ **Component Applicability**: N components auto-filled as NA
✅ **Dynamic Skipping**: System skips N states automatically
✅ **Threshold Validation**: Blocks generation if < 3 components
✅ **User Confirmation**: Requires explicit confirmation at S7

---

## 9. Compatibility Validation Matrix

### 9.1 Neo4j Category Reference

```yaml
Categories:
  - PowerSource
  - Feeder
  - FeederAccessory
  - Cooler
  - Interconnector
  - Torch
  - PowerSourceAccessory
  - ConnectivityAccessory
  - Remote
  - Accessory
```

### 9.2 Component Compatibility Rules

**S1: PowerSource**
- No compatibility validation (first component)
- Cannot be skipped

**S2: Feeder**
- Compatible with: PowerSource
```cypher
MATCH (ps:Product {gin: $power_source_gin})-[:COMPATIBLE_WITH]-(f:Product)
WHERE f.category = 'Feeder'
```

**S3: Cooler**
- Compatible with: PowerSource AND Feeder (if selected)
```cypher
MATCH (ps:Product {gin: $power_source_gin})-[:COMPATIBLE_WITH]-(c:Product)
WHERE c.category = 'Cooler'
  AND ($feeder_gin IS NULL OR EXISTS((c)-[:COMPATIBLE_WITH]-(:Product {gin: $feeder_gin})))
```

**S4: Interconnector**
- Compatible with: PowerSource, Feeder, Cooler (all selected components)
```cypher
MATCH (ps:Product {gin: $power_source_gin})-[:COMPATIBLE_WITH]-(ic:Product)
WHERE ic.category = 'Interconnector'
  AND ($feeder_gin IS NULL OR EXISTS((ic)-[:COMPATIBLE_WITH]-(:Product {gin: $feeder_gin})))
  AND ($cooler_gin IS NULL OR EXISTS((ic)-[:COMPATIBLE_WITH]-(:Product {gin: $cooler_gin})))
```

**S5: Torch**
- Compatible with: Feeder AND Cooler (if selected)
- **Note**: NOT directly with PowerSource
```cypher
MATCH (base:Product {gin: $feeder_gin})-[:COMPATIBLE_WITH]-(t:Product)
WHERE t.category = 'Torch'
  AND ($cooler_gin IS NULL OR EXISTS((t)-[:COMPATIBLE_WITH]-(:Product {gin: $cooler_gin})))
```

**S6: Accessories** (Category-Specific)

```yaml
PowerSourceAccessory:
  compatible_with: [PowerSource]
  query: |
    MATCH (ps:Product {gin: $power_source_gin})-[:COMPATIBLE_WITH]-(a:Product)
    WHERE a.category = 'PowerSourceAccessory'

FeederAccessory:
  compatible_with: [Feeder]
  query: |
    MATCH (f:Product {gin: $feeder_gin})-[:COMPATIBLE_WITH]-(a:Product)
    WHERE a.category = 'FeederAccessory'

ConnectivityAccessory:
  compatible_with: [PowerSource, Feeder]
  query: |
    MATCH (ps:Product {gin: $power_source_gin})-[:COMPATIBLE_WITH]-(a:Product)
    WHERE a.category = 'ConnectivityAccessory'
      AND ($feeder_gin IS NULL OR EXISTS((a)-[:COMPATIBLE_WITH]-(:Product {gin: $feeder_gin})))

Remote:
  compatible_with: [PowerSource, Feeder]
  query: |
    MATCH (ps:Product {gin: $power_source_gin})-[:COMPATIBLE_WITH]-(r:Product)
    WHERE r.category = 'Remote'
      AND ($feeder_gin IS NULL OR EXISTS((r)-[:COMPATIBLE_WITH]-(:Product {gin: $feeder_gin})))
```

### 9.3 Skip Behavior & Compatibility

**When Component is Skipped**:
- Skipped components are NOT included in compatibility validation
- Example: If Feeder is skipped at S2
  - S3 (Cooler): Only validate compatibility with PowerSource
  - S4 (Interconnector): Only validate compatibility with PowerSource + Cooler
  - S5 (Torch): Only validate compatibility with Cooler (if selected)

**Example Flow with Skips**:
```
S1: PowerSource = Aristo 500ix (0446200880)
S2: Feeder = SKIPPED
S3: Cooler = Cool Mate 3 (K2584-1)
  ✓ Validate: Compatible with PowerSource only
S4: Interconnector = SKIPPED
S5: Torch = Bernard Q400
  ✓ Validate: Compatible with Cooler only (Feeder was skipped)
```

### 9.4 Compatibility Query Pattern Template

```python
def build_compatibility_query(
    component_category: str,
    master_json: dict,
    response_json: dict
) -> tuple[str, dict]:
    """
    Build Neo4j query with compatibility validation

    Returns: (query_string, parameters_dict)
    """

    # Get previously selected components
    power_source_gin = response_json.get("PowerSource", {}).get("gin")
    feeder_gin = response_json.get("Feeder", {}).get("gin")
    cooler_gin = response_json.get("Cooler", {}).get("gin")
    interconnect_gin = response_json.get("Interconnect", {}).get("gin")

    # Build base query
    query = f"""
    MATCH (ps:Product {{gin: $power_source_gin}})-[:COMPATIBLE_WITH]-(target:Product)
    WHERE target.category = $category
    """

    # Add component-specific compatibility checks
    if component_category == "Feeder":
        # Only PowerSource compatibility (already in base query)
        pass

    elif component_category == "Cooler":
        query += """
        AND ($feeder_gin IS NULL OR $feeder_gin = ''
             OR EXISTS((target)-[:COMPATIBLE_WITH]-(:Product {gin: $feeder_gin})))
        """

    elif component_category == "Interconnector":
        query += """
        AND ($feeder_gin IS NULL OR $feeder_gin = ''
             OR EXISTS((target)-[:COMPATIBLE_WITH]-(:Product {gin: $feeder_gin})))
        AND ($cooler_gin IS NULL OR $cooler_gin = ''
             OR EXISTS((target)-[:COMPATIBLE_WITH]-(:Product {gin: $cooler_gin})))
        """

    elif component_category == "Torch":
        # Torch is special - compatible with Feeder/Cooler, not PowerSource
        query = """
        MATCH (base:Product)
        WHERE (
          ($feeder_gin IS NOT NULL AND $feeder_gin != '' AND base.gin = $feeder_gin)
          OR ($feeder_gin IS NULL OR $feeder_gin = '') AND base.gin = $power_source_gin
        )
        MATCH (base)-[:COMPATIBLE_WITH]-(target:Product)
        WHERE target.category = $category
          AND ($cooler_gin IS NULL OR $cooler_gin = ''
               OR EXISTS((target)-[:COMPATIBLE_WITH]-(:Product {gin: $cooler_gin})))
        """

    # Add Master JSON parameter filters
    query += build_parameter_filters(component_category, master_json)

    query += """
    RETURN target
    LIMIT 5
    """

    # Build parameters
    params = {
        "category": component_category,
        "power_source_gin": power_source_gin,
        "feeder_gin": feeder_gin or "",
        "cooler_gin": cooler_gin or "",
        **extract_component_parameters(component_category, master_json)
    }

    return query, params
```

---

**Status**: Architecture Updated - Compatibility Validation Added
**Version**: 2.0
**Next**: Get approval on updated architecture, then implement state-by-state handlers
