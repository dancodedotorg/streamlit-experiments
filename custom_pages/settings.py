import streamlit as st
import base64
import json
import uuid
import traceback
from google import genai
from google_auth_oauthlib.flow import Flow

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

def app_page():

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

    if st.button("▶️ Continue to Import", width="stretch"):
        st.switch_page("custom_pages/slides_import.py")

app_page()