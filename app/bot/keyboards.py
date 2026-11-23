from typing import Any, List, Optional
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    WebAppInfo,
)
from app.locales import get_text


def get_lang_inline_keyboard() -> InlineKeyboardMarkup:
    """Inline keyboard for choosing interface language (RU / UZ)."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🇷🇺 Русский", callback_data="set_lang:ru"),
                InlineKeyboardButton(text="🇺🇿 O‘zbekcha", callback_data="set_lang:uz"),
            ]
        ]
    )


def get_multi_route_keyboard(
    webapp_url: str,
    points_count: int,
    lang: str = "ru",
    point_b_id: Any = None,
) -> InlineKeyboardMarkup:
    """
    Inline keyboard containing:
    1. WebAppInfo button to view multi-stop interactive route
    2. Button to rename waypoints (single or menu)
    3. Button to clear current draft and start new route
    """
    button_text = get_text("btn_open_webapp", lang, points_count=points_count)
    clear_text = get_text("btn_clear_route", lang)

    keyboard_rows = [
        [
            InlineKeyboardButton(
                text=button_text,
                web_app=WebAppInfo(url=webapp_url),
            )
        ]
    ]

    # Add Rename button
    if points_count == 2:
        rename_label = get_text("btn_rename_single", lang)
        cb_data = f"rename_pt_id:{point_b_id}" if point_b_id is not None else "rename_pt_idx:0"
        keyboard_rows.append([InlineKeyboardButton(text=rename_label, callback_data=cb_data)])
    elif points_count > 2:
        rename_label = get_text("btn_rename_points", lang)
        keyboard_rows.append([InlineKeyboardButton(text=rename_label, callback_data="rename_points_menu")])

    keyboard_rows.append([
        InlineKeyboardButton(
            text=clear_text,
            callback_data="clear_route",
        )
    ])

    return InlineKeyboardMarkup(inline_keyboard=keyboard_rows)


def get_rename_points_keyboard(
    dest_points: list,
    lang: str = "ru",
) -> InlineKeyboardMarkup:
    """
    Inline keyboard listing each destination waypoint to allow user to pick and rename it.
    """
    keyboard_rows = []
    for idx, pt in enumerate(dest_points):
        label = pt.get("label", f"#{idx + 1}")
        c_name = pt.get("custom_name")
        addr = pt.get("address") or pt.get("name") or ""
        short_addr = (c_name or addr)[:20] if (c_name or addr) else f"Точка {label}"
        btn_text = f"✏️ {label}: {short_addr}"
        pt_id = pt.get("id")
        cb_data = f"rename_pt_id:{pt_id}" if pt_id is not None else f"rename_pt_idx:{idx}"
        keyboard_rows.append([InlineKeyboardButton(text=btn_text, callback_data=cb_data)])

    keyboard_rows.append([
        InlineKeyboardButton(
            text=get_text("btn_back_to_route", lang),
            callback_data="back_to_route",
        )
    ])
    return InlineKeyboardMarkup(inline_keyboard=keyboard_rows)


def get_cancel_rename_keyboard(
    point_id: Any,
    lang: str = "ru",
    has_custom_name: bool = False,
) -> InlineKeyboardMarkup:
    """Inline keyboard for cancelling point rename or resetting custom name."""
    rows = []
    if has_custom_name and point_id is not None:
        rows.append([
            InlineKeyboardButton(
                text=get_text("btn_reset_name", lang),
                callback_data=f"reset_pt_name:{point_id}",
            )
        ])
    rows.append([
        InlineKeyboardButton(
            text=get_text("btn_cancel", lang),
            callback_data="cancel_rename",
        )
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_clear_route_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    """Inline keyboard with Clear Route button."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=get_text("btn_clear_route", lang),
                    callback_data="clear_route",
                )
            ]
        ]
    )


def get_route_webapp_keyboard(
    webapp_url: str,
    lang: str = "ru",
    points_count: int = 1,
) -> InlineKeyboardMarkup:
    """Backwards-compatible helper: route button + clear button."""
    return get_multi_route_keyboard(webapp_url, points_count, lang)


def get_cancel_inline_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    """Inline keyboard with Cancel button for FSM flows."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=get_text("btn_cancel", lang),
                    callback_data="cancel_fsm",
                )
            ]
        ]
    )


def get_name_step_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    """Inline keyboard for Origin name step: Skip or Cancel."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=get_text("btn_skip_name", lang),
                    callback_data="skip_origin_name",
                )
            ],
            [
                InlineKeyboardButton(
                    text=get_text("btn_cancel", lang),
                    callback_data="cancel_fsm",
                )
            ],
        ]
    )


def get_location_request_reply_keyboard(lang: str = "ru") -> ReplyKeyboardMarkup:
    """Convenient reply button to send current location via Telegram."""
    btn_text = "📍 Отправить геопозицию" if lang == "ru" else "📍 Geopozitsiyani yuborish"
    cancel_text = get_text("btn_cancel", lang)
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=btn_text, request_location=True)],
            [KeyboardButton(text=cancel_text)],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
