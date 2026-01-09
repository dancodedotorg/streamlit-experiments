import streamlit as st
import traceback
from voiceover_main import get_gemini_client
from helpers.gemini_helpers import add_elevenlabs_tags

def app_page():
    st.header("Step 3: Add ElevenLabs Audio Tags")
    st.info("💡 The AI will enhance your voiceover script with ElevenLabs audio tags for expressive speech.")
    
    if 'scenes' not in st.session_state or not st.session_state.scenes:
        st.warning("⚠️ No scenes found to process. Please generate voiceover script first.")
        return

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
                st.session_state.scenes = refined_scenes
                
                st.write(f"✅ Enhanced {len(refined_scenes)} scenes!")
                status.update(label="✅ Audio tags complete!", state="complete")
            
            st.session_state.is_processing = False
            st.rerun()
            
        except Exception as e:
            st.session_state.is_processing = False
            st.error(f"❌ Error: {str(e)}")
            with st.expander("🔍 Error Details"):
                st.code(traceback.format_exc())
            
            if st.button("🔄 Retry Audio Tags"):
                st.rerun()

    if 'refined_scenes' in st.session_state and st.session_state.refined_scenes:
        st.divider()
        st.subheader("📝 Review Final Script with Audio Tags")
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
                # This effectively re-runs the current page, triggering regeneration
                st.session_state.is_processing = False # Reset for next attempt
                st.session_state.refined_scenes = None # Clear old refined scenes to force regeneration
                st.rerun()
        
        with col3:
            final_approved = st.checkbox(
                "✓ Final Approval",
                help="Check to approve and enable export"
            )
        
        with col4:
            if st.button(
                "▶️ Continue",
                disabled=not final_approved,
                width="stretch"
            ):
                st.switch_page("custom_pages/generate_elevenlabs_audio.py")

app_page()
