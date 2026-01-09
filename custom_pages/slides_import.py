import streamlit as st
import base64
import traceback
from helpers.google_slides_helpers import get_slides_data_cached, slides_to_pdf
# Assuming google auth flow is handled in main app and creds are in session state

def app_page():
    st.header("Step 0: Import from Google Slides (Optional)")
    st.info("💡 Load slides from Google Slides, edit speaker notes, and generate a PDF. Or skip to upload your own PDF.")
    
    # Check Google authentication
    if "creds" not in st.session_state:
        st.warning("⚠️ Please authenticate with Google in main page to import slides.")
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
            if st.button("⏭️ Skip to Upload", width="stretch"):
                st.switch_page("custom_pages/upload.py")
        
        if load_slides_btn:
            if not presentation_id:
                st.warning("⚠️ Please enter a valid Presentation ID.")
            else:
                with st.spinner("Loading slides data..."):
                    try:
                        # Load slides using cached function
                        # Assumes get_google_oauth_flow or similar is available from main and creds are in session_state
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
            def remove_slide_callback(slide_index):
                """Remove a slide from slides_data and re-index."""
                st.session_state.slides_data = [
                    slide for slide in st.session_state.slides_data
                    if slide["index"] != slide_index
                ]
                # Re-index remaining slides
                for i, slide in enumerate(st.session_state.slides_data):
                    slide["index"] = i
            
            # Display each slide in an expander
            for idx, slide_item in enumerate(st.session_state.slides_data):
                # Use a copy for display to avoid modifying object during iteration, if necessary
                slide = slide_item.copy()
                slide_index = slide["index"]
                
                with st.expander(f"Slide {idx + 1}", expanded=True):
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
                        # Assign unique key to text_area
                        new_notes = st.text_area(
                            "Edit notes:",
                            value=slide.get("notes", ""),
                            height=150,
                            key=f"notes_{slide_index}",
                            label_visibility="collapsed"
                        )
                        # Update notes in current slide_item (original object reference)
                        st.session_state.slides_data[idx]["notes"] = new_notes
                    
                    with col3:
                        st.button(
                            "🗑️ Remove",
                            key=f"remove_{idx}", # Use idx for unique key
                            on_click=remove_slide_callback,
                            args=(idx,), # Pass idx to callback to remove the correct slide
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
                    if st.button("▶️ Continue to Upload", width="stretch"):
                        st.switch_page("custom_pages/upload.py")
            
            # Display PDF preview if available
            if "pdf_base64" in st.session_state and st.session_state.pdf_base64:
                st.divider()
                st.subheader("📄 PDF Preview")
                
                # Decode base64 to bytes for display
                bytes = base64.b64decode(st.session_state.pdf_base64)
                st.pdf(bytes, height=700)
                
                # Download button
                st.download_button(
                    label="📥 Download PDF",
                    data=pdf_bytes,
                    file_name="slides_presentation.pdf",
                    mime="application/pdf",
                    width="stretch"
                )

app_page()
