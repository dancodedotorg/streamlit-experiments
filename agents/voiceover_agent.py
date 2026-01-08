"""
PDF Voiceover Agent

This agent analyzes PDF slides and generates voiceover scripts.
"""

import base64
import json
from typing import AsyncGenerator
from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from google.genai import types
from google.genai.types import Content, Part
from .models import SceneList
from .config import SYSTEM_PROMPTS, GEMINI_MODEL


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
            system_instruction=SYSTEM_PROMPTS['pdf-to-voiceover']
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


def create_voiceover_agent(gemini_client):
    """
    Factory function to create a PDFVoiceoverAgent.
    
    Args:
        gemini_client: Initialized Google Gemini client
        
    Returns:
        PDFVoiceoverAgent instance
    """
    return PDFVoiceoverAgent(gemini_client=gemini_client)
