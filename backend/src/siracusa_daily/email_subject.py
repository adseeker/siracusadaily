from __future__ import annotations

import unicodedata


MIN_SUBJECT_CHARACTERS = 20
MAX_SUBJECT_CHARACTERS = 90
MAX_SUBJECT_BYTES = 180


class EmailSubjectError(ValueError):
    pass


def normalize_email_subject(value: object) -> str:
    """Return a single-line NFC subject or reject unsafe Unicode.

    Subjects are never truncated. Cutting an UTF-8 byte sequence can create the
    malformed value that blocked the Brevo campaigns on 27 August 2026.
    """
    normalized = unicodedata.normalize("NFC", str(value or ""))
    normalized = "".join(" " if character.isspace() else character for character in normalized)
    normalized = " ".join(normalized.split())

    for index, character in enumerate(normalized):
        category = unicodedata.category(character)
        if category.startswith("C"):
            raise EmailSubjectError(
                "carattere Unicode non consentito "
                f"U+{ord(character):04X} ({category}) in posizione {index}"
            )

    try:
        normalized.encode("utf-8", errors="strict")
    except UnicodeEncodeError as exc:
        raise EmailSubjectError("oggetto non codificabile in UTF-8") from exc
    return normalized


def validate_email_subject(
    value: object,
    *,
    minimum_characters: int = MIN_SUBJECT_CHARACTERS,
    maximum_characters: int = MAX_SUBJECT_CHARACTERS,
    maximum_bytes: int = MAX_SUBJECT_BYTES,
) -> str:
    subject = normalize_email_subject(value)
    if not minimum_characters <= len(subject) <= maximum_characters:
        raise EmailSubjectError(
            f"lunghezza oggetto non valida: {len(subject)} caratteri; "
            f"richiesti {minimum_characters}-{maximum_characters}"
        )
    encoded = subject.encode("utf-8", errors="strict")
    if len(encoded) > maximum_bytes:
        raise EmailSubjectError(
            f"oggetto troppo grande in UTF-8: {len(encoded)} byte; massimo {maximum_bytes}"
        )
    return subject
