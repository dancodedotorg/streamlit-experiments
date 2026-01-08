# 🎙️ Voiceover Pipeline - Human-in-the-Loop Agent Application

A Streamlit application that uses Google Gemini ADK agents to generate and refine educational voiceover scripts from PDF slides, with human review and editing at each step.

## 📋 Overview

This application demonstrates a human-in-the-loop workflow using ADK agents:

1. **Upload PDF** - Upload educational slides
2. **Generate Voiceover** - AI generates voiceover scripts for each slide
3. **Review & Edit** - Review and manually edit the generated scripts
4. **Add Audio Tags** - AI adds ElevenLabs audio tags for expressive speech
5. **Final Review** - Review and edit the enhanced scripts
6. **Export** - Download results as JSON or text

### Architecture

```
Streamlit App (UI Orchestrator)
  ├─ PDFVoiceoverAgent (Custom ADK Agent)
  │   └─ Analyzes PDF slides → generates voiceover scripts
  └─ ElevenLabsAgent (Custom ADK Agent)
      └─ Enhances scripts → adds audio tags
```

**Key Design Decision:** The Streamlit UI orchestrates independent agents with human review between each step, rather than using a SequentialAgent. This provides:
- Natural workflow with button clicks
- Full editing control at each stage
- Visual progress indicators
- Flexible workflow (can regenerate, go back, etc.)

## 🏗️ Project Structure

```
voiceover-pipeline/
├── agents/
│   ├── __init__.py              # Package initialization
│   ├── config.py                # System prompts and configuration
│   ├── models.py                # Pydantic models for structured output
│   ├── voiceover_agent.py       # PDF → Voiceover agent
│   └── elevenlabs_agent.py      # Voiceover → Audio tags agent
├── .streamlit/
│   └── secrets.toml.template    # API key configuration template
├── voiceover_app.py             # Main Streamlit application
├── requirements.txt             # Python dependencies
└── README_VOICEOVER_APP.md      # This file
```

## 🚀 Setup Instructions

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure API Key

Create `.streamlit/secrets.toml` from the template:

```bash
cp .streamlit/secrets.toml.template .streamlit/secrets.toml
```

Edit `.streamlit/secrets.toml` and add your Gemini API key:

```toml
GEMINI_API_KEY = "your-actual-api-key-here"
```

Get your API key from: https://aistudio.google.com/app/apikey

### 3. Run the Application

```bash
streamlit run voiceover_app.py
```

The app will open in your browser at `http://localhost:8501`

## 🎯 Usage Guide

### Step-by-Step Workflow

1. **Upload PDF**
   - Click "Choose a PDF file"
   - Select a PDF containing educational slides
   - Click "Next" to continue

2. **Generate Voiceover Script**
   - Click "Generate Voiceover Script"
   - Wait for AI to analyze slides and generate scripts
   - Review the generated scenes

3. **Review & Edit Scripts**
   - Each scene is displayed in an expandable section
   - Edit the comment (scene description)
   - Edit the speech (voiceover text)
   - Click "Save Edits" to save changes
   - Check "Approve & Continue" when ready

4. **Add Audio Tags**
   - Click "Add ElevenLabs Audio Tags"
   - AI enhances scripts with expressive audio tags
   - Review the enhanced versions

5. **Final Review**
   - Compare original vs. tagged versions
   - Edit audio tags if needed
   - Click "Save Final Edits"
   - Check "Final Approval" when ready

6. **Export**
   - Download JSON (full data with metadata)
   - Download TXT (script text only)
   - Preview all scenes
   - Start a new project if desired

## 🎨 Streamlit Best Practices Used

### Caching
- **`@st.cache_resource`** - Agents and clients (singletons)
- **`@st.cache_data`** - PDF processing (data caching)

### Session State
- Proper initialization with defaults
- Workflow state machine
- ADK session management

### UI/UX
- Progress indicators in sidebar
- Status messages during processing
- Expandable sections for scenes
- Button callbacks for state updates
- Disabled buttons during processing
- Error handling with recovery options

### Performance
- Agents created once and reused
- PDF processed and cached
- No unnecessary reruns

## 🔧 Code Highlights

### Agent Implementation

Both agents are **custom ADK agents** (inherit from `BaseAgent`):

```python
class PDFVoiceoverAgent(BaseAgent):
    async def _run_async_impl(self, ctx: InvocationContext):
        # Get PDF from session state
        pdf_base64 = ctx.session.state.get('pdf_base64')
        
        # Process with Gemini
        response = self.gemini_client.models.generate_content(...)
        
        # Save to session state
        ctx.session.state['scenes'] = scenes
        
        # Yield event
        yield Event(...)
```

### Streamlit Orchestration

```python
# Step 1: User uploads PDF
uploaded_file = st.file_uploader(...)

# Step 2: Run first agent
runner = InMemoryRunner(agent=voiceover_agent, ...)
events = list(runner.run(...))

# Step 3: Human reviews and edits
for scene in scenes:
    edited_speech = st.text_area(...)

# Step 4: Run second agent with edited data
session.state['scenes'] = edited_scenes
runner = InMemoryRunner(agent=elevenlabs_agent, ...)
```

## 📊 Features

### Agent Features
- ✅ Structured output with Pydantic models
- ✅ Session state management
- ✅ Error handling
- ✅ Event streaming

### UI Features
- ✅ Multi-step workflow with progress tracking
- ✅ Human review and editing at each stage
- ✅ Visual feedback during processing
- ✅ Expandable scene editors
- ✅ Character counts
- ✅ Export in multiple formats
- ✅ Developer options (cache clearing, session reset)

## 🐛 Troubleshooting

### API Key Not Found
**Error:** "GEMINI_API_KEY not found in secrets"

**Solution:** Create `.streamlit/secrets.toml` with your API key

### Import Errors
**Error:** "No module named 'google.adk'"

**Solution:** Install dependencies:
```bash
pip install -r requirements.txt
```

### No Scenes Generated
**Issue:** Agent runs but no scenes appear

**Solution:** 
1. Check PDF is valid and contains slides
2. Check browser console for errors
3. Use "Developer Options" → "Reset All Session State"

## 📚 Related Documentation

- **ADK Documentation**: [google.github.io/adk-docs](https://google.github.io/adk-docs)
- **Gemini API**: [ai.google.dev/gemini-api](https://ai.google.dev/gemini-api)
- **Streamlit Docs**: [docs.streamlit.io](https://docs.streamlit.io)
- **ElevenLabs Voice**: [elevenlabs.io/docs](https://elevenlabs.io/docs)

## 🎓 Learning Points

### ADK Concepts Demonstrated
1. **Custom Agents** - Inheriting from `BaseAgent`
2. **Session State** - Passing data between agents
3. **Event System** - Yielding events with state deltas
4. **Structured Output** - Using Pydantic schemas
5. **InMemoryRunner** - Running agents independently

### Human-in-the-Loop Pattern
- UI orchestrates agents (not SequentialAgent)
- Each agent is independent and reusable
- State management via ADK sessions + Streamlit session_state
- Natural workflow with button clicks and editing

## 🔮 Future Enhancements

Potential additions:
- [ ] Audio preview with TTS
- [ ] Batch PDF processing
- [ ] Custom prompt editing
- [ ] Export to video timeline formats
- [ ] Translation agent for multiple languages
- [ ] Quality scoring agent
- [ ] Collaborative editing (multi-user)

## 📄 License

This is example code for educational purposes demonstrating ADK and Streamlit integration.

## 🤝 Contributing

This application was created to demonstrate best practices for:
- Building multi-agent systems with Google Gemini ADK
- Creating human-in-the-loop workflows with Streamlit
- Orchestrating agents through UI rather than agent systems
- Managing state between agents and UI

Feel free to adapt this pattern for your own applications!
