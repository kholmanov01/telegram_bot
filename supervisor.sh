#!/bin/bash
# ============================================================
# Supervisor — lightweight background loop that keeps the bot
# alive. Checks every 30 seconds; restarts via start_bot.sh if
# the bot process is gone.
#
# Launch once with:  setsid bash supervisor.sh </dev/null >>supervisor.log 2>&1 &
# ============================================================
cd /home/z/my-project/task_manager_bot || exit 1

SLOG="/home/z/my-project/task_manager_bot/supervisor.log"

echo "$(date '+%Y-%m-%d %H:%M:%S') supervisor: started (pid $$)" >> "$SLOG"

while true; do
    if ! pgrep -f "python3 -m app.main" > /dev/null 2>&1; then
        echo "$(date '+%Y-%m-%d %H:%M:%S') supervisor: bot down — calling start_bot.sh" >> "$SLOG"
        # start_bot.sh handles: deps, .env, DB, migration, and execs the bot.
        setsid bash /home/z/my-project/task_manager_bot/start_bot.sh </dev/null >>/home/z/my-project/task_manager_bot/run.log 2>&1 &
        # Give it time to boot before checking again.
        sleep 15
    fi
    sleep 30
done
