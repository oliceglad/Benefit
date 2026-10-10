"""Поиск ИНН на сайте компании.

Сайт указывает сам работодатель, поэтому запрос — потенциальный SSRF:
разрешены только http(s) на стандартных портах и только публичные адреса
(каждый редирект проверяется заново), ответ читается не больше 2 МБ.
"""

import asyncio
import ipaddress
import logging
import re
import socket
from typing import Protocol
from urllib.parse import urljoin, urlsplit

import httpx

logger = logging.getLogger(__name__)

# Страницы, где обычно публикуют реквизиты.
PAGES = ("", "/contacts", "/about", "/requisites", "/rekvizity")
MAX_BYTES = 2 * 1024 * 1024
MAX_REDIRECTS = 3
TIMEOUT_SECONDS = 8.0


class UnsafeUrlError(Exception):
    pass


class WebsiteChecker(Protocol):
    async def mentions(self, url: str, needle: str) -> bool | None:
        """Есть ли ``needle`` на страницах сайта; ``None`` — сайт недоступен."""
        ...


async def ensure_public(url: str) -> None:
    """Разрешает только публичные адреса (без localhost, внутренней сети,
    служебных диапазонов и метаданных облака)."""
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise UnsafeUrlError("unsupported url")
    if parts.port not in (None, 80, 443):
        raise UnsafeUrlError("non-standard port")
    if parts.username or parts.password:
        raise UnsafeUrlError("credentials in url")
    loop = asyncio.get_running_loop()
    try:
        infos = await loop.getaddrinfo(
            parts.hostname, parts.port or 443, type=socket.SOCK_STREAM
        )
    except socket.gaierror as exc:
        raise UnsafeUrlError("unresolvable host") from exc
    for info in infos:
        address = ipaddress.ip_address(info[4][0])
        if not address.is_global:
            raise UnsafeUrlError(f"non-public address {address}")


def contains_number(text: str, number: str) -> bool:
    """Число целиком (не часть другого числа), с пробелами внутри или без."""
    compact = re.sub(r"[\s  ]+", "", text)
    return re.search(rf"(?<!\d){re.escape(number)}(?!\d)", compact) is not None


class HttpWebsiteChecker:
    async def _fetch(self, client: httpx.AsyncClient, url: str) -> str | None:
        for _ in range(MAX_REDIRECTS + 1):
            await ensure_public(url)
            async with client.stream("GET", url) as response:
                if response.is_redirect:
                    location = response.headers.get("location")
                    if not location:
                        return None
                    url = urljoin(url, location)
                    continue
                if response.status_code != 200:
                    return None
                content_type = response.headers.get("content-type", "")
                if "html" not in content_type and "text" not in content_type:
                    return None
                body = b""
                async for chunk in response.aiter_bytes():
                    body += chunk
                    if len(body) > MAX_BYTES:
                        break
                return body[:MAX_BYTES].decode(
                    response.encoding or "utf-8", errors="ignore"
                )
        return None

    async def mentions(self, url: str, needle: str) -> bool | None:
        base = url.rstrip("/")
        reachable = False
        async with httpx.AsyncClient(
            timeout=TIMEOUT_SECONDS,
            follow_redirects=False,
            headers={"User-Agent": "Benefit/1.0 (company verification)"},
        ) as client:
            for path in PAGES:
                try:
                    text = await self._fetch(client, base + path)
                except (httpx.HTTPError, UnsafeUrlError) as exc:
                    logger.info("Website check %s%s failed: %s", base, path, exc)
                    if not path:
                        # Главная недоступна — сайт проверить нельзя.
                        return None
                    continue
                if text is None:
                    continue
                reachable = True
                if contains_number(text, needle):
                    return True
        return False if reachable else None


def get_website_checker() -> WebsiteChecker:
    return HttpWebsiteChecker()
