import os
import json
from flask import Flask, render_template, request, jsonify
from openai import OpenAI

app = Flask(__name__)

client = OpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY", "apikey"),
    base_url="https://api.deepseek.com",
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORY_FILE = os.path.join(BASE_DIR, "history.json")
PROMPT_FILE = os.path.join(BASE_DIR, "tishici.json")

MAX_HISTORY_MESSAGES = 20


def _as_prompt(value):
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        return "\n".join(v.strip() for v in value if isinstance(v, str) and v.strip())
    return ""


def load_system_prompt():
    default_prompt = "You are a helpful assistant"
    if not os.path.exists(PROMPT_FILE):
        print("[WARN] 未找到 tishici.json，使用默认提示词")
        return default_prompt
    try:
        with open(PROMPT_FILE, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print("[WARN] 读取 tishici.json 失败:", e)
        return default_prompt

    if isinstance(data, dict):
        text = _as_prompt(data.get("system_prompt"))
        return text or default_prompt

    return _as_prompt(data) or default_prompt


SYSTEM_PROMPT = load_system_prompt()


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

    history.append({"role": "user", "content": user_message})
    history.append({"role": "assistant", "content": reply})

    if len(history) > MAX_HISTORY_MESSAGES:
        history = history[-MAX_HISTORY_MESSAGES:]

    save_history(history)

    return jsonify({"reply": reply})


@app.route("/reload_prompt", methods=["POST"])
def reload_prompt():
    global SYSTEM_PROMPT
    SYSTEM_PROMPT = load_system_prompt()
    return jsonify({"ok": True, "prompt": SYSTEM_PROMPT})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)