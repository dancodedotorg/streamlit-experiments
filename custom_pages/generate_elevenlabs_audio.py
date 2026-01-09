import streamlit as st
import traceback
from helpers.elevenlabs_helpers import get_elevenlabs_client, elevenlabs_generation

def app_page():
    st.header("Generate Elevenlabs Audio MP3")
    st.info("Generate audio files using Elevenlabs for your voiceover script.")
    st.warning("⚠️ This Uses Elevenlabs Credits!!!! Be careful!")

    if "elevenlabs_api_key" not in st.session_state or not st.session_state.elevenlabs_api_key:
        st.error("❌ Elevenlabs API key not found. Please set it in the settings page.")
        return

    if "refined_scenes" not in st.session_state or not st.session_state.refined_scenes:
        st.error("❌ No refined scenes found. Please add audio tags first.")
        return

    option = st.selectbox(
        label="Select Voice",
        options=["Dan", "Sam", "Adam", "Hope"],
        key="selected_voice",
        help="Choose the Elevenlabs voice for audio generation."
    )

    if st.button(
        "Generate Audio with Elevenlabs",
        type="primary",
        disabled=st.session_state.is_processing,
        width="stretch"
    ):
        st.session_state.is_processing = True
        
        try:
            with st.status("Generating Audio...", expanded=True) as status:
                elevenlabs_client = get_elevenlabs_client()
                
                st.write("🤖 Calling Elevenlabs audio generation...")
                
                # Direct API call
                script_obj = {
                    'scenes': st.session_state.scenes
                }
                audio_obj = elevenlabs_generation(
                    elevenlabs_client,
                    script_obj=script_obj, 
                    voice_name=option
                    )

                
                st.session_state.audio_scenes = audio_obj.get('scenes', [])
                st.session_state.scenes = audio_obj.get('scenes', [])
                st.session_state.audio = audio_obj.get('audio', None)
            
            st.session_state.is_processing = False
            st.rerun()
            
        except Exception as e:
            st.session_state.is_processing = False
            st.error(f"❌ Error: {str(e)}")
            with st.expander("🔍 Error Details"):
                st.code(traceback.format_exc())
            
            if st.button("🔄 Retry Audio Generation"):
                st.rerun()

    if 'audio' in st.session_state and st.session_state.audio:
        st.divider()
        st.subheader("Listen to Generated Audio")
        st.audio(
            st.session_state.audio,
            format="audio/mpeg",
            start_time=0
        )
        
        # Action buttons
        st.divider()
        if st.button(
            "▶️ Continue",
            disabled='audio' not in st.session_state or not st.session_state.audio,
            width="stretch"
        ):
            st.switch_page("custom_pages/export.py")

app_page()
