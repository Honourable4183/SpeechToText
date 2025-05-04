import os
import requests
from flask import Flask, request

BOT_TOKEN = os.getenv("7961972146:AAGkgOnZafCIueCp8gRjGtFOzaqbt-jiDRU")
DEEPGRAM_API_KEY = os.getenv("5492e41bdcf6b3220831d20c308393d2c7585032")
TG_API = f"https://api.telegram.org/bot{BOT_TOKEN}"
DOWNLOAD_URL = f"https://api.telegram.org/file/bot{BOT_TOKEN}/"

app = Flask(__name__)

def get_file_path(file_id):
    resp = requests.get(f"{TG_API}/getFile?file_id={file_id}")
    return resp.json()["result"]["file_path"]

def download_audio(file_path):
    resp = requests.get(DOWNLOAD_URL + file_path)
    return resp.content

def transcribe(audio_bytes):
    headers = {
        "Authorization": f"Token {DEEPGRAM_API_KEY}",
        "Content-Type": "audio/wav"
    }
    response = requests.post("https://api.deepgram.com/v1/listen", headers=headers, data=audio_bytes)
    return response.json()["results"]["channels"][0]["alternatives"][0]["transcript"]

def send_message(chat_id, text):
    requests.post(f"{TG_API}/sendMessage", data={"chat_id": chat_id, "text": text})

@app.route("/", methods=["POST"])
def webhook():
    data = request.get_json()

    if "voice" in data["message"] or "audio" in data["message"]:
        file_id = data["message"].get("voice", data["message"].get("audio"))["file_id"]
        chat_id = data["message"]["chat"]["id"]

        file_path = get_file_path(file_id)
        audio_data = download_audio(file_path)
        try:
            transcript = transcribe(audio_data)
            if transcript.strip() == "":
                transcript = "[Could not recognize speech]"
        except Exception as e:
            transcript = f"[Error transcribing: {e}]"

        send_message(chat_id, transcript)

    return "OK"
