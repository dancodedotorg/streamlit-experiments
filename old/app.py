import streamlit as st
import json
from google_auth_oauthlib.flow import Flow
import base64
from helpers.google_slides_helpers import get_slides_data_cached, slides_to_pdf

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="Google Slides Manager",
    page_icon="📊",
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

# --- SESSION STATE INITIALIZATION ---
if "slides_data" not in st.session_state:
    st.session_state.slides_data = None

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

# --- SIDEBAR: GOOGLE AUTHENTICATION ---
with st.sidebar:
    st.header("Configuration")
    
    # Google Authentication
    st.subheader("Google Authentication")
    
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
st.title("📊 Google Slides Manager")

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
                    width="stretch"
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
    
    # PDF Generation
    st.divider()
    if st.button("Create PDF", type="primary"):
        with st.spinner("Generating PDF..."):
            try:
                # Call slides_to_pdf function
                pdf_base64 = slides_to_pdf(st.session_state.slides_data)
                st.session_state.pdf_base64 = pdf_base64
                st.success("✅ PDF generated successfully!")
                st.rerun()
            except Exception as e:
                st.error(f"Error generating PDF: {e}")
    
    # Display PDF if available
    if "pdf_base64" in st.session_state and st.session_state.pdf_base64:
        st.subheader("Generated PDF")
        # Decode base64 to bytes for display
        pdf_bytes = base64.b64decode(st.session_state.pdf_base64)
        
        # Display PDF using iframe with data URI
        pdf_display = f'<iframe src="data:application/pdf;base64,{st.session_state.pdf_base64}" width="100%" height="800px" type="application/pdf"></iframe>'
        st.markdown(pdf_display, unsafe_allow_html=True)
        
        # Also provide download button
        st.download_button(
            label="📥 Download PDF",
            data=pdf_bytes,
            file_name="slides_presentation.pdf",
            mime="application/pdf"
        )
else:
    st.info("Load a Google Slides presentation to manage slides and speaker notes.")