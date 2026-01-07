import streamlit as st
from google import genai

# --- 1. SESSION STATE INITIALIZATION ---
if "step" not in st.session_state:
    st.session_state.step = "get_name"
if "user_name" not in st.session_state:
    st.session_state.user_name = ""
if "api_key" not in st.session_state:
    st.session_state.api_key = ""
if "messages" not in st.session_state:
    st.session_state.messages = []

# --- ONBOARDING LOGIC (Simplified for brevity) ---
if st.session_state.step == "get_name":
    st.title("Welcome! 👋")
    name = st.text_input("Please enter your name:")
    if st.button("Submit Name"):
        st.session_state.user_name = name
        st.session_state.step = "get_key"
        st.rerun()

elif st.session_state.step == "get_key":
    st.title(f"Hello, {st.session_state.user_name}!")
    api_key = st.text_input("Enter your Gemini API Key:", type="password")
    if st.button("Submit Key"):
        st.session_state.api_key = api_key
        st.session_state.step = "chat"
        st.rerun()

# --- THE STREAMING MULTIMODAL INTERFACE ---
elif st.session_state.step == "chat":
    st.title("🧮 Math Assistant")
    
    client = genai.Client(api_key=st.session_state.api_key)

    # Display History
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
            key="file_uploader" # Specific key to track the widget
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
                content_to_send.append({
                    "mime_type": uploaded_file.type,
                    "data": file_bytes
                })

        # 3. Stream the Assistant response
        with st.chat_message("assistant"):
            try:
                # Define a generator for Streamlit to consume
                def stream_generator():
                    for chunk in client.models.generate_content_stream(
                            model="gemini-2.5-flash",
                            config={
                                "system_instruction": f"Help {st.session_state.user_name} with math homework."
                            },
                            contents=content_to_send,
                        ):
                        yield chunk.text

                # Use st.write_stream to handle the chunks and cursor
                full_response = st.write_stream(stream_generator())
                
                # Save full response to history
                st.session_state.messages.append({"role": "assistant", "content": full_response})
                
            except Exception as e:
                st.error(f"API Error: {e}")