"""Импорт резюме из PDF.

Текст извлекается из PDF, делится на разделы по типичным заголовкам
(hh.ru, Хабр Карьера, экспорт Benefit) и разбирается эвристиками.
Результат — черновик полей профиля: пользователь проверяет его перед
сохранением. Парсер реализует протокол ``ResumeParser``, поэтому его можно
заменить, например, на разбор с помощью LLM, не меняя остальной код.
"""

import io
import logging
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Protocol

from fastapi import status
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.core.config import settings
from app.core.exceptions import AppError
from app.domain.dictionaries import (
    SOFT_SKILLS,
    Grade,
    ITRole,
    LanguageLevel,
    find_skill,
    normalize_skill,
)

logger = logging.getLogger(__name__)

MAX_PAGES = 15


@dataclass
class ParsedResume:
    draft: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


class ResumeParser(Protocol):
    def parse(self, text: str) -> ParsedResume: ...


def extract_text(raw: bytes) -> str:
    if len(raw) > settings.resume_import_max_bytes:
        raise AppError(
            "Файл должен быть не больше 10 МБ",
            code="file_too_large",
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
        )
    if not raw.startswith(b"%PDF"):
        raise AppError(
            "Загрузите файл в формате PDF", code="invalid_pdf", status_code=422
        )
    try:
        reader = PdfReader(io.BytesIO(raw))
        if reader.is_encrypted:
            raise AppError("PDF защищён паролем", code="encrypted_pdf", status_code=422)
        pages = reader.pages[:MAX_PAGES]
        text = "\n".join(page.extract_text() or "" for page in pages)
    except (PdfReadError, ValueError, KeyError) as exc:
        raise AppError(
            "Не удалось прочитать PDF", code="invalid_pdf", status_code=422
        ) from exc
    if not text.strip():
        raise AppError(
            "В PDF нет текста (возможно, это скан). Заполните профиль вручную",
            code="pdf_without_text",
            status_code=422,
        )
    return text


# --- Разделы -----------------------------------------------------------------

SECTION_HEADINGS: dict[str, list[str]] = {
    "contacts": ["контакты", "контактная информация", "contacts"],
    "position": [
        "желаемая должность и зарплата",
        "желаемая должность",
        "desired position",
    ],
    "about": [
        "обо мне",
        "о себе",
        "дополнительная информация",
        "about",
        "about me",
        "summary",
    ],
    "skills": [
        "ключевые навыки",
        "навыки",
        "стек технологий",
        "стек",
        "технологии",
        "skills",
        "key skills",
        "hard skills",
    ],
    "experience": ["опыт работы", "опыт", "experience", "work experience"],
    "projects": ["проекты", "пет-проекты", "портфолио", "projects"],
    "fsp": ["достижения фсп"],
    "education": ["образование", "высшее образование", "education"],
    "courses": [
        "курсы и сертификаты",
        "повышение квалификации, курсы",
        "курсы",
        "сертификаты",
        "courses",
        "certificates",
    ],
    "languages": ["знание языков", "языки", "languages"],
    "soft_skills": ["софт-скиллы", "soft skills", "личные качества"],
}

_HEADING_INDEX = sorted(
    ((h, key) for key, hs in SECTION_HEADINGS.items() for h in hs),
    key=lambda pair: -len(pair[0]),
)


def _heading(line: str) -> str | None:
    """Ключ раздела, если строка — заголовок (допускается хвост
    вида «Опыт работы — 4 года 9 месяцев»)."""
    normalized = line.strip().lower().rstrip(":")
    if len(normalized) > 60:
        return None
    for heading, key in _HEADING_INDEX:
        if normalized == heading:
            return key
        if normalized.startswith(heading) and re.match(
            r"^\s*[—–\-]", normalized[len(heading) :]
        ):
            return key
    return None


def split_sections(text: str) -> tuple[list[str], dict[str, list[str]]]:
    """Возвращает шапку (строки до первого заголовка) и разделы."""
    header: list[str] = []
    sections: dict[str, list[str]] = {}
    current: list[str] = header
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        key = _heading(line)
        if key:
            current = sections.setdefault(key, [])
            continue
        current.append(line)
    return header, sections


# --- Отдельные поля ------------------------------------------------------------

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PHONE_RE = re.compile(r"(?:\+7|8)[\s(-]*\d{3}[\s)-]*\d{3}[\s-]*\d{2}[\s-]*\d{2}")
TELEGRAM_RE = re.compile(r"(?:t\.me/|telegram:?\s*@?|(?<![\w.])@)([A-Za-z][\w]{4,31})")
URL_RE = re.compile(r"https?://[^\s,;]+|(?:github|gitlab)\.com/[\w.-]+[^\s,;]*")
NAME_WORD = r"[А-ЯЁA-Z][а-яёa-z]+(?:-[А-ЯЁA-Z][а-яёa-z]+)?"
NAME_RE = re.compile(rf"^({NAME_WORD})\s+({NAME_WORD})(?:\s+({NAME_WORD}))?$")

MONTHS_RU = {
    "январ": 1,
    "феврал": 2,
    "март": 3,
    "апрел": 4,
    "ма": 5,
    "июн": 6,
    "июл": 7,
    "август": 8,
    "сентябр": 9,
    "октябр": 10,
    "ноябр": 11,
    "декабр": 12,
}
MONTHS_EN = {
    m: i
    for i, m in enumerate(
        [
            "jan",
            "feb",
            "mar",
            "apr",
            "may",
            "jun",
            "jul",
            "aug",
            "sep",
            "oct",
            "nov",
            "dec",
        ],
        start=1,
    )
}
MONTH_WORD = r"[А-Яа-яЁёA-Za-z]{3,9}\.?"
DATE_POINT = rf"(?:{MONTH_WORD}\s+\d{{4}}|\d{{1,2}}[./]\d{{4}}|\d{{4}})"
PRESENT = r"(?:настоящее время|по настоящее время|сейчас|н\.в\.|present|now|current)"
PERIOD_RE = re.compile(
    rf"^(?P<start>{DATE_POINT})\s*[—–\-]+\s*(?P<end>{DATE_POINT}|{PRESENT})",
    re.IGNORECASE,
)
DURATION_RE = re.compile(r"^\d+\s+(год|года|лет|месяц|месяца|месяцев)", re.IGNORECASE)


def _month_number(word: str) -> int | None:
    word = word.lower().rstrip(".")
    for prefix, number in MONTHS_RU.items():
        if word.startswith(prefix) and (prefix != "ма" or word in ("май", "мая")):
            return number
    return MONTHS_EN.get(word[:3])


def parse_date_point(value: str) -> date | None:
    value = value.strip()
    if m := re.fullmatch(r"(\d{1,2})[./](\d{4})", value):
        month, year = int(m.group(1)), int(m.group(2))
        return date(year, month, 1) if 1 <= month <= 12 else None
    if m := re.fullmatch(r"(\d{4})", value):
        return date(int(m.group(1)), 1, 1)
    if m := re.fullmatch(rf"({MONTH_WORD})\s+(\d{{4}})", value):
        month = _month_number(m.group(1))
        return date(int(m.group(2)), month, 1) if month else None
    return None


def parse_birth_date(text: str) -> date | None:
    if m := re.search(
        r"(?:дата рождения|родил(?:ся|ась))[:\s]+(\d{1,2})[.\s]+"
        r"(\d{1,2}|[а-яё]+)[.\s]+(\d{4})",
        text,
        re.IGNORECASE,
    ):
        day, month_raw, year = m.groups()
        month = int(month_raw) if month_raw.isdigit() else _month_number(month_raw)
        try:
            return date(int(year), month or 0, int(day))
        except ValueError:
            return None
    return None


GRADE_KEYWORDS = [
    (Grade.LEAD, r"\b(lead|тимлид|team\s?lead|техлид|руководитель)\b"),
    (Grade.SENIOR, r"\b(senior|сеньор|старший|ведущий)\b"),
    (Grade.MIDDLE, r"\b(middle|мидл)\b"),
    (Grade.JUNIOR, r"\b(junior|джун|джуниор|младший)\b"),
    (Grade.INTERN, r"\b(intern|стаж[её]р|стажировка)\b"),
]

ROLE_KEYWORDS = [
    (ITRole.FULLSTACK, r"full[\s-]?stack|фулл?стек"),
    (ITRole.BACKEND, r"back[\s-]?end|бэкенд|бекенд|серверн"),
    (ITRole.FRONTEND, r"front[\s-]?end|фронтенд"),
    (ITRole.MOBILE, r"\b(ios|android|mobile|мобильн|flutter)"),
    (ITRole.DEVOPS, r"devops|\bsre\b"),
    (ITRole.QA_AUTOMATION, r"автоматизатор|aqa|qa automation|automation qa"),
    (ITRole.QA, r"\bqa\b|тестировщик|тестирован"),
    (ITRole.DATA_SCIENTIST, r"data scien|дата сайент"),
    (ITRole.ML_ENGINEER, r"\bml\b|machine learning|машинн\w+ обучени"),
    (ITRole.DATA_ENGINEER, r"data engineer|инженер данных"),
    (ITRole.DATA_ANALYST, r"data analyst|аналитик данных|bi[\s-]аналитик"),
    (ITRole.SYSTEM_ANALYST, r"системн\w+ аналитик|system analyst"),
    (ITRole.BUSINESS_ANALYST, r"бизнес[\s-]аналитик|business analyst"),
    (ITRole.PRODUCT_MANAGER, r"product manager|продакт|менеджер продукта"),
    (ITRole.PROJECT_MANAGER, r"project manager|проджект|руководитель проект"),
    (ITRole.DESIGNER, r"дизайнер|designer|ui/ux"),
    (ITRole.GAMEDEV, r"gamedev|game developer|разработчик игр|unity|unreal"),
    (ITRole.SECURITY, r"безопасност|security|пентест|pentest"),
    (ITRole.EMBEDDED, r"embedded|встраиваем|микроконтроллер"),
    (ITRole.DBA, r"\bdba\b|администратор (бд|баз)"),
    (ITRole.TEAM_LEAD, r"тимлид|team\s?lead"),
    (ITRole.ARCHITECT, r"архитектор|architect"),
]

LANGUAGE_NAMES = {
    "русский": "Русский",
    "английский": "Английский",
    "english": "Английский",
    "немецкий": "Немецкий",
    "французский": "Французский",
    "испанский": "Испанский",
    "китайский": "Китайский",
    "японский": "Японский",
    "корейский": "Корейский",
    "итальянский": "Итальянский",
    "турецкий": "Турецкий",
    "казахский": "Казахский",
    "татарский": "Татарский",
}
# Сначала явные коды CEFR, затем слова; более длинные формулировки раньше
# коротких («средне-продвинутый» — B2, а не C1).
LEVEL_WORDS = [
    *((level, rf"\b{level.value.lower()}\b") for level in LanguageLevel),
    (LanguageLevel.NATIVE, r"родной|native"),
    (LanguageLevel.C2, r"в совершенстве|proficient"),
    (LanguageLevel.B2, r"upper[\s-]intermediate|средне-продвинутый"),
    (LanguageLevel.C1, r"продвинутый|advanced|свободн"),
    (LanguageLevel.B1, r"intermediate|средний"),
    (LanguageLevel.A2, r"elementary|элементарный"),
    (LanguageLevel.A1, r"beginner|начальный|базовый"),
]


def _first_match(text: str, patterns: list[tuple[Any, str]]) -> Any | None:
    for value, pattern in patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return value
    return None


def _split_list(lines: list[str]) -> list[str]:
    items = []
    for line in lines:
        for part in re.split(r"\s*[,;•·|]\s*|\s{2,}", line):
            part = re.sub(r"\s*\((базовый|уверенный|продвинутый|эксперт)\)$", "", part)
            part = part.strip(" -–—.")
            if 1 <= len(part) <= 64:
                items.append(part)
    return items


def _skills(sections: dict[str, list[str]], text: str) -> list[dict[str, Any]]:
    names: list[str] = []
    for item in _split_list(sections.get("skills", [])):
        names.append(normalize_skill(item))
    # Навыки из каталога, упомянутые в опыте («Стек: …») и проектах.
    for line in text.splitlines():
        if m := re.match(r"^\s*(стек|технологии|stack)\s*:\s*(.+)$", line, re.I):
            names.extend(normalize_skill(i) for i in _split_list([m.group(2)]))
    seen: set[str] = set()
    result = []
    for name in names:
        if name.lower() not in seen and (find_skill(name) or len(name) <= 40):
            seen.add(name.lower())
            result.append({"name": name})
    return result[:100]


def _languages(lines: list[str]) -> list[dict[str, str]]:
    result = []
    for line in lines:
        lowered = line.lower()
        name = next((v for k, v in LANGUAGE_NAMES.items() if k in lowered), None)
        level = _first_match(lowered, LEVEL_WORDS)
        if name and level and all(r["language"] != name for r in result):
            result.append({"language": name, "level": level.value})
    return result


PERIOD_HEAD_RE = re.compile(
    rf"^{DATE_POINT}\s*[—–\-]+\s*(?:{MONTH_WORD}|по)?$", re.IGNORECASE
)


def _join_wrapped_periods(lines: list[str]) -> list[str]:
    """Склеивает период, перенесённый на следующую строку:
    «Март 2022 —» + «настоящее время», «Июнь 2021 — Февраль» + «2022»."""
    result: list[str] = []
    for line in lines:
        if result and PERIOD_HEAD_RE.match(result[-1]):
            result[-1] = f"{result[-1]} {line}"
        else:
            result.append(line)
    return result


def _experience(lines: list[str], warnings: list[str]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    lines = _join_wrapped_periods(lines)
    blocks: list[tuple[re.Match[str], list[str]]] = []
    for line in lines:
        if m := PERIOD_RE.match(line):
            rest = line[m.end() :].strip()
            blocks.append((m, [rest] if rest else []))
        elif blocks:
            blocks[-1][1].append(line)

    for match, body in blocks:
        start = parse_date_point(match.group("start"))
        end_raw = match.group("end")
        end = (
            None if re.fullmatch(PRESENT, end_raw, re.I) else parse_date_point(end_raw)
        )
        body = [line for line in body if not DURATION_RE.match(line)]
        if start is None or len(body) < 2:
            warnings.append(f"Не удалось разобрать место работы: {match.group(0)}")
            continue
        company, *rest = body
        # Строка «Город, сайт» после компании (формат hh.ru).
        if rest and re.search(r"\.(ru|com|рф|io|net|org)\b|^[А-ЯЁ][а-яё-]+,", rest[0]):
            rest = rest[1:]
        if not rest:
            warnings.append(f"Не найдена должность: {company}")
            continue
        position, *details = rest
        technologies: list[str] = []
        achievements: list[str] = []
        description: list[str] = []
        for line in details:
            if m := re.match(r"^\s*(стек|технологии|stack)\s*:\s*(.+)$", line, re.I):
                technologies = [normalize_skill(i) for i in _split_list([m.group(2)])]
            elif re.match(r"^[•\-–]\s+", line):
                achievements.append(re.sub(r"^[•\-–]\s+", "", line)[:500])
            else:
                description.append(line)
        entries.append(
            {
                "company": company[:200],
                "position": position[:200],
                "start_date": start.isoformat(),
                "end_date": end.isoformat() if end else None,
                "description": "\n".join(description)[:4000] or None,
                "achievements": achievements[:20],
                "technologies": technologies[:50],
            }
        )
    return entries


def _year_blocks(
    lines: list[str], year_key: str, name_key: str, detail_key: str
) -> list[dict[str, Any]]:
    """Записи вида «2020» + «Название» + «Детали» (или «2020 Название»)."""
    result: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for line in lines:
        if m := re.fullmatch(r"(\d{4})(?:\s+(.+))?", line):
            current = {year_key: int(m.group(1))}
            if m.group(2):
                current[name_key] = m.group(2)[:200]
            result.append(current)
        elif current is not None and name_key not in current:
            current[name_key] = line[:200]
        elif current is not None and detail_key not in current:
            current[detail_key] = line[:200]
    return [item for item in result if name_key in item]


def _education(lines: list[str]) -> list[dict[str, Any]]:
    return _year_blocks(lines, "graduation_year", "institution", "faculty")


def _courses(lines: list[str]) -> list[dict[str, Any]]:
    return _year_blocks(lines, "year", "name", "organization")


class HeuristicResumeParser:
    def parse(self, text: str) -> ParsedResume:
        result = ParsedResume()
        draft, warnings = result.draft, result.warnings
        header, sections = split_sections(text)
        top = header + sections.get("contacts", [])

        for line in header[:3]:
            if m := NAME_RE.match(line):
                draft["last_name"], draft["first_name"] = m.group(1), m.group(2)
                if m.group(3):
                    draft["middle_name"] = m.group(3)
                break
        else:
            warnings.append("Не удалось определить ФИО")

        contacts_text = "\n".join(top)
        if m := EMAIL_RE.search(contacts_text) or EMAIL_RE.search(text):
            draft["contact_email"] = m.group(0).lower()
        if m := PHONE_RE.search(contacts_text) or PHONE_RE.search(text):
            draft["phone"] = m.group(0)
        if m := TELEGRAM_RE.search(contacts_text):
            draft["telegram"] = m.group(1)
        links = []
        for url in URL_RE.findall(text):
            url = url if url.startswith("http") else f"https://{url}"
            link_type = next(
                (t for t in ("github", "gitlab", "linkedin", "habr") if t in url),
                "portfolio",
            )
            if all(link["url"] != url for link in links):
                links.append({"type": link_type, "url": url.rstrip(".")})
        if links:
            draft["links"] = links[:10]

        if birth := parse_birth_date(text):
            draft["birth_date"] = birth.isoformat()
        if m := re.search(
            r"(?i:проживает|город)[: ]+([А-ЯЁ][а-яё-]+(?:[ -][А-ЯЁ][а-яё-]+)?)", text
        ):
            draft["city"] = m.group(1)

        position_lines = sections.get("position", [])
        headline = position_lines[0] if position_lines else None
        if headline is None:
            # В шапке строка с IT-ролью сразу после ФИО.
            headline = next(
                (ln for ln in header[1:4] if _first_match(ln, ROLE_KEYWORDS)), None
            )
        if headline:
            draft["headline"] = headline[:200]
        if m := re.search(
            r"от\s+([\d\s]{4,})\s*(₽|руб)", "\n".join(position_lines + header)
        ):
            draft["salary_from"] = int(re.sub(r"\s", "", m.group(1)))

        grade = _first_match(headline or "", GRADE_KEYWORDS) or _first_match(
            "\n".join(header), GRADE_KEYWORDS
        )
        if grade:
            draft["grade"] = grade.value
        roles = [
            role.value
            for role, pattern in ROLE_KEYWORDS
            if re.search(pattern, headline or "", re.IGNORECASE)
        ]
        if roles:
            draft["roles"] = roles[:5]

        if about := sections.get("about"):
            draft["about"] = "\n".join(about)[:4000]
        if skills := _skills(sections, text):
            draft["skills"] = skills
        else:
            warnings.append("Не найден раздел с навыками")

        soft = [s for s in SOFT_SKILLS if re.search(re.escape(s), text, re.IGNORECASE)]
        soft += [
            s
            for s in _split_list(sections.get("soft_skills", []))
            if s.lower() not in {x.lower() for x in soft}
        ]
        if soft:
            draft["soft_skills"] = soft[:30]

        if languages := _languages(sections.get("languages", [])):
            draft["languages"] = languages
        if experience := _experience(sections.get("experience", []), warnings):
            draft["experience"] = experience
        if education := _education(sections.get("education", [])):
            draft["education"] = education
        if courses := _courses(sections.get("courses", [])):
            draft["courses"] = courses
        if "fsp" in sections:
            warnings.append(
                "Достижения ФСП не импортируются из файла: они загружаются "
                "напрямую из ФСП ID"
            )
        return result


def get_resume_parser() -> ResumeParser:
    return HeuristicResumeParser()
