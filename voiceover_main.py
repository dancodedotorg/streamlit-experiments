"""
Voiceover Pipeline - Streamlit App with Human-in-the-Loop

This app uses direct Gemini API calls to generate and refine voiceover scripts,
with human review and editing between each step.

This is the main entry point for the Streamlit application. It handles
global configurations, Google OAuth, cached resources, and session state
initialization. Individual workflow steps are implemented as separate pages
in the `pages/` directory.
"""

import streamlit as st
import base64
import json
import uuid
import traceback
from google import genai
from google_auth_oauthlib.flow import Flow
from gemini_helpers import generate_voiceover_scenes, add_elevenlabs_tags
from slides import get_slides_data_cached, slides_to_pdf


# ============================================
# Page Configuration
# ============================================
st.set_page_config(
    page_title="Voiceover Pipeline",
    page_icon="🎙️",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("🎙️ Voiceover Pipeline with Human-in-the-Loop")
st.caption("Generate and refine educational voiceover scripts from PDF slides")


# ============================================
# Cached Resources (Singletons)
# ============================================

@st.cache_resource
def get_gemini_client():
    """Initialize and cache the Gemini client."""
    api_key = st.secrets.get("GEMINI_API_KEY", None)
    if not api_key:
        api_key = st.session_state.get("gemini_api_key", None)
    
    if not api_key:
        st.error("❌ GEMINI_API_KEY not found in Streamlit secrets or session state. Please add it.")
        st.stop()
    return genai.Client(api_key=api_key)


@st.cache_data
def process_pdf(pdf_bytes):
    """Process and cache PDF data."""
    pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
    return {
        'base64': pdf_base64,
        'size': len(pdf_bytes)
    }


# ============================================
# Session State Initialization
# ============================================

def initialize_session_state():
    """Initialize all session state keys with defaults."""
    # Initialize common session state variables that pages might use
    if 'is_processing' not in st.session_state:
        st.session_state.is_processing = False
    
    # These will be populated by the pages later, but initialize them here for consistency
    if 'slides_data' not in st.session_state:
        st.session_state.slides_data = None
    if 'pdf_base64' not in st.session_state:
        st.session_state.pdf_base64 = None
    if 'scenes' not in st.session_state:
        st.session_state.scenes = None
    if 'refined_scenes' not in st.session_state:
        st.session_state.refined_scenes = None
    if 'voiceover_approved' not in st.session_state:
        st.session_state.voiceover_approved = False
    if 'final_approved' not in st.session_state:
        st.session_state.final_approved = False
    if 'gemini_api_key' not in st.session_state:
        st.session_state.gemini_api_key = ''
    if 'elevenlabs_api_key' not in st.session_state:
        st.session_state.elevenlabs_api_key = ''



initialize_session_state()


# ============================================
# Page Navigation
# ============================================

custom_pages = [
    st.Page("custom_pages/settings.py", title="Settings", icon=":material/settings:", default=True),
    st.Page("custom_pages/slides_import.py", title="Import Slides PTT/PDF", icon=":material/upload_file:"),
    st.Page("custom_pages/upload.py", title="Upload & Process", icon=":material/cloud_upload:"),
    st.Page("custom_pages/generate_voiceover.py", title="Generate Voiceover", icon=":material/mic:"),
    st.Page("custom_pages/add_audio_tags.py", title="Add Audio Tags", icon=":material/music_note:"),
    st.Page("custom_pages/export.py", title="Export Voiceover", icon=":material/download:"),
    st.Page("custom_pages/debug.py", title="Debug & Session", icon=":material/bug_report:")
]

pg = st.navigation(custom_pages)
pg.run()

# ============================================
# Sidebar - Developer Options
# ============================================

with st.sidebar:
    # Developer options
    with st.expander("🔧 Developer Options"):
        if st.button("Clear Resource Cache"):
            st.cache_resource.clear()
            st.success("Agent cache cleared!")
            st.rerun()
        
        if st.button("Clear Data Cache"):
            st.cache_data.clear()
            st.success("Data cache cleared!")
            st.rerun()
        
        if st.button("Reset All Session State"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.success("Session reset!")
            st.rerun()
