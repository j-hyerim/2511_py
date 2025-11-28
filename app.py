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
    raise RuntimeError("GEMINI_API_KEY가 .env에서 읽히지 않았어요!")

# Gemini 설정
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel("gemini-2.5-flash")

# Flask 설정
app = Flask(__name__)
recognizer = sr.Recognizer()

# 간단한 메모리 저장 (서버 껐다 켜면 초기화됨)
chat_history = []       # [(sender, text), ...]
last_bot_text = ""      # 마지막 봇 답변 텍스트
last_audio_ts = None    # 마지막 오디오 타임스탬프(캐시 방지용)


@app.route("/", methods=["GET", "POST"])
def index():
    global chat_history, last_bot_text, last_audio_ts

    if request.method == "POST":
        action = request.form.get("action")  # "text" 또는 "stt"
        user_text = ""

        # 1) 음성(STT)으로 질문하기
        if action == "stt":
            try:
                with sr.Microphone() as source:
                    # 주변 소음 보정
                    recognizer.adjust_for_ambient_noise(source, duration=0.5)
                    print("말하세요... (최대 5초)", flush=True)
                    audio = recognizer.listen(source, timeout=5, phrase_time_limit=5)

                # 한국어 음성 인식
                user_text = recognizer.recognize_google(audio, language="ko-KR")
            except Exception as e:
                error_msg = f"음성 인식 중 에러가 발생했어요: {e}"
                chat_history.append(("bot", error_msg))
                return render_template(
                    "index.html",
                    chat_history=chat_history,
                    audio_ts=last_audio_ts,
                )

        # 2) 텍스트로 질문하기
        elif action == "text":
            user_text = (request.form.get("user_input") or "").strip()

        # 3) 아무 내용도 없으면 안내 메시지
        if not user_text:
            chat_history.append(("bot", "질문을 입력하거나, 음성 버튼을 눌러서 말해줘!"))
            return render_template(
                "index.html",
                chat_history=chat_history,
                audio_ts=last_audio_ts,
            )

        # 4) 히스토리에 사용자 메시지 추가
        chat_history.append(("user", user_text))

        prompt = f"한 줄로 짧게 답해. {user_text}"
        # 5) Gemini에 질문 보내기
        try:
            # response = model.generate_content(user_text)
            response = model.generate_content(prompt)

            bot_text = (response.text or "").strip()
        except Exception as e:
            bot_text = f"Gemini 호출 중 에러가 발생했어요: {e}"

        # 6) 봇 응답 히스토리에 추가
        chat_history.append(("bot", bot_text))

        # 7) TTS 재생을 위해 마지막 텍스트/타임스탬프 저장
        last_bot_text = bot_text
        # 캐시 방지를 위해 매번 다른 값
        last_audio_ts = str(int(time.time() * 1000))

    # GET이든 POST 이후든, 현재까지 대화/오디오TS 렌더링
    return render_template(
        "index.html",
        chat_history=chat_history,
        audio_ts=last_audio_ts,
    )


@app.route("/tts_audio")
def tts_audio():
    """마지막 봇 답변을 TTS로 변환해서 바로 스트리밍."""
    global last_bot_text

    if not last_bot_text:
        # 읽어줄 텍스트가 없으면 내용 없음
        return Response(status=204)

    try:
        # gTTS로 메모리에 바로 쓰기 (파일 저장 X)
        tts = gTTS(last_bot_text, lang="ko")
        buf = BytesIO()
        tts.write_to_fp(buf)
        buf.seek(0)
        audio_bytes = buf.read()

        # audio/mpeg 형식으로 바로 응답
        return Response(audio_bytes, mimetype="audio/mpeg")
    except Exception as e:
        # TTS 중 에러가 나면 그냥 500 + 로그
        print("TTS 에러:", e, flush=True)
        return Response(f"TTS 에러: {e}", status=500)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
