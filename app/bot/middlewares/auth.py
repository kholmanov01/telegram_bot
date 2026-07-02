"""Authentication middleware.

For each update carrying a Telegram user the middleware:

1. Looks up the :class:`User` by ``telegram_id`` (via :class:`UserRepository`
   when available, else via a direct query).
2. Sets ``data["user"]`` (the :class:`User` or ``None``), ``data["user_role"]``
   (the resolved :class:`UserRole` or ``None``) and ``data["is_registered"]``.
3. Allows unregistered users to invoke only ``/start`` — for everything else
   the handler chain is short-circuited and a polite prompt is sent.

The middleware is wrapped in a defensive ``try/except`` so a transient DB
failure never crashes an update; in that case the user is treated as
anonymous and only ``/start`` is permitted.

It depends on the :class:`DatabaseMiddleware` having run first and injected
``data["session"]``.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject, User as TgUser
from loguru import logger
from sqlalchemy import select

from app.models.enums import UserRole
from app.models.user import User

__all__ = ["AuthMiddleware"]


class AuthMiddleware(BaseMiddleware):
    """Resolve the acting user and gate access for unregistered users."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user: TgUser | None = data.get("event_from_user") or getattr(
            event, "from_user", None
        )

        # No Telegram user on this update (channel posts, etc.) — pass through.
        if tg_user is None:
            data.setdefault("user", None)
            data.setdefault("user_role", None)
            data.setdefault("is_registered", False)
            return await handler(event, data)

        user: User | None = None
        is_registered: bool = False

        try:
            user = await self._resolve_user(tg_user.id, data)
        except Exception as exc:  # pragma: no cover — defensive
            logger.warning(
                "AuthMiddleware: failed to resolve user tg_id={} — {!r}",
                tg_user.id,
                exc,
            )

        # Super-admins in the env allow-list are always considered registered.
        if user is None and self._is_env_super_admin(tg_user.id):
            is_registered = True
            data["user_role"] = UserRole.SUPER_ADMIN
        elif user is not None:
            is_registered = bool(user.is_registered)

        data["user"] = user
        data.setdefault("user_role", user.role if user is not None else None)
        data["is_registered"] = is_registered

        # Gate unregistered users to /start only — UNLESS they are in an FSM
        # state (e.g. the registration flow's ``waiting_employee_code`` state,
        # where they need to type their employee code as plain text).
        if not is_registered:
            in_fsm_state = await self._is_in_fsm_state(data)
            if not in_fsm_state and self._is_blocked_message(event):
                await self._prompt_register(event)
                return None

        return await handler(event, data)

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _is_env_super_admin(telegram_id: int) -> bool:
        """Return True if ``telegram_id`` is in ``settings.super_admin_id_list``."""
        from app.config.settings import settings

        return telegram_id in settings.super_admin_id_list

    @staticmethod
    async def _resolve_user(telegram_id: int, data: dict[str, Any]) -> User | None:
        """Look up the user by telegram id, preferring the repository."""
        session = data.get("session")
        if session is None:
            # No session available — we cannot query the DB. Bail out.
            return None

        # Try the UserRepository first (it WILL exist per the worklog).
        try:
            from app.repositories import UserRepository  # type: ignore
        except Exception:  # pragma: no cover — defensive
            UserRepository = None  # type: ignore[assignment]

        if UserRepository is not None:
            try:
                repo = UserRepository(session)  # type: ignore[call-arg]
                return await repo.get_by_telegram_id(telegram_id)  # type: ignore[attr-defined]
            except Exception as exc:  # pragma: no cover — defensive
                logger.debug(
                    "AuthMiddleware: UserRepository lookup failed, "
                    "falling back to direct query — {!r}",
                    exc,
                )

        # Direct fallback query.
        stmt = select(User).where(User.telegram_id == telegram_id)
        result = await session.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def _is_in_fsm_state(data: dict[str, Any]) -> bool:
        """Return True when the user is currently in any FSM state.

        This lets the registration flow's ``waiting_employee_code`` state
        receive plain-text messages (the employee code) without being
        blocked by the unregistered-user gate.
        """
        state = data.get("state")
        if state is None:
            return False
        try:
            current = await state.get_state()
            return current is not None
        except Exception:  # pragma: no cover — defensive
            return False

    @staticmethod
    def _is_blocked_message(event: TelegramObject) -> bool:
        """Return True when an unregistered user's message should be blocked.

        Blocks commands other than ``/start`` / ``/help`` AND plain-text
        messages. Callback queries are never blocked here (they are gated
        by role filters on the handlers themselves).
        """
        if not isinstance(event, Message):
            return False
        text = (event.text or "").strip()
        if not text:
            return False
        if text.startswith("/"):
            # Allow /start, /help (case-insensitive, with optional @bot suffix).
            cmd = text.split()[0].lower().split("@", 1)[0]
            return cmd not in {"/start", "/help"}
        # Plain text from an unregistered user — block (they should /start first).
        return True

    @staticmethod
    async def _prompt_register(event: TelegramObject) -> None:
        """Send a friendly prompt asking the user to register via ``/start``."""
        if not isinstance(event, Message):
            return
        try:
            await event.answer(
                "👋 Salom!\n"
                "Iltimos, ro'yxatdan o'tish uchun /start buyrug'ini yuboring."
            )
        except Exception:  # pragma: no cover — defensive
            logger.debug("AuthMiddleware: failed to send register prompt")
