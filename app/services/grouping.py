from dataclasses import dataclass


@dataclass(frozen=True)
class GroupTemplate:
    key: str
    title: str
    summary: str


GROUP_RULES: list[tuple[tuple[str, ...], GroupTemplate]] = [
    (
        ("почт", "email", "outlook", "mail", "парол"),
        GroupTemplate(
            key="corporate_email",
            title="Ошибка входа в корпоративную почту после смены пароля",
            summary="Several employees report losing access to corporate email after password changes or mail client re-authentication.",
        ),
    ),
    (
        ("vpn", "впн"),
        GroupTemplate(
            key="vpn_access",
            title="Проблемы с доступом к VPN",
            summary="Multiple employees report unstable VPN access that interrupts work with internal tools.",
        ),
    ),
    (
        ("монитор", "monitor", "display", "экран"),
        GroupTemplate(
            key="monitor_request",
            title="Запрос на дополнительный монитор",
            summary="Employees request additional monitors or report missing monitor equipment for daily work.",
        ),
    ),
    (
        ("онбординг", "onboarding", "новый сотрудник", "new hire"),
        GroupTemplate(
            key="onboarding",
            title="Вопросы по онбордингу новых сотрудников",
            summary="Employees share recurring onboarding issues and suggestions for improving the new hire experience.",
        ),
    ),
]


def classify_ticket(text: str) -> GroupTemplate:
    return classify_ticket_fallback(text)


def classify_ticket_fallback(text: str) -> GroupTemplate:
    haystack = text.lower()
    for keywords, template in GROUP_RULES:
        if any(keyword in haystack for keyword in keywords):
            return template

    short = " ".join(text.strip().split())
    short = short[:80].rstrip(" .,;:-") or "General issue"
    return GroupTemplate(
        key=f"custom_{abs(hash(short.lower())) % 10_000_000}",
        title=short,
        summary=f"AI summary for similar tickets related to: {short}.",
    )


def build_excerpt(text: str, limit: int = 90) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 3].rstrip() + "..."


def generate_title(title: str | None, description: str) -> str:
    if title:
        return title.strip()
    first_line = description.strip().splitlines()[0]
    compact = " ".join(first_line.split())
    return compact[:200].rstrip() or "Untitled ticket"


def enhance_text(original_text: str) -> tuple[str, str]:
    return enhance_text_fallback(original_text)


def enhance_text_fallback(original_text: str) -> tuple[str, str]:
    display_prefix = "[AI-enhanced]"
    normalized = " ".join(original_text.split())
    if normalized and normalized[-1] not in ".!?":
        normalized = f"{normalized}."
    enhanced = f"{display_prefix} {normalized}"
    return display_prefix, enhanced
