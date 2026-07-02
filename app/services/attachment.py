"""Attachment service — files / photos linked to a task.

Provides:

- :meth:`add_attachment`               — persist a Telegram file reference.
- :meth:`get_task_attachments`         — list attachments for a task.
- :meth:`get_attachment_count`         — count attachments for a task.
- :meth:`send_attachments_to_user`     — re-send every attachment to a Telegram
  user via the appropriate ``bot.send_*`` call (photo / document / video /
  audio / voice / animation).

Each public method opens its own session via :func:`get_session` by default so
callers do not need to manage transactions. Use :meth:`with_session` to bind
the service to an outer session (e.g. when called from another service that
already holds a session).
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from aiogram.exceptions import TelegramAPIError
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.instance import bot
from app.database.session import get_session
from app.models.attachment import Attachment
from app.repositories.attachment import AttachmentRepository


class AttachmentService:
    """Persist and dispatch :class:`Attachment` records."""

    def __init__(self) -> None:
        """Create a standalone service that opens its own sessions."""
        self._session: AsyncSession | None = None

    # ------------------------------------------------------------------ #
    # Construction helpers
    # ------------------------------------------------------------------ #
    @classmethod
    def with_session(cls, session: AsyncSession) -> "AttachmentService":
        """Return an instance bound to ``session`` for in-transaction use."""
        instance = cls()
        instance._session = session
        return instance

    @asynccontextmanager
    async def _session_scope(self) -> AsyncIterator[AsyncSession]:
        """Yield a usable session (injected or freshly opened)."""
        if self._session is not None:
            yield self._session
        else:
            async with get_session() as session:
                yield session

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #
    async def add_attachment(
        self,
        task_id: int,
        file_id: str,
        file_unique_id: str,
        file_type: str,
        file_name: str | None = None,
        file_size: int | None = None,
        caption: str | None = None,
        mime_type: str | None = None,
        uploaded_by: int | None = None,
    ) -> Attachment:
        """Persist a new :class:`Attachment` row.

        Args:
            task_id: Primary key of the task the file is attached to.
            file_id: Telegram ``file_id`` (bot-specific but stable).
            file_unique_id: Telegram ``file_unique_id`` (globally stable).
            file_type: One of ``photo``, ``document``, ``video``,
                ``audio``, ``voice``, ``animation``.
            file_name: Original file name (documents / videos).
            file_size: File size in bytes (when known).
            caption: Optional caption accompanying the file.
            mime_type: Optional MIME type (e.g. ``image/jpeg``).
            uploaded_by: Optional user id of the uploader.

        Returns:
            The newly created :class:`Attachment` instance.
        """
        async with self._session_scope() as session:
            repo = AttachmentRepository(session)
            attachment = await repo.create(
                {
                    "task_id": task_id,
                    "file_id": file_id,
                    "file_unique_id": file_unique_id,
                    "file_type": file_type,
                    "file_name": file_name,
                    "file_size": file_size,
                    "caption": caption,
                    "mime_type": mime_type,
                    "uploaded_by": uploaded_by,
                }
            )
            logger.info(
                "Attached {} (file_id={!r}, task={})",
                file_type,
                file_id[:32],
                task_id,
            )
            return attachment

    async def get_task_attachments(self, task_id: int) -> list[Attachment]:
        """Return all attachments for the given task ordered by id ascending."""
        async with self._session_scope() as session:
            repo = AttachmentRepository(session)
            return await repo.get_for_task(task_id)

    async def get_attachment_count(self, task_id: int) -> int:
        """Return the number of attachments linked to the task."""
        async with self._session_scope() as session:
            repo = AttachmentRepository(session)
            return await repo.count_for_task(task_id)

    # ------------------------------------------------------------------ #
    # Dispatch
    # ------------------------------------------------------------------ #
    async def send_attachments_to_user(
        self, task_id: int, telegram_id: int
    ) -> int:
        """Send every attachment of a task to the given Telegram user.

        Dispatches to the appropriate ``bot.send_*`` call based on
        ``file_type``. Each send is wrapped in a defensive ``try/except``;
        failures are logged and skipped so a single bad file does not abort
        the whole batch.

        Args:
            task_id: Primary key of the task whose attachments to send.
            telegram_id: Recipient Telegram id.

        Returns:
            The number of attachments successfully sent.
        """
        try:
            attachments = await self.get_task_attachments(task_id)
        except Exception as exc:  # noqa: BLE001 — defensive
            logger.error(
                "Failed to load attachments for task {}: {}",
                task_id,
                exc,
            )
            return 0

        if not attachments:
            return 0

        caption_base = f"📎 Vazifa #{task_id} fayli"
        sent_count = 0

        for attachment in attachments:
            try:
                await self._dispatch_one(
                    attachment, telegram_id, caption_base
                )
                sent_count += 1
            except TelegramAPIError as exc:
                logger.warning(
                    "Telegram API error sending attachment {} to {}: {}",
                    attachment.id,
                    telegram_id,
                    exc,
                )
            except Exception as exc:  # noqa: BLE001 — defensive
                logger.error(
                    "Unexpected error sending attachment {} to {}: {}",
                    attachment.id,
                    telegram_id,
                    exc,
                )

        logger.info(
            "Sent {}/{} attachments of task {} to {}",
            sent_count,
            len(attachments),
            task_id,
            telegram_id,
        )
        return sent_count

    async def _dispatch_one(
        self,
        attachment: Attachment,
        telegram_id: int,
        caption_base: str,
    ) -> None:
        """Send a single attachment via the appropriate bot method.

        Args:
            attachment: The :class:`Attachment` to send.
            telegram_id: Recipient Telegram id.
            caption_base: Base caption prepended to the user's own caption.

        Raises:
            Whatever the underlying ``bot.send_*`` call raises (caught by
            the caller).
        """
        caption = caption_base
        if attachment.caption:
            caption = f"{caption_base}\n{attachment.caption}"

        file_type = (attachment.file_type or "").lower()
        file_id = attachment.file_id
        kwargs: dict[str, Any] = {"caption": caption}

        if file_type == "photo":
            await bot.send_photo(chat_id=telegram_id, photo=file_id, **kwargs)
        elif file_type == "document":
            await bot.send_document(
                chat_id=telegram_id, document=file_id, **kwargs
            )
        elif file_type == "video":
            await bot.send_video(chat_id=telegram_id, video=file_id, **kwargs)
        elif file_type == "audio":
            await bot.send_audio(chat_id=telegram_id, audio=file_id, **kwargs)
        elif file_type == "voice":
            await bot.send_voice(chat_id=telegram_id, voice=file_id, **kwargs)
        elif file_type == "animation":
            await bot.send_animation(
                chat_id=telegram_id, animation=file_id, **kwargs
            )
        else:
            # Unknown type — fall back to document (Telegram tolerates a
            # file_id from any media type for send_document in most cases).
            logger.warning(
                "Unknown attachment file_type={!r} (id={}); sending as document",
                file_type,
                attachment.id,
            )
            await bot.send_document(
                chat_id=telegram_id, document=file_id, **kwargs
            )
