
import os
import textwrap
from typing import Optional

import openai
import streamlit as st

from .conversations import Conversations


@st.cache_resource
def set_openai_api_key():

    if 'OPENAI_API_KEY' in os.environ:
        openai.api_key = os.environ.get("OPENAI_API_KEY")

    print("set API_KEY: ", openai.api_key)


def generate_summary(text: str, max_length: int = 100) -> str:
    prompt = f"下記文章を日本語で{max_length}字以内で要約して:\n\n{text}\n"
    print(prompt)

    completion = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
    )

    summary = completion.choices[0].message["content"]
    return summary


def summarize_large_text(conversations: Conversations,
                         text: str,
                         max_summarize_chars: int = 9000,
                         max_chars_per_request: int = 3000,
                         summary_chars_length: int = 1000) -> Conversations:
    wrapped_text = textwrap.wrap(text, max_chars_per_request)
    length = max_summarize_chars // max_chars_per_request
    wrapped_text = wrapped_text[:length]

    progress_text = "Operation in progress. Please wait."
    my_bar = st.progress(0, text=progress_text)

    try:
        for idx, chunk in enumerate(wrapped_text):
            my_bar.progress(idx, text=progress_text)
            summary_chunk = generate_summary(chunk, summary_chars_length)
            conversations.add_message("user", f"summarize: {chunk}")
            conversations.add_message("assistant", summary_chunk)
        return conversations
    except openai.InvalidRequestError as e:
        print("An error has occurred: ", e)
        # When a "request token exceeded limit" error occurs,
        # the number of characters in the request is reduced
        # by 20% and the request continues to be made.
        # The lower limit on the number of characters in a request
        # is set to 2000 to avoid multiple re-executions.
        if max_chars_per_request < 2000:
            raise e
        elif e.code == 'context_length_exceeded':
            conversations = summarize_large_text(
                conversations,
                text,
                max_chars_per_request=int(max_chars_per_request * 0.8)
            )
            return conversations
        else:
            raise e


def continue_conversation(conversations: Conversations, question: str) -> Conversations:
    conversations.add_message("user", question)

    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=conversations.get_message_dict_list()
    )

    answer = response.choices[0].message["content"]
    conversations.add_message("assistant", answer)

    return conversations
