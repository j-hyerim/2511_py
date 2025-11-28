import os
import time
from io import BytesIO

from dotenv import load_dotenv
from flask import Flask, render_template, request, Response
import google.generativeai as genai
import speech_recognition as sr
from gtts import gTTS

# .env에서 환경변수 불러오기
load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    raise RuntimeError("GEMINI_API_KEY 환경변수 설정 필요!")

# Gemini 설정
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel("gemini-2.5-flash")

# Flask 설정
app = Flask(__name__)
recognizer = sr.Recognizer()

# 간단한 메모리 저장
chat_history = []
last_bot_text = ""
last_audio_ts = None

# ======================
# 텍스트 입력용
# ======================
@app.route("/", methods=["GET", "POST"])
def index():
    global chat_history, last_bot_text, last_audio_ts

    if request.method == "POST":
        user_text = (request.form.get("user_input") or "").strip()
        if not user_text:
            chat_history.append(("bot", "질문을 입력해주세요!"))
        else:
            chat_history.append(("user", user_text))
            try:
                prompt = f"한 줄로 짧게 답해. {user_text}"
                response = model.generate_content(prompt)
                bot_text = (response.text or "").strip()
            except Exception as e:
                bot_text = f"Gemini 호출 중 에러: {e}"
            chat_history.append(("bot", bot_text))
            last_bot_text = bot_text
            last_audio_ts = str(int(time.time() * 1000))

    return render_template("index.html", chat_history=chat_history, audio_ts=last_audio_ts)

# ======================
# 음성 파일 업로드 기반 STT
# ======================
@app.route("/stt_file", methods=["POST"])
def stt_file():
    global chat_history, last_bot_text, last_audio_ts
    if "file" not in request.files:
        return "No file uploaded", 400

    file = request.files["file"]
    try:
        with sr.AudioFile(file) as source:
            audio = recognizer.record(source)
        user_text = recognizer.recognize_google(audio, language="ko-KR")
    except Exception as e:
        return f"STT 에러: {e}", 500

    chat_history.append(("user", user_text))
    try:
        prompt = f"한 줄로 짧게 답해. {user_text}"
        response = model.generate_content(prompt)
        bot_text = (response.text or "").strip()
    except Exception as e:
        bot_text = f"Gemini 호출 중 에러: {e}"

    chat_history.append(("bot", bot_text))
    last_bot_text = bot_text
    last_audio_ts = str(int(time.time() * 1000))
    return {"user": user_text, "bot": bot_text}

# ======================
# TTS 스트리밍
# ======================
@app.route("/tts_audio")
def tts_audio():
    global last_bot_text
    if not last_bot_text:
        return Response(status=204)

    try:
        tts = gTTS(last_bot_text, lang="ko")
        buf = BytesIO()
        tts.write_to_fp(buf)
        buf.seek(0)
        return Response(buf.read(), mimetype="audio/mpeg")
    except Exception as e:
        print("TTS 에러:", e, flush=True)
        return Response(f"TTS 에러: {e}", status=500)

# ======================
# Render 배포용 메인
# ======================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
