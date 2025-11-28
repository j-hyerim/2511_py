import os, time
from io import BytesIO
from dotenv import load_dotenv
from flask import Flask, render_template, request, Response, jsonify
import google.generativeai as genai
import speech_recognition as sr
from gtts import gTTS

load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY: raise RuntimeError("GEMINI_API_KEY 필요")

genai.configure(api_key=API_KEY)
model = genai.GenerativeModel("gemini-2.5-flash")

app = Flask(__name__)
recognizer = sr.Recognizer()
chat_history = []
last_bot_text = ""
last_audio_ts = None

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html", chat_history=chat_history, audio_ts=last_audio_ts)

@app.route("/stt_file", methods=["POST"])
def stt_file():
    global chat_history, last_bot_text, last_audio_ts
    if "file" not in request.files: return "No file", 400
    file = request.files["file"]

    try:
        with sr.AudioFile(file) as source: audio = recognizer.record(source)
        user_text = recognizer.recognize_google(audio, language="ko-KR")
    except Exception as e: return f"STT 에러: {e}", 500

    chat_history.append(("user", user_text))
    try:
        prompt = f"한 줄로 짧게 답해. {user_text}"
        response = model.generate_content(prompt)
        bot_text = (response.text or "").strip()
    except Exception as e: bot_text = f"Gemini 호출 에러: {e}"

    chat_history.append(("bot", bot_text))
    last_bot_text = bot_text
    last_audio_ts = str(int(time.time()*1000))
    return jsonify({"user": user_text, "bot": bot_text})

@app.route("/tts_audio")
def tts_audio():
    global last_bot_text
    if not last_bot_text: return Response(status=204)
    buf = BytesIO()
    gTTS(last_bot_text, lang="ko").write_to_fp(buf)
    buf.seek(0)
    return Response(buf.read(), mimetype="audio/mpeg")

if __name__=="__main__":
    port = int(os.environ.get("PORT",5000))
    app.run(host="0.0.0.0", port=port)
