import asyncio
import logging
import uuid
from typing import Dict
from aiogram import F, Router, Bot
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

from app.config import settings
from app.database import db
from app.locales import format_duration, get_text
from app.services.routing import RouteError, build_multi_route
from app.services.geocoding import enrich_points_with_addresses
from app.bot.keyboards import (
    get_cancel_inline_keyboard,
    get_cancel_rename_keyboard,
    get_clear_route_keyboard,
    get_lang_inline_keyboard,
    get_location_request_reply_keyboard,
    get_multi_route_keyboard,
    get_name_step_keyboard,
    get_rename_points_keyboard,
)

logger = logging.getLogger(__name__)

router = Router(name="bot_router")

# Track background debounce tasks per user_id
user_debounce_tasks: Dict[int, asyncio.Task] = {}


class SetOriginStates(StatesGroup):
    """FSM states for Admin setting new Origin Point A."""
    waiting_for_location = State()
    waiting_for_name = State()


class RenamePointStates(StatesGroup):
    """FSM states for user giving custom names to destination waypoints."""
    waiting_for_name = State()


# ---------------------------------------------------------------------------
# General Commands: /start, /lang, /clear
# ---------------------------------------------------------------------------


@router.message(CommandStart())
async def handle_start(message: Message, state: FSMContext) -> None:
    """Handle /start command: Reset active FSM, welcome user and prompt language selection."""
    await state.clear()
    user_id = message.from_user.id if message.from_user else 0
    logger.info("User %s triggered /start", user_id)
    current_lang = await db.get_user_lang(user_id)
    text = get_text("welcome", current_lang)
    await message.answer(text, reply_markup=get_lang_inline_keyboard(), parse_mode="HTML")


@router.message(Command("lang"))
async def handle_lang_cmd(message: Message) -> None:
    """Handle /lang command: Prompt interface language selection."""
    user_id = message.from_user.id if message.from_user else 0
    logger.info("User %s triggered /lang", user_id)
    current_lang = await db.get_user_lang(user_id)
    text = get_text("choose_lang", current_lang)
    await message.answer(text, reply_markup=get_lang_inline_keyboard(), parse_mode="HTML")


@router.callback_query(F.data.startswith("set_lang:"))
async def handle_set_lang_callback(call: CallbackQuery) -> None:
    """Process language selection callback."""
    if not call.data or not call.from_user:
        return

    lang = call.data.split(":", 1)[1]
    if lang not in ("ru", "uz"):
        lang = "ru"

    await db.set_user_lang(call.from_user.id, lang)
    await call.answer()

    text = get_text("lang_selected", lang)
    if call.message:
        await call.message.edit_text(text, parse_mode="HTML")


@router.message(Command("clear"))
async def handle_clear_command(message: Message) -> None:
    """Clear active route draft waypoints via /clear command."""
    user_id = message.from_user.id if message.from_user else 0
    lang = await db.get_user_lang(user_id)

    # Cancel any pending debounce task
    if user_id in user_debounce_tasks and not user_debounce_tasks[user_id].done():
        user_debounce_tasks[user_id].cancel()

    deleted = await db.clear_draft_points(user_id)
    if deleted > 0:
        await message.answer(get_text("route_cleared", lang), parse_mode="HTML")
    else:
        await message.answer(get_text("route_already_empty", lang), parse_mode="HTML")


@router.callback_query(F.data == "clear_route")
async def handle_clear_route_callback(call: CallbackQuery) -> None:
    """Clear active route draft waypoints via inline button."""
    user_id = call.from_user.id if call.from_user else 0
    lang = await db.get_user_lang(user_id)

    # Cancel any pending debounce task
    if user_id in user_debounce_tasks and not user_debounce_tasks[user_id].done():
        user_debounce_tasks[user_id].cancel()

    await db.clear_draft_points(user_id)
    await call.answer(get_text("route_cleared", lang))

    if call.message:
        await call.message.answer(get_text("route_cleared", lang), parse_mode="HTML")


# ---------------------------------------------------------------------------
# Admin Flow: /origin, /set_origin and FSM
# ---------------------------------------------------------------------------


@router.message(Command("origin"))
async def handle_show_origin(message: Message) -> None:
    """Show current Origin Point A (Admin only)."""
    user_id = message.from_user.id if message.from_user else 0
    lang = await db.get_user_lang(user_id)
    logger.info("User %s requested /origin. Admin list: %s", user_id, settings.ADMIN_IDS)

    if user_id not in settings.ADMIN_IDS:
        await message.answer(get_text("access_denied", lang), parse_mode="HTML")
        return

    origin = await db.get_origin()
    text = get_text(
        "current_origin",
        lang,
        name=origin.get("name", "N/A"),
        lat=origin.get("lat", 0.0),
        lon=origin.get("lon", 0.0),
    )
    await message.answer(text, parse_mode="HTML")
    try:
        await message.answer_location(
            latitude=origin["lat"],
            longitude=origin["lon"],
        )
    except Exception as exc:
        logger.warning("Could not send location pin for origin: %s", exc)


@router.message(Command("set_origin"))
async def handle_set_origin_start(message: Message, state: FSMContext) -> None:
    """Start FSM for updating Origin Point A (Admin only)."""
    user_id = message.from_user.id if message.from_user else 0
    lang = await db.get_user_lang(user_id)
    logger.info("User %s requested /set_origin. Admin list: %s", user_id, settings.ADMIN_IDS)

    if user_id not in settings.ADMIN_IDS:
        await message.answer(get_text("access_denied", lang), parse_mode="HTML")
        return

    await state.set_state(SetOriginStates.waiting_for_location)
    await message.answer(
        get_text("set_origin_step1", lang),
        reply_markup=get_location_request_reply_keyboard(lang),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "cancel_fsm", StateFilter(SetOriginStates))
async def handle_cancel_fsm_callback(call: CallbackQuery, state: FSMContext) -> None:
    """Cancel FSM flow via inline button."""
    user_id = call.from_user.id if call.from_user else 0
    lang = await db.get_user_lang(user_id)
    await state.clear()
    await call.answer()
    if call.message:
        await call.message.edit_text(get_text("action_cancelled", lang), parse_mode="HTML")


@router.message(
    F.text.in_(["❌ Отмена", "❌ Bekor qilish", "/cancel"]),
    StateFilter(SetOriginStates),
)
async def handle_cancel_fsm_message(message: Message, state: FSMContext) -> None:
    """Cancel FSM flow via text message or reply button."""
    user_id = message.from_user.id if message.from_user else 0
    lang = await db.get_user_lang(user_id)
    await state.clear()
    await message.answer(
        get_text("action_cancelled", lang),
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="HTML",
    )


@router.message(SetOriginStates.waiting_for_location, F.location)
async def handle_origin_location_received(message: Message, state: FSMContext) -> None:
    """Receive location for Point A and ask for optional name."""
    if not message.location:
        return

    lat = message.location.latitude
    lon = message.location.longitude
    user_id = message.from_user.id if message.from_user else 0
    lang = await db.get_user_lang(user_id)

    await state.update_data(lat=lat, lon=lon)
    await state.set_state(SetOriginStates.waiting_for_name)

    await message.answer(
        get_text("set_origin_step2", lang, lat=lat, lon=lon),
        reply_markup=get_name_step_keyboard(lang),
        parse_mode="HTML",
    )


@router.callback_query(SetOriginStates.waiting_for_name, F.data == "skip_origin_name")
async def handle_origin_name_skipped(call: CallbackQuery, state: FSMContext) -> None:
    """Skip origin name step and save coordinates with default title."""
    user_id = call.from_user.id if call.from_user else 0
    lang = await db.get_user_lang(user_id)
    data = await state.get_data()

    lat = data.get("lat")
    lon = data.get("lon")

    if lat is not None and lon is not None:
        await db.set_origin(lat, lon, None)
        origin = await db.get_origin()
        await call.answer()
        if call.message:
            await call.message.edit_text(
                get_text("set_origin_success", lang, name=origin["name"], lat=lat, lon=lon),
                parse_mode="HTML",
            )
    await state.clear()


@router.message(SetOriginStates.waiting_for_name, F.text)
async def handle_origin_name_entered(message: Message, state: FSMContext) -> None:
    """Save custom name for Origin Point A."""
    name = message.text.strip() if message.text else ""
    user_id = message.from_user.id if message.from_user else 0
    lang = await db.get_user_lang(user_id)
    data = await state.get_data()

    lat = data.get("lat")
    lon = data.get("lon")

    if lat is not None and lon is not None:
        await db.set_origin(lat, lon, name)
        origin = await db.get_origin()
        await state.clear()
        await message.answer(
            get_text("set_origin_success", lang, name=origin["name"], lat=lat, lon=lon),
            reply_markup=ReplyKeyboardRemove(),
            parse_mode="HTML",
        )
    else:
        await state.clear()
        await message.answer(get_text("action_cancelled", lang), reply_markup=ReplyKeyboardRemove(), parse_mode="HTML")


# ---------------------------------------------------------------------------
# Multi-Stop Routing with Debounce (~1.2s) & Location Naming
# ---------------------------------------------------------------------------


async def process_and_send_route(user_id: int, chat_id: int, bot: Bot) -> None:
    """
    Build multi-stop route via OSRM, enrich with addresses, save to database,
    and send summary message with interactive map and naming controls.
    """
    lang = await db.get_user_lang(user_id)
    origin = await db.get_origin()

    if origin.get("lat") is None or origin.get("lon") is None:
        await bot.send_message(
            chat_id=chat_id,
            text=get_text("origin_not_set", lang),
            parse_mode="HTML",
        )
        return

    draft_points = await db.get_draft_points_records(user_id)
    if not draft_points:
        return

    try:
        await bot.send_chat_action(chat_id=chat_id, action="typing")
    except Exception:
        pass

    try:
        route_payload = await build_multi_route(origin, draft_points)
    except RouteError as exc:
        logger.warning("Routing calculation error for user %s: %s", user_id, exc)
        await bot.send_message(
            chat_id=chat_id,
            text=get_text("route_error", lang),
            reply_markup=get_clear_route_keyboard(lang),
            parse_mode="HTML",
        )
        return
    except Exception as exc:
        logger.exception("Unexpected error in multi-route build for user %s: %s", user_id, exc)
        await bot.send_message(
            chat_id=chat_id,
            text=get_text("route_error", lang),
            reply_markup=get_clear_route_keyboard(lang),
            parse_mode="HTML",
        )
        return

    # Enrich all waypoints with short human-readable addresses
    try:
        route_payload["points"] = await enrich_points_with_addresses(route_payload["points"], lang=lang)
        addr_map = {p["label"]: p.get("address", "") for p in route_payload["points"]}
        for leg in route_payload.get("legs", []):
            leg["from_address"] = addr_map.get(leg["from_label"], "")
            leg["to_address"] = addr_map.get(leg["to_label"], "")
    except Exception as exc:
        logger.warning("Could not enrich points with addresses: %s", exc)

    # Generate unique route_id and persist
    route_id = uuid.uuid4().hex[:12]
    await db.save_route(route_id, user_id, route_payload)

    webapp_url = f"{settings.WEBAPP_URL}/?route_id={route_id}&lang={lang}"
    points = route_payload.get("points", [])
    legs = route_payload.get("legs", [])
    points_count = len(points)
    dest_points = points[1:]
    point_b_id = dest_points[0].get("id") if dest_points else None

    letter_badges = {
        "A": "🅰️", "B": "🅱️", "C": "🅲", "D": "🅳", "E": "🅴",
        "F": "🅵", "G": "🅶", "H": "🅷", "I": "🅸", "J": "🅹", "K": "🅺"
    }

    if len(legs) == 1:
        # Single destination format with real addresses & custom name
        leg = legs[0]
        duration_str = format_duration(leg["duration_min"], lang)
        dest_pt = points[1]
        addr_a = points[0].get("address") or origin.get("name", "Точка А")
        addr_b = dest_pt.get("address", "Точка назначения")
        if dest_pt.get("custom_name"):
            addr_b = f"<b>{dest_pt['custom_name']}</b> ({addr_b})"

        reply_text = get_text(
            "route_ready_single",
            lang,
            addr_a=addr_a,
            addr_b=addr_b,
            distance_km=leg["distance_km"],
            duration_str=duration_str,
        )
    else:
        # Multi-stop chain format (A -> B -> C ...)
        points_lines = []
        for p in points:
            badge = letter_badges.get(p["label"], f"[{p['label']}]")
            addr = p.get("address") or f"{p['lat']:.5f}, {p['lon']:.5f}"
            if p.get("custom_name"):
                points_lines.append(f"{badge} <b>{p['custom_name']} ({p['label']}):</b> {addr}")
            elif p["label"] == "A":
                origin_title = origin.get("name") or "Старт"
                points_lines.append(f"{badge} <b>{origin_title} (A):</b> {addr}")
            else:
                points_lines.append(f"{badge} <b>Точка {p['label']}:</b> {addr}")
        points_text = "\n".join(points_lines)

        leg_lines = []
        for l in legs:
            l_dur_str = format_duration(l["duration_min"], lang)
            leg_lines.append(f"🔹 <b>{l['from_label']} → {l['to_label']}:</b> ~{l['distance_km']:.1f} км (~{l_dur_str})")
        legs_text = "\n".join(leg_lines)
        total_dur_str = format_duration(route_payload["total_duration_min"], lang)

        reply_text = get_text(
            "route_ready_multi",
            lang,
            points_count=points_count,
            points_text=points_text,
            legs_text=legs_text,
            total_distance_km=route_payload["total_distance_km"],
            total_duration_str=total_dur_str,
        )

    keyboard = get_multi_route_keyboard(
        webapp_url=webapp_url,
        points_count=points_count,
        lang=lang,
        point_b_id=point_b_id,
    )

    try:
        await bot.send_message(chat_id=chat_id, text=reply_text, reply_markup=keyboard, parse_mode="HTML")
    except Exception as exc:
        logger.exception("Failed to send route message to user %s: %s", user_id, exc)


async def _debounce_process_user_route(user_id: int, chat_id: int, bot: Bot) -> None:
    """
    Background worker that waits ~1.2s for incoming batch of locations,
    then processes and sends the route summary.
    """
    try:
        await asyncio.sleep(1.2)
    except asyncio.CancelledError:
        return

    await process_and_send_route(user_id, chat_id, bot)


# ---------------------------------------------------------------------------
# Location Naming Handlers
# ---------------------------------------------------------------------------


@router.callback_query(F.data == "rename_points_menu")
async def handle_rename_points_menu(call: CallbackQuery) -> None:
    """Show menu of waypoints for user to choose which one to name/rename."""
    user_id = call.from_user.id if call.from_user else 0
    lang = await db.get_user_lang(user_id)
    origin = await db.get_origin()
    draft_records = await db.get_draft_points_records(user_id)
    if not draft_records:
        await call.answer(get_text("no_active_route_to_rename", lang), show_alert=True)
        return

    from app.services.routing import order_waypoints
    ordered = order_waypoints(origin, draft_records)
    try:
        enriched = await enrich_points_with_addresses(ordered, lang=lang)
    except Exception:
        enriched = ordered

    kb = get_rename_points_keyboard(enriched, lang=lang)
    await call.answer()
    if call.message:
        await call.message.edit_text(
            get_text("choose_point_to_rename", lang),
            reply_markup=kb,
            parse_mode="HTML",
        )


@router.callback_query(F.data.startswith("rename_pt_id:") | F.data.startswith("rename_pt_idx:"))
async def handle_rename_point_select(call: CallbackQuery, state: FSMContext) -> None:
    """Prompt user to enter custom name for selected waypoint."""
    user_id = call.from_user.id if call.from_user else 0
    lang = await db.get_user_lang(user_id)
    data_str = call.data or ""

    point_id = None
    target_idx = None
    if data_str.startswith("rename_pt_id:"):
        try:
            point_id = int(data_str.split(":", 1)[1])
        except (ValueError, TypeError):
            point_id = None
    elif data_str.startswith("rename_pt_idx:"):
        try:
            target_idx = int(data_str.split(":", 1)[1])
        except (ValueError, TypeError):
            target_idx = 0

    origin = await db.get_origin()
    draft_records = await db.get_draft_points_records(user_id)
    if not draft_records:
        await call.answer(get_text("no_active_route_to_rename", lang), show_alert=True)
        return

    from app.services.routing import order_waypoints
    ordered = order_waypoints(origin, draft_records)

    target_pt = None
    if point_id is not None:
        for pt in ordered:
            if pt.get("id") == point_id:
                target_pt = pt
                break
    if not target_pt and target_idx is not None and 0 <= target_idx < len(ordered):
        target_pt = ordered[target_idx]
        point_id = target_pt.get("id")

    if not target_pt:
        target_pt = ordered[0]
        point_id = target_pt.get("id")

    enriched = await enrich_points_with_addresses([target_pt], lang=lang)
    address = enriched[0].get("address") or f"{target_pt['lat']:.5f}, {target_pt['lon']:.5f}"
    label = target_pt.get("label", "B")
    current_name = target_pt.get("custom_name")

    current_name_info = get_text("current_custom_name", lang, name=current_name) if current_name else ""

    await state.set_state(RenamePointStates.waiting_for_name)
    await state.update_data(point_id=point_id, label=label, address=address)

    prompt = get_text(
        "enter_point_name_prompt",
        lang,
        label=label,
        address=address,
        current_name_info=current_name_info,
    )
    kb = get_cancel_rename_keyboard(point_id=point_id, lang=lang, has_custom_name=bool(current_name))
    await call.answer()
    if call.message:
        await call.message.edit_text(prompt, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.startswith("reset_pt_name:"))
async def handle_reset_point_name(call: CallbackQuery, state: FSMContext) -> None:
    """Reset custom name of waypoint back to default."""
    user_id = call.from_user.id if call.from_user else 0
    lang = await db.get_user_lang(user_id)
    await state.clear()
    data_str = call.data or ""
    try:
        point_id = int(data_str.split(":", 1)[1])
        await db.update_draft_point_name(point_id, "")
    except Exception as exc:
        logger.warning("Could not reset point name: %s", exc)

    await call.answer(get_text("point_name_reset_success", lang, label=""), show_alert=False)
    if call.message and call.bot:
        try:
            await call.message.delete()
        except Exception:
            pass
        await process_and_send_route(user_id, call.message.chat.id, call.bot)


@router.callback_query(F.data == "cancel_rename")
async def handle_cancel_rename(call: CallbackQuery, state: FSMContext) -> None:
    """Cancel renaming flow and return to current route."""
    user_id = call.from_user.id if call.from_user else 0
    lang = await db.get_user_lang(user_id)
    await state.clear()
    await call.answer(get_text("action_cancelled", lang))
    if call.message and call.bot:
        try:
            await call.message.delete()
        except Exception:
            pass
        await process_and_send_route(user_id, call.message.chat.id, call.bot)


@router.callback_query(F.data == "back_to_route")
async def handle_back_to_route(call: CallbackQuery) -> None:
    """Back button: delete menu and send route summary."""
    user_id = call.from_user.id if call.from_user else 0
    await call.answer()
    if call.message and call.bot:
        try:
            await call.message.delete()
        except Exception:
            pass
        await process_and_send_route(user_id, call.message.chat.id, call.bot)


@router.message(RenamePointStates.waiting_for_name, F.text)
async def handle_point_name_entered(message: Message, state: FSMContext) -> None:
    """Handle text input for naming waypoint."""
    user_id = message.from_user.id if message.from_user else 0
    lang = await db.get_user_lang(user_id)
    raw_name = message.text.strip() if message.text else ""

    if raw_name in ["❌ Отмена", "❌ Bekor qilish", "/cancel"]:
        await state.clear()
        await message.answer(get_text("action_cancelled", lang), reply_markup=ReplyKeyboardRemove(), parse_mode="HTML")
        if message.bot:
            await process_and_send_route(user_id, message.chat.id, message.bot)
        return

    data = await state.get_data()
    point_id = data.get("point_id")
    label = data.get("label", "")
    await state.clear()

    if point_id is not None:
        await db.update_draft_point_name(point_id, raw_name)

    await message.answer(
        get_text("point_renamed_success", lang, label=label, name=raw_name),
        parse_mode="HTML",
    )

    if message.bot:
        await process_and_send_route(user_id, message.chat.id, message.bot)


# ---------------------------------------------------------------------------
# Location Receiver Handler
# ---------------------------------------------------------------------------


@router.message(F.location)
async def handle_user_destination_location(message: Message) -> None:
    """
    Handle location sent by user.
    Appends point to active draft and triggers debounced route calculation.
    """
    if not message.location or not message.from_user or not message.bot:
        return

    user_id = message.from_user.id
    chat_id = message.chat.id
    dest_lat = message.location.latitude
    dest_lon = message.location.longitude
    lang = await db.get_user_lang(user_id)

    # Check maximum waypoints limit
    current_points = await db.get_draft_points(user_id)
    if len(current_points) >= settings.MAX_WAYPOINTS:
        await message.answer(
            get_text("max_points_reached", lang, max_points=settings.MAX_WAYPOINTS),
            reply_markup=get_clear_route_keyboard(lang),
            parse_mode="HTML",
        )
        return

    # If message has caption, use as initial custom name
    custom_name = message.caption.strip() if message.caption else None

    # Add point to user's active session draft
    await db.add_draft_point(user_id, dest_lat, dest_lon, custom_name=custom_name)

    # Debounce handling: cancel active timer task if another location arrived quickly
    if user_id in user_debounce_tasks and not user_debounce_tasks[user_id].done():
        user_debounce_tasks[user_id].cancel()

    # Schedule calculation in ~1.2s
    task = asyncio.create_task(_debounce_process_user_route(user_id, chat_id, message.bot))
    user_debounce_tasks[user_id] = task


# ---------------------------------------------------------------------------
# Fallback Handler: Any other messages (Text, Photos, Stickers)
# ---------------------------------------------------------------------------


@router.message()
async def handle_fallback_messages(message: Message) -> None:
    """Prompt user to send valid location attachment."""
    user_id = message.from_user.id if message.from_user else 0
    lang = await db.get_user_lang(user_id)
    logger.info("Fallback handler for user %s, text: %s", user_id, message.text)
    await message.answer(get_text("need_location", lang), parse_mode="HTML")
