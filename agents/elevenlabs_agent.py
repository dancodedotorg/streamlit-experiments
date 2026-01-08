"""
ElevenLabs Audio Tag Agent

This agent enhances voiceover scripts with ElevenLabs audio tags.
"""

import json
from typing import AsyncGenerator
from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from google.genai import types
from google.genai.types import Content, Part
from .models import RefinedSceneList
from .config import SYSTEM_PROMPTS, GEMINI_MODEL


class ElevenLabsAgent(BaseAgent):
    """
    Custom agent that adds ElevenLabs audio tags to voiceover scripts.
    Reads scenes from session state and saves refined scenes.
    """
    
    def __init__(self, gemini_client, name="ElevenLabsAgent"):
        super().__init__(
            name=name,
            description="Enhances voiceover scripts with ElevenLabs audio tags for expressive speech"
        )
        # Store as private attributes (underscore prefix) to avoid Pydantic field conflicts
        self._gemini_client = gemini_client
        self._model = GEMINI_MODEL
    
    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        """
        Process scenes from session state and add ElevenLabs audio tags.
        """
        # Get scenes from session state
        scenes = ctx.session.state.get('scenes')
        
        if not scenes:
            error_msg = "No scenes found in session state. Please generate voiceover scripts first."
            yield Event(
                author=self.name,
                content=Content(parts=[Part(text=error_msg)])
            )
            return
        
        # Format scenes as JSON string for the agent
        json_str = json.dumps({"scenes": scenes})
        
        # Build formatted parts for Gemini API
        formatted_parts = [json_str]
        
        # Configure generation
        generate_content_config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=RefinedSceneList,
            system_instruction=SYSTEM_PROMPTS['elevenlabs']
        )
        
        # Generate content
        response = self._gemini_client.models.generate_content(
            model=self._model,
            contents=formatted_parts,
            config=generate_content_config
        )
        
        # Parse response
        data = json.loads(response.text)
        refined_scenes = data.get("scenes", [])
        
        # Save to session state
        ctx.session.state['refined_scenes'] = refined_scenes
        
        # Create response message
        result_msg = f"Added ElevenLabs audio tags to {len(refined_scenes)} scenes."
        
        # Yield event with results
        yield Event(
            author=self.name,
            content=Content(parts=[Part(text=result_msg)]),
            actions=EventActions(state_delta={'refined_scenes': refined_scenes})
        )


def create_elevenlabs_agent(gemini_client):
    """
    Factory function to create an ElevenLabsAgent.
    
    Args:
        gemini_client: Initialized Google Gemini client
        
    Returns:
        ElevenLabsAgent instance
    """
    return ElevenLabsAgent(gemini_client=gemini_client)
