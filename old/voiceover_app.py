"""
Voiceover Pipeline - Streamlit App with Human-in-the-Loop

This app uses direct Gemini API calls to generate and refine voiceover scripts,
with human review and editing between each step.
"""

import streamlit as st
import base64
import json
import traceback
from google import genai
from google_auth_oauthlib.flow import Flow
from helpers.gemini_helpers import generate_voiceover_scenes, add_elevenlabs_tags
from helpers.google_slides_helpers import get_slides_data_cached, slides_to_pdf


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
        st.error("❌ GEMINI_API_KEY not found in secrets. Please add it to .streamlit/secrets.toml")
        st.stop()
    return genai.Client(api_key=api_key)




# ============================================
# Cached Data Processing
# ============================================

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
    if 'workflow_state' not in st.session_state:
        st.session_state.workflow_state = 'slides_import'  # Start with slides import
    
    if 'is_processing' not in st.session_state:
        st.session_state.is_processing = False
    
    # Google Slides state
    if 'slides_data' not in st.session_state:
        st.session_state.slides_data = None


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
# Workflow State Machine
# ============================================

WORKFLOW_STATES = {
    'slides_import': {'next': 'upload', 'display': '📊 Import Slides', 'step': 0},
    'upload': {'next': 'generate_voiceover', 'display': '📤 Upload /PDF', 'step': 1},
    'generate_voiceover': {'next': 'add_audio_tags', 'display': '🎬 Generate & Review Script', 'step': 2},
    'add_audio_tags': {'next': 'export', 'display': '🎨 Add Audio Tags & Review', 'step': 3},
    'export': {'next': 'debug', 'display': '📥 Export', 'step': 4},
    'debug': {'next': None, 'display': '🔧 Debug', 'step': 5}
}


def advance_workflow():
    """Move to next step in workflow."""
    current = st.session_state.workflow_state
    next_state = WORKFLOW_STATES[current]['next']
    if next_state:
        st.session_state.workflow_state = next_state


def reset_workflow():
    """Reset to beginning."""
    st.session_state.workflow_state = 'slides_import'  # Start from slides import
    # Clear relevant session state
    for key in ['slides_data', 'pdf_base64', 'scenes', 'refined_scenes', 'voiceover_approved', 'final_approved']:
        if key in st.session_state:
            del st.session_state[key]


# ============================================
# Session State Helpers
# ============================================

def get_session_state_value(key, default=None):
    """Safely get value from Streamlit session state."""
    return st.session_state.get(key, default)


def set_session_state_value(key, value):
    """Safely set value in Streamlit session state."""
    st.session_state[key] = value


# ============================================
# Sidebar - Google Auth, Progress & Options
# ============================================

with st.sidebar:
    # Google Authentication
    st.header("🔐 Google Authentication")
    
    if "creds" not in st.session_state:
        st.info("Not authenticated with Google")
        try:
            flow = get_google_oauth_flow()
            auth_url, _ = flow.authorization_url(prompt='consent')
            
            # Custom HTML button to open in the same tab
            auth_link = f'<a href="{auth_url}" target="_self"><button style="background-color: #4285F4; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; font-size: 14px; width: 100%;">Log in with Google</button></a>'
            st.markdown(auth_link, unsafe_allow_html=True)
            st.caption("Required for Google Slides import")
        except Exception as e:
            st.error(f"Error setting up Google authentication: {e}")
    else:
        st.success("✅ Authenticated with Google")
        if st.button("Sign out of Google", width="stretch"):
            del st.session_state.creds
            st.rerun()
    
    st.divider()
    
    # Progress
    st.header("📊 Progress")
    
    # Show current step
    current_step = st.session_state.workflow_state
    current_info = WORKFLOW_STATES[current_step]
    total_steps = len(WORKFLOW_STATES)
    
    # Adjust progress for step 0
    if current_info['step'] == 0:
        progress_value = 0.0
    else:
        progress_value = current_info['step'] / (total_steps - 1)
    
    st.progress(progress_value)
    st.caption(f"**Step {current_info['step']}/{total_steps - 1}:** {current_info['display']}")
    
    # Quick navigation buttons
    st.markdown("**Jump to Step:**")
    
    # Create a grid layout for navigation buttons
    nav_cols = st.columns(1)
    for i, (state_key, state_info) in enumerate(WORKFLOW_STATES.items()):
        col_index = i % 1  # Single column
        with nav_cols[col_index]:
            # Highlight current step
            button_type = "primary" if state_key == current_step else "secondary"
            is_current = state_key == current_step
            
            # Create button label with emoji and step number
            button_label = f"{state_info['display']}"
            if is_current:
                button_label = f"➤ {button_label}"
            
            if st.button(
                button_label,
                key=f"nav_{state_key}",
                type=button_type,
                width="stretch",
                disabled=is_current
            ):
                st.session_state.workflow_state = state_key
                st.rerun()
    
    st.divider()
    
    # Workflow controls
    st.subheader("🔄 Workflow Controls")
    
    if st.button("🏠 Start Over", width="stretch"):
        reset_workflow()
        st.rerun()
    
    st.divider()
    
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


# ============================================
# STEP 0: Import Google Slides
# ============================================

if st.session_state.workflow_state == 'slides_import':
    st.header("Step 0: Import from Google Slides (Optional)")
    st.info("💡 Load slides from Google Slides, edit speaker notes, and generate a PDF. Or skip to upload your own PDF.")
    
    # Check Google authentication
    if "creds" not in st.session_state:
        st.warning("⚠️ Please authenticate with Google in the sidebar to import slides.")
        col1, col2 = st.columns(2)
        with col2:
            if st.button("⏭️ Skip to Upload PDF", type="secondary", width="stretch"):
                advance_workflow()
                st.rerun()
    else:
        # Slide Presentation ID Input
        presentation_id = st.text_input(
            "Google Slides Presentation ID:",
            placeholder="Enter the ID from the Google Slides URL",
            help="Find the ID in the URL: https://docs.google.com/presentation/d/[ID]/edit"
        )
        
        col1, col2 = st.columns([3, 1])
        with col1:
            load_slides_btn = st.button("📥 Load Slides", width="stretch")
        with col2:
            if st.button("⏭️ Skip", width="stretch"):
                advance_workflow()
                st.rerun()
        
        if load_slides_btn:
            if not presentation_id:
                st.warning("⚠️ Please enter a valid Presentation ID.")
            else:
                with st.spinner("Loading slides data..."):
                    try:
                        # Load slides using cached function
                        slides_data = get_slides_data_cached(presentation_id, st.session_state.creds)
                        
                        if slides_data is None:
                            st.error("Failed to load slides data. Please check the Presentation ID and permissions.")
                        else:
                            st.session_state.slides_data = slides_data
                            st.success(f"✅ Successfully loaded {len(slides_data)} slides!")
                            st.rerun()
                    except Exception as e:
                        st.error(f"Error loading slides: {e}")
        
        # Display and edit slides if data is available
        if st.session_state.slides_data:
            st.divider()
            st.subheader(f"📝 Edit Slides ({len(st.session_state.slides_data)} slides)")
            
            # Define callback to remove a slide
            def remove_slide(slide_index):
                """Remove a slide from slides_data and re-index."""
                st.session_state.slides_data = [
                    slide for slide in st.session_state.slides_data
                    if slide["index"] != slide_index
                ]
                # Re-index remaining slides
                for i, slide in enumerate(st.session_state.slides_data):
                    slide["index"] = i
            
            # Display each slide in an expander
            for slide in st.session_state.slides_data:
                slide_index = slide["index"]
                
                with st.expander(f"Slide {slide_index + 1}", expanded=False):
                    col1, col2, col3 = st.columns([2, 3, 1])
                    
                    with col1:
                        # Display slide thumbnail
                        if slide.get("png_base64"):
                            try:
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
                            width="stretch"
                        )
            
            # Generate PDF from slides
            st.divider()
            st.subheader("📄 Generate PDF")
            
            col1, col2 = st.columns([2, 1])
            with col1:
                if st.button("🎨 Create PDF from Slides", width="stretch"):
                    with st.spinner("Generating PDF..."):
                        try:
                            # Generate PDF from slides
                            pdf_base64 = slides_to_pdf(st.session_state.slides_data)
                            st.session_state.pdf_base64 = pdf_base64
                            st.success("✅ PDF generated successfully!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error generating PDF: {e}")
                            with st.expander("🔍 Error Details"):
                                st.code(traceback.format_exc())
            
            with col2:
                if "pdf_base64" in st.session_state and st.session_state.pdf_base64:
                    if st.button("▶️ Continue", width="stretch"):
                        advance_workflow()
                        st.rerun()
            
            # Display PDF preview if available
            if "pdf_base64" in st.session_state and st.session_state.pdf_base64:
                st.divider()
                st.subheader("📄 PDF Preview")
                
                # Decode base64 to bytes for display
                pdf_bytes = base64.b64decode(st.session_state.pdf_base64)
                
                # Display PDF using iframe
                pdf_display = f'<iframe src="data:application/pdf;base64,{st.session_state.pdf_base64}" width="100%" height="600px" type="application/pdf"></iframe>'
                st.markdown(pdf_display, unsafe_allow_html=True)
                
                # Download button
                st.download_button(
                    label="📥 Download PDF",
                    data=pdf_bytes,
                    file_name="slides_presentation.pdf",
                    mime="application/pdf",
                    width="stretch"
                )


# ============================================
# STEP 1: Upload PDF
# ============================================

elif st.session_state.workflow_state == 'upload':
    st.header("Step 1: Upload PDF Slide Deck")
    st.info("💡 Upload a PDF containing your educational slides. The AI will analyze each slide and generate voiceover scripts.")
    
    if "pdf_base64" in st.session_state and st.session_state.pdf_base64:
        st.success("✅ PDF already uploaded.")
        
        col1, col2 = st.columns([3, 1])
        with col1:
            st.caption("📄 Uploaded PDF Preview:")
            # Display PDF using iframe
            pdf_display = f'<iframe src="data:application/pdf;base64,{st.session_state.pdf_base64}" width="100%" height="600px" type="application/pdf"></iframe>'
            st.markdown(pdf_display, unsafe_allow_html=True)
        
        with col2:
            if st.button("▶️ Continue", width="stretch"):
                advance_workflow()
                st.rerun()
    else:
        uploaded_file = st.file_uploader(
            "Choose a PDF file",
            type=['pdf'],
            help="Upload a PDF file containing slides for voiceover generation"
        )
        
        if uploaded_file:
            pdf_data = process_pdf(uploaded_file.read())
            st.session_state.pdf_base64 = pdf_data['base64']
            
            col1, col2, col3 = st.columns([2, 2, 1])
            with col1:
                st.success(f"✅ **Uploaded:** {uploaded_file.name}")
            with col2:
                st.caption(f"📦 **Size:** {pdf_data['size']:,} bytes")
            with col3:
                if st.button("▶️ Next", width="stretch"):
                    advance_workflow()
                    st.rerun()
        else:
            st.warning("📤 Please upload a PDF file to continue")


# ============================================
# STEP 2: Generate & Review Voiceover
# ============================================

elif st.session_state.workflow_state == 'generate_voiceover':
    st.header("Step 2: Generate Voiceover Script")
    st.info("💡 The AI will analyze your PDF slides and generate a voiceover script for each slide.")
    
    if 'pdf_base64' not in st.session_state:
        st.error("❌ No PDF found. Please go back and upload a PDF.")
    else:
        if st.button(
            "🎬 Generate Voiceover Script",
            type="primary",
            disabled=st.session_state.is_processing,
            width="stretch"
        ):
            st.session_state.is_processing = True
            
            try:
                with st.status("Generating voiceover script...", expanded=True) as status:
                    # Get Gemini client
                    gemini_client = get_gemini_client()
                    
                    st.write("🤖 Calling Gemini API to analyze PDF...")
                    
                    # Direct API call - no agent, no runner, no async complexity
                    scenes = generate_voiceover_scenes(
                        gemini_client=gemini_client,
                        pdf_base64=st.session_state.pdf_base64
                    )
                    
                    # Store in session state
                    st.session_state.scenes = scenes
                    
                    st.write(f"✅ Generated {len(scenes)} scenes!")
                    status.update(label="✅ Voiceover generation complete!", state="complete")
                
                st.session_state.is_processing = False
                # advance_workflow()
                st.rerun()
                
            except Exception as e:
                st.session_state.is_processing = False
                st.error(f"❌ Error generating voiceover: {str(e)}")
                
                with st.expander("🔍 Error Details"):
                    st.code(traceback.format_exc())
                
                if st.button("🔄 Retry Voiceover"):
                    st.rerun()


# elif st.session_state.workflow_state == 'review_voiceover':
    # st.header("Step 3: Review & Edit Voiceover Script")
    
    if 'scenes' in st.session_state and st.session_state.scenes:
        st.info(f"💡 Review and edit the {len(st.session_state.scenes)} generated scenes. Make any changes you'd like before continuing.")
        
        # Editable scenes
        edited_scenes = []
        for i, scene in enumerate(st.session_state.scenes):
            with st.expander(
                f"🎬 Scene {i+1}: {scene.get('comment', '')[:60]}...",
                expanded=True
            ):
                col1, col2 = st.columns([1, 3])
                
                with col1:
                    st.caption("**Scene Description**")
                    edited_comment = st.text_area(
                        "Comment",
                        value=scene.get('comment', ''),
                        key=f"comment_{i}",
                        height=80,
                        label_visibility="collapsed",
                        help="Brief description of this scene"
                    )
                
                with col2:
                    st.caption("**Voiceover Text**")
                    edited_speech = st.text_area(
                        "Speech",
                        value=scene.get('speech', ''),
                        key=f"speech_{i}",
                        height=120,
                        label_visibility="collapsed",
                        help="Edit the voiceover script"
                    )
                
                st.caption(f"📏 {len(edited_speech)} characters")
                
                edited_scenes.append({
                    'comment': edited_comment,
                    'speech': edited_speech
                })
        
        # Action buttons
        st.divider()
        col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
        
        with col1:
            if st.button("💾 Save Edits", width="stretch"):
                st.session_state.scenes = edited_scenes
                st.success("✅ Edits saved!")
        
        with col2:
            if st.button("🔄 Regenerate Script", width="stretch"):
                st.session_state.workflow_state = 'generate_voiceover'
                st.rerun()
        
        with col3:
            voiceover_approved = st.checkbox(
                "✓ Approve & Continue",
                help="Check to approve and proceed to audio tag generation"
            )
        
        with col4:
            if st.button("▶️", disabled=not voiceover_approved, width="stretch", type="primary"):
                # Save final edits before continuing
                st.session_state.scenes = edited_scenes
                advance_workflow()
                st.rerun()


# ============================================
# STEP 3: Add Audio Tags (ElevenLabs) & Review
# ============================================

elif st.session_state.workflow_state == 'add_audio_tags':
    st.header("Step 4: Add ElevenLabs Audio Tags")
    st.info("💡 The AI will enhance your voiceover script with ElevenLabs audio tags for expressive speech.")
    
    if 'scenes' in st.session_state and st.session_state.scenes:
        if st.button(
            "🎨 Add Audio Tags",
            type="primary",
            disabled=st.session_state.is_processing,
            width="stretch"
        ):
            st.session_state.is_processing = True
            
            try:
                with st.status("Adding audio tags...", expanded=True) as status:
                    gemini_client = get_gemini_client()
                    
                    st.write("🤖 Calling Gemini API to enhance voiceover...")
                    
                    # Direct API call
                    refined_scenes = add_elevenlabs_tags(
                        gemini_client=gemini_client,
                        scenes=st.session_state.scenes
                    )
                    
                    st.session_state.refined_scenes = refined_scenes
                    
                    st.write(f"✅ Enhanced {len(refined_scenes)} scenes!")
                    status.update(label="✅ Audio tags complete!", state="complete")
                
                st.session_state.is_processing = False
                # advance_workflow()
                st.rerun()
                
            except Exception as e:
                st.session_state.is_processing = False
                st.error(f"❌ Error: {str(e)}")
                with st.expander("🔍 Error Details"):
                    st.code(traceback.format_exc())
                
                if st.button("🔄 Retry Audio Tags"):
                    st.rerun()


# elif st.session_state.workflow_state == 'review_final':
#     st.header("Step 5: Review Final Script with Audio Tags")
    
    if 'refined_scenes' in st.session_state and st.session_state.refined_scenes:
        st.info(f"💡 Review the final scripts with audio tags. You can edit the tags before exporting.")
        
        # Editable refined scenes
        edited_refined = []
        for i, scene in enumerate(st.session_state.refined_scenes):
            with st.expander(
                f"🎬 Scene {i+1}: {scene.get('comment', '')[:60]}...",
                expanded=True
            ):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.caption("**Original Speech**")
                    st.text_area(
                        "Original",
                        value=scene.get('speech', ''),
                        key=f"orig_{i}",
                        height=100,
                        disabled=True,
                        label_visibility="collapsed"
                    )
                
                with col2:
                    st.caption("**With Audio Tags**")
                    edited_elevenlabs = st.text_area(
                        "ElevenLabs",
                        value=scene.get('elevenlabs', ''),
                        key=f"elevenlabs_{i}",
                        height=120,
                        label_visibility="collapsed",
                        help="Edit audio tags and text"
                    )
                
                st.caption(f"📏 Enhanced version: {len(edited_elevenlabs)} characters")
                
                edited_refined.append({
                    'comment': scene.get('comment', ''),
                    'speech': scene.get('speech', ''),
                    'elevenlabs': edited_elevenlabs
                })
        
        # Action buttons
        st.divider()
        col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
        
        with col1:
            if st.button("💾 Save Final Edits", width="stretch"):
                st.session_state.refined_scenes = edited_refined
                st.success("✅ Final edits saved!")
        
        with col2:
            if st.button("🔄 Regenerate Tags", width="stretch"):
                st.session_state.workflow_state = 'add_audio_tags'
                st.rerun()
        
        with col3:
            final_approved = st.checkbox(
                "✓ Final Approval",
                help="Check to approve and enable export"
            )
        
        with col4:
            if st.button("▶️", disabled=not final_approved, width="stretch", type="primary"):
                # Save before export
                st.session_state.refined_scenes = edited_refined
                advance_workflow()
                st.rerun()


# ============================================
# STEP 6: Export
# ============================================

elif st.session_state.workflow_state == 'export':
    st.header("Step 6: Export Results")
    st.success("🎉 Pipeline complete! Your voiceover scripts are ready.")
    
    if 'refined_scenes' in st.session_state:
        # Summary
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Scenes", len(st.session_state.refined_scenes))
        with col2:
            total_chars = sum(len(s.get('elevenlabs', '')) for s in st.session_state.refined_scenes)
            st.metric("Total Characters", f"{total_chars:,}")
        with col3:
            avg_chars = total_chars // len(st.session_state.refined_scenes) if st.session_state.refined_scenes else 0
            st.metric("Avg per Scene", f"{avg_chars:,}")
        
        st.divider()
        
        # Export options
        st.subheader("📥 Download Options")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # JSON export
            output_json = {
                'scenes': st.session_state.refined_scenes,
                'metadata': {
                    'total_scenes': len(st.session_state.refined_scenes)
                }
            }
            
            st.download_button(
                label="📄 Download JSON",
                data=json.dumps(output_json, indent=2),
                file_name="voiceover_scenes.json",
                mime="application/json",
                width="stretch"
            )
        
        with col2:
            # Text export (script only)
            script_text = "\n\n".join([
                f"Scene {i+1}: {scene.get('comment', '')}\n{scene.get('elevenlabs', '')}"
                for i, scene in enumerate(st.session_state.refined_scenes)
            ])
            
            st.download_button(
                label="📝 Download Script (TXT)",
                data=script_text,
                file_name="voiceover_script.txt",
                mime="text/plain",
                width="stretch"
            )
        
        st.divider()
        
        # Preview
        with st.expander("👁️ Preview Final Scenes"):
            for i, scene in enumerate(st.session_state.refined_scenes):
                st.markdown(f"**Scene {i+1}:** {scene.get('comment', '')}")
                st.code(scene.get('elevenlabs', ''), language=None)
                st.divider()
        
        # Start over
        if st.button("🔄 Create New Project", width="stretch", type="primary"):
            reset_workflow()
            st.rerun()


# ============================================
# STEP 7: Debug - Session State Inspector
# ============================================

elif st.session_state.workflow_state == 'debug':
    st.header("Step 7: Debug - Session State Inspector")
    st.info("💡 View all session state variables and their values for debugging purposes.")
    
    # Overview metrics
    st.subheader("📊 Session Overview")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Session State Keys", len(st.session_state.keys()))
    
    with col2:
        workflow_step = WORKFLOW_STATES[st.session_state.workflow_state]['step']
        st.metric("Current Workflow Step", f"{workflow_step}/{len(WORKFLOW_STATES) - 1}")
    
    with col3:
        has_pdf = "✅" if "pdf_base64" in st.session_state and st.session_state.pdf_base64 else "❌"
        st.metric("PDF Loaded", has_pdf)
    
    st.divider()
    
    # Display full session state
    st.subheader("🔍 Full Session State")
    
    # Create a JSON-serializable version of session state
    session_state_dict = {}
    for key in st.session_state.keys():
        value = st.session_state[key]
        
        # Handle non-serializable objects
        if key in ['session_service', 'adk_session', 'creds']:
            session_state_dict[key] = f"<{type(value).__name__} object>"
        elif key == 'pdf_base64' and value:
            # Truncate base64 data for display
            session_state_dict[key] = f"<base64 data, {len(value)} chars>"
        elif key == 'slides_data' and value:
            # Show summary of slides data
            session_state_dict[key] = {
                "type": "list of slides",
                "count": len(value),
                "sample": value[0] if value else None
            }
        elif isinstance(value, (str, int, float, bool, type(None))):
            session_state_dict[key] = value
        elif isinstance(value, (list, dict)):
            session_state_dict[key] = value
        else:
            session_state_dict[key] = f"<{type(value).__name__}>"
    
    # Use st.json for pretty display
    st.json(session_state_dict)
    
    st.divider()
    
    # Individual key inspection
    st.subheader("🔎 Inspect Individual Keys")
    
    # Filter options
    show_all = st.checkbox("Show all keys (including internal)", value=False)
    
    # Get keys to display
    all_keys = sorted(st.session_state.keys())
    internal_keys = ['session_service', 'adk_session', 'creds', 'FormSubmitter']
    
    if show_all:
        display_keys = all_keys
    else:
        display_keys = [k for k in all_keys if not any(internal in k for internal in internal_keys)]
    
    # Select a key to inspect
    if display_keys:
        selected_key = st.selectbox("Select a key to inspect:", display_keys)
        
        if selected_key:
            st.markdown(f"**Key:** `{selected_key}`")
            st.markdown(f"**Type:** `{type(st.session_state[selected_key]).__name__}`")
            
            value = st.session_state[selected_key]
            
            # Display value based on type
            if isinstance(value, (str, int, float, bool, type(None))):
                st.write("**Value:**")
                st.code(str(value))
            elif isinstance(value, dict):
                st.write("**Value (JSON):**")
                st.json(value)
            elif isinstance(value, list):
                st.write(f"**Value (List with {len(value)} items):**")
                st.json(value)
            else:
                st.write("**Value:**")
                st.write(value)
    else:
        st.info("No session state keys to display")
    
    st.divider()
    
    # Actions
    st.subheader("⚙️ Actions")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🏠 Go to Start", width="stretch"):
            st.session_state.workflow_state = 'slides_import'
            st.rerun()
    
    with col2:
        if st.button("🔄 Reset Workflow", width="stretch"):
            reset_workflow()
            st.rerun()
    
    with col3:
        if st.button("📥 Go to Export", width="stretch"):
            st.session_state.workflow_state = 'export'
            st.rerun()

