"""Bot package — Bot instance, Dispatcher and Redis-backed storage."""

from app.bot.instance import bot, dp

__all__ = ["bot", "dp"]
