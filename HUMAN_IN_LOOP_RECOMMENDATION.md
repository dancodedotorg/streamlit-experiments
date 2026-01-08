# Human-in-the-Loop Architecture Recommendation

## Your Requirement

You want to insert human review/approval steps between each agent:

```
PDF → VoiceoverAgent → [HUMAN REVIEW/EDIT] → ElevenLabsAgent → [HUMAN REVIEW/EDIT] → Done
```

This is a **critical architectural decision** that changes the recommendation significantly.

## Two Viable Approaches

### ✅ Approach 1: Streamlit UI Orchestration (RECOMMENDED)

**Architecture**: The UI (Streamlit) orchestrates individual agents, NOT a SequentialAgent

```
Streamlit App (Orchestrator)
  ├─ Button: "Generate Voiceover" → runs PDFVoiceoverAgent
  ├─ Display/Edit: Shows scenes, allows editing
  ├─ Button: "Approve & Add Audio Tags" → runs ElevenLabsAgent  
  ├─ Display/Edit: Shows refined scenes, allows editing
  └─ Button: "Export/Continue" → next step
```

**How It Works**:

```python
# In your Streamlit app
import streamlit as st
from google.adk.runners import InMemoryRunner
from google.adk.sessions import InMemorySessionService

# Define agents (NOT in a SequentialAgent)
voiceover_agent = LlmAgent(name="PDFVoiceoverAgent", ...)
elevenlabs_agent = LlmAgent(name="ElevenLabsAgent", ...)

# Session management
session_service = InMemorySessionService()
session = await session_service.get_or_create_session(...)

# STEP 1: Generate voiceover
if st.button("Generate Voiceover Script"):
    runner = InMemoryRunner(agent=voiceover_agent, session_service=session_service)
    
    # Run agent and stream events
    for event in runner.run(user_id, session_id, pdf_input):
        if event.is_final_response():
            st.session_state.scenes = session.state['scenes']

# STEP 2: Show editable results
if 'scenes' in st.session_state:
    st.subheader("Generated Voiceover Script")
    
    # Display and allow editing
    edited_scenes = []
    for i, scene in enumerate(st.session_state.scenes):
        with st.expander(f"Scene {i+1}: {scene['comment']}"):
            edited_speech = st.text_area(
                "Speech", 
                value=scene['speech'],
                key=f"scene_{i}"
            )
            edited_scenes.append({
                'comment': scene['comment'],
                'speech': edited_speech  # User can edit!
            })
    
    # Update session state with edits
    if st.button("Save Edits"):
        session.state['scenes'] = edited_scenes
        st.success("Edits saved!")

# STEP 3: Generate ElevenLabs refinement
if st.button("Add Audio Tags"):
    runner = InMemoryRunner(agent=elevenlabs_agent, session_service=session_service)
    
    # ElevenLabs agent reads from session.state['scenes'] (which includes user edits!)
    for event in runner.run(user_id, session_id, continue_message):
        if event.is_final_response():
            st.session_state.refined_scenes = session.state['refined_scenes']

# STEP 4: Show refined results for final approval
if 'refined_scenes' in st.session_state:
    # Similar editing interface...
    pass
```

**Advantages**:
- ✅ **Perfect for Streamlit** - leverages Streamlit's strengths
- ✅ **Full control** - users can edit any field
- ✅ **Visual feedback** - see results before continuing
- ✅ **Flexible workflow** - users can go back, regenerate specific steps
- ✅ **Simpler agent design** - each agent is independent
- ✅ **State management** - Streamlit session_state + ADK session state work together
- ✅ **No blocking** - no need for complex polling/waiting mechanisms

**Disadvantages**:
- ⚠️ Orchestration logic is in UI code (but that's actually fine for this use case)
- ⚠️ Requires page refreshes/reruns (standard Streamlit behavior)

---

### ⚡ Approach 2: Custom Tool for Human Approval (COMPLEX)

**Architecture**: A SequentialAgent with custom "approval tools" that pause and wait

```python
from google.adk.agents import SequentialAgent, LlmAgent

def request_human_approval(context: ToolContext, data_key: str) -> dict:
    """
    Pauses execution and requests human approval.
    This is COMPLEX - requires external polling mechanism.
    """
    # 1. Get data from state
    data = context.state.get(data_key)
    
    # 2. Send to external system (database, message queue, webhook)
    approval_id = send_to_approval_system(data)
    
    # 3. BLOCK and wait for human response (polling, webhook, etc.)
    # This is the tricky part - you need an external system
    while True:
        status = check_approval_status(approval_id)
        if status['completed']:
            # Return edited data from human
            context.state[data_key] = status['edited_data']
            return {'approved': True, 'edits': status['edited_data']}
        time.sleep(5)  # Poll every 5 seconds

# Agent that requests approval after generating
voiceover_agent = LlmAgent(
    name="VoiceoverWithApproval",
    instruction="Generate voiceover, then call request_approval tool",
    tools=[request_human_approval],
    output_key="scenes"
)

pipeline = SequentialAgent(
    sub_agents=[voiceover_agent, elevenlabs_agent]
)
```

**Challenges**:
- ❌ **Requires external infrastructure** (database, queue, webhook handler)
- ❌ **Blocking execution** - agent execution pauses for potentially hours
- ❌ **Complex state management** - need to persist and resume
- ❌ **Difficult UI integration** - how does user see/edit data?
- ❌ **Timeout handling** - what if user never approves?
- ❌ **No native ADK support** - you build everything custom

**When to Use**:
- Background/batch processing where humans respond asynchronously
- Enterprise workflows with dedicated approval systems
- Multi-day processes where execution can pause

**Not recommended for your use case** because:
- You have a Streamlit UI (perfect for synchronous interaction)
- You want immediate visual feedback
- You want editing capabilities (not just approve/reject)

---

## Detailed Recommendation: Streamlit UI Orchestration

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│                   Streamlit App                         │
│                  (UI Orchestrator)                       │
└─────────────────────────────────────────────────────────┘
                          │
         ┌────────────────┼────────────────┐
         ▼                ▼                ▼
   ┌─────────┐      ┌─────────┐     ┌─────────┐
   │ Session │      │ Session │     │ Session │
   │ Service │      │ Service │     │ Service │
   └─────────┘      └─────────┘     └─────────┘
         │                │                │
         ▼                ▼                ▼
   ┌─────────┐      ┌─────────┐     ┌─────────┐
   │Voiceover│      │ElevenLabs│    │ Future │
   │  Agent  │      │  Agent   │    │ Agent  │
   └─────────┘      └─────────┘     └─────────┘

Flow:
1. User uploads PDF → stored in session state
2. [Click] "Generate" → Runner executes VoiceoverAgent
3. [Display] Results shown in expandable editors
4. [Edit] User modifies text directly
5. [Click] "Save & Continue" → updates session.state['scenes']
6. [Click] "Add Audio Tags" → Runner executes ElevenLabsAgent
7. [Display] Refined results with audio tags
8. [Edit] User modifies tags/text
9. [Click] "Approve & Export" → final step
```

### Code Structure

```
voiceover_app/
├── app.py                          # Main Streamlit app (orchestrator)
├── agents/
│   ├── __init__.py
│   ├── voiceover_agent.py         # PDFVoiceoverAgent definition
│   ├── elevenlabs_agent.py        # ElevenLabsAgent definition
│   └── base_config.py             # Shared config (model, client, etc.)
├── models/
│   └── schemas.py                 # Pydantic models (Scene, RefinedScene)
├── config/
│   └── prompts.py                 # System prompts
└── utils/
    ├── session_manager.py         # ADK session helpers
    └── ui_components.py           # Reusable Streamlit components
```

### Implementation: `app.py`

```python
import streamlit as st
import asyncio
from google.adk.runners import InMemoryRunner
from google.adk.sessions import InMemorySessionService
from agents.voiceover_agent import create_voiceover_agent
from agents.elevenlabs_agent import create_elevenlabs_agent
import json
import base64

st.title("🎙️ Voiceover Pipeline with Human-in-the-Loop")

# Initialize session service (singleton)
if 'session_service' not in st.session_state:
    st.session_state.session_service = InMemorySessionService()
    st.session_state.app_name = "voiceover_pipeline"
    st.session_state.user_id = "user_001"
    st.session_state.session_id = "session_001"

# Create ADK session
async def get_session():
    return await st.session_state.session_service.get_or_create_session(
        app_name=st.session_state.app_name,
        user_id=st.session_state.user_id,
        session_id=st.session_state.session_id
    )

# ============================================
# STEP 1: Upload PDF
# ============================================
st.header("Step 1: Upload Slide Deck")
uploaded_file = st.file_uploader("Upload PDF slides", type=['pdf'])

if uploaded_file:
    pdf_bytes = uploaded_file.read()
    pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
    st.session_state.pdf_base64 = pdf_base64
    st.success(f"✅ Uploaded: {uploaded_file.name}")

# ============================================
# STEP 2: Generate Voiceover
# ============================================
st.header("Step 2: Generate Voiceover Script")

if st.button("🎬 Generate Voiceover Script", disabled='pdf_base64' not in st.session_state):
    with st.spinner("Generating voiceover script..."):
        # Create agent
        voiceover_agent = create_voiceover_agent()
        
        # Get ADK session and set PDF in state
        session = asyncio.run(get_session())
        session.state['pdf_base64'] = st.session_state.pdf_base64
        
        # Run agent
        runner = InMemoryRunner(
            agent=voiceover_agent,
            app_name=st.session_state.app_name,
            session_service=st.session_state.session_service
        )
        
        # Execute and collect events
        events = []
        for event in runner.run(
            user_id=st.session_state.user_id,
            session_id=st.session_state.session_id,
            new_message={"text": "Generate voiceover from PDF"}
        ):
            events.append(event)
            if event.is_final_response():
                # Get scenes from state
                updated_session = asyncio.run(get_session())
                st.session_state.scenes = updated_session.state.get('scenes', [])
                st.success("✅ Voiceover script generated!")

# ============================================
# STEP 3: Review and Edit Voiceover
# ============================================
if 'scenes' in st.session_state:
    st.header("Step 3: Review & Edit Voiceover")
    
    st.info("💡 Review and edit the voiceover script. Click 'Save Edits' before continuing.")
    
    # Create editable fields for each scene
    edited_scenes = []
    for i, scene in enumerate(st.session_state.scenes):
        with st.expander(f"🎬 Scene {i+1}", expanded=(i == 0)):
            col1, col2 = st.columns([1, 3])
            
            with col1:
                st.caption("Scene Info")
                edited_comment = st.text_input(
                    "Comment",
                    value=scene.get('comment', ''),
                    key=f"comment_{i}",
                    help="Internal comment about this scene"
                )
            
            with col2:
                st.caption("Voiceover Script")
                edited_speech = st.text_area(
                    "Speech",
                    value=scene.get('speech', ''),
                    key=f"speech_{i}",
                    height=100,
                    help="Edit the voiceover text"
                )
            
            edited_scenes.append({
                'comment': edited_comment,
                'speech': edited_speech
            })
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col1:
        if st.button("💾 Save Edits"):
            st.session_state.scenes = edited_scenes
            # Update ADK session state
            session = asyncio.run(get_session())
            session.state['scenes'] = edited_scenes
            asyncio.run(st.session_state.session_service.update_session(session))
            st.success("✅ Edits saved!")
    
    with col2:
        if st.button("🔄 Regenerate Script"):
            # User can regenerate if not satisfied
            if 'scenes' in st.session_state:
                del st.session_state.scenes
            st.rerun()
    
    with col3:
        st.session_state.voiceover_approved = st.checkbox(
            "✓ Approve",
            help="Check to approve and enable next step"
        )

# ============================================
# STEP 4: Add Audio Tags (ElevenLabs)
# ============================================
st.header("Step 4: Add Audio Tags")

if st.button(
    "🎨 Add ElevenLabs Audio Tags",
    disabled=not st.session_state.get('voiceover_approved', False)
):
    with st.spinner("Adding audio tags..."):
        # Create agent
        elevenlabs_agent = create_elevenlabs_agent()
        
        # Run agent (reads from session.state['scenes'])
        runner = InMemoryRunner(
            agent=elevenlabs_agent,
            app_name=st.session_state.app_name,
            session_service=st.session_state.session_service
        )
        
        for event in runner.run(
            user_id=st.session_state.user_id,
            session_id=st.session_state.session_id,
            new_message={"text": "Add audio tags to scenes"}
        ):
            if event.is_final_response():
                updated_session = asyncio.run(get_session())
                st.session_state.refined_scenes = updated_session.state.get('refined_scenes', [])
                st.success("✅ Audio tags added!")

# ============================================
# STEP 5: Review and Edit Refined Script
# ============================================
if 'refined_scenes' in st.session_state:
    st.header("Step 5: Review Final Script with Audio Tags")
    
    st.info("💡 Review the audio tags. Click 'Save Final Edits' before exporting.")
    
    edited_refined = []
    for i, scene in enumerate(st.session_state.refined_scenes):
        with st.expander(f"🎬 Scene {i+1}", expanded=(i == 0)):
            st.caption("Original Speech")
            st.text(scene.get('speech', ''))
            
            st.caption("With Audio Tags")
            edited_elevenlabs = st.text_area(
                "ElevenLabs Script",
                value=scene.get('elevenlabs', ''),
                key=f"elevenlabs_{i}",
                height=120,
                help="Edit audio tags and text"
            )
            
            edited_refined.append({
                'comment': scene.get('comment', ''),
                'speech': scene.get('speech', ''),
                'elevenlabs': edited_elevenlabs
            })
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("💾 Save Final Edits"):
            st.session_state.refined_scenes = edited_refined
            session = asyncio.run(get_session())
            session.state['refined_scenes'] = edited_refined
            asyncio.run(st.session_state.session_service.update_session(session))
            st.success("✅ Final edits saved!")
    
    with col2:
        st.session_state.final_approved = st.checkbox(
            "✓ Final Approval",
            help="Check to approve and enable export"
        )

# ============================================
# STEP 6: Export
# ============================================
if st.session_state.get('final_approved', False):
    st.header("Step 6: Export")
    
    if st.button("📥 Download JSON"):
        output = {
            'scenes': st.session_state.refined_scenes
        }
        st.download_button(
            label="Download refined_scenes.json",
            data=json.dumps(output, indent=2),
            file_name="refined_scenes.json",
            mime="application/json"
        )
    
    st.success("🎉 Pipeline complete! You can download the results above.")
```

### Implementation: `agents/voiceover_agent.py`

```python
from google.adk.agents import LlmAgent
from google.genai import types
from models.schemas import SceneList
from config.prompts import SYSTEM_PROMPTS
from agents.base_config import GEMINI_MODEL

def create_voiceover_agent():
    """Creates the PDF Voiceover Agent."""
    return LlmAgent(
        name="PDFVoiceoverAgent",
        model=GEMINI_MODEL,
        instruction=SYSTEM_PROMPTS['pdf-to-voiceover'],
        output_key="scenes",  # Saves to session.state['scenes']
        description="Generates voiceover scripts from PDF slide decks",
        generate_content_config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=SceneList
        )
    )
```

### Implementation: `agents/elevenlabs_agent.py`

```python
from google.adk.agents import LlmAgent
from google.genai import types
from models.schemas import RefinedSceneList
from config.prompts import SYSTEM_PROMPTS
from agents.base_config import GEMINI_MODEL

def create_elevenlabs_agent():
    """Creates the ElevenLabs Audio Tag Agent."""
    
    # Instruction uses {scenes} to inject from state
    instruction = f"""{SYSTEM_PROMPTS['elevenlabs']}

Process the following scenes:
{{scenes}}
"""
    
    return LlmAgent(
        name="ElevenLabsAgent",
        model=GEMINI_MODEL,
        instruction=instruction,
        output_key="refined_scenes",  # Saves to session.state['refined_scenes']
        description="Adds ElevenLabs audio tags to voiceover scripts",
        generate_content_config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=RefinedSceneList
        )
    )
```

## Key Benefits of This Approach

### 1. **Natural Streamlit Workflow**
- Each step is a clear button click
- Visual progression through the pipeline
- Users can see and edit at each stage

### 2. **Flexible Orchestration**
- Users can go back and regenerate
- Can skip steps if needed
- Can save drafts and come back later

### 3. **State Management**
- Streamlit `session_state` for UI state
- ADK `session.state` for agent data
- Both work together seamlessly

### 4. **Easy to Extend**
```python
# Add a new step easily:
if st.button("Translate to Spanish"):
    translation_agent = create_translation_agent()
    runner.run(...)
```

### 5. **Event Streaming**
```python
# Show progress in real-time
progress_bar = st.progress(0)
for i, event in enumerate(runner.run(...)):
    progress_bar.progress((i + 1) / total_steps)
    if event.is_tool_call():
        st.caption(f"Calling: {event.tool_name}")
```

## Comparison Table

| Feature | Streamlit Orchestration | Agent-Internal Tool |
|---------|------------------------|---------------------|
| **Implementation Complexity** | ⭐⭐ Simple | ⭐⭐⭐⭐⭐ Very Complex |
| **User Experience** | ⭐⭐⭐⭐⭐ Excellent | ⭐⭐⭐ Depends on external UI |
| **Editing Capability** | ⭐⭐⭐⭐⭐ Full control | ⭐⭐ Limited by tool design |
| **Visual Feedback** | ⭐⭐⭐⭐⭐ Built-in | ⭐⭐ Need separate UI |
| **Development Time** | ⭐⭐⭐⭐⭐ Fast | ⭐⭐ Slow (infrastructure) |
| **Flexibility** | ⭐⭐⭐⭐⭐ Very flexible | ⭐⭐⭐ Limited |
| **Infrastructure Required** | ⭐⭐⭐⭐⭐ Just Streamlit | ⭐⭐ Database, queues, etc. |
| **Suitable for Your Use Case** | ✅ YES | ❌ NO |

## Final Recommendation

**Use Streamlit UI Orchestration** because:

1. ✅ You already have/want a Streamlit UI
2. ✅ You want immediate visual feedback and editing
3. ✅ Your workflow is interactive, not background batch
4. ✅ Much simpler to implement and maintain
5. ✅ Better user experience
6. ✅ Each agent remains simple and focused
7. ✅ Easy to extend with new steps
8. ✅ Natural state management between steps

**Don't try to build human-in-the-loop into the agents** because:
- ❌ Requires complex infrastructure
- ❌ Harder to provide good UX
- ❌ Agents become tightly coupled to approval mechanism
- ❌ Less flexible for changes
- ❌ You'd still need a UI anyway to show/edit data

## Agent Definition Summary

With Streamlit orchestration, your agents are **simpler**:

```python
# voiceover_agent.py - Independent, reusable agent
voiceover_agent = LlmAgent(
    name="PDFVoiceoverAgent",
    instruction=SYSTEM_PROMPTS['pdf-to-voiceover'],
    output_key="scenes"
)

# elevenlabs_agent.py - Independent, reusable agent  
elevenlabs_agent = LlmAgent(
    name="ElevenLabsAgent",
    instruction=f"{SYSTEM_PROMPTS['elevenlabs']}\n\nProcess: {{scenes}}",
    output_key="refined_scenes"
)

# No SequentialAgent needed - Streamlit IS the orchestrator!
```

The mental model shift:
- ❌ OLD: "Agent system orchestrates everything end-to-end"
- ✅ NEW: "Streamlit orchestrates agents with human approval between each"

This is actually **more aligned with ADK principles** - each agent has a single, clear responsibility, and external orchestration (your UI) manages the workflow.

---

## Streamlit Best Practices for This Architecture

Based on Streamlit documentation, here are specific best practices to apply:

### 1. Cache Agent Initialization with `@st.cache_resource`

Agents, session services, and Gemini clients are **global resources** that should be cached:

```python
import streamlit as st
from google.adk.agents import LlmAgent
from google.adk.sessions import InMemorySessionService
from google import genai

# ✅ CORRECT: Cache expensive agent initialization
@st.cache_resource
def get_session_service():
    """Initialize and cache the session service (singleton)."""
    return InMemorySessionService()

@st.cache_resource
def get_gemini_client():
    """Initialize and cache the Gemini client (singleton)."""
    return genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

@st.cache_resource
def create_voiceover_agent():
    """Create and cache the voiceover agent (singleton)."""
    return LlmAgent(
        name="PDFVoiceoverAgent",
        model="gemini-2.5-flash",
        instruction=SYSTEM_PROMPTS['pdf-to-voiceover'],
        output_key="scenes",
        generate_content_config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=SceneList
        )
    )

@st.cache_resource
def create_elevenlabs_agent():
    """Create and cache the ElevenLabs agent (singleton)."""
    return LlmAgent(
        name="ElevenLabsAgent",
        model="gemini-2.5-flash",
        instruction=f"{SYSTEM_PROMPTS['elevenlabs']}\n\nProcess: {{scenes}}",
        output_key="refined_scenes",
        generate_content_config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=RefinedSceneList
        )
    )

# In your app
session_service = get_session_service()
voiceover_agent = create_voiceover_agent()
elevenlabs_agent = create_elevenlabs_agent()
```

**Why `@st.cache_resource` and not `@st.cache_data`?**
- Use `@st.cache_resource` for **unserializable objects** like agents, database connections, ML models
- Returns the **same object** across all users and reruns (singleton pattern)
- Use `@st.cache_data` for **data** (DataFrames, lists, dicts) that should be copied per use

**Benefits**:
- ✅ Agents created once, reused across all sessions
- ✅ Faster app initialization
- ✅ Lower memory usage
- ✅ No repeated API client setup

### 2. Session State Initialization Pattern

Always initialize session state keys before using them:

```python
# ✅ CORRECT: Initialize session state safely
def initialize_session_state():
    """Initialize all session state keys with defaults."""
    if 'session_service' not in st.session_state:
        st.session_state.session_service = get_session_service()
    
    if 'app_name' not in st.session_state:
        st.session_state.app_name = "voiceover_pipeline"
    
    if 'user_id' not in st.session_state:
        st.session_state.user_id = f"user_{uuid.uuid4().hex[:8]}"
    
    if 'session_id' not in st.session_state:
        st.session_state.session_id = f"session_{uuid.uuid4().hex[:8]}"
    
    if 'current_step' not in st.session_state:
        st.session_state.current_step = 'upload'
    
    # ADK session state is separate from Streamlit session state
    if 'adk_session' not in st.session_state:
        st.session_state.adk_session = None

# Call at the start of your app
initialize_session_state()
```

### 3. Use Callbacks with Buttons for State Updates

Instead of checking button return values, use callbacks:

```python
# ❌ AVOID: Button state checking can be unreliable
if st.button("Generate Voiceover"):
    st.session_state.current_step = 'generating'
    # Run agent...

# ✅ CORRECT: Use callbacks for state changes
def start_generation():
    """Callback to start voiceover generation."""
    st.session_state.current_step = 'generating'

st.button("Generate Voiceover", on_click=start_generation)

# Check state separately
if st.session_state.current_step == 'generating':
    # Run agent...
```

**Why callbacks?**
- Callbacks execute **before** the script reruns
- State changes are available immediately in the same rerun
- Cleaner separation of concerns

### 4. Workflow State Machine Pattern

For multi-step processes, use a state machine:

```python
# Define workflow states
WORKFLOW_STATES = {
    'upload': {'next': 'generate_voiceover', 'display': '📤 Upload PDF'},
    'generate_voiceover': {'next': 'review_voiceover', 'display': '🎬 Generate Script'},
    'review_voiceover': {'next': 'add_audio_tags', 'display': '✏️ Review Script'},
    'add_audio_tags': {'next': 'review_final', 'display': '🎨 Add Audio Tags'},
    'review_final': {'next': 'export', 'display': '👀 Final Review'},
    'export': {'next': None, 'display': '📥 Export'}
}

def advance_workflow():
    """Move to next step in workflow."""
    current = st.session_state.workflow_state
    next_state = WORKFLOW_STATES[current]['next']
    if next_state:
        st.session_state.workflow_state = next_state

def reset_workflow():
    """Reset to beginning."""
    st.session_state.workflow_state = 'upload'

# Initialize
if 'workflow_state' not in st.session_state:
    st.session_state.workflow_state = 'upload'

# Display progress
current_step = st.session_state.workflow_state
st.progress(list(WORKFLOW_STATES.keys()).index(current_step) / len(WORKFLOW_STATES))
st.caption(f"Current: {WORKFLOW_STATES[current_step]['display']}")

# Conditional rendering based on state
if st.session_state.workflow_state == 'upload':
    # Show upload UI
    pass
elif st.session_state.workflow_state == 'generate_voiceover':
    # Show generation UI
    pass
# ... etc
```

### 5. Use `st.status` for Long-Running Agent Operations

Provide visual feedback during agent execution:

```python
import asyncio

def run_agent_with_status(agent, runner, message):
    """Run an agent with visual status updates."""
    with st.status(f"Running {agent.name}...", expanded=True) as status:
        st.write("🔄 Initializing...")
        
        # Get ADK session
        session = asyncio.run(get_adk_session())
        
        st.write("🤖 Calling agent...")
        result_events = []
        
        # Stream events
        for i, event in enumerate(runner.run(
            user_id=st.session_state.user_id,
            session_id=st.session_state.session_id,
            new_message=message
        )):
            if event.is_tool_call():
                st.write(f"🔧 Using tool: {event.tool_name}")
            elif event.is_final_response():
                st.write("✅ Generation complete!")
                result_events.append(event)
        
        status.update(label=f"✅ {agent.name} completed!", state="complete")
        return result_events

# Usage
if st.button("Generate Voiceover"):
    events = run_agent_with_status(
        voiceover_agent,
        runner,
        Content(parts=[Part(text="Generate voiceover from PDF")])
    )
```

### 6. Use `st.expander` for Scene Reviews

Organize scene editing with expanders:

```python
# ✅ CORRECT: Use expanders for better organization
st.subheader(f"📝 Review {len(st.session_state.scenes)} Scenes")

for i, scene in enumerate(st.session_state.scenes):
    # Expand first scene by default
    with st.expander(
        f"🎬 Scene {i+1}: {scene['comment'][:50]}...",
        expanded=(i == 0)
    ):
        # Use columns for better layout
        col1, col2 = st.columns([1, 3])
        
        with col1:
            st.caption("**Scene Info**")
            edited_comment = st.text_input(
                "Comment",
                value=scene['comment'],
                key=f"comment_{i}",
                label_visibility="collapsed",
                help="Brief description of this scene"
            )
        
        with col2:
            st.caption("**Voiceover Text**")
            edited_speech = st.text_area(
                "Speech",
                value=scene['speech'],
                key=f"speech_{i}",
                height=100,
                label_visibility="collapsed",
                help="Edit the voiceover script"
            )
        
        # Show character count
        st.caption(f"📏 {len(edited_speech)} characters")
        
        # Save edited scene
        st.session_state.scenes[i] = {
            'comment': edited_comment,
            'speech': edited_speech
        }
```

### 7. Disable Buttons During Processing

Prevent double-clicking during async operations:

```python
# Track processing state
if 'is_processing' not in st.session_state:
    st.session_state.is_processing = False

def start_processing():
    st.session_state.is_processing = True

def finish_processing():
    st.session_state.is_processing = False

# Disable button during processing
st.button(
    "🎬 Generate Voiceover",
    on_click=start_processing,
    disabled=st.session_state.is_processing or 'pdf_base64' not in st.session_state,
    help="Upload a PDF first" if 'pdf_base64' not in st.session_state else None
)

if st.session_state.is_processing:
    # Run agent
    with st.spinner("Generating..."):
        # ... agent execution ...
        finish_processing()
        st.rerun()
```

### 8. Cache Data Processing with `@st.cache_data`

Cache processed PDF data:

```python
@st.cache_data
def process_pdf(pdf_bytes):
    """Process and cache PDF data."""
    pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
    # Extract metadata or preview if needed
    return {
        'base64': pdf_base64,
        'size': len(pdf_bytes),
        'timestamp': time.time()
    }

# Usage
uploaded_file = st.file_uploader("Upload PDF", type=['pdf'])
if uploaded_file:
    pdf_data = process_pdf(uploaded_file.read())
    st.session_state.pdf_base64 = pdf_data['base64']
    st.success(f"✅ Uploaded: {uploaded_file.name} ({pdf_data['size']:,} bytes)")
```

### 9. Use Columns for Action Buttons

Organize buttons horizontally:

```python
# ✅ CORRECT: Use columns for button layout
col1, col2, col3, col4 = st.columns([2, 2, 2, 1])

with col1:
    if st.button("💾 Save Edits", use_container_width=True):
        # Save logic
        pass

with col2:
    if st.button("🔄 Regenerate", use_container_width=True):
        # Regenerate logic
        pass

with col3:
    if st.button("⏭️ Skip to Next", use_container_width=True):
        advance_workflow()

with col4:
    if st.button("❌", key="cancel", help="Cancel and reset"):
        reset_workflow()
```

### 10. Display Real-Time Progress with Event Streaming

Show progress as agent generates:

```python
def stream_agent_events(agent, runner, user_id, session_id, message):
    """Stream agent events with real-time updates."""
    progress_bar = st.progress(0, text="Starting...")
    status_text = st.empty()
    
    events = list(runner.run(user_id, session_id, message))
    total_events = len(events)
    
    for i, event in enumerate(events):
        progress = (i + 1) / total_events
        progress_bar.progress(progress)
        
        if event.is_tool_call():
            status_text.text(f"🔧 Calling tool: {event.tool_name}")
        elif event.content:
            status_text.text(f"💬 Generating response...")
        
        # Small delay for visual feedback
        time.sleep(0.1)
    
    progress_bar.progress(1.0, text="✅ Complete!")
    status_text.text(f"✅ Generated {total_events} events")
    
    return events
```

### 11. Clear Cache When Needed

Provide option to clear cached resources:

```python
# Add to sidebar for developer options
with st.sidebar:
    with st.expander("🔧 Developer Options"):
        if st.button("Clear Agent Cache"):
            st.cache_resource.clear()
            st.success("Agent cache cleared!")
            st.rerun()
        
        if st.button("Clear Data Cache"):
            st.cache_data.clear()
            st.success("Data cache cleared!")
            st.rerun()
        
        if st.button("Reset Session"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.success("Session reset!")
            st.rerun()
```

### 12. Error Handling with User Feedback

Provide clear error messages and recovery options:

```python
try:
    with st.spinner("Generating voiceover..."):
        session = asyncio.run(get_or_create_adk_session())
        runner = InMemoryRunner(
            agent=voiceover_agent,
            app_name=st.session_state.app_name,
            session_service=get_session_service()
        )
        
        # Run agent
        for event in runner.run(...):
            if event.is_final_response():
                st.session_state.scenes = session.state.get('scenes', [])
                st.success(f"✅ Generated {len(st.session_state.scenes)} scenes!")
                
except Exception as e:
    st.error(f"❌ Error generating voiceover: {str(e)}")
    
    # Show expandable details for debugging
    with st.expander("🔍 Error Details"):
        st.code(traceback.format_exc())
    
    # Offer recovery options
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 Retry"):
            st.rerun()
    with col2:
        if st.button("↩️ Go Back"):
            st.session_state.workflow_state = 'upload'
            st.rerun()
```

## Complete Streamlit Best Practices Summary

| Practice | Why | Decorator/Pattern |
|----------|-----|-------------------|
| **Cache agents** | Expensive to create, reuse across sessions | `@st.cache_resource` |
| **Cache data processing** | Avoid reprocessing same inputs | `@st.cache_data` |
| **Initialize session state** | Prevent KeyErrors | `if key not in st.session_state` |
| **Use button callbacks** | State updates before rerun | `on_click=callback` |
| **State machine pattern** | Clear workflow progression | `workflow_state` variable |
| **Status indicators** | User feedback during processing | `st.status()`, `st.progress()` |
| **Expanders** | Organize many items | `st.expander()` |
| **Disable during processing** | Prevent double-clicks | `disabled=is_processing` |
| **Column layouts** | Better button organization | `st.columns()` |
| **Error handling** | Graceful failures | `try/except` with `st.error()` |
| **Event streaming** | Show real-time progress | Loop through `runner.run()` |
| **Clear cache option** | Development & debugging | `st.cache_resource.clear()` |

These practices ensure your Streamlit app is **performant, user-friendly, and maintainable** while working seamlessly with ADK agents.
