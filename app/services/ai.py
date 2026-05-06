import json
from functools import lru_cache

from app.core.config import get_settings
from app.services.grouping import (
    GroupTemplate,
    classify_ticket_fallback,
    enhance_text_fallback,
)

try:
    from yandex_cloud_ml_sdk import YCloudML
except ImportError:  # pragma: no cover
    YCloudML = None


settings = get_settings()


class AIService:
    def __init__(self) -> None:
        self._sdk = None
        self._model = None

    def is_available(self) -> bool:
        return bool(YCloudML and settings.yandex_folder_id and settings.yandex_auth_token)

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
            return None
        text = getattr(result, "text", None)
        return text.strip() if isinstance(text, str) and text.strip() else None

    def enhance_ticket_description(self, original_text: str) -> tuple[str, str]:
        display_prefix = "[AI-enhanced]"
        system_prompt = (
            "Ты помощник поддержки сотрудников. Улучши описание тикета: исправь грамматику, "
            "убери лишнюю разговорность, сохрани смысл. Верни только итоговый текст на том же языке."
        )
        response = self._run(system_prompt=system_prompt, user_prompt=original_text)
        if not response:
            return enhance_text_fallback(original_text)
        cleaned = " ".join(response.split())
        if cleaned and cleaned[-1] not in ".!?":
            cleaned = f"{cleaned}."
        if not cleaned.startswith(display_prefix):
            cleaned = f"{display_prefix} {cleaned}"
        return display_prefix, cleaned

    def classify_ticket(self, text: str) -> GroupTemplate:
        fallback = classify_ticket_fallback(text)
        system_prompt = (
            "Ты группируешь внутренние employee tickets по фиксированным категориям. "
            "Выбери categoryKey только из списка: corporate_email, vpn_access, monitor_request, onboarding, other. "
            "Верни только JSON объекта вида "
            '{"categoryKey":"vpn_access","title":"...","summary":"..."} . '
            "title должен быть коротким названием группы на русском. "
            "summary должен быть кратким AI summary на английском. "
            "Если категория не подходит, используй other."
        )
        response = self._run(system_prompt=system_prompt, user_prompt=text)
        if not response:
            return fallback
        try:
            payload = json.loads(response)
        except json.JSONDecodeError:
            return fallback

        category_key = payload.get("categoryKey")
        title = payload.get("title")
        summary = payload.get("summary")
        if category_key in {"corporate_email", "vpn_access", "monitor_request", "onboarding"}:
            return GroupTemplate(
                key=category_key,
                title=title.strip() if isinstance(title, str) and title.strip() else fallback.title,
                summary=summary.strip() if isinstance(summary, str) and summary.strip() else fallback.summary,
            )
        return fallback


@lru_cache
def get_ai_service() -> AIService:
    return AIService()
