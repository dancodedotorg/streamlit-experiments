"""
Pydantic models for structured outputs
"""

from pydantic import BaseModel, Field
from typing import List


class Scene(BaseModel):
    """A single scene containing a comment and speech"""
    comment: str = Field(description="A 1-sentence metadata comment for the generated scene")
    speech: str = Field(description="The voiceover speech for this particular scene")


class SceneList(BaseModel):
    """A list of one or more scenes."""
    scenes: List[Scene]


class RefinedScene(BaseModel):
    """A single scene containing a comment, speech, and elevenlabs audio tags"""
    comment: str = Field(description="A 1-sentence metadata comment for the generated scene")
    speech: str = Field(description="The voiceover speech for this particular scene")
    elevenlabs: str = Field(description="The augmented ElevenLabs voiceover with audio tags")


class RefinedSceneList(BaseModel):
    """A list of one or more refined scenes."""
    scenes: List[RefinedScene]
