import streamlit as st
import json
import uuid # Although not used directly in debug, kept for consistency if needed for keys

def app_page():
    st.header("Step 5: Debug - Session State Inspector")
    st.info("💡 View all session state variables and their values for debugging purposes.")
    
    # Overview metrics
    st.subheader("📊 Session Overview")
    col1, col2 = st.columns(2)
    
    with col1:
        st.metric("Session State Keys", len(st.session_state.keys()))
    
    with col2:
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
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🏠 Go to Start", width="stretch"):
            # Clear relevant session state here for a fresh start for the workflow
            for key in ['slides_data', 'pdf_base64', 'scenes', 'refined_scenes', 'voiceover_approved', 'final_approved']:
                if key in st.session_state:
                    del st.session_state[key]
            st.page_link("voiceover_main.py", label="", icon="🏠")
            st.rerun()

    with col2:
        if st.button("🔄 Reset All Session State Here", width="stretch"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.success("Session reset!")
            st.rerun()

app_page()
