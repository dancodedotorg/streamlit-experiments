# ADK Web Quick Start Guide

This is a quick reference for running the agents with `adk web`.

## Setup (One-time)

1. **Configure API Keys** - Add your Google API key to the `.env` files:

   Edit [`voiceover_agent/.env`](voiceover_agent/.env):
   ```bash
   GOOGLE_API_KEY=your_actual_gemini_api_key_here
   ```

   Edit [`elevenlabs_agent/.env`](elevenlabs_agent/.env):
   ```bash
   GOOGLE_API_KEY=your_actual_gemini_api_key_here
   ```

2. **Activate Virtual Environment**:
   ```bash
   # Windows
   .venv\Scripts\activate
   
   # Linux/Mac
   source .venv/bin/activate
   ```

## Running ADK Web

From the project root directory:

```bash
# Standard command
adk web

# Windows (if you get subprocess errors)
adk web --no-reload
```

Then open your browser to: **http://localhost:8000**

## Available Agents

### 1. voiceover_agent
- **Purpose:** Analyzes PDF slides and generates voiceover scripts
- **Input Required:** PDF file in session state (`pdf_base64`)
- **Output:** Scenes with voiceover scripts (`state['scenes']`)

### 2. elevenlabs_agent
- **Purpose:** Adds ElevenLabs audio tags to voiceover scripts
- **Input Required:** Scenes from session state (`scenes`)
- **Output:** Refined scenes with audio tags (`state['refined_scenes']`)

## Basic Usage

1. **Select Agent** - Use the dropdown in top-left
2. **Set State** - Manually add required data to session state (see below)
3. **Send Message** - Chat with the agent to trigger processing
4. **View Events** - Check the Events tab to see results and state changes

## Session State Setup

The ADK web interface requires manual state setup. Here's what each agent needs:

### For voiceover_agent:
```json
{
  "pdf_base64": "base64_encoded_pdf_data_here"
}
```

### For elevenlabs_agent:
```json
{
  "scenes": [
    {
      "comment": "Scene description",
      "speech": "The voiceover text"
    }
  ]
}
```

## Tips

- ✅ Use the **Events** tab to inspect agent actions
- ✅ Use the **Trace** button to see timing information  
- ✅ Check **Console** output for agent initialization messages
- ✅ Session state persists across messages in the same session

## For Full Workflow

For a complete human-in-the-loop workflow with PDF upload, editing, and export:

```bash
streamlit run voiceover_app.py
```

See [`README_ADK_COMPATIBILITY.md`](README_ADK_COMPATIBILITY.md) for full documentation.
