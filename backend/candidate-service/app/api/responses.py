"""Общие HTTP-ответы."""

from urllib.parse import quote

from fastapi import Response


def pdf_response(pdf: bytes, last_name: str | None) -> Response:
    filename = f"resume-{last_name or 'candidate'}.pdf"
    return Response(
        pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": "attachment; filename=resume.pdf; "
            f"filename*=UTF-8''{quote(filename)}"
        },
    )
