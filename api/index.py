import os
import requests
from flask import Flask, request, jsonify
from groq import Groq

app = Flask(__name__)

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
GROQ_API_KEY = os.environ["GROQ_API_KEY"]

TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

client = Groq(api_key=GROQ_API_KEY)

MODEL = "openai/gpt-oss-120b"


def send_message(chat_id, text, reply_to_message_id=None):
    url = f"{TELEGRAM_API}/sendMessage"

    data = {
        "chat_id": chat_id,
        "text": text
    }

    if reply_to_message_id:
        data["reply_to_message_id"] = reply_to_message_id

    try:
        response = requests.post(
            url,
            json=data,
            timeout=20
        )

        print("TELEGRAM STATUS:", response.status_code)
        print("TELEGRAM RESPONSE:", response.text)

    except Exception as e:
        print("TELEGRAM ERROR:", repr(e))


def ask_groq(text):
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "Ты дружелюбный Telegram AI-бот. "
                    "Отвечай понятно и полезно. "
                    "Отвечай на языке пользователя."
                )
            },
            {
                "role": "user",
                "content": text
            }
        ],
        reasoning_effort="medium",
        max_tokens=2048
    )

    return response.choices[0].message.content


@app.route("/api/webhook", methods=["POST"])
def webhook():
    try:
        update = request.get_json(silent=True)

        if not update:
            return jsonify({"ok": True})

        message = update.get("message")

        if not message:
            return jsonify({"ok": True})

        # Только текстовые сообщения
        text = message.get("text")

        if not text:
            return jsonify({"ok": True})

        chat = message.get("chat", {})
        chat_id = chat.get("id")
        chat_type = chat.get("type")

        if not chat_id:
            return jsonify({"ok": True})

# =====================================================
# ГРУППЫ
# =====================================================

if chat_type in ("group", "supergroup"):

    # Команда должна быть строго в начале:
    # /ask текст
    # /ask@telegpt5436789_bot текст

    if not text.startswith("/ask"):
        return jsonify({"ok": True})

    # Получаем первое слово сообщения
    first_word = text.split(maxsplit=1)[0]

    # Разрешаем:
    # /ask
    # /ask@username

    if first_word == "/ask":
        prompt = text[len("/ask"):].strip()

    elif first_word.startswith("/ask@"):
        # Получаем username после @
        bot_username = first_word[5:]

        # Проверяем, что username действительно принадлежит
        # этому боту
        me_response = requests.get(
            f"{TELEGRAM_API}/getMe",
            timeout=10
        )

        me_data = me_response.json()

        if not me_data.get("ok"):
            return jsonify({"ok": True})

        my_username = me_data["result"].get("username", "")

        if bot_username.lower() != my_username.lower():
            return jsonify({"ok": True})

        prompt = text[len(first_word):].strip()

    else:
        # Например:
        # /asking
        # /ask123
        return jsonify({"ok": True})

    # /ask без текста — игнорируем
    if not prompt:
        return jsonify({"ok": True})

        # =====================================================
        # ЛИЧНЫЕ СООБЩЕНИЯ
        # =====================================================

        elif chat_type == "private":

            # В личке принимаем:
            #
            # Привет
            # /ask Привет
            #
            # Если начинается с /ask — убираем команду.

            if text.startswith("/ask"):

                if len(text) > 4 and not text[4].isspace():
                    # Например /asking
                    prompt = text

                else:
                    prompt = text[4:].strip()

                    # /ask без текста
                    if not prompt:
                        return jsonify({"ok": True})

            else:
                prompt = text

        # Неизвестный тип чата
        else:
            return jsonify({"ok": True})

        # =====================================================
        # GROQ
        # =====================================================

        print("USER MESSAGE:", prompt)

        answer = ask_groq(prompt)

        if not answer:
            answer = "Модель не вернула ответ 😕"

        # Telegram ограничивает длину сообщения.
        # Разбиваем длинные ответы.
        chunks = [
            answer[i:i + 4000]
            for i in range(0, len(answer), 4000)
        ]

        for chunk in chunks:
            send_message(
                chat_id,
                chunk
            )

        return jsonify({"ok": True})

    except Exception as e:

        print("BOT ERROR:", repr(e))

        # Возвращаем 200 Telegram, чтобы он
        # не пытался бесконечно повторять update.
        return jsonify({
            "ok": True
        })


@app.route("/api/webhook", methods=["GET"])
def health():
    return "Bot is alive! 🚀", 200
