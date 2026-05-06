from dataclasses import dataclass
import re


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


def normalize_group_key(text: str) -> str:
    lowered = text.lower().strip()
    transliterated = (
        lowered.replace("а", "a")
        .replace("б", "b")
        .replace("в", "v")
        .replace("г", "g")
        .replace("д", "d")
        .replace("е", "e")
        .replace("ё", "e")
        .replace("ж", "zh")
        .replace("з", "z")
        .replace("и", "i")
        .replace("й", "i")
        .replace("к", "k")
        .replace("л", "l")
        .replace("м", "m")
        .replace("н", "n")
        .replace("о", "o")
        .replace("п", "p")
        .replace("р", "r")
        .replace("с", "s")
        .replace("т", "t")
        .replace("у", "u")
        .replace("ф", "f")
        .replace("х", "h")
        .replace("ц", "c")
        .replace("ч", "ch")
        .replace("ш", "sh")
        .replace("щ", "sch")
        .replace("ъ", "")
        .replace("ы", "y")
        .replace("ь", "")
        .replace("э", "e")
        .replace("ю", "yu")
        .replace("я", "ya")
    )
    normalized = re.sub(r"[^a-z0-9]+", "_", transliterated)
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    return normalized[:64] or f"group_{abs(hash(text.lower())) % 10_000_000}"


def classify_ticket_fallback(text: str) -> GroupTemplate:
    haystack = text.lower()
    for keywords, template in GROUP_RULES:
        if any(keyword in haystack for keyword in keywords):
            return GroupTemplate(
                key=normalize_group_key(template.title),
                title=template.title,
                summary=template.summary,
            )

    short = " ".join(text.strip().split())
    short = short[:80].rstrip(" .,;:-") or "General issue"
    return GroupTemplate(
        key=normalize_group_key(short),
        title=short,
        summary=f"AI summary for similar tickets related to: {short}.",
    )


def build_excerpt(text: str, limit: int = 90) -> str:
    normalized = " ".join(text.split())
    return normalized


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
