import streamlit as st
from google import genai
from google.genai import types
import json
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

# --- GOOGLE OAUTH CONFIGURATION ---
SCOPES = [
    'https://www.googleapis.com/auth/presentations.readonly',
    'https://www.googleapis.com/auth/drive.readonly'
]

def get_flow():
    """Create and return OAuth flow for Google authentication."""
    # Load client config from Streamlit Secrets
    client_config = json.loads(st.secrets["CLIENT_CONFIG"])
    
    # The redirect_uri must match exactly what is in your Google Cloud Console
    # For local testing, use http://localhost:8501
    redirect_uri = st.secrets.get("REDIRECT_URI", "http://localhost:8501")
    
    return Flow.from_client_config(
        client_config,
        scopes=SCOPES,
        redirect_uri=redirect_uri
    )

# --- SESSION STATE INITIALIZATION ---
if "api_key" not in st.session_state:
    st.session_state.api_key = ""
if "elevenlabs_api_key" not in st.session_state:
    st.session_state.elevenlabs_api_key = ""
if "messages" not in st.session_state:
    st.session_state.messages = []

# --- HANDLE GOOGLE OAUTH CALLBACK ---
# Check if we are returning from Google Auth
if "code" in st.query_params and "creds" not in st.session_state:
    try:
        flow = get_flow()
        flow.fetch_token(code=st.query_params["code"])
        st.session_state.creds = flow.credentials
        # Clean the URL by removing the code
        st.query_params.clear()
        st.rerun()
    except Exception as e:
        st.error(f"Authentication error: {e}")
        st.query_params.clear()

# --- SIDEBAR: API KEY INPUT ---
with st.sidebar:
    st.header("Configuration")
    
    # Gemini API Key (Required)
    st.subheader("Gemini API Key (Required)")
    api_key = st.text_input(
        "Enter your Gemini API Key:",
        type="password",
        value=st.session_state.api_key,
        key="api_key_input"
    )
    if st.button("Save Gemini API Key"):
        st.session_state.api_key = api_key
        st.rerun()
    
    if st.session_state.api_key:
        st.success("Gemini API Key configured ✓")
    else:
        st.info("Please enter your API key to use the chat")
    
    st.divider()
    
    # ElevenLabs API Key (Optional)
    st.subheader("ElevenLabs API Key (Optional)")
    elevenlabs_api_key = st.text_input(
        "Enter your ElevenLabs API Key:",
        type="password",
        value=st.session_state.elevenlabs_api_key,
        key="elevenlabs_api_key_input"
    )
    if st.button("Save ElevenLabs API Key"):
        st.session_state.elevenlabs_api_key = elevenlabs_api_key
        st.rerun()
    
    if st.session_state.elevenlabs_api_key:
        st.success("ElevenLabs API Key configured ✓")
    
    st.divider()
    
    # Google Authentication (Optional)
    st.subheader("Google Authentication (Optional)")
    st.caption("Required for Google Slides and Drive access")
    
    if "creds" not in st.session_state:
        st.info("Not authenticated with Google")
        try:
            flow = get_flow()
            auth_url, _ = flow.authorization_url(prompt='consent')
            
            # Custom HTML button to open in the same tab
            auth_link = f'<a href="{auth_url}" target="_self"><button style="background-color: #4285F4; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; font-size: 14px;">Log in with Google</button></a>'
            st.markdown(auth_link, unsafe_allow_html=True)
        except Exception as e:
            st.error(f"Error setting up Google authentication: {e}")
    else:
        st.success("✅ Authenticated with Google")
        if st.button("Sign out of Google"):
            del st.session_state.creds
            st.rerun()

# --- MAIN SCREEN: CHAT INTERFACE ---
st.title("🧮 Math Assistant")

# Check if API key is present
if not st.session_state.api_key:
    st.warning("⚠️ Please enter a valid Gemini API Key in the sidebar to start chatting.")
else:
    # Initialize Gemini client
    client = genai.Client(api_key=st.session_state.api_key)

    # Display chat history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # File Uploader Container
    with st.container():
        uploaded_files = st.file_uploader(
            "Attach materials",
            type=["png", "jpg", "jpeg", "pdf", "mp4", "wav", "mp3"],
            accept_multiple_files=True,
            label_visibility="collapsed",
            key="file_uploader"
        )

    # Chat Input
    if prompt := st.chat_input("Ask a math question..."):
        # 1. Store and display user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # 2. Prepare multimodal content
        content_to_send = [prompt]
        if uploaded_files:
            for uploaded_file in uploaded_files:
                file_bytes = uploaded_file.read()
                content_to_send.append(
                    types.Part.from_bytes(
                        data=file_bytes,
                        mime_type=uploaded_file.type,
                    )
                )

        # 3. Stream the Assistant response
        with st.chat_message("assistant"):
            try:
                # Define a generator for Streamlit to consume
                def stream_generator():
                    for chunk in client.models.generate_content_stream(
                            model="gemini-2.5-flash",
                            config=types.GenerateContentConfig(
                                system_instruction="Help with math homework."
                            ),
                            contents=content_to_send,
                        ):
                        yield chunk.text

                # Use st.write_stream to handle the chunks and cursor
                full_response = st.write_stream(stream_generator())
                
                # Save full response to history
                st.session_state.messages.append({"role": "assistant", "content": full_response})
                
            except Exception as e:
                st.error(f"API Error: {e}")