"""Telegram message helpers — extracting file metadata.

Pure-logic utilities that inspect an :class:`aiogram.types.Message` and pull
out a normalized dict of file metadata. These helpers have NO side effects and
do not touch the database; they live in ``app.utils`` so both handlers and
services can reuse them without import cycles.
"""

from __future__ import annotations

from typing import Any

from aiogram.types import Message

__all__ = ["extract_file_info"]


def extract_file_info(message: Message) -> dict[str, Any] | None:
    """Extract file metadata from a Telegram message.

    Inspects ``message.photo`` / ``message.document`` / ``message.video`` /
    ``message.audio`` / ``message.voice`` / ``message.animation`` in turn
    and returns the first match.

    For photos, the largest size is taken (``message.photo[-1]`` since
    Telegram sorts photo sizes ascending).

    Args:
        message: An :class:`aiogram.types.Message` carrying a media payload.

    Returns:
        A dict with the following keys, or ``None`` if no recognizable
        file is present::

            {
                "file_id":         str,        # Telegram file_id (bot-specific)
                "file_unique_id":  str,        # Telegram file_unique_id (global)
                "file_type":       str,        # photo|document|video|audio|voice|animation
                "file_name":       str | None, # original filename (when available)
                "file_size":       int | None, # size in bytes (when available)
                "mime_type":       str | None, # MIME type (when available)
                "caption":         str | None, # message caption (when present)
            }
    """
    caption = getattr(message, "caption", None)
    file_id: str | None = None
    file_unique_id: str | None = None
    file_type: str | None = None
    file_name: str | None = None
    file_size: int | None = None
    mime_type: str | None = None

    # Photos come as a list sorted from smallest to largest.
    if message.photo:
        largest = message.photo[-1]
        file_id = largest.file_id
        file_unique_id = largest.file_unique_id
        file_type = "photo"
        file_size = largest.file_size
    elif message.document is not None:
        doc = message.document
        file_id = doc.file_id
        file_unique_id = doc.file_unique_id
        file_type = "document"
        file_name = doc.file_name
        file_size = doc.file_size
        mime_type = doc.mime_type
    elif message.video is not None:
        vid = message.video
        file_id = vid.file_id
        file_unique_id = vid.file_unique_id
        file_type = "video"
        file_name = vid.file_name
        file_size = vid.file_size
        mime_type = vid.mime_type
    elif message.audio is not None:
        aud = message.audio
        file_id = aud.file_id
        file_unique_id = aud.file_unique_id
        file_type = "audio"
        file_name = aud.file_name
        file_size = aud.file_size
        mime_type = aud.mime_type
    elif message.voice is not None:
        vc = message.voice
        file_id = vc.file_id
        file_unique_id = vc.file_unique_id
        file_type = "voice"
        file_size = vc.file_size
        mime_type = vc.mime_type
    elif message.animation is not None:
        ani = message.animation
        file_id = ani.file_id
        file_unique_id = ani.file_unique_id
        file_type = "animation"
        file_name = ani.file_name
        file_size = ani.file_size
        mime_type = ani.mime_type

    if file_id is None or file_unique_id is None or file_type is None:
        return None

    return {
        "file_id": file_id,
        "file_unique_id": file_unique_id,
        "file_type": file_type,
        "file_name": file_name,
        "file_size": file_size,
        "mime_type": mime_type,
        "caption": caption,
    }
