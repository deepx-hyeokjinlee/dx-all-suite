"""Rule-based fallback engine for when API key is not configured or API calls fail."""
from __future__ import annotations

import re


def _keyword_matches(keyword: str, lower_message: str) -> bool:
    """Match keyword in message: word-boundary for short ASCII, substring for CJK."""
    kw = keyword.lower()
    if not kw:
        return False
    if len(kw) <= 3 and re.fullmatch(r"[a-z0-9_+-]+", kw):
        return re.search(rf"(?<![a-z0-9_+-]){re.escape(kw)}(?![a-z0-9_+-])", lower_message) is not None
    return kw in lower_message


COMMON_RULES: list[tuple[list[str], dict[str, str]]] = [
    (
        ["안녕", "hello", "hi", "hey", "반가", "こんにちは", "你好"],
        {
            "ko": "안녕하세요! 🤖 **DX Assistant**입니다.\n"
                  "DeepX Edge AI 플랫폼에 대해 무엇이든 물어보세요!\n\n"
                  "💡 AI 응답을 사용하려면 채팅 설정(⚙️)에서 API 키를 설정하세요.",
            "en": "Hello! 🤖 I'm **DX Assistant**.\n"
                  "Ask me anything about the DeepX Edge AI platform!\n\n"
                  "💡 To use AI responses, open chat settings (⚙️) and set your API key.",
            "ja": "こんにちは! 🤖 **DX Assistant** です。\n"
                  "DeepX Edge AI プラットフォームについて何でも質問してください!\n\n"
                  "💡 AI 応答を使用するには、チャット設定(⚙️)で API キーを設定してください。",
            "zh-CN": "你好！🤖 我是 **DX Assistant**。\n"
                     "欢迎询问任何有关 DeepX Edge AI 平台的问题！\n\n"
                     "💡 要使用 AI 响应，请在聊天设置(⚙️)中设置 API 密钥。",
            "zh-TW": "你好！🤖 我是 **DX Assistant**。\n"
                     "歡迎詢問任何關於 DeepX Edge AI 平台的問題！\n\n"
                     "💡 若要使用 AI 回應，請在聊天設定(⚙️)中設定 API 金鑰。",
            "es": "¡Hola! 🤖 Soy **DX Assistant**.\n"
                  "Pregúnteme lo que desee sobre la plataforma DeepX Edge AI.\n\n"
                  "💡 Para usar respuestas de IA, abra la configuración del chat (⚙️) y establezca su clave API.",
        },
    ),
    (
        ["도움", "help", "사용법", "기능", "ヘルプ", "帮助", "說明",
         "what does this app do", "이 앱", "このアプリ", "这个应用", "這個應用"],
        {
            "ko": "**DX AI Studio** 주요 기능:\n"
                  "- 📊 **DX App** — AI 모델 추론, 하드웨어 모니터링\n"
                  "- 🎬 **DX Stream** — 비디오 스트리밍 파이프라인\n"
                  "- 🗂️ **DX Model Zoo** — 280+ 모델 카탈로그\n"
                  "- ⚙️ **DX Compiler** — ONNX → NPU 컴파일\n"
                  "- 🧪 **DX Sandbox** — 하드웨어 시뮬레이션",
            "en": "**DX AI Studio** key features:\n"
                  "- 📊 **DX App** — AI model inference, hardware monitoring\n"
                  "- 🎬 **DX Stream** — Video streaming pipeline\n"
                  "- 🗂️ **DX Model Zoo** — 280+ model catalog\n"
                  "- ⚙️ **DX Compiler** — ONNX → NPU compilation\n"
                  "- 🧪 **DX Sandbox** — Hardware simulation",
            "ja": "**DX AI Studio** の主な機能:\n"
                  "- 📊 **DX App** — AI モデル推論、ハードウェア監視\n"
                  "- 🎬 **DX Stream** — ビデオストリーミングパイプライン\n"
                  "- 🗂️ **DX Model Zoo** — 280+ モデルカタログ\n"
                  "- ⚙️ **DX Compiler** — ONNX → NPU コンパイル\n"
                  "- 🧪 **DX Sandbox** — ハードウェアシミュレーション",
            "zh-CN": "**DX AI Studio** 主要功能:\n"
                     "- 📊 **DX App** — AI 模型推理、硬件监控\n"
                     "- 🎬 **DX Stream** — 视频流管道\n"
                     "- 🗂️ **DX Model Zoo** — 280+ 模型目录\n"
                     "- ⚙️ **DX Compiler** — ONNX → NPU 编译\n"
                     "- 🧪 **DX Sandbox** — 硬件仿真",
            "zh-TW": "**DX AI Studio** 主要功能:\n"
                     "- 📊 **DX App** — AI 模型推論、硬體監控\n"
                     "- 🎬 **DX Stream** — 影片串流管線\n"
                     "- 🗂️ **DX Model Zoo** — 280+ 模型目錄\n"
                     "- ⚙️ **DX Compiler** — ONNX → NPU 編譯\n"
                     "- 🧪 **DX Sandbox** — 硬體模擬",
            "es": "Funciones principales de **DX AI Studio**:\n"
                  "- 📊 **DX App** — Inferencia de modelos de IA, monitoreo de hardware\n"
                  "- 🎬 **DX Stream** — Pipeline de transmisión de vídeo\n"
                  "- 🗂️ **DX Model Zoo** — Catálogo de más de 280 modelos\n"
                  "- ⚙️ **DX Compiler** — Compilación ONNX → NPU\n"
                  "- 🧪 **DX Sandbox** — Simulación de hardware",
        },
    ),
]

SETUP_BANNER = {
    "ko": "⚠️ AI 어시스턴트를 사용하려면 **채팅 설정**(⚙️)에서 API 키를 설정하세요.",
    "en": "⚠️ To use the AI assistant, open **chat settings** (⚙️) and set your API key.",
    "ja": "⚠️ AI アシスタントを使用するには、**チャット設定**(⚙️)で API キーを設定してください。",
    "zh-CN": "⚠️ 要使用 AI 助手，请在**聊天设置**(⚙️)中设置 API 密钥。",
    "zh-TW": "⚠️ 若要使用 AI 助理，請在**聊天設定**(⚙️)中設定 API 金鑰。",
    "es": "⚠️ Para usar el asistente de IA, abra la **configuración del chat** (⚙️) y establezca su clave API.",
}

DEFAULT_RESPONSE = {
    "ko": "죄송합니다, 현재 AI 모델이 연결되어 있지 않아 자세한 답변이 어렵습니다.\n\n"
          "**채팅 설정**(⚙️)에서 API 키를 설정하시면 더 정확한 답변을 받을 수 있습니다.\n\n"
          "**지원 프로바이더:** OpenAI, Anthropic (Claude), Google (Gemini)",
    "en": "Sorry, no AI model is currently connected for detailed responses.\n\n"
          "Set your API key in **chat settings** (⚙️) for more accurate answers.\n\n"
          "**Supported providers:** OpenAI, Anthropic (Claude), Google (Gemini)",
    "ja": "申し訳ありません。現在 AI モデルが接続されていないため、詳細な回答はできません。\n\n"
          "**チャット設定**(⚙️)で API キーを設定すると、より正確な回答を利用できます。\n\n"
          "**対応プロバイダー:** OpenAI, Anthropic (Claude), Google (Gemini)",
    "zh-CN": "抱歉，当前未连接 AI 模型，无法提供详细回答。\n\n"
             "请在**聊天设置**(⚙️)中设置 API 密钥，以获得更准确的回答。\n\n"
             "**支持的提供商:** OpenAI, Anthropic (Claude), Google (Gemini)",
    "zh-TW": "抱歉，目前未連接 AI 模型，無法提供詳細回答。\n\n"
             "請在**聊天設定**(⚙️)中設定 API 金鑰，以取得更準確的回答。\n\n"
             "**支援的提供者:** OpenAI, Anthropic (Claude), Google (Gemini)",
    "es": "Lo sentimos, actualmente no hay un modelo de IA conectado para respuestas detalladas.\n\n"
          "Establezca su clave API en la **configuración del chat** (⚙️) para obtener respuestas más precisas.\n\n"
          "**Proveedores compatibles:** OpenAI, Anthropic (Claude), Google (Gemini)",
}

# Keyword lists for identifying match type
_GREETING_KEYWORDS = COMMON_RULES[0][0]
_HELP_KEYWORDS = COMMON_RULES[1][0]


class FallbackEngine:
    def __init__(self, app_rules: list[tuple[list[str], str | dict]] | None = None):
        """app_rules: list of (keywords, response) tuples for app-specific rules."""
        self._app_rules = app_rules or []

    def respond(self, message: str, lang: str = "en") -> dict:
        """Returns {"reply": str, "is_fallback": True, "suggestions": list[str]}."""
        lower = message.lower()

        for keywords, response in self._app_rules:
            if any(_keyword_matches(kw, lower) for kw in keywords):
                if isinstance(response, dict):
                    resp_text = response.get(lang) or response.get("en") or next(iter(response.values()), "")
                else:
                    resp_text = response
                banner = SETUP_BANNER.get(lang, SETUP_BANNER["en"])
                reply = f"{banner}\n\n---\n\n{resp_text}"
                return {
                    "reply": reply,
                    "is_fallback": True,
                    "suggestions": self._suggestions(lang),
                }

        for keywords, response in COMMON_RULES:
            if any(_keyword_matches(kw, lower) for kw in keywords):
                resp_text = response.get(lang) or response.get("en") or next(iter(response.values()), "")
                banner = SETUP_BANNER.get(lang, SETUP_BANNER["en"])
                reply = f"{banner}\n\n---\n\n{resp_text}"
                suggestions = self._suggestions_for(keywords, lang)
                return {
                    "reply": reply,
                    "is_fallback": True,
                    "suggestions": suggestions,
                }

        banner = SETUP_BANNER.get(lang, SETUP_BANNER["en"])
        default = DEFAULT_RESPONSE.get(lang, DEFAULT_RESPONSE["en"])
        reply = f"{banner}\n\n---\n\n{default}"
        return {
            "reply": reply,
            "is_fallback": True,
            "suggestions": self._suggestions(lang),
        }

    def _suggestions(self, lang: str) -> list[str]:
        suggestions = {
            "ko": ["안녕", "도움말", "이 앱 기능이 뭐야?"],
            "en": ["Hello", "Help", "What does this app do?"],
            "ja": ["こんにちは", "ヘルプ", "このアプリは何ができますか？"],
            "zh-CN": ["你好", "帮助", "这个应用能做什么？"],
            "zh-TW": ["你好", "說明", "這個應用可以做什麼？"],
            "es": ["Hola", "Ayuda", "¿Qué hace esta aplicación?"],
        }
        return suggestions.get(lang, suggestions["en"])

    @staticmethod
    def _suggestions_for(keywords: list[str], lang: str) -> list[str]:
        greeting = {
            "ko": ["이 앱은 뭐하는 앱이야?", "도움말"],
            "en": ["What does this app do?", "Help"],
            "ja": ["このアプリは何ができますか？", "ヘルプ"],
            "zh-CN": ["这个应用能做什么？", "帮助"],
            "zh-TW": ["這個應用可以做什麼？", "說明"],
            "es": ["¿Qué hace esta aplicación?", "Ayuda"],
        }
        more = {
            "ko": ["더 자세히 알려줘"],
            "en": ["Tell me more"],
            "ja": ["詳しく教えて"],
            "zh-CN": ["请更详细地说明"],
            "zh-TW": ["請更詳細說明"],
            "es": ["Cuénteme más"],
        }
        if keywords is _GREETING_KEYWORDS:
            return greeting.get(lang, greeting["en"])
        if keywords is _HELP_KEYWORDS:
            return []
        return more.get(lang, more["en"])
