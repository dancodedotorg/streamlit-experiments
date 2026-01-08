import streamlit as st
from google import genai
from google.genai import types
import json
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
import base64
from slides import get_slides_data_cached

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="Math Assistant",
    page_icon="🧮",
    layout="wide"  # Makes content fill the screen width
)

# --- GOOGLE OAUTH CONFIGURATION ---
SCOPES = [
    'https://www.googleapis.com/auth/presentations.readonly',
    'https://www.googleapis.com/auth/drive.readonly'
]

@st.cache_resource
def get_flow():
    """Create and return OAuth flow for Google authentication.
    
    Cached as a resource since Flow objects are expensive to create
    and can be reused across sessions.
    """
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

@st.cache_resource
def get_gemini_client(api_key: str):
    """Create and return a Gemini client.
    
    Cached as a resource to avoid recreating the client on every rerun.
    The cache key includes the API key so a new client is created if the key changes.
    
    Args:
        api_key: The Gemini API key
        
    Returns:
        genai.Client: A configured Gemini client
    """
    return genai.Client(api_key=api_key)

# --- SESSION STATE INITIALIZATION ---
if "api_key" not in st.session_state:
    st.session_state.api_key = ""
if "elevenlabs_api_key" not in st.session_state:
    st.session_state.elevenlabs_api_key = ""
if "messages" not in st.session_state:
    st.session_state.messages = []
if "slides_data" not in st.session_state:
    st.session_state.slides_data = None
if "html_content" not in st.session_state:
    st.session_state.html_content = ""

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

# --- MAIN SCREEN ---
st.title("🧮 Math Assistant")

# Check if API key is present
if not st.session_state.api_key:
    st.warning("⚠️ Please enter a valid Gemini API Key in the sidebar to start chatting.")
else:
    # Initialize Gemini client (cached to avoid recreating on every rerun)
    client = get_gemini_client(st.session_state.api_key)

    # Create tabs for different functionalities
    tab1, tab2, tab3 = st.tabs(["💬 Chat", "📊 Google Slides Manager", "🐛 Debug"])
    
    # --- TAB 1: CHAT INTERFACE ---
    with tab1:
        # Display chat history
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        # Chat Input with built-in file upload support
        if submission := st.chat_input(
            "Ask a math question...",
            accept_file="multiple",
            file_type=["png", "jpg", "jpeg", "pdf", "mp4", "wav", "mp3"]
        ):
            # 1. Extract message and files from submission
            user_message = submission.text if hasattr(submission, 'text') else submission
            uploaded_files = submission.files if hasattr(submission, 'files') else []
            
            # 2. Store and display user message
            st.session_state.messages.append({"role": "user", "content": user_message})
            with st.chat_message("user"):
                st.markdown(user_message)
                # Display attached files
                if uploaded_files:
                    st.caption(f"📎 {len(uploaded_files)} file(s) attached")

            # 3. Prepare multimodal content
            content_to_send = [user_message] if user_message else []
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
    
    # --- TAB 2: GOOGLE SLIDES MANAGEMENT ---
    with tab2:
        st.subheader("Google Slides Manager")
        
        # Slide Presentation ID Input
        presentation_id = st.text_input(
            "Slide Presentation ID:",
            placeholder="Enter the Google Slides ID",
            help="The ID from the Google Slides URL"
        )
        
        if st.button("Load Slides", type="primary"):
            # Check if user is authenticated with Google
            if "creds" not in st.session_state:
                st.error("❌ Please authenticate with Google in the sidebar first.")
            elif not presentation_id:
                st.warning("⚠️ Please enter a valid Presentation ID.")
            else:
                with st.spinner("Loading slides data..."):
                    try:
                        # Call cached get_slides_data from slides.py
                        # Cached with presentation_id as key to avoid re-fetching same presentation
                        slides_data = get_slides_data_cached(presentation_id, st.session_state.creds)
                        
                        if slides_data is None:
                            st.error("Failed to load slides data. Please check the Presentation ID and permissions.")
                        else:
                            st.session_state.slides_data = slides_data
                            st.success(f"✅ Successfully loaded {len(slides_data)} slides!")
                            st.rerun()
                    except Exception as e:
                        st.error(f"Error loading slides: {e}")
        
        st.divider()
        
        # Display and edit slides if data is available
        if st.session_state.slides_data:
            st.subheader(f"Manage Slides ({len(st.session_state.slides_data)} slides)")
            
            # Option to clear slides data
            if st.button("Clear Slides Data"):
                st.session_state.slides_data = None
                st.rerun()
            
            st.divider()
            
            # Define callback function to remove a slide
            def remove_slide(slide_index):
                """Remove a slide from slides_data and re-index remaining slides."""
                st.session_state.slides_data = [
                    slide for slide in st.session_state.slides_data
                    if slide["index"] != slide_index
                ]
                # Re-index remaining slides
                for i, slide in enumerate(st.session_state.slides_data):
                    slide["index"] = i
            
            # Create expanders for each slide
            for slide in st.session_state.slides_data:
                slide_index = slide["index"]
                
                with st.expander(f"Slide {slide_index + 1}", expanded=False):
                    col1, col2, col3 = st.columns([2, 3, 1])
                    with col1:
                        # Display slide thumbnail
                        if slide.get("png_base64"):
                            try:
                                # Decode base64 image and display
                                # image_data = base64.b64decode(slide["png_base64"])
                                image_html = f"<img src='{slide['png_base64']}' style='width:100%; height:auto;' />"
                                st.markdown(image_html, unsafe_allow_html=True)
                            except Exception as e:
                                st.warning(f"Could not display thumbnail: {e}")
                    with col2:
                        # Edit speaker notes
                        st.markdown("**Speaker Notes:**")
                        new_notes = st.text_area(
                            "Edit notes:",
                            value=slide.get("notes", ""),
                            height=150,
                            key=f"notes_{slide_index}",
                            label_visibility="collapsed"
                        )
                        # Update notes in session state if changed
                        if new_notes != slide.get("notes", ""):
                            st.session_state.slides_data[slide_index]["notes"] = new_notes
                    with col3:
                        st.button(
                            "🗑️ Remove",
                            key=f"remove_{slide_index}",
                            on_click=remove_slide,
                            args=(slide_index,),
                            use_container_width=True
                        )
            
            # Export option
            st.divider()
            st.subheader("Export Data")
            if st.button("Download Slides Data as JSON"):
                json_data = json.dumps(st.session_state.slides_data, indent=2)
                st.download_button(
                    label="📥 Download JSON",
                    data=json_data,
                    file_name="slides_data.json",
                    mime="application/json"
                )
        else:
            st.info("Load a Google Slides presentation to manage slides and speaker notes.")
    
    # --- TAB 3: DEBUG SESSION STATE ---
    with tab3:
        st.subheader("Session State Debug")
        st.caption("Current session state for debugging purposes")
        
        # Display session state as JSON
        st.json(dict(st.session_state))
        
        st.divider()
        
        # Display individual session state items
        st.subheader("Session State Items")
        for key, value in st.session_state.items():
            with st.expander(f"📋 {key}"):
                st.write(f"**Type:** `{type(value).__name__}`")
                
                # Display differently based on type
                if key == "creds":
                    st.info("Google credentials object (not displayed for security)")
                elif isinstance(value, (str, int, float, bool)):
                    st.code(repr(value))
                elif isinstance(value, list):
                    st.write(f"**Length:** {len(value)}")
                    if len(value) > 0:
                        st.json(value[:5] if len(value) > 5 else value)
                        if len(value) > 5:
                            st.caption(f"Showing first 5 of {len(value)} items")
                elif isinstance(value, dict):
                    st.json(value)
                else:
                    st.write(value)