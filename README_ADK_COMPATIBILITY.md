# ADK Web Compatibility Guide

This document explains how the voiceover agents work with both **Streamlit** and **Google ADK Web** using a single source of truth.

## Overview

The agents in this project follow Google ADK best practices and are structured to work seamlessly in two environments:

1. **Google ADK Web Interface** (`adk web` command) - The primary design target for agent development and debugging
2. **Streamlit Application** ([`voiceover_app.py`](voiceover_app.py)) - A production-ready web UI with human-in-the-loop workflow

## Single Source of Truth

**Key Design Principle:** There is only ONE implementation of each agent, following ADK conventions. The same agent code works in both environments through different initialization patterns.

## Directory Structure

```
streamlit-experiments/
├── voiceover_agent/                 # Voiceover agent (single source)
│   ├── __init__.py                  # Package imports  
│   ├── agent.py                     # Agent implementation + factory function
│   └── .env                         # API key for adk web
│
├── elevenlabs_agent/                # ElevenLabs agent (single source)
│   ├── __init__.py                  # Package imports
│   ├── agent.py                     # Agent implementation + factory function
│   └── .env                         # API key for adk web
│
├── voiceover_app.py                 # Streamlit application
├── ADK_QUICKSTART.md                # Quick start for adk web
└── README_VOICEOVER_APP.md          # Streamlit usage guide
```

## How It Works

Each agent file ([`agent.py`](voiceover_agent/agent.py)) contains:

### 1. Agent Class Definition (Shared)
```python
class PDFVoiceoverAgent(BaseAgent):
    def __init__(self, gemini_client, name="PDFVoiceoverAgent"):
        super().__init__(name=name, description="...")
        self._gemini_client = gemini_client
    
    async def _run_async_impl(self, ctx: InvocationContext):
        # Core agent logic (same for both environments)
        ...
```

### 2. Factory Function (For Streamlit)
```python
def create_voiceover_agent(gemini_client):
    """Factory function for Streamlit or external use."""
    return PDFVoiceoverAgent(gemini_client=gemini_client)
```

### 3. Root Agent (For ADK Web)
```python
# Initialize client from environment
api_key = os.environ.get("GOOGLE_API_KEY")
client = genai.Client(api_key=api_key) if api_key else None

# Create root_agent that adk web discovers
root_agent = PDFVoiceoverAgent(gemini_client=client, name="voiceover_agent")
```

## Usage

### For Streamlit (Production)

The Streamlit app imports the factory functions and passes its own initialized client:

```python
# voiceover_app.py
from voiceover_agent.agent import create_voiceover_agent
from elevenlabs_agent.agent import create_elevenlabs_agent

# Initialize client with Streamlit secrets
gemini_client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

# Create agents using factory functions
voiceover_agent = create_voiceover_agent(gemini_client)
elevenlabs_agent = create_elevenlabs_agent(gemini_client)
```

**Run:**
```bash
streamlit run voiceover_app.py
```

### For ADK Web (Development/Debugging)

ADK Web discovers agents by looking for `root_agent` in each directory's `agent.py`:

1. **Configure API Keys** - Edit `.env` files:
   ```bash
   # voiceover_agent/.env
   GOOGLE_API_KEY=your_actual_api_key_here
   
   # elevenlabs_agent/.env
   GOOGLE_API_KEY=your_actual_api_key_here
   ```

2. **Run ADK Web:**
   ```bash
   adk web
   # or on Windows: adk web --no-reload
   ```

3. **Access UI:** Open `http://localhost:8000`

4. **Select Agent:** Choose from dropdown:
   - `voiceover_agent`
   - `elevenlabs_agent`

## Agent Capabilities

### Voiceover Agent

**Purpose:** Analyzes PDF slides and generates educational voiceover scripts

**Input:** PDF file (in session state as `pdf_base64`)

**Output:** Array of scenes with voiceover scripts (saved to `state['scenes']`)

**Scene Format:**
```json
{
  "scenes": [
    {
      "comment": "Description of the scene",
      "speech": "The voiceover text for this slide"
    }
  ]
}
```

### ElevenLabs Agent

**Purpose:** Enhances voiceover scripts with ElevenLabs audio tags for expressive speech

**Input:** Scenes array (from session state `scenes`)

**Output:** Refined scenes with audio tags (saved to `state['refined_scenes']`)

**Refined Scene Format:**
```json
{
  "scenes": [
    {
      "comment": "Description of the scene",
      "speech": "The original voiceover text",
      "elevenlabs": "[warmly] The voiceover text with audio tags!"
    }
  ]
}
```

## Best Practices

### Development Workflow

1. ✅ **Design agents following ADK conventions** - Use ADK directory structure with `root_agent`
2. ✅ **Test with `adk web` first** - Verify agent logic in the ADK debugging environment
3. ✅ **Add factory function** - Export a creation function for external use (Streamlit)
4. ✅ **Integrate with Streamlit** - Use factory function to create agents in your app
5. ✅ **Keep logic identical** - The core `_run_async_impl` should be the same in both contexts

### File Organization

```python
# agent.py structure:

# 1. Imports
from google.adk.agents import BaseAgent
...

# 2. Pydantic Models (if needed)
class Scene(BaseModel):
    ...

# 3. Configuration Constants
GEMINI_MODEL = "gemini-2.5-flash"
SYSTEM_PROMPT = """..."""

# 4. Agent Class
class MyAgent(BaseAgent):
    ...

# 5. Factory Function (for external use)
def create_my_agent(gemini_client):
    return MyAgent(gemini_client=gemini_client)

# 6. Root Agent (for adk web)
api_key = os.environ.get("GOOGLE_API_KEY")
client = genai.Client(api_key=api_key) if api_key else None
root_agent = MyAgent(gemini_client=client) if client else PlaceholderAgent()
```

### Configuration Management

**For ADK Web:**
- Use `.env` files in agent directories
- Set `GOOGLE_API_KEY` environment variable
- Agents initialize their own clients

**For Streamlit:**
- Use `.streamlit/secrets.toml` for API keys
- Initialize client in Streamlit app
- Pass client to factory functions

## Troubleshooting

### ADK Web Issues

**Problem:** Agent not showing in dropdown

**Solution:** 
- Ensure you're running `adk web` from the parent directory
- Check that [`__init__.py`](voiceover_agent/__init__.py) exists: `from . import agent`
- Verify [`agent.py`](voiceover_agent/agent.py) defines `root_agent` variable

**Problem:** API key not found

**Solution:**
- Edit `.env` file in agent directory
- Set `GOOGLE_API_KEY=your_key_here`
- Restart `adk web`

**Problem:** `_make_subprocess_transport NotImplementedError` on Windows

**Solution:**
- Use `adk web --no-reload` instead

### Streamlit Issues

**Problem:** Import errors

**Solution:**
- Activate virtual environment: `.venv\Scripts\activate`
- Install dependencies: `pip install -r requirements.txt`

**Problem:** Agent not initialized

**Solution:**
- Check `GEMINI_API_KEY` in `.streamlit/secrets.toml`
- Verify client is passed to factory function

## Migration Guide

### Adding a New Agent

To add a new agent compatible with both environments:

1. **Create agent directory:**
   ```
   my_agent/
   ├── __init__.py          # from . import agent
   ├── agent.py             # Implementation
   └── .env                 # GOOGLE_API_KEY=...
   ```

2. **Implement agent following the pattern:**
   ```python
   # my_agent/agent.py
   
   class MyAgent(BaseAgent):
       def __init__(self, gemini_client, name="MyAgent"):
           super().__init__(name=name, description="...")
           self._gemini_client = gemini_client
       
       async def _run_async_impl(self, ctx):
           # Implementation
           pass
   
   # Factory for Streamlit
   def create_my_agent(gemini_client):
       return MyAgent(gemini_client=gemini_client)
   
   # Root agent for ADK Web
   api_key = os.environ.get("GOOGLE_API_KEY")
   client = genai.Client(api_key=api_key) if api_key else None
   root_agent = MyAgent(gemini_client=client, name="my_agent") if client else ...
   ```

3. **Test in ADK Web:**
   ```bash
   adk web
   # Select my_agent from dropdown
   ```

4. **Integrate with Streamlit:**
   ```python
   from my_agent.agent import create_my_agent
   
   my_agent = create_my_agent(gemini_client)
   ```

## Benefits of This Approach

✅ **Single Source of Truth** - One agent implementation, not two
✅ **ADK Best Practices** - Follows Google's recommended structure
✅ **Easy Debugging** - Use `adk web` for development
✅ **Production Ready** - Same agents work in Streamlit
✅ **Maintainable** - Update logic in one place
✅ **Flexible** - Different initialization patterns for different needs

## Additional Resources

- [Google ADK Documentation](https://adk.google.dev/)
- [ADK Quick Start](ADK_QUICKSTART.md)
- [Streamlit Usage Guide](README_VOICEOVER_APP.md)
- [Gemini API Documentation](https://ai.google.dev/gemini-api/docs)

## Summary

This project demonstrates how to structure ADK agents following Google's best practices while maintaining compatibility with custom application frameworks like Streamlit. The key insight is that ADK agents can export both a `root_agent` (for ADK Web discovery) and factory functions (for programmatic use), enabling a single codebase to serve both purposes.
