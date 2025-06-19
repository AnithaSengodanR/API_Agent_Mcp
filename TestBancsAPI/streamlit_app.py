import streamlit as st
from llm_chat_agent import agent_executor

st.title("BaNCS API Chatbot")
st.markdown("Interact with your Bancs API via LLM and tools!")

# Store chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat history
for message in st.session_state.messages:
    st.chat_message(message["role"]).write(message["content"])

# User input
user_input = st.chat_input("Ask something like 'Create an account for user John'")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    st.chat_message("user").write(user_input)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                result = agent_executor.invoke({"input": user_input})
                st.session_state.messages.append({"role": "assistant", "content": str(result)})
                st.write(result)
            except Exception as e:
                st.session_state.messages.append({"role": "assistant", "content": str(e)})
                st.error(f"Error: {str(e)}")
