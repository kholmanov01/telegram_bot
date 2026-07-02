#!/bin/bash
# ============================================================
# Watchdog — ensures the Telegram bot is always running.
# Called by cron every minute. Idempotent: does nothing if the
# bot is already alive; starts it (via start_bot.sh) if not.
# ============================================================
cd /home/z/my-project/task_manager_bot || exit 1

LOGFILE="/home/z/my-project/task_manager_bot/watchdog.log"

# Rotate watchdog log if it gets big.
[ -f "$LOGFILE" ] && [ "$(stat -c%s "$LOGFILE" 2>/dev/null || echo 0)" -gt 1048576 ] && : > "$LOGFILE"

if pgrep -f "python3 -m app.main" > /dev/null 2>&1; then
    # Bot is alive — nothing to do.
    exit 0
fi

echo "$(date '+%Y-%m-%d %H:%M:%S') watchdog: bot down — restarting..." >> "$LOGFILE"
# Start the bot detached; start_bot.sh runs it in the foreground,
# so we wrap it in setsid + nohup to detach from the cron process group.
setsid bash /home/z/my-project/task_manager_bot/start_bot.sh </dev/null >>/home/z/my-project/task_manager_bot/run.log 2>&1 &
echo "$(date '+%Y-%m-%d %H:%M:%S') watchdog: restart triggered" >> "$LOGFILE"
