import os
import json
from flask import Flask, render_template, request, jsonify
from openai import OpenAI

app = Flask(__name__)

client = OpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY", "apikey"),
    base_url="https://api.deepseek.com",
)

SYSTEM_PROMPT = "You are a helpful assistant"

HISTORY_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "history.json"
)

MAX_HISTORY_MESSAGES = 20


def load_history():
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def save_history(history):
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except OSError as e:
        print("[WARN] 保存历史失败:", e)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/history", methods=["GET"])
def get_history():
    return jsonify({"messages": load_history()})


@app.route("/clear", methods=["POST"])
def clear_history():
    save_history([])
    return jsonify({"ok": True})


@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}
    user_message = (data.get("message") or "").strip()
    if not user_message:
        return jsonify({"error": "消息不能为空"}), 400

    history = load_history()

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    try:
        response = client.chat.completions.create(
            model="deepseek-flash",
            messages=messages,
            max_tokens=1024,
            temperature=0.7,
            stream=False,
        )
        reply = response.choices[0].message.content
    except Exception as e:
        return jsonify({"error": f"调用模型失败：{str(e)}"}), 500

    history.append({"role": "user",      "content": user_message})
    history.append({"role": "assistant", "content": reply})

    if len(history) > MAX_HISTORY_MESSAGES:
        history = history[-MAX_HISTORY_MESSAGES:]

    save_history(history)

    return jsonify({"reply": reply})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)