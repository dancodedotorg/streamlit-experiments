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
# Google OAuth Configuration
# ============================================

SCOPES = [
    'https://www.googleapis.com/auth/presentations.readonly',
    'https://www.googleapis.com/auth/drive.readonly'
]


@st.cache_resource
def get_google_oauth_flow():
    """Create and return OAuth flow for Google authentication."""
    client_config = json.loads(st.secrets["CLIENT_CONFIG"])
    redirect_uri = st.secrets.get("REDIRECT_URI", "http://localhost:8501")
    
    return Flow.from_client_config(
        client_config,
        scopes=SCOPES,
        redirect_uri=redirect_uri
    )


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


# ==============================
# Handle Google OAuth Callback
# ==============================
# Check if we are returning from Google Auth
if "code" in st.query_params and "creds" not in st.session_state:
    try:
        flow = get_google_oauth_flow()
        flow.fetch_token(code=st.query_params["code"])
        st.session_state.creds = flow.credentials
        # Clean the URL by removing the code
        st.query_params.clear()
        st.rerun()
    except Exception as e:
        st.error(f"Authentication error: {e}")
        st.query_params.clear()

initialize_session_state()


# ============================================
# Main Content - API Key Inputs and Google Auth UI
# ============================================

st.subheader("Configure API Keys")

gemini_api_key_input = st.text_input("Google Gemini API Key", type="password", value=st.session_state.gemini_api_key)
if gemini_api_key_input:
    st.session_state.gemini_api_key = gemini_api_key_input

elevenlabs_api_key_input = st.text_input("ElevenLabs API Key (for audio tags)", type="password", value=st.session_state.elevenlabs_api_key)
if elevenlabs_api_key_input:
    st.session_state.elevenlabs_api_key = elevenlabs_api_key_input

st.markdown("--- ")

st.subheader("🔐 Google Account Authentication")
if "creds" not in st.session_state:
    st.info("Not authenticated with Google. Required for Google Slides import.")
    try:
        flow = get_google_oauth_flow()
        auth_url, _ = flow.authorization_url(prompt='consent')
        auth_link = f'<a href="{auth_url}" target="_self"><button style="background-color: #4285F4; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; font-size: 14px; width: 100%;">Log in with Google</button></a>'
        st.markdown(auth_link, unsafe_allow_html=True)
    except Exception as e:
        st.error(f"Error setting up Google authentication: {e}")
else:
    st.success("✅ Authenticated with Google")
    if st.button("Sign out of Google", width="stretch"):
        del st.session_state.creds
        st.rerun()

st.markdown("--- ")

# The rest of the content will be in respective pages/ files

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
