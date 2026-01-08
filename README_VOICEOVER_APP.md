# 🎙️ Voiceover Pipeline - Human-in-the-Loop Agent Application

A Streamlit application that uses Google Gemini ADK agents to generate and refine educational voiceover scripts from PDF slides, with human review and editing at each step.

> **Note:** This application uses ADK-compliant agents that also work with `adk web`. See [README_ADK_COMPATIBILITY.md](README_ADK_COMPATIBILITY.md) for details on the dual-mode architecture.

## 📋 Overview

This application demonstrates a human-in-the-loop workflow using ADK agents:

1. **Import Slides** - Import from Google Slides or upload PDF
2. **Generate Voiceover** - AI generates voiceover scripts for each slide
3. **Review & Edit** - Review and manually edit the generated scripts
4. **Add Audio Tags** - AI adds ElevenLabs audio tags for expressive speech
5. **Final Review** - Review and edit the enhanced scripts
6. **Export** - Download results as JSON or text

### Architecture

```
Streamlit App (UI Orchestrator)
  ├─ PDFVoiceoverAgent (ADK-compliant Custom Agent)
  │   └─ Analyzes PDF slides → generates voiceover scripts
  └─ ElevenLabsAgent (ADK-compliant Custom Agent)
      └─ Enhances scripts → adds audio tags
```

**Key Design Decision:** The Streamlit UI orchestrates independent ADK agents with human review between each step. The agents follow Google ADK best practices and are also compatible with `adk web` for debugging.

## 🏗️ Project Structure

```
streamlit-experiments/
├── voiceover_agent/             # Voiceover agent (ADK-compliant)
│   ├── __init__.py              # Package initialization
│   ├── agent.py                 # Agent class + factory function
│   └── .env                     # API key for adk web
├── elevenlabs_agent/            # ElevenLabs agent (ADK-compliant)
│   ├── __init__.py              # Package initialization
│   ├── agent.py                 # Agent class + factory function
│   └── .env                     # API key for adk web
├── .streamlit/
│   └── secrets.toml.template    # API key configuration template
├── voiceover_app.py             # Main Streamlit application
├── slides.py                    # Google Slides integration
├── requirements.txt             # Python dependencies
├── README_VOICEOVER_APP.md      # This file (Streamlit guide)
├── README_ADK_COMPATIBILITY.md  # ADK compatibility details
└── ADK_QUICKSTART.md            # Quick start for adk web
```

## 🚀 Setup Instructions

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure API Keys

#### For Streamlit

Create `.streamlit/secrets.toml` from the template:

```bash
cp .streamlit/secrets.toml.template .streamlit/secrets.toml
```

Edit `.streamlit/secrets.toml` and add your Gemini API key:

```toml
GEMINI_API_KEY = "your-actual-api-key-here"
```

Get your API key from: https://aistudio.google.com/app/apikey

#### For ADK Web (Optional)

If you also want to test agents with `adk web`, edit the `.env` files:

```bash
# voiceover_agent/.env
GOOGLE_API_KEY=your_actual_api_key_here

# elevenlabs_agent/.env
GOOGLE_API_KEY=your_actual_api_key_here
```

### 3. Run the Application

```bash
streamlit run voiceover_app.py
```

The app will open in your browser at `http://localhost:8501`

## 🎯 Usage Guide

### Step-by-Step Workflow

1. **Import Slides (Optional)**
   - Authenticate with Google
   - Enter Google Slides Presentation ID
   - Load and edit speaker notes
   - Generate PDF from slides
   - Or skip to upload your own PDF

2. **Upload PDF**
   - Upload a PDF containing educational slides
   - Preview the uploaded PDF
   - Click "Next" to continue

3. **Generate Voiceover Script**
   - Click "Generate Voiceover Script"
   - Wait for AI to analyze slides and generate scripts
   - Review the generated scenes

4. **Review & Edit Scripts**
   - Each scene is displayed in an expandable section
   - Edit the comment (scene description)
   - Edit the speech (voiceover text)
   - Click "Save Edits" to save changes
   - Check "Approve & Continue" when ready

5. **Add Audio Tags**
   - Click "Add ElevenLabs Audio Tags"
   - AI enhances scripts with expressive audio tags
   - Review the enhanced versions

6. **Final Review**
   - Compare original vs. tagged versions
   - Edit audio tags if needed
   - Click "Save Final Edits"
   - Check "Final Approval" when ready

7. **Export**
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

### ADK-Compliant Agent Structure

Each agent follows ADK best practices with both a class definition and factory function:

```python
# voiceover_agent/agent.py

class PDFVoiceoverAgent(BaseAgent):
    def __init__(self, gemini_client, name="PDFVoiceoverAgent"):
        super().__init__(name=name, description="...")
        self._gemini_client = gemini_client
    
    async def _run_async_impl(self, ctx: InvocationContext):
        # Get PDF from session state
        pdf_base64 = ctx.session.state.get('pdf_base64')
        
        # Process with Gemini
        response = self._gemini_client.models.generate_content(...)
        
        # Save to session state
        ctx.session.state['scenes'] = scenes
        
        # Yield event
        yield Event(...)

# Factory function for Streamlit
def create_voiceover_agent(gemini_client):
    return PDFVoiceoverAgent(gemini_client=gemini_client)

# Root agent for adk web
root_agent = PDFVoiceoverAgent(gemini_client=client, name="voiceover_agent")
```

### Streamlit Integration

```python
# voiceover_app.py
from voiceover_agent.agent import create_voiceover_agent
from elevenlabs_agent.agent import create_elevenlabs_agent

# Initialize client with Streamlit secrets
gemini_client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

# Create agents using factory functions
voiceover_agent = create_voiceover_agent(gemini_client)
elevenlabs_agent = create_elevenlabs_agent(gemini_client)

# Use agents in workflow
runner = Runner(agent=voiceover_agent, ...)
events = list(runner.run(...))
```

## 📊 Features

### Agent Features
- ✅ ADK-compliant structure (works with `adk web`)
- ✅ Structured output with Pydantic models
- ✅ Session state management
- ✅ Error handling
- ✅ Event streaming
- ✅ Factory functions for programmatic use

### UI Features
- ✅ Google Slides import and editing
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
**Error:** "No module named 'voiceover_agent'"

**Solution:** Make sure you're in the project directory and virtual environment is activated:
```bash
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
```

### No Scenes Generated
**Issue:** Agent runs but no scenes appear

**Solution:** 
1. Check PDF is valid and contains slides
2. Check browser console for errors
3. Use "Developer Options" → "Reset All Session State"

## 🔬 Testing with ADK Web

You can also test the agents independently using `adk web`:

```bash
# Configure .env files with API keys first
adk web

# Open http://localhost:8000
# Select voiceover_agent or elevenlabs_agent
```

See [ADK_QUICKSTART.md](ADK_QUICKSTART.md) for details.

## 📚 Related Documentation

- **[README_ADK_COMPATIBILITY.md](README_ADK_COMPATIBILITY.md)** - How agents work in both Streamlit and ADK Web
- **[ADK_QUICKSTART.md](ADK_QUICKSTART.md)** - Using agents with `adk web`
- **[Google ADK Docs](https://adk.google.dev/)** - Official ADK documentation
- **[Gemini API](https://ai.google.dev/gemini-api)** - Gemini API reference
- **[Streamlit Docs](https://docs.streamlit.io)** - Streamlit documentation
- **[ElevenLabs Voice](https://elevenlabs.io/docs)** - ElevenLabs voice synthesis

## 🎓 Learning Points

### ADK Concepts Demonstrated
1. **Custom Agents** - Inheriting from `BaseAgent`
2. **ADK Compliance** - Following Google's recommended structure
3. **Dual-Mode Design** - Same agents work in multiple environments
4. **Session State** - Passing data between agents
5. **Event System** - Yielding events with state deltas
6. **Structured Output** - Using Pydantic schemas
7. **Factory Pattern** - Providing flexible initialization

### Human-in-the-Loop Pattern
- UI orchestrates agents (not SequentialAgent)
- Each agent is independent and reusable
- State management via ADK sessions + Streamlit session_state
- Natural workflow with button clicks and editing
- Single source of truth for agent logic

## 🔮 Future Enhancements

Potential additions:
- [ ] Audio preview with TTS
- [ ] Batch PDF processing
- [ ] Custom prompt editing in UI
- [ ] Export to video timeline formats
- [ ] Translation agent for multiple languages
- [ ] Quality scoring agent
- [ ] Collaborative editing (multi-user)
- [ ] Voice selection for ElevenLabs

## 📄 License

This is example code for educational purposes demonstrating ADK and Streamlit integration.

## 🤝 Contributing

This application demonstrates best practices for:
- Building ADK-compliant agents that work in multiple environments
- Creating human-in-the-loop workflows with Streamlit
- Orchestrating agents through UI rather than agent systems
- Managing state between agents and UI
- Following Google ADK conventions

Feel free to adapt this pattern for your own applications!
