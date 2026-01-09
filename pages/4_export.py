import streamlit as st
import json

def app_page():
    st.header("Step 4: Export Results")

    if 'refined_scenes' not in st.session_state or not st.session_state.refined_scenes:
        st.warning("⚠️ No refined scenes found to export. Please complete previous steps first.")
        return
    
    if 'refined_scenes' in st.session_state and st.session_state.refined_scenes:
        st.success("🎉 Pipeline complete! Your voiceover scripts are ready.")
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
                use_container_width=True
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
                use_container_width=True
            )
        
        st.divider()
        
        # Preview
        with st.expander("👁️ Preview Final Scenes"):
            for i, scene in enumerate(st.session_state.refined_scenes):
                st.markdown(f"**Scene {i+1}:** {scene.get('comment', '')}")
                st.code(scene.get('elevenlabs', ''), language=None)
                st.divider()
        
        # Start over button. This will reset relevant session state and navigate to the first page.
        if st.button("🔄 Create New Project", use_container_width=True, type="primary"):
            # Clear relevant session state here
            for key in ['slides_data', 'pdf_base64', 'scenes', 'refined_scenes', 'voiceover_approved', 'final_approved']:
                if key in st.session_state:
                    del st.session_state[key]
            # Rerun to clear page content and implicitely refresh navigation to main
            st.page_link("voiceover_main.py", label="") # Navigate to the initial page
            st.rerun()

app_page()
