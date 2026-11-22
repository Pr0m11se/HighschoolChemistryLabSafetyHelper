# -*- coding: utf-8 -*-
"""高中化学实验室安全助手 —— Flask + DeepSeek 流式对话服务

启动：
    python app.py
或双击「启动.bat」。
"""

import json
import logging
import os
import sys
import threading
import unicodedata
import webbrowser

from flask import (
    Flask,
    Response,
    jsonify,
    render_template,
    request,
    stream_with_context,
)

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    OpenAI,
    RateLimitError,
)

# ---------------------------------------------------------------------------
# 基础配置
# ---------------------------------------------------------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORY_FILE = os.path.join(BASE_DIR, "history.json")
PROMPT_FILE = os.path.join(BASE_DIR, "tishici.json")
ENV_FILE = os.path.join(BASE_DIR, ".env")

MAX_HISTORY_MESSAGES = 20      # 最多保留多少条历史（成对保存）
MAX_USER_MESSAGE_CHARS = 2000  # 单条消息最大长度

DEFAULT_MODEL = "deepseek-chat"
API_BASE_URL = "https://api.deepseek.com"

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("chem-safety")

# Windows 控制台默认 GBK，中文日志可能报 UnicodeEncodeError，这里兜一下
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

app = Flask(__name__)
app.config["JSON_AS_ASCII"] = False
app.json.ensure_ascii = False

# ---------------------------------------------------------------------------
# API Key 读取
# ---------------------------------------------------------------------------


def load_env_file(path=ENV_FILE):
    """读取简单的 KEY=VALUE 形式的 .env 文件（不覆盖已存在的环境变量）。"""
    if not os.path.exists(path):
        return
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and value and not os.environ.get(key):
                    os.environ[key] = value
    except OSError as e:
        log.warning("读取 .env 失败：%s", e)


load_env_file()


def get_api_key():
    """返回可用的 API Key，未配置或明显是占位符时返回空字符串。"""
    key = (os.environ.get("DEEPSEEK_API_KEY") or "").strip()
    if not key:
        return ""
    if any(ch.isspace() for ch in key):
        return ""
    # 常见占位符：apikey / 1 / your_key / sk- 等
    if len(key) < 20 or key.lower() in {"apikey", "api_key", "your_api_key", "sk-"}:
        return ""
    return key


def save_api_key(key):
    """把 API Key 写进同目录的 .env（不修改注册表，卸载时删文件即可）。"""
    key = (key or "").strip()
    if not key:
        raise ValueError("API Key 不能为空")
    lines = []
    if os.path.exists(ENV_FILE):
        try:
            with open(ENV_FILE, "r", encoding="utf-8-sig") as f:
                lines = [ln for ln in f.read().splitlines() if ln.strip()]
        except OSError:
            lines = []
    lines = [ln for ln in lines if not ln.strip().startswith("DEEPSEEK_API_KEY=")]
    lines.append("DEEPSEEK_API_KEY=" + key)
    with open(ENV_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    os.environ["DEEPSEEK_API_KEY"] = key
    _client_cache.clear()


def get_model():
    return (os.environ.get("DEEPSEEK_MODEL") or DEFAULT_MODEL).strip() or DEFAULT_MODEL


_client_cache = {}


def get_client():
    """按当前 Key 惰性创建客户端，Key 更新后自动重建。"""
    key = get_api_key()
    if not key:
        return None
    cached = _client_cache.get("client")
    if cached is not None and _client_cache.get("key") == key:
        return cached
    client = OpenAI(
        api_key=key,
        base_url=API_BASE_URL,
        timeout=60.0,
        max_retries=2,
    )
    _client_cache["key"] = key
    _client_cache["client"] = client
    return client


def friendly_error(err):
    """把 SDK 异常翻译成给中学生的中文提示。"""
    if isinstance(err, AuthenticationError):
        return "API Key 无效或已失效，请点击右上角「设置密钥」重新填写。"
    if isinstance(err, RateLimitError):
        return "请求太频繁或账户余额不足，请稍后再试。"
    if isinstance(err, APITimeoutError):
        return "模型响应超时，请稍后重试。"
    if isinstance(err, APIConnectionError):
        return "无法连接 DeepSeek 服务器，请检查网络或代理设置。"
    if isinstance(err, BadRequestError):
        if "model" in str(err).lower():
            return f"模型名称「{get_model()}」不可用，请检查 DEEPSEEK_MODEL 设置。"
        return f"请求参数有误：{err}"
    if isinstance(err, APIStatusError):
        return f"服务器返回错误（HTTP {err.status_code}），请稍后重试。"
    return f"调用模型失败：{err}"


# ---------------------------------------------------------------------------
# 提示词 / 历史
# ---------------------------------------------------------------------------


def _as_prompt(value):
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        return "\n".join(v.strip() for v in value if isinstance(v, str) and v.strip())
    return ""


def load_system_prompt():
    default_prompt = "你是高中化学实验室安全助手，只回答与化学实验安全相关的问题。"
    if not os.path.exists(PROMPT_FILE):
        log.warning("未找到 tishici.json，使用默认提示词")
        return default_prompt
    try:
        with open(PROMPT_FILE, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        log.warning("读取 tishici.json 失败：%s", e)
        return default_prompt

    if isinstance(data, dict):
        text = _as_prompt(data.get("system_prompt"))
    else:
        text = _as_prompt(data)
    return text or default_prompt


SYSTEM_PROMPT = load_system_prompt()


def _clean_history(items):
    """只保留 role/content 合法的消息。"""
    cleaned = []
    if not isinstance(items, list):
        return cleaned
    for item in items:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        content = item.get("content")
        if role in ("user", "assistant") and isinstance(content, str) and content.strip():
            cleaned.append({"role": role, "content": content})
    if cleaned and cleaned[0]["role"] != "user":
        cleaned = cleaned[1:]
    return cleaned


def load_history():
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        log.warning("读取历史失败：%s", e)
        return []
    return _clean_history(data)


def save_history(history):
    history = _clean_history(history)
    if len(history) > MAX_HISTORY_MESSAGES:
        # 按「一问一答」成对裁剪，保证首条仍是 user
        excess = len(history) - MAX_HISTORY_MESSAGES
        history = history[excess + (excess % 2):]
        while history and history[0]["role"] != "user":
            history = history[1:]
    try:
        tmp = HISTORY_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
        os.replace(tmp, HISTORY_FILE)
    except OSError as e:
        log.warning("保存历史失败：%s", e)


# ---------------------------------------------------------------------------
# 路由
# ---------------------------------------------------------------------------


def sse(payload):
    return "data: " + json.dumps(payload, ensure_ascii=False) + "\n\n"


# ---------------------------------------------------------------------------
# 用户输入内容校验
# ---------------------------------------------------------------------------

MAX_SAME_QUESTION_REPEAT = 3  # 同一个问题最多连续问几次

_KEYBOARD_ROWS = (
    "qwertyuiop",
    "asdfghjkl",
    "zxcvbnm",
)


def _normalize_question(text):
    """去掉空白、标点和符号并统一小写，只留下“真正表达意思”的字符。

    用于两件事：判断输入是不是只有标点/空白，以及判断两次输入是不是同一个问题。
    （emoji、※、★ 这类符号的 Unicode 类别是 S/P，会被去掉）
    """
    text = (text or "").strip().lower()
    kept = []
    for ch in text:
        if ch.isspace():
            continue
        category = unicodedata.category(ch)
        if category.startswith("P") or category.startswith("S"):
            continue
        kept.append(ch)
    return "".join(kept)


def _is_keyboard_mash(normalized):
    """判断是不是随手在键盘上滚出来的东西，如 asdfgh、zxcvbn、qwerty。"""
    if len(normalized) < 6 or not normalized.isascii() or not normalized.isalpha():
        return False
    return any(all(ch in row for ch in normalized) for row in _KEYBOARD_ROWS)


def check_user_input(user_message, history=None):
    """检查用户输入是否有意义，返回 None 表示通过，否则返回给用户看的中文提示。"""
    normalized = _normalize_question(user_message)

    # 1）只有空格、标点、符号，或单字刷屏：？？？？、。。。。、哈哈哈哈
    if not normalized:
        return "请描述具体的化学实验安全问题，不要只发送空格或标点符号。"
    if len(normalized) < 2:
        return "问题太短了，请补充一下你具体想了解什么。"
    if len(set(normalized)) == 1:
        return "这看起来是无意义的重复字符，请输入具体的问题。"

    # 2）键盘乱敲：asdfgh、zxcvbn、qwerty
    if _is_keyboard_mash(normalized):
        return "这看起来是随意敲的字符，请用完整的句子描述你的问题。"

    # 3）连续多次问同一个问题（历史里最后几条 user 消息）
    history = history or []
    same_count = 0
    for old in reversed(history):
        if old.get("role") != "user":
            continue
        if _normalize_question(old.get("content")) == normalized:
            same_count += 1
        else:
            break
    if same_count >= MAX_SAME_QUESTION_REPEAT - 1:
        return (
            f"这个问题你已经连续问了 {MAX_SAME_QUESTION_REPEAT} 次了，"
            "先看看上面的回答，或者换个说法再问吧。"
        )

    return None


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/health")
def health():
    return jsonify(
        {
            "ok": True,
            "api_key_configured": bool(get_api_key()),
            "model": get_model(),
        }
    )


@app.route("/api/key", methods=["POST"])
def api_set_key():
    data = request.get_json(silent=True) or {}
    key = (data.get("key") or "").strip()
    try:
        save_api_key(key)
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    except OSError as e:
        return jsonify({"ok": False, "error": f"保存失败：{e}"}), 500
    return jsonify({"ok": True})


@app.route("/history", methods=["GET"])
def get_history():
    return jsonify({"messages": load_history()})


@app.route("/clear", methods=["POST"])
def clear_history():
    save_history([])
    return jsonify({"ok": True})


@app.route("/reload_prompt", methods=["POST"])
def reload_prompt():
    global SYSTEM_PROMPT
    SYSTEM_PROMPT = load_system_prompt()
    return jsonify({"ok": True, "prompt": SYSTEM_PROMPT})


@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}
    user_message = (data.get("message") or "").strip()
    if not user_message:
        return jsonify({"error": "消息不能为空"}), 400

    history = load_history()
    # 用户输入内容校验：无意义字符、连续重复提问都直接拦下，不调用模型
    invalid_reason = check_user_input(user_message, history)
    if invalid_reason:
        return jsonify({"error": invalid_reason, "invalid_input": True}), 400

    if len(user_message) > MAX_USER_MESSAGE_CHARS:
        user_message = user_message[:MAX_USER_MESSAGE_CHARS]

    client = get_client()
    if client is None:
        return (
            jsonify(
                {
                    "error": "尚未配置 DeepSeek API Key，请点击右上角「设置密钥」填写后再试。",
                    "need_key": True,
                }
            ),
            503,
        )

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    def generate():
        full_reply = ""
        try:
            stream = client.chat.completions.create(
                model=get_model(),
                messages=messages,
                max_tokens=2050,
                temperature=0.85,
                stream=True,
            )
            for chunk in stream:
                choices = getattr(chunk, "choices", None)
                if not choices:
                    continue
                delta = getattr(choices[0], "delta", None)
                content = getattr(delta, "content", None) if delta else None
                if content:
                    full_reply += content
                    yield sse({"delta": content})
        except Exception as e:  # noqa: BLE001 - 统一转成前端可读提示
            log.warning("模型调用失败：%s", e)
            yield sse({"error": friendly_error(e)})
            return

        if not full_reply.strip():
            yield sse({"error": "模型没有返回内容，请换个说法再试一次。"})
            return

        new_history = history + [
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": full_reply},
        ]
        save_history(new_history)

        yield sse({"done": True})

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ---------------------------------------------------------------------------
# 启动
# ---------------------------------------------------------------------------


def _open_browser(url):
    try:
        webbrowser.open(url)
    except Exception:
        pass


def main():
    port = int(os.environ.get("PORT", "5000"))
    host = (os.environ.get("HOST") or "127.0.0.1").strip()
    if not get_api_key():
        log.warning("尚未配置 DEEPSEEK_API_KEY，可在网页右上角「设置密钥」中填写。")

    log.info("服务已启动： http://127.0.0.1:%d/", port)
    if os.environ.get("NO_BROWSER", "").strip() not in {"1", "true", "True"}:
        threading.Timer(1.2, _open_browser, args=(f"http://127.0.0.1:{port}/",)).start()

    app.run(host=host, port=port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
