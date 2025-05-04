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
    try:
        return response.json()["results"]["channels"][0]["alternatives"][0]["transcript"]
    except (KeyError, IndexError, TypeError):
        print("[!] Error extracting transcript from Deepgram response.")
        return ""

def send_message(chat_id, text):
    print(f"[*] Sending message to chat_id {chat_id}")
    resp = requests.post(f"{TG_API}/sendMessage", data={"chat_id": chat_id, "text": text})
    print("[*] Telegram sendMessage response:", resp.text)

@app.route("/", methods=["GET", "POST"])
def health_check():
    print("[*] Root path was hit!")
    logging.info(f"Request method on root: {request.method}")
    if request.method == "POST":
        logging.info(f"Request data on root: {request.get_data().decode('utf-8')}")
    return "Bot is running!", 200

@app.route("/webhook", methods=["POST"])
def webhook_handler():
    print("[*] Simple webhook handler hit!")
    logging.info("Simple webhook received")
    return "OK", 200  #
    print("[*] /webhook endpoint was hit!")
    logging.info("Received a POST request on /webhook")
    print("[*] Request method:", request.method)
    print("[*] Request data:", request.get_data().decode('utf-8')) 
    if request.method == "GET":
        return "Webhook is live!", 200

    data = request.get_json()
    print("[*] Webhook received:", data)
    logging.info("Received data: %s", data)

    try:
        if "message" in data and ("voice" in data["message"] or "audio" in data["message"]):
            logging.info("Voice or audio detected")
            file_info = data["message"].get("voice") or data["message"].get("audio")
            file_id = file_info["file_id"]
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
            print("[!] Message does not contain voice or audio or is malformed.")
    except Exception as e:
        print("[!] General error in webhook:", e)

    return "OK", 200

if __name__ == "__main__":
    app.run(debug=True)
