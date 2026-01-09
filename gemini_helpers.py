"""
Gemini API Helper Functions for Voiceover Pipeline

This module provides simplified functions for:
1. Generating voiceover scripts from PDF slides
2. Adding ElevenLabs audio tags to voiceover scripts

Uses direct Gemini SDK calls (no ADK framework).
"""

import base64
import json
from typing import List
from google import genai
from google.genai import types
from pydantic import BaseModel, Field


# ============================================
# Pydantic Models for Structured Outputs
# ============================================

class Scene(BaseModel):
    """A single scene containing a comment and speech"""
    comment: str = Field(description="A 1-sentence metadata comment for the generated scene")
    speech: str = Field(description="The voiceover speech for this particular scene")


class SceneList(BaseModel):
    """A list of one or more scenes."""
    scenes: List[Scene]


class RefinedScene(BaseModel):
    """A single scene with original content plus ElevenLabs audio tags"""
    comment: str = Field(description="A 1-sentence metadata comment for the generated scene")
    speech: str = Field(description="The voiceover speech for this particular scene")
    elevenlabs: str = Field(description="The augmented ElevenLabs voiceover with audio tags")


class RefinedSceneList(BaseModel):
    """A list of one or more refined scenes."""
    scenes: List[RefinedScene]


# ============================================
# System Prompts
# ============================================

VOICEOVER_SYSTEM_PROMPT = """You are generating voiceover scripts for a high school introductory Python course. You will be provided a set of slides - for each slide: generate a voiceover narration explaining the content of the slide.

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


ELEVENLABS_SYSTEM_PROMPT = """# 1. General Instructions - Creating Audio Tags

**Role and Goal**: You are an AI assistant specializing in enhancing dialogue text for speech generation.

Your **PRIMARY GOAL** is to dynamically integrate **audio tags** (e.g., `[thoughtfully]`, `[patiently]`) into dialogue, making it more expressive and engaging for auditory experiences, while **STRICTLY** preserving the original text and meaning.

# 2. Audio Tag Guide

This guide provides the most effective tags and techniques for prompting Eleven v3.

Eleven v3 introduces emotional control through audio tags. You can direct voices to laugh, whisper, act sarcastic, or express curiosity among many other styles. Speed is also controlled through audio tags.

## 2.A **Common tags for narrative control**

Here are some tags that help direct longform delivery, internal monologue, and exposition:

* **Story beats:** [short pause], [continues softly], [hesitates], [resigned]
* **Tone setting:** [dramatic tone], [lighthearted], [reflective], [serious tone]
* **Narrator POV:** [awe], [sarcastic tone], [wistful], [matter-of-fact]
* **Rhythm & flow:** [slows down], [rushed], [emphasized]

These can be sequenced for subtle build-up: [reflective] I never thought I'd say this, but... [short pause] maybe the machine was right.

## 2.B **Controlling timing, pacing, and presence**

Tags give you access to the subtle cues humans use to pace speech naturally:

* **Pauses & breaks:** [short pause], [breathes], [continues after a beat]
* **Speed cues:** [rushed], [slows down], [deliberate], [rapid-fire]
* **Hesitation & rhythm:** [stammers], [drawn out], [repeats], [timidly]
* **Emphasis:** [emphasized], [stress on next word], [understated]

## 2.C **Punctuation**

Punctuation significantly affects delivery in v3:

* **Ellipses (...)** add pauses and weight
* **Standard punctuation** provides natural speech rhythm

```text Example
"It was a very long day [sigh] ... nobody listens anymore."
```

## 2.D **Tag Best Practices**

- Placement matters: Insert tags at the point in the text where you want the effect to start.
- Context and wording: The model infers emotion from the surrounding text, not just the tags. Audio tags are a more direct way to force an effect, but you'll get the most reliable results by aligning the tag with context. For instance, writing "No... please [crying] don't go." is better than just "No, please don't go." with a [crying] tag slapped on, because the first version provides context that matches the crying tone. A combination of tags and descriptive prompting yields the best performances.
- Use punctuation as tags' ally: Punctuation plays a big role in ElevenLabs v3 outputs. An ellipsis (...) will cause a pause or trailing off, which can amplify a sad or dramatic moment. Commas and periods ensure the voice takes natural breaths. An exclamation mark conveys excitement or shouting. Don't underestimate how important good punctuation is in sculpting the delivery - they work hand in hand with the tags to produce life-like speech.
- Discovering new tags:** While the documentation provides many tags, it's not an exhaustive list of everything the model can understand.

## 2.E **Example Audio Tags (Non-Exhaustive)**

Use these as a guide. You can infer similar, contextually appropriate **audio tags**.

**Directions:**
* `[happy]`
* `[sad]`
* `[excited]`
* `[angry]`
* `[whisper]`
* `[annoyed]`
* `[appalled]`
* `[thoughtful]`
* `[surprised]`
* *(and similar emotional/delivery directions)*

# 3 Specific Directives

Follow these directives meticulously to ensure high-quality output: You are assisting in the development of voiceover scripts demonstrating how to solve Python tasks for an introductory Python course. You are helping to optimize the voiceover lines using appropriate audio tags and punctuation.

## 3.A The Input Format
You will receive an object (dictionary), with an array of objects, where each object represents a single scene needing a voiceover.

  * **Format:** `{'scenes': [{'comment': <string>, 'speech': <string>}, ...]`
  * **`comment`**: A general description of the scene
  * **`speech`**: The voiceover line to augment with Audio Tags.

## 3.B Positive Imperatives (DO):

* DO integrate **audio tags** based on the provided guide and best practices to add expression, emotion, and realism to the dialogue. These tags MUST describe something auditory.
* DO use audio tags associated with a patient, concise, warm tutor who is helping to explain concepts and key steps to students.
* DO pause for emphasis at key moments, emphasize key words and phrasing using audio tags, and use a warm inviting tone with moments of excitement and enthusiasm.
* DO ensure that all **audio tags** are contextually appropriate and genuinely enhance the emotion or subtext of the dialogue line they are associated with.
* DO strive for a diverse range of emotional expressions (e.g., energetic, relaxed, casual, surprised, thoughtful) across the dialogue, reflecting the nuances of human conversation.
* DO place **audio tags** strategically to maximize impact, typically immediately before the dialogue segment they modify or immediately after. (e.g., `[annoyed] This is hard.` or `This is hard. [sighs]`).
* DO ensure **audio tags** contribute to the enjoyment and engagement of spoken dialogue.

## 3.C Negative Imperatives (DO NOT):

* DO NOT alter, add, or remove any words from the original dialogue text itself. Your role is to *prepend* **audio tags**, not to *edit* the speech. **This also applies to any narrative text provided; you must *never* place original text inside brackets or modify it in any way.**
* DO NOT create **audio tags** from existing narrative descriptions. **Audio tags** are *new additions* for expression, not reformatting of the original text. (e.g., if the text says "He laughed loudly," do not change it to "[laughing loudly] He laughed." Instead, add a tag if appropriate, e.g., "He laughed loudly [chuckles].")
* Do NOT use markdown syntax for emphasis - use audio tags when you want to emphasize words.
* Do NOT use capitalization to emphasize words - leave all words in their original case.
* DO NOT invent new dialogue lines.

## 3.D Workflow

1. **Analyze Dialogue**: Carefully read and understand the mood, context, and emotional tone of **EACH** line of dialogue provided in the input.
2. **Select Tag(s)**: Based on your analysis, choose one or more suitable **audio tags**. Ensure they are relevant to the dialogue's specific emotions and dynamics.
3. **Integrate Tag(s)**: Place the selected **audio tag(s)** in square brackets `[]` strategically before or after the relevant dialogue segment, or at a natural pause if it enhances clarity.
4. **Add Emphasis:** You cannot change the text at all, but you can add emphasis by adding audio tags like [emphasize] or [important], adding a question mark or adding an exclamation mark where it makes sense, or adding ellipses as well too.
5. **Verify Appropriateness**: Review the enhanced dialogue to confirm:
    * The **audio tag** fits naturally.
    * It enhances meaning without altering it.
    * It adheres to all Core Directives.

## 3.E Output Format
* Return an identical array with a new "elevenlabs" property containing the results of your work.
* Present ONLY the enhanced dialogue text in a conversational format.
* **Audio tags** **MUST** be enclosed in square brackets (e.g., `[laughing]`).
* The output should maintain the narrative flow of the original dialogue."""


# ============================================
# Main Functions
# ============================================

def generate_voiceover_scenes(gemini_client: genai.Client, pdf_base64: str) -> list[dict]:
    """
    Generate voiceover scenes from a PDF using Gemini API.
    
    Args:
        gemini_client: Initialized genai.Client instance
        pdf_base64: Base64-encoded PDF bytes
        
    Returns:
        List of scene dictionaries with 'comment' and 'speech' keys
        
    Raises:
        Exception: If API call fails or response parsing fails
    """
    # Decode PDF from base64
    pdf_bytes = base64.b64decode(pdf_base64)
    
    # Build content parts for the API call
    contents = [
        "Analyze the slides in this PDF and generate voiceover scripts.",
        types.Part.from_bytes(
            data=pdf_bytes,
            mime_type="application/pdf"
        )
    ]
    
    # Configure structured output generation
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=SceneList,
        system_instruction=VOICEOVER_SYSTEM_PROMPT
    )
    
    # Call Gemini API
    response = gemini_client.models.generate_content(
        model="gemini-2.5-flash",
        contents=contents,
        config=config
    )
    
    # Parse and return scenes
    data = json.loads(response.text)
    return data.get("scenes", [])


def add_elevenlabs_tags(gemini_client: genai.Client, scenes: list[dict]) -> list[dict]:
    """
    Add ElevenLabs audio tags to voiceover scenes using Gemini API.
    
    Args:
        gemini_client: Initialized genai.Client instance
        scenes: List of scene dictionaries with 'comment' and 'speech' keys
        
    Returns:
        List of refined scene dictionaries with added 'elevenlabs' key
        
    Raises:
        Exception: If API call fails or response parsing fails
    """
    # Format scenes as JSON string
    json_str = json.dumps({"scenes": scenes})
    
    # Configure structured output generation
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=RefinedSceneList,
        system_instruction=ELEVENLABS_SYSTEM_PROMPT
    )
    
    # Call Gemini API
    response = gemini_client.models.generate_content(
        model="gemini-2.5-flash",
        contents=json_str,
        config=config
    )
    
    # Parse and return refined scenes
    data = json.loads(response.text)
    return data.get("scenes", [])
