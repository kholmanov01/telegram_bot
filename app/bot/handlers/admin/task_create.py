"""Task-creation FSM wizard (8 steps + confirm, with optional attachment).

Flow::

    title → description → attachment_choice → (attachment)? → employee →
    priority → date → time → timezone → confirm

The ``employee`` and ``priority`` steps are driven by ``CallbackQuery``
(inline-button picks); the rest are typed messages. The wizard stores the
collected fields in the FSM context and, at the ``timezone`` step, builds
the tz-aware UTC deadline via :func:`build_deadline`.

Between ``description`` and ``employee`` an optional ``attachment_choice``
step asks the admin whether to attach a file/photo; if they accept, the
wizard pauses in ``waiting_attachment`` for a single media message. The
extracted file metadata is stored under the ``attachment`` key in FSM data
and persisted via :class:`AttachmentService` once the task has been created.
"""

from __future__ import annotations

from datetime import date, datetime, time
from types import SimpleNamespace

import pytz
from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from loguru import logger

from app.bot.keyboards.admin import (
    admin_menu,
    cancel_keyboard,
    confirm_inline,
    employee_select_inline,
    priority_inline,
)
from app.bot.keyboards.calendar import (
    CalendarCallback,
    TimePickerCallback,
    calendar_keyboard,
    hour_keyboard,
    minute_keyboard,
    shift_month,
)
from app.bot.keyboards.callbacks import (
    ConfirmCallback,
    EmployeeCallback,
    MenuCallback,
    PriorityCallback,
)
from app.bot.states.task import TaskCreationStates
from app.config.settings import settings
from app.models.enums import TaskPriority, TaskStatus
from app.models.user import User
from app.notifications.templates import (
    ask_task_date,
    ask_task_description,
    ask_task_employee,
    ask_task_priority,
    ask_task_time,
    ask_task_timezone,
    ask_task_title,
    cancelled,
    error_message,
    invalid_input,
    no_tasks,
    task_confirm_card,
    task_created_success,
)
from app.services.attachment import AttachmentService
from app.services.employee import EmployeeService
from app.services.task import TaskService
from app.utils.dates import build_deadline, now_local, parse_date, parse_time
from app.utils.formatting import escape_html
from app.utils.security import sanitize_text
from app.utils.telegram import extract_file_info

router = Router(name="admin.task_create")


# --------------------------------------------------------------------------- #
# Step 1: title
# --------------------------------------------------------------------------- #
@router.message(
    StateFilter(TaskCreationStates.waiting_title),
    F.text,
)
async def step_title(message: Message, state: FSMContext) -> None:
    """Capture the title and advance to the description step."""
    title = sanitize_text(message.text or "")
    if not title:
        await message.answer(invalid_input("Sarlavha"))
        await message.answer(ask_task_title())
        return

    await state.update_data(title=title)
    await state.set_state(TaskCreationStates.waiting_description)
    await message.answer(ask_task_description())


# --------------------------------------------------------------------------- #
# Step 2: description
# --------------------------------------------------------------------------- #
@router.message(
    StateFilter(TaskCreationStates.waiting_description),
    F.text,
)
async def step_description(message: Message, state: FSMContext) -> None:
    """Capture the description (or ``—`` to skip) and advance to attachment choice."""
    raw = sanitize_text(message.text or "")
    description: str | None = None if raw in {"—", "/skip", ""} else raw

    await state.update_data(description=description)
    await state.set_state(TaskCreationStates.waiting_attachment_choice)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Ha, biriktiraman",
                    callback_data=MenuCallback(action="attach_yes").pack(),
                ),
                InlineKeyboardButton(
                    text="⏭ Yo'q, davom etish",
                    callback_data=MenuCallback(action="attach_no").pack(),
                ),
            ]
        ]
    )
    await message.answer(
        "📎 <b>Vazifaga fayl yoki rasm biriktirasizmi?</b>",
        reply_markup=kb,
    )


# --------------------------------------------------------------------------- #
# Step 2b: attachment choice (callback-driven) + attachment capture
# --------------------------------------------------------------------------- #
async def _proceed_to_employee_selection(
    message: Message,
    state: FSMContext,
) -> None:
    """Shared helper — fetch active employees and advance to ``waiting_employee``.

    Cleans up any leftover ``attachment`` key from FSM data when called from
    the "no attachment" path; the caller is responsible for that cleanup.
    """
    try:
        employees = await EmployeeService().get_active_employees()
    except Exception as exc:  # noqa: BLE001 — defensive
        logger.error("Failed to load employees for task wizard: {}", exc)
        await message.answer(error_message())
        return

    if not employees:
        await message.answer(
            no_tasks() + "\n\nIltimos, avval xodim qo'shing."
        )
        await state.clear()
        await message.answer(cancelled(), reply_markup=admin_menu())
        return

    await state.set_state(TaskCreationStates.waiting_employee)
    await message.answer(
        ask_task_employee(),
        reply_markup=employee_select_inline(employees),
    )


@router.callback_query(
    MenuCallback.filter(F.action == "attach_yes"),
    StateFilter(TaskCreationStates.waiting_attachment_choice),
)
async def step_attach_yes(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Admin chose to attach a file — enter ``waiting_attachment`` state."""
    await state.set_state(TaskCreationStates.waiting_attachment)
    message = callback.message
    if isinstance(message, Message):
        await message.answer(
            "📎 Fayl yoki rasmni yuboring (yoki /skip bilan o'tkazib yuboring):",
            reply_markup=cancel_keyboard(),
        )
    await callback.answer()


@router.callback_query(
    MenuCallback.filter(F.action == "attach_no"),
    StateFilter(TaskCreationStates.waiting_attachment_choice),
)
async def step_attach_no(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Admin chose to skip the attachment — proceed to employee selection."""
    await state.update_data(attachment=None)
    message = callback.message
    if isinstance(message, Message):
        await _proceed_to_employee_selection(message, state)
    await callback.answer()


@router.message(
    StateFilter(TaskCreationStates.waiting_attachment),
    F.photo | F.document | F.video | F.audio | F.voice | F.animation,
)
async def step_attachment_file(message: Message, state: FSMContext) -> None:
    """Capture file metadata, store it in FSM state and proceed to employee selection."""
    info = extract_file_info(message)
    if info is None:
        await message.answer(
            invalid_input("fayl") + "\nIltimos, rasm yoki fayl yuboring."
        )
        return

    await state.update_data(attachment=info)
    await message.answer("✅ Fayl qabul qilindi.")
    await _proceed_to_employee_selection(message, state)


@router.message(
    StateFilter(TaskCreationStates.waiting_attachment),
    Command("skip"),
)
async def step_attachment_skip(message: Message, state: FSMContext) -> None:
    """Skip the attachment step and proceed to employee selection."""
    await state.update_data(attachment=None)
    await _proceed_to_employee_selection(message, state)


@router.message(
    StateFilter(TaskCreationStates.waiting_attachment),
    F.text == "/skip",
)
async def step_attachment_skip_text(
    message: Message, state: FSMContext
) -> None:
    """Text fallback for ``/skip`` in the attachment step."""
    await state.update_data(attachment=None)
    await _proceed_to_employee_selection(message, state)


@router.message(
    StateFilter(TaskCreationStates.waiting_attachment_choice),
    F.text == "⏭ Yo'q, davom etish",
)
async def step_attachment_choice_text_skip(
    message: Message, state: FSMContext
) -> None:
    """Reply-keyboard fallback for skipping the attachment choice."""
    await state.update_data(attachment=None)
    await _proceed_to_employee_selection(message, state)


# --------------------------------------------------------------------------- #
# Step 3: employee (callback-driven) — single employee OR all employees
# --------------------------------------------------------------------------- #
@router.callback_query(
    EmployeeCallback.filter(F.action == "view"),
    StateFilter(TaskCreationStates.waiting_employee),
)
async def step_employee(
    callback: CallbackQuery,
    callback_data: EmployeeCallback,
    state: FSMContext,
) -> None:
    """Store the selected employee id and advance to the priority step."""
    try:
        employee_id = int(callback_data.employee_id)
    except (TypeError, ValueError):
        await callback.answer("Noto'g'ri xodim.", show_alert=True)
        return

    await state.update_data(employee_id=employee_id, assign_all=False)
    await state.set_state(TaskCreationStates.waiting_priority)

    message = callback.message
    if isinstance(message, Message):
        await message.answer(ask_task_priority(), reply_markup=priority_inline())
    await callback.answer()


@router.callback_query(
    MenuCallback.filter(F.action == "assign_all_employees"),
    StateFilter(TaskCreationStates.waiting_employee),
)
async def step_employee_all(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Broadcast the task to ALL active employees — skip single selection."""
    await state.update_data(employee_id=None, assign_all=True)
    await state.set_state(TaskCreationStates.waiting_priority)

    message = callback.message
    if isinstance(message, Message):
        await message.answer(
            "👥 <b>Hamma xodimlarga yuborish</b> tanlandi.\n"
            "Vazifa barcha faol xodimlarga yuboriladi.\n\n"
            + ask_task_priority(),
            reply_markup=priority_inline(),
        )
    await callback.answer("👥 Hamma xodimlarga")


# --------------------------------------------------------------------------- #
# Step 4: priority (callback-driven)
# --------------------------------------------------------------------------- #
@router.callback_query(
    PriorityCallback.filter(),
    StateFilter(TaskCreationStates.waiting_priority),
)
async def step_priority(
    callback: CallbackQuery,
    callback_data: PriorityCallback,
    state: FSMContext,
) -> None:
    """Store the priority and advance to the date step (calendar picker)."""
    try:
        priority = TaskPriority(callback_data.priority)
    except ValueError:
        await callback.answer("Noto'g'ri ustuvorlik.", show_alert=True)
        return

    await state.update_data(priority=priority.value)
    await state.set_state(TaskCreationStates.waiting_date)

    message = callback.message
    if isinstance(message, Message):
        today = now_local().date()
        await message.answer(
            ask_task_date(),
            reply_markup=calendar_keyboard(today.year, today.month),
        )
    await callback.answer()


# --------------------------------------------------------------------------- #
# Step 5: date — inline calendar (with text fallback)
# --------------------------------------------------------------------------- #
@router.callback_query(
    CalendarCallback.filter(F.action == "nav"),
    StateFilter(TaskCreationStates.waiting_date),
)
async def step_date_nav(
    callback: CallbackQuery,
    callback_data: CalendarCallback,
) -> None:
    """Navigate to the previous / next month in the calendar."""
    try:
        year = int(callback_data.year)
        month = int(callback_data.month)
        direction = int(callback_data.direction)
    except (TypeError, ValueError):
        await callback.answer()
        return

    new_year, new_month = shift_month(year, month, direction)
    message = callback.message
    if isinstance(message, Message):
        try:
            await message.edit_reply_markup(
                reply_markup=calendar_keyboard(new_year, new_month)
            )
        except Exception:  # noqa: BLE001 — "message not modified" etc.
            pass
    await callback.answer()


@router.callback_query(
    CalendarCallback.filter(F.action == "day"),
    StateFilter(TaskCreationStates.waiting_date),
)
async def step_date_pick(
    callback: CallbackQuery,
    callback_data: CalendarCallback,
    state: FSMContext,
) -> None:
    """Store the picked day and advance to the time (hour) step."""
    try:
        d = date(int(callback_data.year), int(callback_data.month), int(callback_data.day))
    except (TypeError, ValueError):
        await callback.answer("Noto'g'ri sana.", show_alert=True)
        return

    await state.update_data(date=d.isoformat())
    await state.set_state(TaskCreationStates.waiting_time)

    message = callback.message
    if isinstance(message, Message):
        await message.answer(ask_task_time(), reply_markup=hour_keyboard())
    await callback.answer(f"✅ {d.strftime('%d.%m.%Y')} tanlandi")


@router.callback_query(
    CalendarCallback.filter(F.action == "today"),
    StateFilter(TaskCreationStates.waiting_date),
)
async def step_date_today(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Jump to / pick today as the deadline date."""
    today = now_local().date()
    await state.update_data(date=today.isoformat())
    await state.set_state(TaskCreationStates.waiting_time)

    message = callback.message
    if isinstance(message, Message):
        await message.answer(ask_task_time(), reply_markup=hour_keyboard())
    await callback.answer(f"✅ Bugun ({today.strftime('%d.%m.%Y')}) tanlandi")


@router.callback_query(
    CalendarCallback.filter(F.action == "cancel"),
    StateFilter(TaskCreationStates.waiting_date),
)
async def step_date_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    """Abort the wizard from the calendar view."""
    await state.clear()
    message = callback.message
    if isinstance(message, Message):
        await message.answer(cancelled(), reply_markup=admin_menu())
    await callback.answer()


@router.callback_query(
    CalendarCallback.filter(F.action == "ignore"),
    StateFilter(TaskCreationStates.waiting_date),
)
async def step_date_ignore(callback: CallbackQuery) -> None:
    """No-op for header / blank / past-day buttons."""
    await callback.answer()


@router.message(
    StateFilter(TaskCreationStates.waiting_date),
    F.text,
)
async def step_date_text(message: Message, state: FSMContext) -> None:
    """Text fallback: parse a typed date (DD.MM.YYYY) and advance."""
    try:
        d: date = parse_date(message.text or "")
    except ValueError:
        await message.answer(invalid_input("sana"))
        await message.answer(ask_task_date())
        return

    await state.update_data(date=d.isoformat())
    await state.set_state(TaskCreationStates.waiting_time)
    await message.answer(ask_task_time(), reply_markup=hour_keyboard())


# --------------------------------------------------------------------------- #
# Step 6: time — inline time picker (with text fallback)
# --------------------------------------------------------------------------- #
@router.callback_query(
    TimePickerCallback.filter(F.action == "hour"),
    StateFilter(TaskCreationStates.waiting_time),
)
async def step_time_hour(
    callback: CallbackQuery,
    callback_data: TimePickerCallback,
) -> None:
    """Store the hour and show the minute grid."""
    try:
        hour = int(callback_data.value)
    except (TypeError, ValueError):
        await callback.answer("Noto'g'ri soat.", show_alert=True)
        return
    if not 0 <= hour <= 23:
        await callback.answer("Noto'g'ri soat.", show_alert=True)
        return

    message = callback.message
    if isinstance(message, Message):
        try:
            await message.edit_reply_markup(reply_markup=minute_keyboard(hour))
        except Exception:  # noqa: BLE001 — defensive
            await message.answer(ask_task_time(), reply_markup=minute_keyboard(hour))
    await callback.answer(f"⏰ {hour:02d}:__ — daqiqani tanlang")


@router.callback_query(
    TimePickerCallback.filter(F.action == "minute"),
    StateFilter(TaskCreationStates.waiting_time),
)
async def step_time_minute(
    callback: CallbackQuery,
    callback_data: TimePickerCallback,
    state: FSMContext,
) -> None:
    """Store the picked time and advance to the timezone step."""
    try:
        hour = int(callback_data.hour)
        minute = int(callback_data.value)
    except (TypeError, ValueError):
        await callback.answer("Noto'g'ri vaqt.", show_alert=True)
        return
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        await callback.answer("Noto'g'ri vaqt.", show_alert=True)
        return

    t = time(hour, minute)
    await state.update_data(time=t.isoformat())
    await state.set_state(TaskCreationStates.waiting_timezone)

    message = callback.message
    if isinstance(message, Message):
        tz_kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🌍 Asia/Tashkent",
                        callback_data=MenuCallback(action="tz_default").pack(),
                    )
                ]
            ]
        )
        await message.answer(ask_task_timezone(), reply_markup=tz_kb)
    await callback.answer(f"✅ {t.strftime('%H:%M')} tanlandi")


@router.callback_query(
    TimePickerCallback.filter(F.action == "back"),
    StateFilter(TaskCreationStates.waiting_time),
)
async def step_time_back(callback: CallbackQuery) -> None:
    """Return from the minute grid to the hour grid."""
    message = callback.message
    if isinstance(message, Message):
        try:
            await message.edit_reply_markup(reply_markup=hour_keyboard())
        except Exception:  # noqa: BLE001 — defensive
            pass
    await callback.answer()


@router.callback_query(
    TimePickerCallback.filter(F.action == "cancel"),
    StateFilter(TaskCreationStates.waiting_time),
)
async def step_time_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    """Abort the wizard from the time picker."""
    await state.clear()
    message = callback.message
    if isinstance(message, Message):
        await message.answer(cancelled(), reply_markup=admin_menu())
    await callback.answer()


@router.message(
    StateFilter(TaskCreationStates.waiting_time),
    F.text,
)
async def step_time_text(message: Message, state: FSMContext) -> None:
    """Text fallback: parse a typed time (HH:MM) and advance."""
    try:
        t: time = parse_time(message.text or "")
    except ValueError:
        await message.answer(invalid_input("vaqt"))
        await message.answer(ask_task_time(), reply_markup=hour_keyboard())
        return

    await state.update_data(time=t.isoformat())
    await state.set_state(TaskCreationStates.waiting_timezone)

    tz_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🌍 Asia/Tashkent",
                    callback_data=MenuCallback(action="tz_default").pack(),
                )
            ]
        ]
    )
    await message.answer(ask_task_timezone(), reply_markup=tz_kb)


# --------------------------------------------------------------------------- #
# Step 7: timezone (callback OR text)
# --------------------------------------------------------------------------- #
@router.callback_query(
    MenuCallback.filter(F.action == "tz_default"),
    StateFilter(TaskCreationStates.waiting_timezone),
)
async def step_tz_default(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Use the default app timezone and advance to the confirm step."""
    message = callback.message
    if isinstance(message, Message):
        await _finalize_timezone(message, state, settings.app_timezone)
    await callback.answer()


@router.message(
    StateFilter(TaskCreationStates.waiting_timezone),
    F.text,
)
async def step_tz_text(message: Message, state: FSMContext) -> None:
    """Validate the typed timezone and advance to the confirm step."""
    tz_input = sanitize_text(message.text or "")
    try:
        pytz.timezone(tz_input)
    except pytz.UnknownTimeZoneError:
        await message.answer(invalid_input("vaqt zonasi"))
        await message.answer(ask_task_timezone())
        return

    await _finalize_timezone(message, state, tz_input)


async def _finalize_timezone(
    message: Message,
    state: FSMContext,
    tz_name: str,
) -> None:
    """Build the deadline, render the confirm card and advance state."""
    data = await state.get_data()

    try:
        d = parse_date(data["date"])
        t = parse_time(data["time"])
    except (KeyError, ValueError):
        await message.answer(error_message())
        await state.clear()
        await message.answer(cancelled(), reply_markup=admin_menu())
        return

    deadline_utc = build_deadline(d, t, tz_name)
    await state.update_data(
        timezone=tz_name,
        deadline_utc=deadline_utc.isoformat(),
    )

    priority = TaskPriority(data.get("priority", TaskPriority.MEDIUM.value))
    task_obj = SimpleNamespace(
        id="—",
        title=data.get("title", ""),
        description=data.get("description"),
        priority=priority,
        deadline=deadline_utc,
        status=TaskStatus.PENDING,
    )

    employee = None
    assign_all = data.get("assign_all", False)
    if assign_all:
        # Broadcast mode — no single employee to show; use a stub.
        employee = SimpleNamespace(
            code="ALL",
            full_name="Hamma xodimlar",
            position=None,
            department=None,
        )
    elif data.get("employee_id") is not None:
        try:
            employee = await EmployeeService().get_employee(int(data["employee_id"]))
        except Exception as exc:  # noqa: BLE001 — defensive
            logger.warning("Could not load employee for confirm card: {}", exc)

    # During creation the attachment has been captured but not yet persisted
    # (it will be saved after the task row exists). Show 1 if one is queued.
    queued_attachment = data.get("attachment")
    attachment_count = 1 if queued_attachment else 0

    card = task_confirm_card(
        task_obj,
        employee=employee,
        attachment_count=attachment_count,
    )
    await state.set_state(TaskCreationStates.waiting_confirm)
    await message.answer(card, reply_markup=confirm_inline(payload="create_task"))


# --------------------------------------------------------------------------- #
# Step 8: confirm (yes / no)
# --------------------------------------------------------------------------- #
async def _persist_attachment_for_task(
    task_id: int,
    attachment: dict,
    uploaded_by: int,
) -> None:
    """Persist the queued attachment dict onto the freshly created task.

    Args:
        task_id: Primary key of the task.
        attachment: Dict produced by :func:`extract_file_info`.
        uploaded_by: User id of the acting admin.
    """
    try:
        await AttachmentService().add_attachment(
            task_id=task_id,
            file_id=attachment["file_id"],
            file_unique_id=attachment["file_unique_id"],
            file_type=attachment["file_type"],
            file_name=attachment.get("file_name"),
            file_size=attachment.get("file_size"),
            caption=attachment.get("caption"),
            mime_type=attachment.get("mime_type"),
            uploaded_by=uploaded_by,
        )
    except Exception as exc:  # noqa: BLE001 — defensive
        logger.error(
            "Failed to persist attachment for task {}: {}",
            task_id,
            exc,
        )


async def _notify_task_created(task_id: int) -> None:
    """Fire-and-forget NEW_TASK notification to the assigned employee."""
    try:
        from app.services.notification import NotificationService

        await NotificationService().send_new_task_notification(task_id)
    except Exception as exc:  # noqa: BLE001 — defensive
        logger.warning(
            "Failed to dispatch NEW_TASK notification for task {}: {}",
            task_id,
            exc,
        )


@router.callback_query(
    ConfirmCallback.filter((F.action == "yes") & (F.payload == "create_task")),
    StateFilter(TaskCreationStates.waiting_confirm),
)
async def confirm_create(
    callback: CallbackQuery,
    state: FSMContext,
    user: User | None = None,
) -> None:
    """Create the task (for one employee or all) and return to the admin menu."""
    data = await state.get_data()
    message = callback.message

    try:
        priority = TaskPriority(data.get("priority", TaskPriority.MEDIUM.value))
        deadline = datetime.fromisoformat(data["deadline_utc"])
        if user is None:
            raise RuntimeError("Acting user not resolved by middleware")
        assigned_by = user.id

        assign_all = data.get("assign_all", False)
        attachment = data.get("attachment") or None
        if not isinstance(attachment, dict):
            attachment = None

        if assign_all:
            # Broadcast mode: create a separate task for every active employee.
            employees = await EmployeeService().get_active_employees()
            if not employees:
                raise RuntimeError("Faol xodimlar topilmadi")
            created_count = 0
            for emp in employees:
                task = await TaskService().create_task(
                    title=data["title"],
                    description=data.get("description"),
                    employee_id=emp.id,
                    priority=priority,
                    deadline=deadline,
                    assigned_by=assigned_by,
                )
                if attachment:
                    await _persist_attachment_for_task(
                        task.id, attachment, uploaded_by=assigned_by
                    )
                await _notify_task_created(task.id)
                created_count += 1
            logger.info(
                "Admin {} broadcast task {!r} to {} employees",
                assigned_by,
                data["title"],
                created_count,
            )
            if isinstance(message, Message):
                await message.answer(
                    f"✅ <b>Vazifa {created_count} ta xodimga yuborildi!</b>\n\n"
                    f"📋 Sarlavha: {escape_html(data['title'])}\n"
                    f"👥 Hamma faol xodimlarga: {created_count} ta",
                    reply_markup=admin_menu(),
                )
        else:
            # Single-employee mode.
            task = await TaskService().create_task(
                title=data["title"],
                description=data.get("description"),
                employee_id=int(data["employee_id"]),
                priority=priority,
                deadline=deadline,
                assigned_by=assigned_by,
            )
            if attachment:
                await _persist_attachment_for_task(
                    task.id, attachment, uploaded_by=assigned_by
                )
            employee = await EmployeeService().get_employee(int(data["employee_id"]))
            emp_name = employee.full_name if employee else "Xodim"

            logger.info(
                "Admin {} created task id={} title={!r}",
                assigned_by,
                task.id,
                task.title,
            )

            # Fire-and-forget NEW_TASK notification (sends task card + any
            # attached files to the assigned employee).
            await _notify_task_created(task.id)

            if isinstance(message, Message):
                await message.answer(
                    task_created_success(task.title, emp_name),
                    reply_markup=admin_menu(),
                )
    except Exception as exc:  # noqa: BLE001 — defensive
        logger.error("Task creation failed: {}", exc)
        if isinstance(message, Message):
            await message.answer(error_message(), reply_markup=admin_menu())
    finally:
        await state.clear()
        await callback.answer()


@router.callback_query(
    ConfirmCallback.filter((F.action == "no") & (F.payload == "create_task")),
    StateFilter(TaskCreationStates.waiting_confirm),
)
async def cancel_create(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Abort the task-creation wizard."""
    await state.clear()
    message = callback.message
    if isinstance(message, Message):
        await message.answer(cancelled(), reply_markup=admin_menu())
    await callback.answer()


# Step labels are also used by the catch-all fallback handler to display a
# friendly message when the user types something unexpected mid-wizard.
_STEP_PROMPTS = {
    TaskCreationStates.waiting_title: ask_task_title,
    TaskCreationStates.waiting_description: ask_task_description,
    TaskCreationStates.waiting_date: ask_task_date,
    TaskCreationStates.waiting_time: ask_task_time,
    TaskCreationStates.waiting_timezone: ask_task_timezone,
}


# Re-export for handlers package.
_ = escape_html  # kept for future inline-html usage
__all__ = ["router"]
