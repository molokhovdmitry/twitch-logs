import os
import socket
import threading
import datetime

import streamlit as st
import psycopg2
from dotenv import load_dotenv


load_dotenv()

# Streamlit UI elements
st.title("twitch-logs")

# Initialize session state variables
if "channels" not in st.session_state:
    st.session_state.channels = []
if "active_threads" not in st.session_state:
    st.session_state.active_threads = {}
if "stop_flags" not in st.session_state:
    st.session_state.stop_flags = {}

log_file = "irc_messages.log"

db_config = {
    'host': os.getenv('POSTGRES_HOST'),
    'database': os.getenv('POSTGRES_DB'),
    'user': os.getenv('POSTGRES_USER'),
    'password': os.getenv('POSTGRES_PASSWORD')
}


def connect_and_log(server, port, nickname, channel, stop_flag, db_config):
    try:
        # Connect to IRC server
        irc = socket.socket()
        irc.connect((server, port))
        irc.send("PASS oauth:placeholder\r\n".encode("utf-8"))
        irc.send(f"NICK {nickname}\r\n".encode("utf-8"))
        irc.send(f"JOIN #{channel}\r\n".encode("utf-8"))

        # Connect to PostgreSQL
        conn = psycopg2.connect(**db_config)
        cur = conn.cursor()

        # Read and log messages
        while not stop_flag.is_set():
            response = irc.recv(2048).decode("utf-8")
            if response.startswith("PING"):
                irc.send("PONG :tmi.twitch.tv\r\n".encode("utf-8"))
            else:
                messages = parse_response(response)
                for message in messages:
                    username, text = message
                    timestamp = datetime.datetime.now() \
                        .strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]

                    # Insert message into PostgreSQL table
                    cur.execute("""
                        INSERT INTO public.messages
                            (timestamp, channel, username, text)
                        VALUES (%s, %s, %s, %s)
                    """, (timestamp, channel, username, text))
                    conn.commit()

    except Exception as e:
        print(f"Error connecting to #{channel}: {e}")
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()
        irc.close()


def parse_response(response: str) -> list[dict]:
    if response:
        messages = []
        for resp in response.split('\r\n'):
            if 'PRIVMSG' in resp:
                print(resp)
                username = resp.split(':', 1)[-1].split('!', 1)[0]
                text = resp.split('PRIVMSG')[-1].split(':', 1)[-1]
                text = preprocess_text(text)
                messages.append((username, text))
    return messages


def preprocess_text(text: str):
    hidden_char = '\U000e0000'
    last_index = text.rfind(hidden_char)
    if last_index != -1:
        text = text[:last_index]

    text = text.strip()
    return text


# Add new channel form with Streamlit
with st.form("channel_form"):
    new_channel = st.text_input("Enter Twitch channel name (without #):")
    submit_button = st.form_submit_button("Add Channel")

if submit_button and new_channel:
    if new_channel not in st.session_state.channels:
        st.session_state.channels.append(new_channel)
        st.success(f"Added channel: {new_channel}")
    else:
        st.warning(f"Channel #{new_channel} is already connected.")

# Display connected channels and stop buttons
st.subheader("Connected Channels")
for ch in st.session_state.channels:
    col1, col2 = st.columns([3, 1])
    with col1:
        st.write(f"- {ch}")
    with col2:
        if st.button(f"Stop {ch}"):
            if ch in st.session_state.stop_flags:
                # Signal the thread to stop
                st.session_state.stop_flags[ch].set()
                # Wait for the thread to finish
                st.session_state.active_threads[ch].join()
                # Remove the thread from active threads
                del st.session_state.active_threads[ch]
                # Remove the stop flag
                del st.session_state.stop_flags[ch]
                # Remove the channel from the list
                st.session_state.channels.remove(ch)
                st.success(f"Stopped and removed channel: {ch}")

# Start threads for new channels only
for channel in st.session_state.channels:
    if channel not in st.session_state.active_threads:
        stop_flag = threading.Event()
        thread = threading.Thread(
            target=connect_and_log,
            args=("irc.chat.twitch.tv", 6667, "justinfan12345",
                  channel, stop_flag, db_config)
        )
        thread.daemon = True
        thread.start()
        st.session_state.active_threads[channel] = thread
        st.session_state.stop_flags[channel] = stop_flag
