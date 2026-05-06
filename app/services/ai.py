import json
import logging
from functools import lru_cache

from app.core.config import get_settings
from app.services.grouping import (
    GroupTemplate,
    classify_ticket_fallback,
    enhance_text_fallback,
    generate_title,
    normalize_group_key,
)

try:
    from yandex_cloud_ml_sdk import YCloudML
except ImportError:  # pragma: no cover
    YCloudML = None


settings = get_settings()
logger = logging.getLogger(__name__)


class AIService:
    def __init__(self) -> None:
        self._sdk = None
        self._model = None

    def is_available(self) -> bool:
        available = bool(YCloudML and settings.yandex_folder_id and settings.yandex_auth_token)
        if not available:
            logger.info("Yandex AI provider disabled: missing SDK or YANDEX_FOLDER_ID / YANDEX_AUTH_TOKEN")
        return available

    def _get_model(self):
        if not self.is_available():
            return None
        if self._model is None:
            self._sdk = YCloudML(folder_id=settings.yandex_folder_id, auth=settings.yandex_auth_token)
            model = self._sdk.models.completions(settings.yandex_gpt_model)
            model.configure(
                temperature=settings.yandex_gpt_temperature,
                max_tokens=settings.yandex_gpt_max_tokens,
            )
            self._model = model
        return self._model

    def _run(self, *, system_prompt: str, user_prompt: str) -> str | None:
        model = self._get_model()
        if model is None:
            return None
        try:
            result = model.run(
                [
                    {"role": "system", "text": system_prompt},
                    {"role": "user", "text": user_prompt},
                ]
            )
        except Exception:
            logger.exception("Yandex AI request failed, using fallback")
            return None
        text = getattr(result, "text", None)
        return text.strip() if isinstance(text, str) and text.strip() else None

    def enhance_ticket_description(self, original_text: str) -> tuple[str, str]:
        display_prefix = "[AI-enhanced]"
        system_prompt = (
            "Ты помощник поддержки сотрудников. Перепиши описание тикета в нейтральном, "
            "безличном и стандартизированном стиле: исправь грамматику, убери разговорные обороты, "
            "эмоциональные формулировки, индивидуальные стилистические особенности автора и любые "
            "личные маркеры письма. Сохрани только факты, проблему, симптомы и контекст, не меняя смысл. "
            "Верни только итоговый текст на том же языке."
        )
        response = self._run(system_prompt=system_prompt, user_prompt=original_text)
        if not response:
            logger.info("Using fallback enhancement for ticket description")
            return enhance_text_fallback(original_text)
        cleaned = " ".join(response.split())
        if cleaned and cleaned[-1] not in ".!?":
            cleaned = f"{cleaned}."
        if not cleaned.startswith(display_prefix):
            cleaned = f"{display_prefix} {cleaned}"
        return display_prefix, cleaned

    def generate_ticket_title(self, description: str) -> str:
        system_prompt = (
            "Ты помощник поддержки сотрудников. Сгенерируй короткий, нейтральный и информативный "
            "заголовок тикета по описанию проблемы. Не добавляй кавычки, префиксы, номера или пояснения. "
            "Ответ должен быть одной строкой на том же языке, не длиннее 200 символов."
        )
        response = self._run(system_prompt=system_prompt, user_prompt=description)
        if not response:
            logger.info("Using fallback title generation for ticket")
            return generate_title(None, description)
        title = " ".join(response.split())
        return title[:200].rstrip() or generate_title(None, description)

    def classify_ticket(self, text: str) -> GroupTemplate:
        fallback = classify_ticket_fallback(text)
        system_prompt = (
            "Ты группируешь внутренние employee tickets в смысловые кластеры. "
            "Сгенерируй устойчивый semantic key для группы, короткий и в snake_case на латинице. "
            "Для похожих проблем возвращай один и тот же key. "
            "Верни только JSON объекта вида "
            '{"clusterKey":"vpn_access_disconnects","title":"...","summary":"..."} . '
            "title должен быть коротким названием группы на русском. "
            "summary должен быть кратким AI summary на английском."
        )
        response = self._run(system_prompt=system_prompt, user_prompt=text)
        if not response:
            logger.info("Using fallback classification for ticket grouping")
            return fallback
        try:
            payload = json.loads(response)
        except json.JSONDecodeError:
            logger.warning("Yandex AI returned non-JSON classification payload, using fallback")
            return fallback

        category_key = payload.get("clusterKey") or payload.get("categoryKey")
        title = payload.get("title")
        summary = payload.get("summary")
        if isinstance(category_key, str) and category_key.strip():
            return GroupTemplate(
                key=normalize_group_key(category_key),
                title=title.strip() if isinstance(title, str) and title.strip() else fallback.title,
                summary=summary.strip() if isinstance(summary, str) and summary.strip() else fallback.summary,
            )
        logger.info("Yandex AI returned invalid cluster key '%s', using fallback", category_key)
        return fallback


@lru_cache
def get_ai_service() -> AIService:
    return AIService()
