"""Centralized, Uzbek, HTML message templates for the bot.

Every user-facing string lives here. Functions return HTML strings ready to
be sent with the bot's HTML parse mode. All dynamic content is escaped via
:func:`app.utils.formatting.escape_html` to prevent HTML injection.

Style guide:
- Dark-mode friendly (avoid code blocks / monospaced backgrounds).
- Professional tone, Uzbek language.
- Emojis used sparingly but consistently.
"""

from __future__ import annotations

from typing import Any

from app.utils import dates
from app.utils.formatting import divider, employee_card, escape_html, task_card


# --------------------------------------------------------------------------- #
# Onboarding / auth
# --------------------------------------------------------------------------- #
def welcome_message() -> str:
    """Initial welcome shown to any new chat with the bot."""
    return (
        f"{divider()}\n"
        "👋 <b>Assalomu alaykum!</b>\n"
        "Bu — korxonaviy vazifalarni boshqarish boti.\n"
        "Davom etish uchun registratsiyadan o'ting.\n"
        f"{divider()}"
    )


def ask_employee_code() -> str:
    """Prompt the user for their employee code."""
    return (
        "🔑 Iltimos, xodim kodini kiriting.\n"
        "Misol: <code>EMP001</code>"
    )


def registration_success(full_name: str, code: str) -> str:
    """Successful registration confirmation."""
    return (
        f"{divider()}\n"
        "✅ <b>Registratsiya muvaffaqiyatli yakunlandi!</b>\n"
        f"👤 <b>Ism:</b> {escape_html(full_name)}\n"
        f"📛 <b>Kod:</b> <code>{escape_html(code)}</code>\n"
        f"{divider()}"
    )


def registration_failed(reason: str) -> str:
    """Registration failure message.

    :param reason: Short human-readable reason (already localised).
    """
    return (
        f"❌ <b>Registratsiya amalga oshmadi.</b>\n"
        f"{escape_html(reason)}"
    )


def not_authorized() -> str:
    """Access-denied message for unauthorised users."""
    return (
        f"{divider()}\n"
        "🚫 <b>Ruxsat berilmagan.</b>\n"
        "Sizda ushbu amalni bajarish huquqi yo'q.\n"
        f"{divider()}"
    )


def admin_welcome() -> str:
    """Welcome shown to a super admin after authentication."""
    return (
        f"{divider()}\n"
        "🛡 <b>Administrator paneliga xush kelibsiz!</b>\n"
        "Quyidagi menyudan kerakli amalni tanlang.\n"
        f"{divider()}"
    )


def employee_welcome(full_name: str) -> str:
    """Welcome shown to a registered employee."""
    return (
        f"{divider()}\n"
        f"👋 Xush kelibsiz, <b>{escape_html(full_name)}</b>!\n"
        "Sizga biriktirilgan vazifalarni quyidagi menyudan ko'rishingiz mumkin.\n"
        f"{divider()}"
    )


# --------------------------------------------------------------------------- #
# Task creation flow
# --------------------------------------------------------------------------- #
def ask_task_title() -> str:
    """Prompt for a new task title."""
    return "✏️ Vazifa sarlavhasini kiriting:"


def ask_task_description() -> str:
    """Prompt for a new task description."""
    return "📝 Vazifaning ta'rifini kiriting (yoki o'tkazib yuborish uchun «—»):"


def ask_task_employee() -> str:
    """Prompt to choose the employee to assign the task to."""
    return "👤 Vazifa biriktiriladigan xodimni tanlang:"


def ask_task_priority() -> str:
    """Prompt to choose the task priority."""
    return "⚡️ Vazifa ustuvorligini tanlang:"


def ask_task_date() -> str:
    """Prompt for the deadline date (calendar picker is shown inline)."""
    return (
        "📅 <b>Muddat sanasini tanlang.</b>\n"
        "👇 Kalendar dan bir sanani bosing.\n"
        "‹ › tugmalari bilan oyni almashtiring.\n\n"
        "<i>(Yoki matn kiriting: <code>DD.MM.YYYY</code>)</i>"
    )


def ask_task_time() -> str:
    """Prompt for the deadline time (time picker is shown inline)."""
    return (
        "🕐 <b>Muddat vaqtini tanlang.</b>\n"
        "👇 Avval soatni, so'ng daqiqani bosing.\n\n"
        "<i>(Yoki matn kiriting: <code>HH:MM</code>)</i>"
    )


def ask_task_timezone() -> str:
    """Prompt for the timezone in which the deadline was entered."""
    return (
        "🌍 Vaqt zonasi tanlang (yoki o'zingiznikini kiriting, masalan "
        "<code>Asia/Tashkent</code>):"
    )


def task_confirm_card(
    task: Any,
    employee: Any | None = None,
    attachment_count: int = 0,
) -> str:
    """Render the confirmation card for a task being created.

    Args:
        task: Task-like object.
        employee: Optional employee object.
        attachment_count: Number of attachments queued for this task. When
            greater than zero an ``📎 Biriktirilgan fayl: N ta`` line is
            appended to the card.
    """
    card = task_card(
        task,
        employee=employee,
        with_remaining=True,
        header="🔍 <b>Vazifa tasdiqi</b>",
    )
    if attachment_count > 0:
        card += f"\n📎 <b>Biriktirilgan fayl:</b> {int(attachment_count)} ta"
    return card


def task_created_success(task_title: str, employee_name: str) -> str:
    """Success message shown to the admin after a task is created."""
    return (
        f"{divider()}\n"
        "✅ <b>Vazifa muvaffaqiyatli yaratildi!</b>\n"
        f"📌 <b>Sarlavha:</b> {escape_html(task_title)}\n"
        f"👤 <b>Xodim:</b> {escape_html(employee_name)}\n"
        f"{divider()}"
    )


# --------------------------------------------------------------------------- #
# Notifications (received by employees / admins)
# --------------------------------------------------------------------------- #
def new_task_notification(task: Any, attachment_count: int = 0) -> str:
    """Card the employee receives when a new task is assigned to them.

    Args:
        task: Task-like object.
        attachment_count: Number of attachments linked to the task. When
            greater than zero an ``📎 Biriktirilgan fayl: N ta`` line is
            appended to the card.
    """
    card = task_card(
        task,
        with_remaining=True,
        header="📌 <b>Yangi vazifa</b>",
    )
    if attachment_count > 0:
        card += f"\n📎 <b>Biriktirilgan fayl:</b> {int(attachment_count)} ta"
    return card


def reminder_notification(task: Any, offset_minutes: int) -> str:
    """Reminder card sent shortly before the deadline.

    :param task: Task object.
    :param offset_minutes: How many minutes until the deadline (used in the
        intro line).
    """
    if offset_minutes >= 60:
        hours = offset_minutes / 60
        if hours.is_integer():
            remaining_phrase = f"{int(hours)} soat"
        else:
            remaining_phrase = f"{hours:.1f} soat"
    else:
        remaining_phrase = f"{offset_minutes} daqiqa"
    header = f"⏰ <b>Eslatma: vazifaga {remaining_phrase} qoldi</b>"
    return task_card(task, with_remaining=True, header=header)


def deadline_passed_employee(task: Any) -> str:
    """Message an employee receives when their task's deadline passes."""
    return (
        task_card(task, with_remaining=True, header="❌ <b>Muddat o'tdi</b>")
        + "\n\n❌ <b>Vazifani o'z vaqtida bajarmadingiz.</b>\n"
        "Iltimos, tezroq holatni bartaraf eting va administrator bilan bog'laning."
    )


def deadline_passed_admin(employee_name: str, task_title: str) -> str:
    """Message an admin receives when a task expires."""
    return (
        f"{divider()}\n"
        "❌ <b>Vazifa muddati o'tdi</b>\n"
        f"📌 <b>Vazifa:</b> {escape_html(task_title)}\n"
        f"👤 <b>Xodim:</b> {escape_html(employee_name)}\n"
        f"{divider()}"
    )


def task_completed_admin(employee_name: str, task_title: str, completed_at: str) -> str:
    """Message an admin receives when an employee completes a task."""
    return (
        f"{divider()}\n"
        "✅ <b>Vazifa bajarildi</b>\n"
        f"📌 <b>Vazifa:</b> {escape_html(task_title)}\n"
        f"👤 <b>Xodim:</b> {escape_html(employee_name)}\n"
        f"🕒 <b>Bajarilgan vaqt:</b> {escape_html(completed_at)}\n"
        f"{divider()}"
    )


def task_completed_employee() -> str:
    """Confirmation shown to the employee after they mark a task complete."""
    return "✅ <b>Vazifa bajarilgan deb belgilandi.</b>\nRahmat!"


def task_archived() -> str:
    """Confirmation shown when a task is archived."""
    return "🗄 <b>Vazifa arxivlandi.</b>"


def task_restored() -> str:
    """Confirmation shown when a task is restored from the archive."""
    return "♻️ <b>Vazifa arxivdan qaytarildi.</b>"


# --------------------------------------------------------------------------- #
# Empty states & errors
# --------------------------------------------------------------------------- #
def no_tasks() -> str:
    """Shown when a list of tasks is empty."""
    return (
        f"{divider()}\n"
        "📭 <b>Vazifalar topilmadi.</b>\n"
        "Hozircha ko'rsatish uchun vazifalar yo'q.\n"
        f"{divider()}"
    )


def error_message() -> str:
    """Generic error message."""
    return "⚠️ <b>Xatolik yuz berdi. Qayta urinib ko'ring.</b>"


def cancelled() -> str:
    """Shown when an operation is cancelled."""
    return "🚫 <b>Amal bekor qilindi.</b>"


def settings_menu() -> str:
    """Settings menu header."""
    return (
        f"{divider()}\n"
        "⚙️ <b>Sozlamalar</b>\n"
        "O'zgartirmoqchi bo'lgan parameterni tanlang.\n"
        f"{divider()}"
    )


def profile_card(user: Any, employee: Any | None = None) -> str:
    """Render the current user's profile card.

    :param user: User-like object (uses telegram_id, username, role, etc.).
    :param employee: Optional linked employee object.
    """
    from app.models.enums import UserRole

    role = getattr(user, "role", None)
    if role == UserRole.SUPER_ADMIN or str(role).lower() == "super_admin":
        role_label = "Administrator"
    else:
        role_label = "Xodim"

    lines: list[str] = [
        divider(),
        "👤 <b>Profil</b>",
        f"<b>Rol:</b> {role_label}",
    ]
    username = getattr(user, "username", None)
    if username:
        lines.append(f"<b>Username:</b> @{escape_html(username)}")
    first_name = getattr(user, "first_name", None)
    last_name = getattr(user, "last_name", None)
    full = " ".join(p for p in [first_name, last_name] if p)
    if full:
        lines.append(f"<b>Ism:</b> {escape_html(full)}")
    telegram_id = getattr(user, "telegram_id", None)
    if telegram_id is not None:
        lines.append(f"<b>Telegram ID:</b> <code>{escape_html(str(telegram_id))}</code>")

    reg_date = getattr(user, "registration_date", None)
    if reg_date is not None:
        lines.append(f"<b>Registratsiya:</b> {dates.format_datetime(reg_date)}")

    if employee is not None:
        lines.append("")
        lines.append(employee_card(employee))
    lines.append(divider())
    return "\n".join(lines)


def invalid_input(field: str) -> str:
    """Generic invalid-input message for a given field name.

    :param field: Human-readable field label (already localised).
    """
    return f"⚠️ <b>{escape_html(field)} noto'g'ri kiritildi.</b>\nIltimos, qaytadan urinib ko'ring."
