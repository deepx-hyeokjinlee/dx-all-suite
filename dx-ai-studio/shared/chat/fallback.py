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
                  "DEEPX Edge AI 플랫폼에 대해 무엇이든 물어보세요!\n\n"
                  "💡 AI 응답을 사용하려면 채팅 설정(⚙️)에서 API 키를 설정하세요.",
            "en": "Hello! 🤖 I'm **DX Assistant**.\n"
                  "Ask me anything about the DEEPX Edge AI platform!\n\n"
                  "💡 To use AI responses, open chat settings (⚙️) and set your API key.",
            "ja": "こんにちは! 🤖 **DX Assistant** です。\n"
                  "DEEPX Edge AI プラットフォームについて何でも質問してください!\n\n"
                  "💡 AI 応答を使用するには、チャット設定(⚙️)で API キーを設定してください。",
            "zh-CN": "你好！🤖 我是 **DX Assistant**。\n"
                     "欢迎询问任何有关 DEEPX Edge AI 平台的问题！\n\n"
                     "💡 要使用 AI 响应，请在聊天设置(⚙️)中设置 API 密钥。",
            "zh-TW": "你好！🤖 我是 **DX Assistant**。\n"
                     "歡迎詢問任何關於 DEEPX Edge AI 平台的問題！\n\n"
                     "💡 若要使用 AI 回應，請在聊天設定(⚙️)中設定 API 金鑰。",
            "es": "¡Hola! 🤖 Soy **DX Assistant**.\n"
                  "Pregúnteme lo que desee sobre la plataforma DEEPX Edge AI.\n\n"
                  "💡 Para usar respuestas de IA, abra la configuración del chat (⚙️) y establezca su clave API.",
        },
    ),
    (
        ["도움", "help", "사용법", "기능", "ヘルプ", "帮助", "說明",
         "what does this app do", "이 앱", "このアプリ", "这个应用", "這個應用"],
        {
            "ko": "**DX AI Studio** 주요 기능:\n"
                  "- **DX App** — NPU 실시간 추론, 데모 실행, 모델 비교\n"
                  "- **DX Stream** — GStreamer 영상 파이프라인 · 데모\n"
                  "- **DX Model Zoo** — 약 500개 DEEPX 모델 카탈로그\n"
                  "- **DX Compiler** — ONNX → DXNN 컴파일\n"
                  "- **DX Benchmark** — 보드별 실측 성능\n"
                  "- **DX Monitor** — NPU · 시스템 실시간 상태\n"
                  "- **DX EdgeGuide** — 작업에 맞는 보드 · 호스트 추천\n"
                  "- **DX Agent Dev** — 자연어로 NPU 앱 만들기",
            "en": "**DX AI Studio** key features:\n"
                  "- **DX App** — real-time NPU inference, demos, model comparison\n"
                  "- **DX Stream** — GStreamer video pipelines and demos\n"
                  "- **DX Model Zoo** — catalog of nearly 500 DEEPX models\n"
                  "- **DX Compiler** — ONNX → DXNN compilation\n"
                  "- **DX Benchmark** — measured performance per board\n"
                  "- **DX Monitor** — live NPU and system status\n"
                  "- **DX EdgeGuide** — board and host recommendation for a workload\n"
                  "- **DX Agent Dev** — build NPU apps in natural language",
            "ja": "**DX AI Studio** の主な機能:\n"
                  "- **DX App** — NPU リアルタイム推論、デモ実行、モデル比較\n"
                  "- **DX Stream** — GStreamer 映像パイプラインとデモ\n"
                  "- **DX Model Zoo** — 約 500 の DEEPX モデルカタログ\n"
                  "- **DX Compiler** — ONNX → DXNN コンパイル\n"
                  "- **DX Benchmark** — ボードごとの実測性能\n"
                  "- **DX Monitor** — NPU とシステムのリアルタイム状態\n"
                  "- **DX EdgeGuide** — ワークロードに合うボードとホストの推奨\n"
                  "- **DX Agent Dev** — 自然言語で NPU アプリを作成",
            "zh-CN": "**DX AI Studio** 主要功能:\n"
                     "- **DX App** — NPU 实时推理、演示运行、模型对比\n"
                     "- **DX Stream** — GStreamer 视频管道与演示\n"
                     "- **DX Model Zoo** — 近 500 个 DEEPX 模型目录\n"
                     "- **DX Compiler** — ONNX → DXNN 编译\n"
                     "- **DX Benchmark** — 各开发板的实测性能\n"
                     "- **DX Monitor** — NPU 与系统实时状态\n"
                     "- **DX EdgeGuide** — 按工作负载推荐开发板与主机\n"
                     "- **DX Agent Dev** — 用自然语言构建 NPU 应用",
            "zh-TW": "**DX AI Studio** 主要功能:\n"
                     "- **DX App** — NPU 即時推論、示範執行、模型比較\n"
                     "- **DX Stream** — GStreamer 影像管線與示範\n"
                     "- **DX Model Zoo** — 近 500 個 DEEPX 模型目錄\n"
                     "- **DX Compiler** — ONNX → DXNN 編譯\n"
                     "- **DX Benchmark** — 各開發板的實測效能\n"
                     "- **DX Monitor** — NPU 與系統即時狀態\n"
                     "- **DX EdgeGuide** — 依工作負載推薦開發板與主機\n"
                     "- **DX Agent Dev** — 用自然語言建立 NPU 應用程式",
            "es": "Funciones principales de **DX AI Studio**:\n"
                  "- **DX App** — inferencia NPU en tiempo real, demos y comparación de modelos\n"
                  "- **DX Stream** — pipelines de vídeo GStreamer y demos\n"
                  "- **DX Model Zoo** — catálogo de casi 500 modelos DEEPX\n"
                  "- **DX Compiler** — compilación ONNX → DXNN\n"
                  "- **DX Benchmark** — rendimiento medido por placa\n"
                  "- **DX Monitor** — estado en vivo de la NPU y del sistema\n"
                  "- **DX EdgeGuide** — recomendación de placa y host para una carga de trabajo\n"
                  "- **DX Agent Dev** — cree apps para NPU en lenguaje natural",
        },
    ),
]

SETUP_BANNER = {
    "ko": "⚠️ 연결된 AI 모델이 없습니다 — Studio는 **모델을 내장하지 않습니다** (오프라인 우선 설계).\n"
          "• **채팅 설정**(⚙️)에서 API 키(OpenAI/Anthropic/Google 등)를 설정하거나\n"
          "• 완전 오프라인으로 사용: **local**(자체 Ollama 호환 서버) 또는 **agent-cli**(이미 로그인된 claude/copilot/cursor/opencode CLI 재사용) — 클라우드 키가 필요 없습니다.",
    "en": "⚠️ No AI model connected — Studio ships with **no bundled model** (offline by design).\n"
          "• Set an API key (OpenAI/Anthropic/Google/etc.) in **chat settings** (⚙️), or\n"
          "• Go fully offline: choose **local** (your own Ollama-compatible server) or **agent-cli** (reuse an already-logged-in claude/copilot/cursor/opencode CLI) — no cloud key needed.",
    "ja": "⚠️ 接続された AI モデルがありません — Studio は**モデルを同梱していません**(オフライン設計)。\n"
          "• **チャット設定**(⚙️)で API キー(OpenAI/Anthropic/Google など)を設定するか、\n"
          "• 完全オフラインで利用: **local**(自前の Ollama 互換サーバー)または **agent-cli**(ログイン済みの claude/copilot/cursor/opencode CLI を再利用)— クラウドキー不要。",
    "zh-CN": "⚠️ 尚未连接 AI 模型 — Studio **不内置任何模型**(按设计离线运行)。\n"
             "• 在**聊天设置**(⚙️)中设置 API 密钥(OpenAI/Anthropic/Google 等)，或\n"
             "• 完全离线使用：选择 **local**(您自己的 Ollama 兼容服务器)或 **agent-cli**(复用已登录的 claude/copilot/cursor/opencode CLI)——无需云端密钥。",
    "zh-TW": "⚠️ 尚未連接 AI 模型 — Studio **不內建任何模型**(依設計離線運作)。\n"
             "• 在**聊天設定**(⚙️)中設定 API 金鑰(OpenAI/Anthropic/Google 等)，或\n"
             "• 完全離線使用：選擇 **local**(您自己的 Ollama 相容伺服器)或 **agent-cli**(重複使用已登入的 claude/copilot/cursor/opencode CLI)——不需要雲端金鑰。",
    "es": "⚠️ No hay ningún modelo de IA conectado — Studio **no incluye ningún modelo** (diseñado para funcionar sin conexión).\n"
          "• Establezca una clave API (OpenAI/Anthropic/Google, etc.) en la **configuración del chat** (⚙️), o\n"
          "• Use el modo totalmente sin conexión: elija **local** (su propio servidor compatible con Ollama) o **agent-cli** (reutilice una CLI claude/copilot/cursor/opencode ya autenticada) — sin necesidad de clave en la nube.",
}

DEFAULT_RESPONSE = {
    "ko": "죄송합니다, 현재 AI 모델이 연결되어 있지 않아 자세한 답변이 어렵습니다.\n\n"
          "**채팅 설정**(⚙️)에서 API 키를 설정하시면 더 정확한 답변을 받을 수 있습니다.\n\n"
          "**지원 프로바이더:** OpenAI, Anthropic (Claude), Google (Gemini), GitHub Models, local (Ollama 호환), agent-cli, Custom",
    "en": "Sorry, no AI model is currently connected for detailed responses.\n\n"
          "Set your API key in **chat settings** (⚙️) for more accurate answers.\n\n"
          "**Supported providers:** OpenAI, Anthropic (Claude), Google (Gemini), GitHub Models, local (Ollama-compatible), agent-cli, Custom",
    "ja": "申し訳ありません。現在 AI モデルが接続されていないため、詳細な回答はできません。\n\n"
          "**チャット設定**(⚙️)で API キーを設定すると、より正確な回答を利用できます。\n\n"
          "**対応プロバイダー:** OpenAI, Anthropic (Claude), Google (Gemini), GitHub Models, local (Ollama 互換), agent-cli, Custom",
    "zh-CN": "抱歉，当前未连接 AI 模型，无法提供详细回答。\n\n"
             "请在**聊天设置**(⚙️)中设置 API 密钥，以获得更准确的回答。\n\n"
             "**支持的提供商:** OpenAI, Anthropic (Claude), Google (Gemini), GitHub Models, local (兼容 Ollama), agent-cli, Custom",
    "zh-TW": "抱歉，目前未連接 AI 模型，無法提供詳細回答。\n\n"
             "請在**聊天設定**(⚙️)中設定 API 金鑰，以取得更準確的回答。\n\n"
             "**支援的提供者:** OpenAI, Anthropic (Claude), Google (Gemini), GitHub Models, local (相容 Ollama), agent-cli, Custom",
    "es": "Lo sentimos, actualmente no hay un modelo de IA conectado para respuestas detalladas.\n\n"
          "Establezca su clave API en la **configuración del chat** (⚙️) para obtener respuestas más precisas.\n\n"
          "**Proveedores compatibles:** OpenAI, Anthropic (Claude), Google (Gemini), GitHub Models, local (compatible con Ollama), agent-cli, Custom",
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
