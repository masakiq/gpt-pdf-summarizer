import io
from typing import Optional

import requests
import sqlite3
import streamlit as st
from services.conversations import Conversations
from services.summary_service import continue_conversation, set_openai_api_key
from streamlit_chat import message as chat_message
from langchain import OpenAI, SQLDatabase, SQLDatabaseChain
from langchain import PromptTemplate


@st.cache_resource
def handle_pdf_upload(pdf_file: io.BytesIO) -> Optional[Conversations]:
    if pdf_file is not None:
        files = {"pdf_file": pdf_file.getvalue()}
        response = requests.post(
            "http://localhost:8001/upload_pdf/",
            files=files
        )
        response.raise_for_status()

        messages = response.json()["conversations"]["messages"]
        conversations = Conversations()

        for m in messages:
            conversations.add_message(m['role'], m['content'])

        return conversations
    return None


def main():
    st.title("PDF Summarizer")

    set_openai_api_key()
    create_table()

    if "conversations" not in st.session_state:
        st.session_state.conversations = Conversations()

    if "uploaded" not in st.session_state:
        st.session_state.uploaded = False

    pdf_file = st.file_uploader("Upload a PDF file", type="pdf")

    if pdf_file is not None and st.session_state.uploaded is False:
        print("handle_pdf_upload")
        conversations = handle_pdf_upload(pdf_file)
        add_data(conversations)
        st.session_state.uploaded = True

    question = st.text_input("Type your question here")

    if st.button("Ask", key="ask_button"):
        if question:
            print("continue_conversation")
            result = ask_question(question)
            print(result)
            print(result['result'])
            chat_message(result['result'], key='assistant')

    if st.button("Clear All cache", key="clear_cache"):
        st.cache_resource.clear()
        st.session_state.conversations = Conversations()
        delete_data()
        create_table()


def create_table():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute(
        'CREATE TABLE IF NOT EXISTS books (id INTEGER PRIMARY KEY, role TEXT, content TEXT)'
    )
    conn.commit()
    conn.close()


def add_data(conversations: Conversations):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    for message in conversations.get_messages():
        print(message.role)
        print(message.content)
        cursor.execute(
            f"INSERT INTO books (role, content) VALUES (\"{message.role}\", \"{message.content}\")"
        )
    conn.commit()
    conn.close()


def ask_question(question: str):
    db = SQLDatabase.from_uri("sqlite:///database.db")
    llm = OpenAI(temperature=0)

    _DEFAULT_TEMPLATE = """Given an input question, first create a syntactically correct {dialect} query to run, then look at the results of the query and return the answer.
    Use the following format:

    Question: "Question here"
    SQLQuery: "SQL Query to run"
    SQLResult: "Result of the SQLQuery"
    Answer: "Final answer here"

    Only use the following tables:

    {table_info}

    Question: {input}"""

    PROMPT = PromptTemplate(
        input_variables=["input", "table_info", "dialect"], template=_DEFAULT_TEMPLATE
    )
    db_chain = SQLDatabaseChain(
        llm=llm, database=db, prompt=PROMPT, verbose=True, return_intermediate_steps=True
    )
    result = db_chain(question)
    return result


def delete_data():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute(
        'DELETE FROM books'
    )
    conn.commit()
    conn.close()


if __name__ == "__main__":
    main()
