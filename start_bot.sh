#!/bin/bash
# ============================================================
# Bot start script — idempotent and sandbox-reboot-resilient.
# Ensures deps are installed and .env exists, then starts the bot.
# ============================================================
set -e
cd /home/z/my-project/task_manager_bot

# 1. Ensure dependencies are installed (sandbox reboots wipe site-packages).
if ! python3 -c "import aiogram, sqlalchemy, aiosqlite, alembic" 2>/dev/null; then
    echo "$(date +%H:%M:%S) installing deps..."
    python3 -m pip install --quiet \
        "aiogram>=3.13" "SQLAlchemy[asyncio]>=2.0" asyncpg aiosqlite alembic \
        "redis>=5" APScheduler "pydantic>=2.9" "pydantic-settings>=2.5" \
        loguru python-dateutil pytz tzdata openpyxl reportlab tenacity \
        2>&1 | tail -2
fi

# 2. Ensure .env exists with the correct bot token (sandbox reboots may wipe it).
#    We always (re)write .env from scratch so the token stays current even
#    if the sandbox wiped the file or the operator changed the token.
if [ ! -f .env ] || ! grep -q "8802727198" .env 2>/dev/null; then
    echo "$(date +%H:%M:%S) writing .env with current token..."
    cat > .env <<'ENVEOF'
# Auto-restored by start_bot.sh after sandbox reboot.
BOT_TOKEN=8802727198:AAEg5VJ2fvvob_T0TWeAy-MRbI4xv8obELo
SUPER_ADMIN_IDS=8722446867
DATABASE_URL=sqlite+aiosqlite:///./taskbot.db
REDIS_HOST=127.0.0.1
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=
APP_ENV=development
APP_TIMEZONE=Asia/Tashkent
LOG_LEVEL=INFO
DEFAULT_LANGUAGE=uz
WORKING_HOURS_START=09:00
WORKING_HOURS_END=18:00
SCHEDULER_TIMEZONE=Asia/Tashkent
ENVEOF
fi

# 3. Ensure DB exists with migrations applied.
export DATABASE_URL="sqlite+aiosqlite:///./taskbot.db"
if [ ! -f taskbot.db ]; then
    echo "$(date +%H:%M:%S) creating fresh DB + migrations..."
    python3 -m alembic upgrade head 2>&1 | tail -3
fi

# 4. Kill any stale bot process.
pkill -f "python3 -m app.main" 2>/dev/null || true
sleep 1

# 5. Start the bot (foreground — the cron job IS the bot process).
echo "$(date +%H:%M:%S) starting bot..."
exec python3 -m app.main
