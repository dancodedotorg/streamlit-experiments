# Agent Refactoring Recommendation

## Executive Summary

Your current functions [`gemini_voiceover()`](gemini_agents.py:417) and [`generate_elevenlabs_speech()`](gemini_agents.py:475) are excellent candidates for refactoring into a multi-agent system using the Gemini ADK. This refactoring will provide better modularity, maintainability, and extensibility for future agents.

## Current Architecture Analysis

### Function 1: `gemini_voiceover`
- **Input**: Base64-encoded PDF
- **Processing**: Analyzes PDF slides and generates voiceover scripts
- **Output**: List of scene dictionaries with `comment` and `speech` fields
- **Uses**: Structured output with `SceneList` Pydantic model

### Function 2: `generate_elevenlabs_speech`
- **Input**: List of scenes from previous function
- **Processing**: Adds ElevenLabs audio tags to speech
- **Output**: Refined scenes with additional `elevenlabs` field
- **Uses**: Structured output with `RefinedSceneList` Pydantic model

### Current Workflow
```
PDF (base64) → gemini_voiceover() → scenes → generate_elevenlabs_speech() → refined_scenes
```

## Recommended Agent Architecture

Based on ADK best practices, here's the recommended architecture:

### 1. Agent Hierarchy

```
📦 VoiceoverPipelineAgent (SequentialAgent - Root/Orchestrator)
  ├─ 🎯 PDFVoiceoverAgent (LlmAgent)
  └─ 🎨 ElevenLabsRefinementAgent (LlmAgent)
```

### 2. Agent Specifications

#### **VoiceoverPipelineAgent** (Orchestrator)
- **Type**: `SequentialAgent` (workflow agent)
- **Purpose**: Orchestrates the sequential execution of sub-agents
- **Why Sequential**: The workflow is deterministic - ElevenLabs refinement MUST happen after voiceover generation
- **Advantages**:
  - Deterministic, predictable execution
  - No LLM overhead for orchestration
  - Easy to extend with additional pipeline stages
  - Built-in state management for data passing

#### **PDFVoiceoverAgent** (Sub-agent 1)
- **Type**: `LlmAgent`
- **Model**: `gemini-2.5-flash` (or configurable)
- **Input**: PDF document (via state or context)
- **Instruction**: Current `SYSTEM_PROMPTS['pdf-to-voiceover']`
- **Output**: Scene list with `comment` and `speech`
- **Key Configuration**:
  - `output_key="scenes"` - Saves result to `state['scenes']`
  - `response_schema=SceneList` - Maintains structured output
  - `response_mime_type="application/json"`

#### **ElevenLabsRefinementAgent** (Sub-agent 2)
- **Type**: `LlmAgent`
- **Model**: `gemini-2.5-flash` (can use cheaper model if needed)
- **Input**: Scenes from state (via `{scenes}` in instruction)
- **Instruction**: Current `SYSTEM_PROMPTS['elevenlabs']` with state injection
- **Output**: Refined scenes with audio tags
- **Key Configuration**:
  - `output_key="refined_scenes"` - Saves result to `state['refined_scenes']`
  - `response_schema=RefinedSceneList` - Maintains structured output
  - Instruction uses `{scenes}` to access previous agent's output

### 3. Data Flow Using State

```
User Input (PDF) 
    ↓
state['pdf_base64'] = <base64_data>
    ↓
PDFVoiceoverAgent reads PDF from state/context
    ↓
PDFVoiceoverAgent outputs → state['scenes'] (via output_key)
    ↓
ElevenLabsRefinementAgent reads {scenes} from state (via instruction template)
    ↓
ElevenLabsRefinementAgent outputs → state['refined_scenes'] (via output_key)
    ↓
Final Result: state['refined_scenes']
```

## Key ADK Patterns to Use

### 1. **State Management with `output_key`**
```python
agent = LlmAgent(
    name="PDFVoiceoverAgent",
    output_key="scenes"  # Automatically saves response to state['scenes']
)
```

### 2. **State Injection in Instructions**
```python
instruction = """
Process the following scenes:
{scenes}  # This will be replaced with state['scenes']
"""
```

### 3. **Structured Output Configuration**
```python
generate_content_config = types.GenerateContentConfig(
    response_mime_type="application/json",
    response_schema=SceneList  # Pydantic model
)
```

### 4. **PDF Handling Options**

**Option A: Pass PDF via State (Recommended)**
```python
# In initial setup
session.state['pdf_bytes'] = pdf_bytes
session.state['pdf_mime_type'] = 'application/pdf'

# In PDFVoiceoverAgent instruction
instruction = """
Analyze the PDF provided in the context...
"""
```

**Option B: Use Custom Tool**
```python
def get_pdf_for_analysis(context: ToolContext) -> bytes:
    """Retrieves the PDF bytes from session state."""
    return context.state.get('pdf_bytes')
```

## Implementation Comparison

### Current Approach (Functions)
```python
# Tightly coupled, manual orchestration
pdf_base64 = get_pdf()
scenes = gemini_voiceover(pdf_base64)
refined = generate_elevenlabs_speech(scenes)
```

### Proposed Approach (Agents)
```python
# Modular, automatic orchestration
from google.adk.agents import SequentialAgent, LlmAgent
from google.adk.runners import Runner

# Define agents (done once)
voiceover_agent = LlmAgent(
    name="PDFVoiceoverAgent",
    model="gemini-2.5-flash",
    instruction=SYSTEM_PROMPTS['pdf-to-voiceover'],
    output_key="scenes",
    generate_content_config=types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=SceneList
    )
)

elevenlabs_agent = LlmAgent(
    name="ElevenLabsRefinementAgent",
    model="gemini-2.5-flash",
    instruction=SYSTEM_PROMPTS['elevenlabs'],
    output_key="refined_scenes",
    generate_content_config=types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=RefinedSceneList
    )
)

# Orchestrator
pipeline = SequentialAgent(
    name="VoiceoverPipelineAgent",
    sub_agents=[voiceover_agent, elevenlabs_agent],
    description="Generates and refines voiceover scripts from PDF slides"
)

# Use (each time)
runner = Runner(agent=pipeline, app_name="voiceover", session_service=session_service)
session.state['pdf_input'] = pdf_data  # Store PDF
result = await runner.run_async(user_id, session_id, user_message)
refined_scenes = session.state['refined_scenes']  # Get final result
```

## Advantages of Agent-Based Approach

### 1. **Modularity**
- Each agent is self-contained with clear responsibilities
- Easy to test agents independently
- Can reuse agents in different pipelines

### 2. **Extensibility**
- Add new agents to pipeline easily:
  ```python
  sub_agents=[voiceover_agent, elevenlabs_agent, quality_check_agent, export_agent]
  ```

### 3. **Maintainability**
- Instructions are clearly associated with agents
- Configuration is centralized in agent definition
- State management is automatic

### 4. **Flexibility**
- Easy to switch models per agent (e.g., use `gemini-1.5-flash` for simple tasks)
- Can add parallel processing with `ParallelAgent` if needed
- Can add conditional logic with custom agents

### 5. **Production Features**
- Built-in session management
- Event streaming for progress updates
- Callback hooks for monitoring
- Memory management across conversations
- Deployment to Vertex AI Agent Engine

## Future Extensibility Examples

### Example 1: Add Quality Check Agent
```python
quality_agent = LlmAgent(
    name="QualityCheckAgent",
    instruction="Review the refined scenes and check for...",
    output_key="quality_report"
)

pipeline = SequentialAgent(
    sub_agents=[voiceover_agent, elevenlabs_agent, quality_agent]
)
```

### Example 2: Add Parallel Translation
```python
from google.adk.agents import ParallelAgent

spanish_agent = LlmAgent(name="SpanishTranslator", ...)
french_agent = LlmAgent(name="FrenchTranslator", ...)

translation_group = ParallelAgent(
    name="TranslationGroup",
    sub_agents=[spanish_agent, french_agent]
)

pipeline = SequentialAgent(
    sub_agents=[voiceover_agent, elevenlabs_agent, translation_group]
)
```

### Example 3: Add Conditional Logic with Custom Agent
```python
class QualityGateAgent(BaseAgent):
    async def _run_async_impl(self, ctx: InvocationContext):
        quality_score = ctx.session.state.get('quality_score', 0)
        if quality_score < 0.8:
            # Regenerate or escalate
            yield Event(actions=EventActions(escalate=True))
        else:
            yield Event(content=Content(parts=[Part(text="Quality check passed")]))
```

## Handling PDF Input in Agents

### Challenge
The current `gemini_voiceover` function receives PDF as base64 and converts it to bytes for the Gemini API:

```python
def gemini_voiceover(pdf_base64):
    pdf_bytes = base64.b64decode(pdf_base64)
    formatted_parts = [
        "Analyze the slides in this PDF...",
        types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf")
    ]
```

### Solution for Agents

**Option 1: Custom Tool (Recommended)**
Create a tool that the agent can call to access the PDF:

```python
def analyze_pdf_slides(context: ToolContext) -> str:
    """
    Analyzes PDF slides and returns the content for voiceover generation.
    The PDF is provided via the session context.
    """
    pdf_bytes = context.state.get('pdf_bytes')
    if not pdf_bytes:
        return "Error: No PDF provided"
    
    # Agent will process this in its normal flow
    # Return a signal that PDF is ready
    return "PDF loaded and ready for analysis"

voiceover_agent = LlmAgent(
    name="PDFVoiceoverAgent",
    tools=[analyze_pdf_slides],
    instruction="""
    First, call analyze_pdf_slides to access the PDF.
    Then generate voiceover scripts...
    """
)
```

**Option 2: Pre-process in Callback**
Use `before_model_callback` to inject PDF into the request:

```python
def inject_pdf_callback(ctx: CallbackContext):
    """Inject PDF bytes into the agent's request before model call."""
    pdf_bytes = ctx.state.get('pdf_bytes')
    if pdf_bytes:
        # Modify the request to include PDF
        ctx.request.contents.append(
            types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf")
        )

voiceover_agent = LlmAgent(
    name="PDFVoiceoverAgent",
    before_model_callback=inject_pdf_callback,
    ...
)
```

**Option 3: Custom Agent (Most Control)**
For complex PDF handling, create a custom agent:

```python
from google.adk.agents import BaseAgent

class PDFVoiceoverAgent(BaseAgent):
    async def _run_async_impl(self, ctx: InvocationContext):
        # Get PDF from state
        pdf_bytes = ctx.session.state.get('pdf_bytes')
        
        # Use GEMINI_CLIENT directly like current function
        formatted_parts = [
            "Analyze the slides in this PDF...",
            types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf")
        ]
        
        response = GEMINI_CLIENT.models.generate_content(
            model=GEMINI_MODEL,
            contents=formatted_parts,
            config=generate_content_config
        )
        
        # Save to state
        scenes = json.loads(response.text)["scenes"]
        ctx.session.state['scenes'] = scenes
        
        # Yield event with result
        yield Event(
            author=self.name,
            content=Content(parts=[Part(text=response.text)]),
            actions=EventActions(state_delta={'scenes': scenes})
        )
```

## Migration Strategy

### Phase 1: Create Agent Wrappers (Low Risk)
Keep existing functions, create agents that call them:

```python
class LegacyVoiceoverAgent(BaseAgent):
    async def _run_async_impl(self, ctx: InvocationContext):
        pdf_base64 = ctx.session.state.get('pdf_base64')
        scenes = gemini_voiceover(pdf_base64)  # Call existing function
        ctx.session.state['scenes'] = scenes
        yield Event(...)
```

### Phase 2: Pure ADK Implementation
Rewrite using native ADK patterns with LlmAgent.

### Phase 3: Add New Agents
Extend with quality checks, translations, etc.

## Recommended Next Steps

1. **Start Simple**: Create basic LlmAgent versions of both functions
2. **Test Independently**: Ensure each agent works in isolation
3. **Combine with SequentialAgent**: Wire them together
4. **Add Session/Runner Infrastructure**: Set up proper session management
5. **Test End-to-End**: Verify complete pipeline works
6. **Add Monitoring**: Use callbacks for logging and metrics
7. **Extend**: Add new agents for additional capabilities

## Code Structure Recommendation

```
gemini_agents.py  (current)
    ↓ refactor to ↓
├── agents/
│   ├── __init__.py
│   ├── voiceover_agent.py      # PDFVoiceoverAgent
│   ├── elevenlabs_agent.py     # ElevenLabsRefinementAgent
│   └── pipeline_agent.py       # VoiceoverPipelineAgent (orchestrator)
├── models/
│   └── schemas.py              # Scene, SceneList, RefinedScene, etc.
├── config/
│   └── prompts.py              # SYSTEM_PROMPTS
└── utils/
    └── gemini_client.py        # GEMINI_CLIENT setup
```

## Mental Model Correction

### ❌ Incorrect Mental Model
"An orchestration agent should use LLM reasoning to decide which agent to call"

### ✅ Correct Mental Model (for your use case)
"An orchestration agent (SequentialAgent) provides **deterministic workflow control** for predictable, ordered execution. LLM-driven delegation is for **dynamic routing** based on user intent."

### When to Use Each Pattern

**SequentialAgent (Your Use Case)**
- Fixed, predictable workflow
- One step must complete before the next
- Example: PDF → Voiceover → Refinement → Export

**LLM-Driven Delegation (Different Use Case)**
- User intent determines which agent to use
- Multiple possible paths based on query
- Example: User asks about weather → delegate to WeatherAgent; User asks about booking → delegate to BookingAgent

**ParallelAgent**
- Independent tasks that can run concurrently
- Example: Generate voiceovers in multiple languages simultaneously

**Custom Agent**
- Conditional logic based on runtime conditions
- Complex state management
- Example: If quality score < 0.8, re-run voiceover generation

## Conclusion

Your functions are **perfect candidates** for the Sequential Agent pattern. The workflow is linear and deterministic, making SequentialAgent the ideal orchestrator. This provides:

- ✅ Clear separation of concerns
- ✅ Easy extensibility for future agents  
- ✅ Automatic state management
- ✅ Production-ready infrastructure (sessions, callbacks, deployment)
- ✅ Maintainable, testable code

The refactoring aligns perfectly with ADK best practices for building multi-agent systems.
