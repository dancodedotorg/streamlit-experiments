import streamlit as st
from google import genai
from google.genai import types

# --- SESSION STATE INITIALIZATION ---
if "api_key" not in st.session_state:
    st.session_state.api_key = ""
if "messages" not in st.session_state:
    st.session_state.messages = []

# --- SIDEBAR: API KEY INPUT ---
with st.sidebar:
    st.header("Configuration")
    api_key = st.text_input(
        "Enter your Gemini API Key:",
        type="password",
        value=st.session_state.api_key,
        key="api_key_input"
    )
    if st.button("Save API Key"):
        st.session_state.api_key = api_key
        st.rerun()
    
    if st.session_state.api_key:
        st.success("API Key configured ✓")
    else:
        st.info("Please enter your API key to use the chat")

# --- MAIN SCREEN: CHAT INTERFACE ---
st.title("🧮 Math Assistant")

# Check if API key is present
if not st.session_state.api_key:
    st.warning("⚠️ Please enter a valid Gemini API Key in the sidebar to start chatting.")
else:
    # Initialize Gemini client
    client = genai.Client(api_key=st.session_state.api_key)

    # Display chat history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # File Uploader Container
    with st.container():
        uploaded_files = st.file_uploader(
            "Attach materials",
            type=["png", "jpg", "jpeg", "pdf", "mp4", "wav", "mp3"],
            accept_multiple_files=True,
            label_visibility="collapsed",
            key="file_uploader"
        )

    # Chat Input
    if prompt := st.chat_input("Ask a math question..."):
        # 1. Store and display user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # 2. Prepare multimodal content
        content_to_send = [prompt]
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