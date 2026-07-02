"""Statistics handlers — period picker, report rendering, Excel export.

Covers:

- ``StatsCallback(period="daily|weekly|monthly|overall")`` — render the
  matching report via :class:`StatisticsService` and ``stats_card``.
- ``StatsCallback(period="employee")`` — first asks the admin to pick an
  employee via a custom inline list (``EmployeeCallback(action="stats")``),
  then renders that employee's stats.
- ``EmployeeCallback(action="stats", employee_id)`` — completes the
  per-employee flow above.
- ``MenuCallback(action="export_stats_excel")`` — re-renders the last
  statistics dict as an Excel download.
"""

from __future__ import annotations

from datetime import datetime, timezone

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from aiogram.types.input_file import BufferedInputFile
from loguru import logger

from app.bot.keyboards.callbacks import (
    EmployeeCallback,
    MenuCallback,
    StatsCallback,
)
from app.notifications.templates import error_message
from app.services.employee import EmployeeService
from app.services.export import ExportService
from app.services.statistics import StatisticsService
from app.utils.formatting import stats_card

router = Router(name="admin.statistics")


async def _send_stats(
    message: Message,
    stats: dict,
    state: FSMContext,
) -> None:
    """Render the stats card + an Excel-export button; cache the dict."""
    # FSM data is JSON-serialisable; the stats dict already is.
    await state.update_data(last_stats=stats)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📊 Excel",
                    callback_data=MenuCallback(
                        action="export_stats_excel"
                    ).pack(),
                )
            ]
        ]
    )
    await message.answer(stats_card(stats), reply_markup=kb)


# --------------------------------------------------------------------------- #
# Period picker
# --------------------------------------------------------------------------- #
@router.callback_query(StatsCallback.filter(F.period == "overall"))
async def stats_overall(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Render overall system statistics."""
    message = callback.message
    if not isinstance(message, Message):
        await callback.answer()
        return

    try:
        stats = await StatisticsService().overall_stats()
    except Exception as exc:  # noqa: BLE001 — defensive
        logger.error("overall_stats failed: {}", exc)
        await message.answer(error_message())
        await callback.answer()
        return

    await _send_stats(message, stats, state)
    await callback.answer()


@router.callback_query(StatsCallback.filter(F.period == "daily"))
async def stats_daily(callback: CallbackQuery, state: FSMContext) -> None:
    """Render today's daily report."""
    message = callback.message
    if not isinstance(message, Message):
        await callback.answer()
        return

    try:
        stats = await StatisticsService().daily_report()
    except Exception as exc:  # noqa: BLE001 — defensive
        logger.error("daily_report failed: {}", exc)
        await message.answer(error_message())
        await callback.answer()
        return

    await _send_stats(message, stats, state)
    await callback.answer()


@router.callback_query(StatsCallback.filter(F.period == "weekly"))
async def stats_weekly(callback: CallbackQuery, state: FSMContext) -> None:
    """Render the current week's report."""
    message = callback.message
    if not isinstance(message, Message):
        await callback.answer()
        return

    try:
        stats = await StatisticsService().weekly_report()
    except Exception as exc:  # noqa: BLE001 — defensive
        logger.error("weekly_report failed: {}", exc)
        await message.answer(error_message())
        await callback.answer()
        return

    await _send_stats(message, stats, state)
    await callback.answer()


@router.callback_query(StatsCallback.filter(F.period == "monthly"))
async def stats_monthly(callback: CallbackQuery, state: FSMContext) -> None:
    """Render the current month's report."""
    message = callback.message
    if not isinstance(message, Message):
        await callback.answer()
        return

    try:
        stats = await StatisticsService().monthly_report()
    except Exception as exc:  # noqa: BLE001 — defensive
        logger.error("monthly_report failed: {}", exc)
        await message.answer(error_message())
        await callback.answer()
        return

    await _send_stats(message, stats, state)
    await callback.answer()


# --------------------------------------------------------------------------- #
# Per-employee stats
# --------------------------------------------------------------------------- #
@router.callback_query(StatsCallback.filter(F.period == "employee"))
async def stats_employee_pick(callback: CallbackQuery) -> None:
    """Ask the admin to pick an employee for per-employee stats."""
    message = callback.message
    if not isinstance(message, Message):
        await callback.answer()
        return

    try:
        employees = await EmployeeService().get_active_employees()
    except Exception as exc:  # noqa: BLE001 — defensive
        logger.error("Failed to load employees for stats: {}", exc)
        await message.answer(error_message())
        await callback.answer()
        return

    if not employees:
        await message.answer("📭 Hozircha xodimlar yo'q.")
        await callback.answer()
        return

    rows: list[list[InlineKeyboardButton]] = []
    for emp in employees:
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{emp.code} — {emp.full_name}",
                    callback_data=EmployeeCallback(
                        action="stats", employee_id=str(emp.id)
                    ).pack(),
                )
            ]
        )
    kb = InlineKeyboardMarkup(inline_keyboard=rows)

    await message.answer(
        "👤 Statistikani ko'rish uchun xodimni tanlang:",
        reply_markup=kb,
    )
    await callback.answer()


@router.callback_query(EmployeeCallback.filter(F.action == "stats"))
async def stats_employee_render(
    callback: CallbackQuery,
    callback_data: EmployeeCallback,
    state: FSMContext,
) -> None:
    """Render per-employee stats for the selected employee."""
    message = callback.message
    if not isinstance(message, Message):
        await callback.answer()
        return

    try:
        employee_id = int(callback_data.employee_id)
    except (TypeError, ValueError):
        await callback.answer("Noto'g'ri xodim.", show_alert=True)
        return

    try:
        stats = await StatisticsService().employee_stats(employee_id)
    except Exception as exc:  # noqa: BLE001 — defensive
        logger.error("employee_stats failed: {}", exc)
        await message.answer(error_message())
        await callback.answer()
        return

    employee = await EmployeeService().get_employee(employee_id)
    name = employee.full_name if employee else "Xodim"
    stats = {**stats, "employee": name}
    await _send_stats(message, stats, state)
    await callback.answer()


# --------------------------------------------------------------------------- #
# Excel export of the last rendered stats
# --------------------------------------------------------------------------- #
@router.callback_query(
    MenuCallback.filter(F.action == "export_stats_excel"),
)
async def export_stats_excel(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Build an Excel document from the last rendered stats dict."""
    message = callback.message
    if not isinstance(message, Message):
        await callback.answer()
        return

    data = await state.get_data()
    stats = data.get("last_stats")
    if not stats:
        await callback.answer(
            "Avval statistikani ko'rsating.", show_alert=True
        )
        return

    await callback.answer("⏳ Tayyorlanmoqda...")
    try:
        blob = await ExportService().export_statistics_excel(stats)
    except Exception as exc:  # noqa: BLE001 — defensive
        logger.error("Stats Excel export failed: {}", exc)
        await message.answer(error_message())
        return

    await message.answer_document(
        document=BufferedInputFile(
            blob,
            filename=f"stats_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.xlsx",
        ),
        caption="📊 Statistika hisoboti (Excel)",
    )


__all__ = ["router"]
