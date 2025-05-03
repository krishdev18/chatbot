import os
import sqlite3
import tempfile
import streamlit as st
from langchain.chains import create_sql_query_chain
from langchain_community.utilities import SQLDatabase
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq

# --- Page Configuration ---
st.set_page_config(page_title="SQL Chatbot", page_icon="🔎", layout="wide")

# --- Custom Styling to Keep Input Bar & Voice Button Fixed at Bottom ---
st.markdown("""
     <style>
        .chat-container {position: fixed !important; bottom: 0px; width: 90%; left: 5%; right: 5%; display: flex; align-items: center;background-color: #f8f9fa;padding: 10px;
            border-radius: 8px;}
        .chat-input {flex-grow: 1; padding: 10px; border-radius: 8px;}
        .voice-btn {background-color: #4CAF50; color: white; padding: 8px 12px; border-radius: 8px; cursor: pointer; margin-left: 10px;}
    </style>
    """, unsafe_allow_html=True)

# --- Page Header ---
st.title("SQL Chatbot with Chat Format & Voice Input")
st.markdown("Upload your `.sql` file and query it with natural language.")

# --- Sidebar Configuration ---
with st.sidebar:
    st.header("LLM Configuration")
    groq_api_key = st.text_input("🔑 Groq API Key", type="password")

# --- File Upload Section ---
uploaded_file = st.file_uploader("📂 Upload your MySQL .sql file", type=["sql"])

# --- Check if Speech Should Be Enabled (based on environment variable) ---
use_voice = os.getenv("USE_VOICE", "True") == "True"  # Default to True, but you can set this to False in the cloud

# --- Speech-to-Text (STT) Function (Disabled in Cloud) ---
def get_voice_input():
    if use_voice:  # Only enable voice input if the flag is set
        import speech_recognition as sr
        recognizer = sr.Recognizer()
        with sr.Microphone() as source:
            st.info("🎙 Speak now...")
            recognizer.adjust_for_ambient_noise(source)
            audio = recognizer.listen(source)

        try:
            query = recognizer.recognize_google(audio)
            st.success(f"🗣 You said: {query}")
            return query
        except sr.UnknownValueError:
            st.warning("⚠️ Could not understand the audio. Try again.")
            return None
        except sr.RequestError:
            st.error("❌ Error with Google Speech Recognition API.")
            return None
    else:
        return None  # Return None if voice input is disabled

# --- Text-to-Speech (TTS) Function (Disabled in Cloud) ---
def speak_text(text):
    if use_voice:  # Only enable TTS if the flag is set
        import pyttsx3
        engine = pyttsx3.init()
        engine.say(text)
        engine.runAndWait()
    else:
        pass  # Skip TTS if it's disabled

# --- Chat History ---
if "messages" not in st.session_state:
    st.session_state.messages = []

# --- Main Logic ---
if groq_api_key:
    os.environ["GROQ_API_KEY"] = groq_api_key

    if uploaded_file:
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp_file:
                db_path = tmp_file.name

            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            sql_script = uploaded_file.read().decode("utf-8")
            cursor.executescript(sql_script)
            conn.commit()
            conn.close()

            db = SQLDatabase.from_uri(f"sqlite:///{db_path}")
            llm = ChatGroq(temperature=0, model_name="compound-beta-mini")  
            prompt = ChatPromptTemplate.from_messages([
                ("system", "You are a data assistant. Write SQL for this database:\n{schema}"),
                ("human", "{question}"),
            ])
            sql_chain = prompt | llm | StrOutputParser()

            st.success("✅ Database loaded and ready!")

            # --- Input Bar (Stays at Bottom) ---
            with st.container():
                for msg in st.session_state.messages[-5:]:
                    with st.chat_message(msg["role"]):
                        st.markdown(msg["content"])

            col1, col2 = st.columns([5, 1])  # Ensuring voice button stays inline

            with col1:
                user_question = st.chat_input("Ask a question about your data")  # Main input field

            with col2:
                if use_voice:  # Only show the voice button if it's enabled
                    if st.button("🎙 Speak"):
                        voice_text = get_voice_input()
                        if voice_text:
                            user_question = voice_text  # ✅ Use voice input directly

            if user_question:
                st.session_state.messages.append({"role": "user", "content": user_question})

                with st.chat_message("user"):
                    st.markdown(user_question)

                try:
                    schema = db.get_table_info()
                    query = sql_chain.invoke({"question": user_question, "schema": schema})

                    response_message = f"Here is your SQL query:\n```sql\n{query}\n```"
                    st.session_state.messages.append({"role": "assistant", "content": response_message})

                    with st.chat_message("assistant"):
                        st.markdown(response_message)

                    result = db.run(query)
                    st.dataframe(result)

                    speak_text(f"Here is your SQL query: {query}")

                except Exception:
                    error_message = " Ask more questions about your database."
                    st.session_state.messages.append({"role": "assistant", "content": error_message})

                    with st.chat_message("assistant"):
                        st.markdown(error_message)

        except Exception as e:
            st.error(f"❌ Failed to process SQL file: {e}")

else:
    st.info("⬅ Upload a `.sql` file and enter your Groq API key to begin.")
