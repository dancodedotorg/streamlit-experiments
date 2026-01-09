import streamlit as st
import traceback
from voiceover_main import get_gemini_client
from helpers.gemini_helpers import generate_voiceover_scenes

def app_page():
    st.header("Step 2: Generate Voiceover Script")
    st.info("💡 The AI will analyze your PDF slides and generate a voiceover script for each slide.")
    
    if 'pdf_base64' not in st.session_state:
        st.error("❌ No PDF found in session. Please go back and upload a PDF.")
        if st.button("Upload PDF", type="secondary"):
            st.switch_page("custom_pages/upload.py")
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
                    # add empty 'html' property to each scene for later use
                    for scene in scenes:
                        scene['html'] = ''
                    
                    st.write(f"✅ Generated {len(scenes)} scenes!")
                    status.update(label="✅ Voiceover generation complete!", state="complete")
                
                st.session_state.is_processing = False
                st.rerun()
                
            except Exception as e:
                st.session_state.is_processing = False
                st.error(f"❌ Error generating voiceover: {str(e)}")
                
                with st.expander("🔍 Error Details"):
                    st.code(traceback.format_exc())
                
                if st.button("🔄 Retry Voiceover"):
                    st.rerun()

        if 'scenes' in st.session_state and st.session_state.scenes:
            st.divider()
            st.subheader("📝 Review & Edit Voiceover Script")

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
                    # This effectively re-runs the current page, triggering regeneration
                    st.session_state.is_processing = False # Reset for next attempt
                    st.rerun()
            
            with col3:
                voiceover_approved = st.checkbox(
                    "✓ Approve & Continue",
                    help="Check to approve and proceed to audio tag generation"
                )
            
            with col4:
                if st.button(
                    "▶️ Continue",
                    disabled=not voiceover_approved,
                    width="stretch"
                ):
                    st.switch_page("custom_pages/add_audio_tags.py")

app_page()
