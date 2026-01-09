import streamlit as st
from elevenlabs.client import ElevenLabs
from typing import List, Dict, Any, Tuple, Iterable
from pathlib import Path
from pydantic import BaseModel, Field


# ============================================
# Constants
# ============================================

# Model and Voice Configuration
MODEL = "eleven_v3"
OUTPUT_FORMAT = "mp3_44100_128"
SAM_VOICE_ID = "utHJATTigr4CyfAK1MPl"
DAN_VOICE_ID = "VtuhZ4p3OdnFWQ5O4O7Y"
ADAM_VOICE_ID = "s3TPKV1kjDlVtZbl4Ksh"
HOPE_VOICE_ID = "tnSpp4vdxKPjI9w0GnoV"
ALL_VOICE_IDS = {
    "Sam": SAM_VOICE_ID,
    "Dan": DAN_VOICE_ID,
    "Adam": ADAM_VOICE_ID,
    "Hope": HOPE_VOICE_ID
}

# The text used to separate scenes in the prompt
SCENE_SEPARATOR = " [pause] "

# If True: The script assumes the API returns alignment data for the " [pause] " text itself.
#          We will advance the cursor past the pause characters.
# If False: The script assumes the API converts " [pause] " to silence and DOES NOT return
#           alignment data for those characters (most likely for V3 models).
EXPECT_CONTROL_ALIGNMENT_DATA = False

# ============================================================================
# Helper Functions
# ============================================================================

@st.cache_resource
def get_elevenlabs_client():
    """Initialize and cache the ElevenLabs client."""
    api_key = st.secrets.get("ELEVENLABS_API_KEY", None)
    if not api_key:
        api_key = st.session_state.get("elevenlabs_api_key", None)
    
    if not api_key:
        st.error("❌ ELEVENLABS_API_KEY not found in Streamlit secrets or session state. Please add it.")
        st.stop()
    return ElevenLabs(api_key=api_key)

def get_alignment(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract alignment data.
    IMPORTANT: We prefer raw 'alignment' over 'normalized_alignment' here
    so that character counts match the input script 1:1.
    """
    return data.get("alignment") or data.get("normalized_alignment")


def calculate_durations_by_char_count(scenes: List[Dict[str, Any]], alignment: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Calculates scene durations by mapping character counts directly to alignment timestamps.
    Uses EXPECT_CONTROL_ALIGNMENT_DATA to handle separator logic.
    """
    char_starts = alignment.get("character_start_times_seconds")
    char_ends = alignment.get("character_end_times_seconds")
    chars = alignment.get("characters") # Useful for debugging

    if not char_starts or not char_ends:
        print("[Error] Alignment data missing keys")
        return scenes

    total_alignment_chars = len(char_starts)
    alignment_cursor = 0

    for i, scene in enumerate(scenes):
        text = scene.get("elevenlabs", "")
        text_len = len(text)

        # Handle empty scenes
        if text_len == 0:
            scene['duration'] = "0s"
            # If we are expecting control data, we might need to skip the separator
            # but usually empty text implies no separator needed, depending on join logic.
            continue

        # --- 1. Determine Start/End Indices for THIS Scene ---
        start_idx = alignment_cursor
        end_idx = alignment_cursor + text_len - 1

        # Validation to prevent crashes
        if start_idx >= total_alignment_chars:
            print(f"[Warn] Scene {i} starts at index {start_idx} which is out of bounds (Max: {total_alignment_chars}).")
            scene['duration'] = "error"
            break

        # Clamp end_idx if specific chars (like spaces) were dropped by API
        effective_end_idx = min(end_idx, total_alignment_chars - 1)

        try:
            t_start = char_starts[start_idx]
            t_end = char_ends[effective_end_idx]

            # Calculate duration
            duration = t_end - t_start

            # Optional: Add small buffer (0.5s) for "breathing room" in the UI
            final_duration = duration + 0.5
            scene['duration'] = f"{final_duration:.2f}s"

            # Debug print to verify alignment for the first few scenes
            # if i < 3:
            #     snippet = "".join(chars[start_idx:effective_end_idx+1])
            #     print(f"[Debug] Scene {i} matched alignment text: '{snippet}'")

        except IndexError:
            scene['duration'] = "error"

        # --- 2. Advance Cursor for the next loop ---

        # A. Advance past the text of the current scene
        alignment_cursor += text_len

        # B. Handle the separator (if this is not the last scene)
        if i < len(scenes) - 1:
            if EXPECT_CONTROL_ALIGNMENT_DATA:
                # If the API includes [pause] in alignment, we must count those chars
                # so our cursor lands on the start of the next real sentence.
                alignment_cursor += len(SCENE_SEPARATOR)
            else:
                # If the API strips [pause] (turns it to silence), we do NOT increment.
                # The next index in the array should immediately be the start of the next scene.
                pass

    return scenes

# ============================================================================
# Core Functions
# ============================================================================

def generate_audio(elevenlabs_client, voiceover: str, voiceid: str, verbose: bool = False) -> Dict[str, Any]:
    """
    Generate audio from text using ElevenLabs API with character-level timestamps.
    """
    # print(f"Sending text length: {len(voiceover)} chars")
    st.write(f"🤖 Sending text length: {len(voiceover)} characters to ElevenLabs API...")

    resp = elevenlabs_client.text_to_speech.convert_with_timestamps(
        voice_id=voiceid,
        text=voiceover,
        model_id=MODEL,
        output_format=OUTPUT_FORMAT,
    )
    st.write(f"🤖 Response received!")

    data = resp if isinstance(resp, dict) else getattr(resp, "dict", lambda: resp)()

    if verbose:
        print("Top-level keys:", list(data.keys()))
        aln = get_alignment(data)
        if aln:
            print("Alignment keys:", list(aln.keys()))
            print("Num chars in alignment:", len(aln["characters"]))
        else:
            print("No alignment returned.")

    return data

def elevenlabs_generation(elevenlabs_client, script_obj: Dict[str, Any] = None, voice_name: str = None):
    """Main execution of the audio generation and segmentation pipeline."""

    # Test voiceover script with scene markers
    if script_obj is None:
        # Example script object for testing
        script_obj = {
            "scenes": [
                {
                "comment": "Scene 1: Introduction",
                "html": "",
                "speech": "Welcome! Today we're learning about functions.",
                "duration": "auto",
                "elevenlabs": "Welcome! Today we're learning about FUNCTIONS."
                },
                {
                "comment": "Scene 2: Defining",
                "html": "",
                "speech": "To define a function in Python, we start with def.",
                "duration": "auto",
                "elevenlabs": "To define a function in Python, we start with the keyword DEF."
                },
                {
                "comment": "Scene 3: Naming",
                "html": "",
                "speech": "After def, we give our function a name.",
                "duration": "auto",
                "elevenlabs": "After DEF, we give our function a name."
                }
            ]
        }

    voice_id = ALL_VOICE_IDS.get(voice_name, "Dan")

    scenes = script_obj.get("scenes", [])

    # Task 1: Concatenate Voiceover
    # We use join to avoid a trailing separator at the very end
    texts = [s.get("elevenlabs", "") for s in scenes]
    voiceover = SCENE_SEPARATOR.join(texts)

    # Toggle to generate new audio (set to True to regenerate)
    GENERATE_NEW = True
    data = {}

    if GENERATE_NEW:
        # print(f"Generating new audio...")
        st.write(f"🤖 Generating audio with ElevenLabs voice: {voice_name}...")
        # print(f"Separator: '{SCENE_SEPARATOR}' | Expect Control Data: {EXPECT_CONTROL_ALIGNMENT_DATA}")

        data = generate_audio(elevenlabs_client, voiceover, voice_id, verbose=True)
        if "audio_base64" in data:
            script_obj["audio"] = "data:audio/mpeg;base64," + data["audio_base64"]

    # Task 2: Calculate Durations
    # print("\nCalculating timestamps...")
    st.write("🤖 Calculating scene durations from alignment data...")
    # Use raw alignment to match input string length exactly
    alignment = data.get("alignment")

    if alignment:
        script_obj["scenes"] = calculate_durations_by_char_count(scenes, alignment)

        # Output results
        print("-" * 40)
        for i, s in enumerate(script_obj["scenes"]):
            # print(f"Scene {i+1} duration: {s.get('duration')}")
            st.write(f"✅ Scene {i+1} duration: {s.get('duration')}")
        print("-" * 40)
    else:
        print("[Error] No alignment data found in response.")

    return script_obj