"""Ограничение регистрации по почте российскими доменами."""

from app.core.config import settings


def _to_ascii(domain: str) -> str:
    """Punycode-форма домена: ``пример.рф`` -> ``xn--e1afmkfd.xn--p1ai``."""
    return domain.strip().rstrip(".").lower().encode("idna").decode("ascii")


def is_email_domain_allowed(email: str) -> bool:
    """Разрешены домены в российских зонах (.ru, .su, .рф) и явно
    перечисленные в ``ALLOWED_EMAIL_DOMAINS``."""
    domain = _to_ascii(email.rsplit("@", 1)[-1])
    allowed_domains = {_to_ascii(d) for d in settings.allowed_email_domains}
    if domain in allowed_domains:
        return True
    allowed_tlds = {_to_ascii(tld) for tld in settings.allowed_email_tlds}
    return domain.rsplit(".", 1)[-1] in allowed_tlds
