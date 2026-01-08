"""
PDF Voiceover Agent for ADK Web

This agent analyzes PDF slides and generates voiceover scripts.
Compatible with both `adk web` and Streamlit applications.
"""

import os
import base64
import json
from typing import AsyncGenerator
from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from google.genai import types
from google.genai.types import Content, Part
from google import genai
from pydantic import BaseModel, Field
from typing import List


# --------------------------------------------------------------------------------
# Pydantic Models for Structured Outputs
# --------------------------------------------------------------------------------

class Scene(BaseModel):
    """A single scene containing a comment and speech"""
    comment: str = Field(description="A 1-sentence metadata comment for the generated scene")
    speech: str = Field(description="The voiceover speech for this particular scene")


class SceneList(BaseModel):
    """A list of one or more scenes."""
    scenes: List[Scene]


# --------------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------------

GEMINI_MODEL = "gemini-2.5-flash"

SYSTEM_PROMPT = """You are generating voiceover scripts for a high school introductory Python course. You will be provided a set of slides - for each slide: generate a voiceover narration explaining the content of the slide.

- DO act as a patient, clear, concise, warm tutor who is helping to explain concepts and key steps to students.
- DO generate a voiceover for each uniqe slide and do not combine slides.
- Do NOT use academic vocabulary other than what is included in the slides. Instead, use language appropriate for a teenager.
- Do NOT include markdown text such as ** or `` in your voiceover
- Do NOT vary significantly from the content on the slides, and keep explanations short and concise for each slide.
- Do NOT mention the Unit Guide - focus only on the concept and skill being introduced in the slides.
- DO format your response as a JSON object with the property "scenes", then an array of objects with properties "comment" and "speech".

 Here is an example of a speeches that follows these guidelines:
- 'Welcome! This is a quick byte about functions.
- "So, what exactly is a function? A function is a named block of code that performs a specific task. They are incredibly useful because they allow us to reuse code and organize our programs more efficiently. Let's see how functions work in code."
- 'Here's a simple Python program that uses a function to print the greeting "hello world" to the screen. We'll go through this program step by step to understand how it works.'
- 'The first step is to define your function, which is where you give it a name and specify the commands you want it to run. We use the keyword "def" to indicate that we are defining a new function.
- 'Next, we give our function a descriptive name. In this example, our function is called "greet".'
- "When we define a function, we always include parenthesis and a colon. The colon tells the program we're about to enter the specific steps of our function."
- 'speech': 'After the definition, each line of our function needs to be indented - otherwise we'll get a syntax error. This function just has one line: it'll print "Hello World".'
- 'Once we've defined our function, the next step is to call it. You do that by typing the name of the function with its parenthesis. In our case, we'd type "greet" with an open and close parenthesis.'
- "When the program runs and gets to this function, it will look up it's definition from earlier in the program..."
- 'And then run the code inside the definition. In this case, it would print Hello World.'"""


# --------------------------------------------------------------------------------
# PDFVoiceoverAgent Class
# --------------------------------------------------------------------------------

class PDFVoiceoverAgent(BaseAgent):
    """
    Custom agent that processes PDF slides and generates voiceover scripts.
    Reads PDF from session state and saves scenes to state.
    """
    
    def __init__(self, gemini_client, name="PDFVoiceoverAgent"):
        super().__init__(
            name=name,
            description="Analyzes PDF slides and generates voiceover scripts for educational content"
        )
        # Store as private attributes (underscore prefix) to avoid Pydantic field conflicts
        self._gemini_client = gemini_client
        self._model = GEMINI_MODEL
    
    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        """
        Process PDF from session state and generate voiceover scripts.
        """
        # Get PDF from session state
        pdf_base64 = ctx.session.state.get('pdf_base64')
        
        if not pdf_base64:
            error_msg = "No PDF found in session state. Please upload a PDF first."
            yield Event(
                author=self.name,
                content=Content(parts=[Part(text=error_msg)])
            )
            return
        
        # Decode PDF
        pdf_bytes = base64.b64decode(pdf_base64)
        
        # Build formatted parts for Gemini API
        formatted_parts = [
            "Analyze the slides in this PDF and generate voiceover scripts.",
            types.Part.from_bytes(
                data=pdf_bytes,
                mime_type="application/pdf"
            )
        ]
        
        # Configure generation
        generate_content_config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=SceneList,
            system_instruction=SYSTEM_PROMPT
        )
        
        # Generate content
        response = self._gemini_client.models.generate_content(
            model=self._model,
            contents=formatted_parts,
            config=generate_content_config
        )
        
        # Parse response
        data = json.loads(response.text)
        scenes = data.get("scenes", [])
        
        # Save to session state
        ctx.session.state['scenes'] = scenes
        
        # Create response message
        result_msg = f"Generated {len(scenes)} voiceover scenes from PDF."
        
        # Yield event with results
        yield Event(
            author=self.name,
            content=Content(parts=[Part(text=result_msg)]),
            actions=EventActions(state_delta={'scenes': scenes})
        )


# --------------------------------------------------------------------------------
# Factory Function for Streamlit/External Use
# --------------------------------------------------------------------------------

def create_voiceover_agent(gemini_client):
    """
    Factory function to create a PDFVoiceoverAgent.
    
    Args:
        gemini_client: Initialized Google Gemini client
        
    Returns:
        PDFVoiceoverAgent instance
    """
    return PDFVoiceoverAgent(gemini_client=gemini_client)


# --------------------------------------------------------------------------------
# ADK Web Root Agent Definition
# --------------------------------------------------------------------------------

# Initialize Gemini client using API key from environment
# The API key should be set in a .env file in this directory
api_key = os.environ.get("GOOGLE_API_KEY")

if not api_key:
    print("WARNING: GOOGLE_API_KEY environment variable not set.")
    print("Please create a .env file in the voiceover_agent directory with:")
    print("GOOGLE_API_KEY=your_api_key_here")

# Initialize the Gemini client
client = genai.Client(api_key=api_key) if api_key else None

# Create the root agent for ADK Web
if client:
    root_agent = PDFVoiceoverAgent(gemini_client=client, name="voiceover_agent")
else:
    # Create a placeholder that will fail gracefully if API key is missing
    class PlaceholderAgent(BaseAgent):
        async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
            error_msg = "Agent not initialized. Please set GOOGLE_API_KEY in .env file."
            yield Event(
                author=self.name,
                content=Content(parts=[Part(text=error_msg)])
            )
    
    root_agent = PlaceholderAgent(
        name="voiceover_agent",
        description="Voiceover agent (not initialized - missing API key)"
    )
