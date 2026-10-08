"""Сборка писем из шаблонов в ``app/templates``.

Шаблон — пара файлов ``<name>.txt`` и ``<name>.html``, параметры
подставляются через ``string.Template`` (``$code``); в HTML значения
экранируются.
"""

import html
from email.message import EmailMessage
from pathlib import Path
from string import Template

from app.core.config import settings

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"


def render(
    name: str,
    *,
    to: str,
    subject: str,
    params: dict[str, object],
    raw_html: dict[str, str] | None = None,
) -> EmailMessage:
    """``raw_html`` — уже безопасные HTML-фрагменты (не экранируются)."""
    text = Template((TEMPLATES_DIR / f"{name}.txt").read_text("utf-8"))
    markup = Template((TEMPLATES_DIR / f"{name}.html").read_text("utf-8"))

    message = EmailMessage()
    message["From"] = settings.mail_from
    message["To"] = to
    message["Subject"] = subject
    message.set_content(text.substitute(params))
    message.add_alternative(
        markup.substitute(
            {k: html.escape(str(v)) for k, v in params.items()} | (raw_html or {})
        ),
        subtype="html",
    )
    return message
