import os
from flask import Flask, render_template, request, jsonify
from openai import OpenAI

app = Flask(__name__)

client = OpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY", "***REMOVED***"),
    base_url="https://api.deepseek.com",
)

SYSTEM_PROMPT = "You are a helpful assistant"


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}
    user_message = (data.get("message") or "").strip()

    if not user_message:
        return jsonify({"error": "消息不能为空"}), 400

    try:
        response = client.chat.completions.create(
            model="deepseek-flash",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": user_message},
            ],
            max_tokens=1024,
            temperature=0.7,
            stream=False,
        )

        reply = response.choices[0].message.content

        return jsonify({"reply": reply})

    except Exception as e:
        return jsonify({"error": f"调用模型失败：{str(e)}"}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)