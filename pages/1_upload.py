import streamlit as st
import base64
from voiceover_main import process_pdf # Assuming process_pdf is in voiceover_main.py

def app_page():
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
            # Link to the next step
            st.page_link("pages/2_generate_voiceover.py", label="▶️ Continue", width="stretch")
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
                # Link to the next step
                st.page_link("pages/2_generate_voiceover.py", label="▶️ Next", width="stretch")
        else:
            st.warning("📤 Please upload a PDF file to continue")

app_page()
