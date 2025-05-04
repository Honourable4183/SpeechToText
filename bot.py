import os
import requests
from flask import Flask, request
import logging
logging.basicConfig(level=logging.INFO)

BOT_TOKEN = "7961972146:AAGkgOnZafCIueCp8gRjGtFOzaqbt-jiDRU"
DEEPGRAM_API_KEY = "40c5039a98a95ec960e242c60441d8f029e650dd"

# Get secrets from environment variables (don't paste actual tokens directly in code)
BOT_TOKEN = os.getenv("BOT_TOKEN")
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")

if not BOT_TOKEN or not DEEPGRAM_API_KEY:
    raise ValueError("BOT_TOKEN and DEEPGRAM_API_KEY must be set in environment variables.")

TG_API = f"https://api.telegram.org/bot{BOT_TOKEN}"
DOWNLOAD_URL = f"https://api.telegram.org/file/bot{BOT_TOKEN}/"

app = Flask(__name__)

def get_file_path(file_id):
    print("[*] Fetching file path from Telegram...")
    resp = requests.get(f"{TG_API}/getFile?file_id={file_id}")
    print("[*] Telegram file path response:", resp.json())
    return resp.json()["result"]["file_path"]

def download_audio(file_path):
    print("[*] Downloading audio file...")
    resp = requests.get(DOWNLOAD_URL + file_path)
    print("[*] Audio downloaded, size (bytes):", len(resp.content))
    return resp.content

def transcribe(audio_bytes):
    print("[*] Transcribing with Deepgram...")
    headers = {
        "Authorization": f"Token {DEEPGRAM_API_KEY}",
        "Content-Type": "audio/wav"
    }
    response = requests.post("https://api.deepgram.com/v1/listen", headers=headers, data=audio_bytes)
    print("[*] Deepgram response:", response.json())
    return response.json()["results"]["channels"][0]["alternatives"][0]["transcript"]

def send_message(chat_id, text):
    print(f"[*] Sending message to chat_id {chat_id}")
    resp = requests.post(f"{TG_API}/sendMessage", data={"chat_id": chat_id, "text": text})
    print("[*] Telegram sendMessage response:", resp.text)

@app.route("/webhook", methods=["GET", "POST"])
def health_check():
    return "Bot is running!", 200

def webhook():
    if request.method == "GET":
        return "Webhook is live!", 200
        
    data = request.get_json()
    print("[*] Webhook received:", data)
    logging.info("Received data: %s", data)

    try:
        if "voice" in data["message"] or "audio" in data["message"]:
            logging.info("Voice or audio detected")
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
                print("[!] Deepgram error:", e)

            send_message(chat_id, transcript)
        else:
            print("[!] Message does not contain voice or audio.")
    except Exception as e:
        print("[!] General error in webhook:", e)

    return "OK"
