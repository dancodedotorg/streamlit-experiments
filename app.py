import streamlit as st
from google import genai

# --- 1. SESSION STATE INITIALIZATION ---
# This tracks where the user is in the onboarding process
if "step" not in st.session_state:
    st.session_state.step = "get_name"
if "user_name" not in st.session_state:
    st.session_state.user_name = ""
if "api_key" not in st.session_state:
    st.session_state.api_key = ""
if "messages" not in st.session_state:
    st.session_state.messages = []

st.set_page_config(page_title="Math Homework Helper", layout="centered")

# --- 2. STEP 1: GET USER NAME ---
if st.session_state.step == "get_name":
    st.title("Welcome! 👋")
    name = st.text_input("Please enter your name:")
    if st.button("Submit Name"):
        if name:
            st.session_state.user_name = name
            st.session_state.step = "get_key"
            st.rerun() # Forces the script to restart and move to the next 'if' block
        else:
            st.warning("Please enter a name to continue.")

# --- 3. STEP 2: GET API KEY ---
elif st.session_state.step == "get_key":
    st.title(f"Hello, {st.session_state.user_name}!")
    api_key = st.text_input("Enter your Gemini API Key:", type="password")
    st.caption("Your key is stored locally in your session and not saved to a database.")
    
    if st.button("Submit Key"):
        if api_key.startswith("AIza"): # Simple validation
            st.session_state.api_key = api_key
            st.session_state.step = "chat"
            st.rerun()
        else:
            st.error("Invalid API key format. Please try again.")

# --- 4. STEP 3: THE CHAT INTERFACE ---
elif st.session_state.step == "chat":
    st.title("🧮 Math Homework Assistant")
    st.info(f"Logged in as: **{st.session_state.user_name}**")

    # Initialize the Gemini Client
    client = genai.Client(api_key=st.session_state.api_key)
    
    # Display Chat History
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Chat Input
    if prompt := st.chat_input("Ask a math question..."):
        # Add user message to UI and state
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Generate Response
        with st.chat_message("assistant"):
            try:
                # We include the system prompt in the content generation
                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    config={
                        "system_instruction": f"Help {st.session_state.user_name} with math homework. Be encouraging and show steps."
                    },
                    contents=prompt
                )
                
                output_text = response.text
                st.markdown(output_text)
                
                # Add to history
                st.session_state.messages.append({"role": "assistant", "content": output_text})
            except Exception as e:
                st.error(f"An error occurred: {e}")

    # Reset Button (Optional)
    if st.sidebar.button("Clear Session / Log Out"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()