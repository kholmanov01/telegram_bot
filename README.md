# Enterprise Telegram Task Management Bot

A production-ready, enterprise-grade Telegram bot for managing employee tasks,
deadlines, reminders, and analytics. Built with **Clean Architecture**, the
**Repository Pattern**, a **Service Layer**, and **Dependency Injection** —
fully async, horizontally scalable, and containerised.

> Roles: **Super Admin** · **Employee**

---

## ✨ Features

| Area | Capabilities |
|------|--------------|
| **Employee lifecycle** | Admin creates employees → unique `EMP###` code generated → employee self-registers via `/start` → Telegram ID, username, first name & registration date saved. Duplicate registration prevented. |
| **Task management** | 8-step creation wizard (title → description → employee → priority → deadline date/time/timezone → confirm). Beautiful task cards. Archive / restore. Search & filters. |
| **Automated expiry** | A scheduler checks every minute; pending tasks past their deadline are auto-expired and both employee & admin are notified. |
| **Smart reminders** | Automatic reminders at **24h, 12h, 6h, 1h, 30m, 10m** before the deadline (idempotent). |
| **Statistics** | Per-employee & overall stats, success %, average completion time, daily / weekly / monthly reports. |
| **Exports** | Excel & PDF export of tasks and statistics. |
| **Audit trail** | Every state-changing action is logged (login, task create/edit/complete/expire, notifications, settings). |
| **Security** | `.env`-based secrets, role filters, throttling/duplicate-click prevention, SQL-injection-safe (parameterised queries via SQLAlchemy), race-condition-safe transactions. |
| **Resilience** | Centralised error handling, structured logging to separate `info.log` / `warning.log` / `error.log`, fail-open throttling. |

---

## 🧱 Tech Stack

- **Python 3.12** · **Aiogram 3.x**
- **PostgreSQL** · **SQLAlchemy 2.0 (async)** · **Alembic**
- **Redis** (FSM storage + throttling)
- **APScheduler** (expiry & reminders)
- **Pydantic Settings** · **Loguru**
- **Docker / Docker Compose**
- **openpyxl / reportlab** (Excel/PDF export)

---

## 📁 Project Structure

```
task_manager_bot/
├── app/
│   ├── bot/
│   │   ├── handlers/
│   │   │   ├── admin/        # admin menu, task wizard, employees, tasks, stats, settings
│   │   │   ├── employee/     # my tasks, completed, today, notifications, profile
│   │   │   └── common/       # /start, registration, /help, /cancel, error handler
│   │   ├── keyboards/        # reply menus + inline builders + callback factories
│   │   ├── filters/          # SuperAdminFilter, RoleFilter
│   │   ├── middlewares/      # database, auth, throttling, logging
│   │   ├── states/           # FSM state groups
│   │   └── instance.py       # Bot + Dispatcher singletons
│   ├── services/             # business logic (auth, employee, task, statistics, ...)
│   ├── repositories/         # data-access layer (one repo per aggregate)
│   ├── database/             # engine, session, base, Alembic migrations
│   ├── models/               # ORM models + enums
│   ├── scheduler/            # APScheduler jobs (expiry, reminders, daily report)
│   ├── notifications/        # centralised message templates (Uzbek, HTML)
│   ├── config/               # Pydantic settings + Loguru logging
│   ├── utils/                # dates, formatting, security, export helpers
│   └── main.py               # entry point
├── logs/                     # rotating log files
├── tests/                    # pytest test suite
├── alembic.ini
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
└── README.md
```

---

## 🚀 Quick Start

### 1. Configure environment
```bash
cp .env.example .env
# edit .env — set BOT_TOKEN and SUPER_ADMIN_IDS (your Telegram user ID)
```
> To find your Telegram user ID, message `@userinfobot` or run `/id` in the bot
> after a first launch (the bot replies with your ID).

### 2. Run with Docker (recommended)
```bash
docker compose up --build -d
docker compose logs -f bot
```
PostgreSQL + Redis start first (health-checked), then the bot. Alembic migrations
should be applied once:

```bash
docker compose exec bot alembic upgrade head
```

### 3. Run locally (without Docker)
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# ensure PostgreSQL & Redis are running and DATABASE_URL/REDIS_URL point to them
alembic upgrade head
python -m app.main
```

---

## 🧭 Usage

### Super Admin menu (reply keyboard)
```
➕ New Task   👥 Employees
📋 All Tasks  📈 Statistics
⚙ Settings
```

### Employee menu (reply keyboard)
```
📌 My Tasks       ✅ Completed Tasks
📅 Today          🔔 Notifications
⚙ Profile
```

### Registration flow
1. Admin opens **👥 Employees → ➕ Yangi xodim**, enters the employee's name.
   The bot generates a code like `EMP001`.
2. The admin shares this code with the employee.
3. The employee opens the bot, sends `/start`, enters `EMP001` → registered.
   Telegram ID, username, first name & registration date are stored.

### Task lifecycle
- **Created** → employee receives a task card with ✅ Completed / 📝 View Details buttons.
- **Completed** → DB updated with completion time; admin notified.
- **Expired** → scheduler auto-marks; employee & admin notified.
- **Archived / Restored** by admin anytime.

---

## ⏰ Automated Jobs

| Job | Schedule | Description |
|-----|----------|-------------|
| `check_expired_tasks` | every minute | Expire pending tasks past deadline, notify employee + admin. |
| `send_task_reminders` | every minute | Send 24h/12h/6h/1h/30m/10m reminders (idempotent). |
| `daily_summary_report` | 18:05 daily | Send a daily statistics summary to all super admins. |

---

## 🗄️ Database Schema

7 tables: `users`, `employees`, `tasks`, `notifications`, `task_logs`,
`audit_logs`, `settings`. Schema is managed by Alembic; the initial migration
creates all tables, indexes and foreign keys.

### Run / create migrations
```bash
alembic upgrade head                              # apply
alembic revision --autogenerate -m "description"  # create new
alembic downgrade -1                              # roll back one
```

---

## 🔒 Security

- No secrets in code — everything via `.env`.
- Role-based access via `SuperAdminFilter` / `RoleFilter` on routers.
- Duplicate-click prevention via Redis-backed throttling middleware.
- Parameterised queries (SQLAlchemy) — SQL-injection safe.
- Transactional writes (`get_session` commits/rolls back atomically).
- HTML-escaping of all user-provided text in messages.

---

## 📝 Logging

Loguru writes to three rotating files under `logs/`:
- `info.log` (≥ INFO, 20 MB rotation, 30-day retention)
- `warning.log` (≥ WARNING, 10 MB, 60-day)
- `error.log` (≥ ERROR, 10 MB, 90-day)

A colourised console sink is also enabled. Standard-library logging is
intercepted and routed through Loguru.

---

## 🧪 Testing

```bash
pytest -v
```
Tests cover repositories, services and keyboard/callback contracts using
mocked sessions (no real DB required).

---

## 🛠️ Development Notes

- **Clean Architecture**: handlers → services → repositories → models.
  Dependencies point inward; services never import handlers.
- **DI**: repositories are constructed inside service methods on a shared
  session; services expose `with_session(session)` for in-transaction use.
- **Async everywhere**: `async`/`await` end-to-end; APScheduler uses
  `AsyncIOScheduler` on the same loop as aiogram.
- **i18n-ready**: all user-facing text lives in `app/notifications/templates.py`
  (Uzbek by default; `DEFAULT_LANGUAGE` setting reserved for future languages).

---

## 📦 Production Checklist

- [ ] Replace the test `BOT_TOKEN` with a real one.
- [ ] Set strong `POSTGRES_PASSWORD` & `REDIS_PASSWORD`.
- [ ] Set `SUPER_ADMIN_IDS` to real admin Telegram IDs.
- [ ] Run `alembic upgrade head` after every code deploy.
- [ ] Mount persistent volumes for `logs/` and Postgres/Redis data.
- [ ] Configure a reverse proxy / watchdog to restart the container on failure.

---

## 📄 License

Proprietary — internal enterprise use.
