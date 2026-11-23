from typing import Any, Dict, List


MESSAGES: Dict[str, Dict[str, str]] = {
    "ru": {
        "welcome": (
            "👋 <b>Добро пожаловать!</b>\n\n"
            "Я помогу вам построить автомобильный маршрут от нашей точки отправления до ваших локаций.\n\n"
            "📍 <b>Поддерживаются мультимаршруты (A → B → C → ...):</b>\n"
            "Вы можете отправить как одну точку, так и сразу несколько геопозиций подряд или пересылкой — "
            "бот автоматически упорядочит их по оптимальному пути!\n\n"
            "Пожалуйста, выберите удобный язык интерфейса:"
        ),
        "choose_lang": "🌐 Пожалуйста, выберите язык интерфейса:",
        "lang_selected": (
            "✅ Выбран русский язык.\n\n"
            "📍 <b>Как проложить маршрут:</b>\n"
            "Нажмите на скрепку 📎 внизу, выберите <b>«Геопозиция»</b> и отправьте точку назначения.\n\n"
            "💡 <i>Вы можете отправить сразу несколько точек подряд или переслать несколько геолокаций "
            "— бот объединит их в единый цепочечный маршрут (A → B → C...)!</i>"
        ),
        "route_ready_single": (
            "🚗 <b>Маршрут построен!</b>\n\n"
            "📍 <b>Точки маршрута:</b>\n"
            "🅰️ <b>Старт:</b> {addr_a}\n"
            "🅱️ <b>Финиш:</b> {addr_b}\n\n"
            "📏 <b>Расстояние:</b> ~{distance_km:.1f} км\n"
            "⏱ <b>Время в пути:</b> ~{duration_str}\n\n"
            "💡 <i>Отправьте ещё локацию, чтобы добавить точку C, или начните заново:</i>"
        ),
        "route_ready_multi": (
            "🚗 <b>Маршрут построен! ({points_count} точек)</b>\n\n"
            "📍 <b>Точки маршрута:</b>\n{points_text}\n\n"
            "📋 <b>Отрезки пути:</b>\n{legs_text}\n\n"
            "🏁 <b>Итого:</b> ~{total_distance_km:.1f} км • ~{total_duration_str}\n\n"
            "💡 <i>Отправьте ещё точку для добавления в цепочку или очистите маршрут:</i>"
        ),
        "btn_open_webapp": "🗺 Открыть маршрут на карте ({points_count} т.)",
        "btn_clear_route": "🗑 Новый маршрут / Очистить",
        "route_cleared": (
            "🗑 <b>Черновик маршрута очищен!</b>\n\n"
            "Отправьте новые геопозиции (через скрепку 📎), чтобы построить свежий маршрут."
        ),
        "route_already_empty": "ℹ️ Черновик маршрута уже пуст. Отправьте геопозицию, чтобы начать.",
        "max_points_reached": (
            "⚠️ <b>Достигнут лимит точек маршрута!</b> (максимум {max_points} точек).\n"
            "Пожалуйста, очистите маршрут по кнопке ниже или командой /clear, чтобы начать заново."
        ),
        "route_error": (
            "⚠️ Не удалось построить автомобильный маршрут между точками.\n"
            "Возможно, поблизости нет проезжих дорог или сервис маршрутизации временно недоступен.\n"
            "Попробуйте отправить точку ближе к автомобильной дороге."
        ),
        "origin_not_set": "⚠️ Исходная точка (Точка А) ещё не настроена. Пожалуйста, обратитесь к администратору.",
        "need_location": (
            "ℹ️ Пожалуйста, отправьте геопозицию через меню вложений Telegram.\n\n"
            "Нажмите 📎 (Скрепка) → <b>«Геопозиция»</b> и отправьте одну или несколько точек."
        ),
        "access_denied": "⛔️ У вас нет прав администратора для выполнения этой команды.",
        "current_origin": (
            "📍 <b>Текущая Точка А (исходная):</b>\n\n"
            "🏷 <b>Название:</b> {name}\n"
            "🌐 <b>Координаты:</b> <code>{lat:.6f}, {lon:.6f}</code>"
        ),
        "set_origin_step1": (
            "📍 <b>Настройка Точки А (Старт)</b>\n\n"
            "Пожалуйста, отправьте геопозицию новой точки отправления через меню вложений (📎 → Геопозиция)."
        ),
        "set_origin_step2": (
            "📍 Координаты получены: <code>{lat:.6f}, {lon:.6f}</code>\n\n"
            "Теперь введите название для этой точки (например: <i>Главный склад, Юнусабад</i>) или нажмите кнопку ниже, чтобы оставить без названия."
        ),
        "set_origin_success": (
            "✅ Точка А успешно сохранена!\n\n"
            "🏷 <b>Название:</b> {name}\n"
            "🌐 <b>Координаты:</b> <code>{lat:.6f}, {lon:.6f}</code>"
        ),
        "btn_skip_name": "⏩ Оставить без названия",
        "btn_cancel": "❌ Отмена",
        "action_cancelled": "Действие отменено.",
        "btn_lang_ru": "🇷🇺 Русский",
        "btn_lang_uz": "🇺🇿 O‘zbekcha",
        "btn_rename_points": "✏️ Назвать точки",
        "btn_rename_single": "✏️ Назвать точку B",
        "choose_point_to_rename": "✏️ <b>Выберите точку, чтобы задать или изменить её название:</b>",
        "enter_point_name_prompt": (
            "✏️ <b>Точка {label}</b>\n"
            "📍 Адрес: <i>{address}</i>\n"
            "{current_name_info}\n"
            "Введите понятное название для этой точки (например: <i>Клиент Алишер</i> или <i>Склад №3</i>):"
        ),
        "current_custom_name": "🏷 Текущее название: <b>{name}</b>\n",
        "point_renamed_success": "✅ <b>Название для Точки {label} сохранено:</b> «{name}»",
        "point_name_reset_success": "🔄 Название для Точки {label} сброшено.",
        "btn_reset_name": "🔄 Сбросить название",
        "btn_back_to_route": "🔙 Назад к маршруту",
        "no_active_route_to_rename": "ℹ️ Нет активных точек для переименования. Пожалуйста, отправьте геопозицию.",
    },
    "uz": {
        "welcome": (
            "👋 <b>Xush kelibsiz!</b>\n\n"
            "Men sizga jo'nash manzilimizdan sizning nuqtalaringizgacha bo'lgan avtomobil marshrutini hisoblash va ko'rsatishda yordam beraman.\n\n"
            "📍 <b>Ko'p nuqtali marshrutlar (A → B → C → ...):</b>\n"
            "Siz bitta yoki ketma-ket bir nechta geopozitsiyalarni yuborishingiz mumkin — "
            "bot ularni optimal tartibda avtomatik birlashtiradi!\n\n"
            "Iltimos, o'zingizga qulay interfeys tilini tanlang:"
        ),
        "choose_lang": "🌐 Iltimos, interfeys tilini tanlang:",
        "lang_selected": (
            "✅ O‘zbek tili (lotin) tanlandi.\n\n"
            "📍 <b>Marshrut tuzish uchun:</b>\n"
            "Pastdagi qisqich 📎 belgisini bosing, <b>«Geopozitsiya»</b> (Joylashuv) bo'limini tanlang va manzilni yuboring.\n\n"
            "💡 <i>Bir nechta nuqtalarni ketma-ket yuborishingiz mumkin — bot ularni yagona zanjirli "
            "marshrutga (A → B → C...) birlashtiradi!</i>"
        ),
        "route_ready_single": (
            "🚗 <b>Marshrut tayyor!</b>\n\n"
            "📍 <b>Marshrut nuqtalari:</b>\n"
            "🅰️ <b>Boshlanish:</b> {addr_a}\n"
            "🅱️ <b>Manzil:</b> {addr_b}\n\n"
            "📏 <b>Masofa:</b> ~{distance_km:.1f} km\n"
            "⏱ <b>Yo'l vaqti:</b> ~{duration_str}\n\n"
            "💡 <i>C nuqtasini qo'shish uchun yana manzil yuboring yoki yangidan boshlang:</i>"
        ),
        "route_ready_multi": (
            "🚗 <b>Marshrut tayyor! ({points_count} ta nuqta)</b>\n\n"
            "📍 <b>Marshrut nuqtalari:</b>\n{points_text}\n\n"
            "📋 <b>Yo'l qismlari:</b>\n{legs_text}\n\n"
            "🏁 <b>Jami:</b> ~{total_distance_km:.1f} km • ~{total_duration_str}\n\n"
            "💡 <i>Yana nuqta qo'shish uchun manzil yuboring yoki marshrutni tozalang:</i>"
        ),
        "btn_open_webapp": "🗺 Xaritada marshrutni ochish ({points_count} ta)",
        "btn_clear_route": "🗑 Yangi marshrut / Tozalash",
        "route_cleared": (
            "🗑 <b>Marshrut qoralamasi tozalandi!</b>\n\n"
            "Yangi marshrut tuzish uchun geopozitsiyalarni yuboring (📎 qisqich orqali)."
        ),
        "route_already_empty": "ℹ️ Marshrut qoralamasi allaqachon bo'sh. Boshlash uchun geopozitsiyani yuboring.",
        "max_points_reached": (
            "⚠️ <b>Marshrut nuqtalari chegarasiga yetildi!</b> (maksimal {max_points} ta nuqta).\n"
            "Yangidan boshlash uchun quyidagi tugmani bosing yoki /clear buyrug'idan foydalaning."
        ),
        "route_error": (
            "⚠️ Nuqtalar orasida avtomobil marshrutini tuzib bo'lmadi.\n"
            "Ehtimol, yaqin atrofda avtomobil yo'li mavjud emas yoki yo'nalish xizmati vaqtincha band.\n"
            "Avtomobil yo'liga yaqinroq nuqtani yuborishga urinib ko'ring."
        ),
        "origin_not_set": "⚠️ Boshlang'ich nuqta (A nuqta) hali sozlanmagan. Iltimos, administratorga murojaat qiling.",
        "need_location": (
            "ℹ️ Iltimos, Telegram biriktirmalari (clip) orqali geopozitsiyangizni yuboring.\n\n"
            "Pastdagi 📎 (Qisqich) belgisini bosing → <b>«Geopozitsiya»</b>ni tanlang va bir yoki bir nechta nuqtalarni yuboring."
        ),
        "access_denied": "⛔️ Ushbu buyruqni bajarish uchun sizda administrator huquqi yo'q.",
        "current_origin": (
            "📍 <b>Joriy A Nuqtasi (boshlang'ich):</b>\n\n"
            "🏷 <b>Nomi:</b> {name}\n"
            "🌐 <b>Koordinatalar:</b> <code>{lat:.6f}, {lon:.6f}</code>"
        ),
        "set_origin_step1": (
            "📍 <b>A Nuqtasini (Boshlang'ich) o'rnatish</b>\n\n"
            "Iltimos, yangi jo'nash manzilining geopozitsiyasini yuboring (📎 → Geopozitsiya orqali)."
        ),
        "set_origin_step2": (
            "📍 Koordinatalar qabul qilindi: <code>{lat:.6f}, {lon:.6f}</code>\n\n"
            "Endi ushbu nuqta uchun nom kiriting (masalan: <i>Mizu, Bosh ombor</i>) yoki nomsiz qoldirish uchun quyidagi tugmani bosing."
        ),
        "set_origin_success": (
            "✅ A Nuqtasi muvaffaqiyatli saqlandi!\n\n"
            "🏷 <b>Nomi:</b> {name}\n"
            "🌐 <b>Koordinatalar:</b> <code>{lat:.6f}, {lon:.6f}</code>"
        ),
        "btn_skip_name": "⏩ Nomsiz qoldirish",
        "btn_cancel": "❌ Bekor qilish",
        "action_cancelled": "Amal bekor qilindi.",
        "btn_lang_ru": "🇷🇺 Русский",
        "btn_lang_uz": "🇺🇿 O‘zbekcha",
        "btn_rename_points": "✏️ Nuqtalarni nomlash",
        "btn_rename_single": "✏️ B nuqtasini nomlash",
        "choose_point_to_rename": "✏️ <b>Nom berish yoki o'zgartirish uchun nuqtani tanlang:</b>",
        "enter_point_name_prompt": (
            "✏️ <b>{label} Nuqtasi</b>\n"
            "📍 Manzil: <i>{address}</i>\n"
            "{current_name_info}\n"
            "Ushbu nuqta uchun nom kiriting (masalan: <i>Alisher mijoz</i> yoki <i>3-ombor</i>):"
        ),
        "current_custom_name": "🏷 Joriy nom: <b>{name}</b>\n",
        "point_renamed_success": "✅ <b>{label} Nuqtasi uchun nom saqlandi:</b> «{name}»",
        "point_name_reset_success": "🔄 {label} Nuqtasi nomi bekor qilindi.",
        "btn_reset_name": "🔄 Nomni bekor qilish",
        "btn_back_to_route": "🔙 Marshrutga qaytish",
        "no_active_route_to_rename": "ℹ️ Nomlash uchun faol nuqtalar yo'q. Iltimos, avval geopozitsiyani yuboring.",
    },
}


def get_text(key: str, lang: str = "ru", **kwargs: Any) -> str:
    """Get localized text by key and language with optional string formatting."""
    lang_dict = MESSAGES.get(lang, MESSAGES["ru"])
    template = lang_dict.get(key, MESSAGES["ru"].get(key, key))
    if kwargs:
        try:
            return template.format(**kwargs)
        except KeyError:
            return template
    return template


def format_duration(minutes: float, lang: str = "ru") -> str:
    """Format duration in minutes into a human-readable string (RU / UZ)."""
    total_mins = max(1, round(minutes))
    hours = total_mins // 60
    mins = total_mins % 60

    if lang == "uz":
        if hours > 0 and mins > 0:
            return f"{hours} s {mins} daq"
        elif hours > 0:
            return f"{hours} soat"
        return f"{mins} daq"
    else:
        if hours > 0 and mins > 0:
            return f"{hours} ч {mins} мин"
        elif hours > 0:
            return f"{hours} ч"
        return f"{mins} мин"
