# 🚗 Telegram-бот с интерактивным Mini App для построения автомобильного маршрута

Готовое к запуску production-ready решение: Telegram-бот на базе **aiogram 3.x** с встроенным **Telegram Mini App** (Leaflet.js + Tailwind CSS) и **FastAPI** бэкендом, который рассчитывает и визуализирует автомобильный маршрут от фиксированной Точки А (управляемой администратором) до любой Точки Б, отправленной пользователем.

---

## 🌟 Ключевой функционал

1. **Мультимаршруты (A → B → C → ...):**
   - Пользователь может отправлять точки назначения по очереди или сразу пересылать несколько геолокаций подряд.
   - **Debounce (~1.2 сек):** бот накапливает пачку отправленных локаций и отвечает одним итоговым сообщением со всей цепочкой.
   - **Автоматическая сортировка точек (Nearest Neighbor / Haversine):**
     - Точка A (заданная админом) всегда остаётся неизменным стартом;
     - Точка B — ближайшая к A;
     - Точка C — следующая ближайшая к B (гарантирует логичный и кратчайший объезд);
     - Точки D, E... — далее по цепочке.
   - **Управление черновиком:** команда `/clear` и кнопка «🗑 Новый маршрут / Очистить» сбрасывают черновик в любой момент. Лимит — до 10 точек, автоочистка неактивных черновиков через 30 минут.
   - **Сохранение по `route_id`:** маршрут кэшируется в SQLite с коротким ID, в Mini App передаётся ссылка вида `?route_id=...&lang=...` без длинных URL и без повторных запросов к OSRM.

2. **Мультиязычность (RU / UZ):**
   - Двуязычный интерфейс: 🇷🇺 Русский и 🇺🇿 O‘zbekcha (латиница).
   - Выбор языка при старте (`/start`), смене (`/lang`) или прямо внутри Mini App.

3. **Интерактивный Telegram Mini App:**
   - Полноэкранная тёмная карта OpenStreetMap с тёмным CSS-фильтром (без API-ключей и водяных знаков).
   - **Разноцветные неоновые отрезки:** каждый участок пути окрашен в свой контрастный цвет (`A → B`: циановый, `B → C`: фиолетовый, `C → D`: изумрудный, `D → E`: янтарный...).
   - **Интерактивный список отрезков:** при клике на конкретный отрезок карта плавно фокусируется на нём.
   - **Вся цепочка в навигаторах:** Яндекс Карты, 2GIS и Google Maps открывают маршрут со всеми промежуточными точками через `openLink`.

4. **Архитектурная чистота и безопасность:**
   - Преобразование порядка координат: OSRM использует `[longitude, latitude]`, а Leaflet — `[latitude, longitude]`. Выделена отдельная чистая функция конвертации.
   - Серверное проксирование запросов к OSRM через FastAPI `/api/route`: исключает CORS-блокировки браузера и централизованно обрабатывает таймауты.
   - Запуск FastAPI и aiogram в **едином асинхронном процессе** Python с graceful shutdown.

---

## 📁 Структура проекта

```text
suv-bot/
├── app/
│   ├── __init__.py
│   ├── config.py           # Загрузка и валидация .env (Pydantic Settings)
│   ├── database.py         # Асинхронная БД SQLite (users, settings)
│   ├── locales.py          # Переводы RU / UZ и форматирование времени
│   ├── services/
│   │   ├── __init__.py
│   │   └── routing.py      # Клиент OSRM, конвертация геометрии, расчет дистанции и времени
│   ├── bot/
│   │   ├── __init__.py
│   │   ├── keyboards.py    # Inline и Reply клавиатуры (языки, Mini App, FSM)
│   │   └── handlers.py     # Хендлеры aiogram 3 (/start, /lang, /set_origin, /origin, F.location)
│   └── web/
│       ├── __init__.py
│       ├── server.py       # FastAPI приложение (/api/route, /api/health, раздача static/)
│       └── static/
│           ├── index.html  # Интерфейс Mini App с Tailwind CSS
│           ├── styles.css  # Стили карты, неонового маршрута и bottom sheet
│           └── app.js      # Логика Leaflet, WebApp SDK, RU/UZ, навигаторы
├── main.py                 # Единая точка входа: одновременный запуск FastAPI и aiogram
├── requirements.txt        # Зависимости Python
├── .env.example            # Шаблон конфигурации с комментариями
├── Dockerfile              # Docker-образ для деплоя
├── docker-compose.yml      # Быстрый запуск контейнера
└── README.md
```

---

## 🚀 Пошаговая инструкция по запуску

### Шаг 1. Создание бота в Telegram (@BotFather)

1. Откройте в Telegram диалог с [@BotFather](https://t.me/BotFather).
2. Отправьте команду `/newbot` и следуйте подсказкам:
   - Введите отображаемое имя бота (например, `Маршрут Такси Бот`).
   - Введите username бота (например, `my_route_car_bot`).
3. Скопируйте полученный **HTTP API токен** (вида `1234567890:ABCdef...`).
4. Узнайте свой Telegram ID (например, через бота [@userinfobot](https://t.me/userinfobot) или [@raw_data_bot](https://t.me/raw_data_bot)).

---

### Шаг 2. Настройка конфигурации `.env`

Создайте файл `.env` на основе шаблона `.env.example`:

```bash
cp .env.example .env
```

Заполните переменные в `.env`:

```env
# Токен бота от @BotFather
BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrSTUvwxYZ_example

# Ваш Telegram ID (и ID других админов через запятую)
ADMIN_IDS=123456789

# Публичный HTTPS URL веб-сервера (Mini App).
# Для локальной разработки используйте туннель Cloudflare или ngrok (см. Шаг 4)
WEBAPP_URL=https://your-domain.com

# Дефолтная Точка А (по умолчанию Фархадский базар в Ташкенте)
DEFAULT_ORIGIN_LAT=41.2858
DEFAULT_ORIGIN_LON=69.2036
DEFAULT_ORIGIN_NAME=Фархадский базар (Farhod bozori)

# Порт веб-сервера
SERVER_HOST=0.0.0.0
SERVER_PORT=8000
DB_PATH=data/bot.db
```

---

### Шаг 3. Локальный запуск (Python 3.11+)

1. **Создайте и активируйте виртуальное окружение:**
   - **Linux / macOS:**
     ```bash
     python3 -m venv venv
     source venv/bin/activate
     ```
   - **Windows (PowerShell):**
     ```powershell
     python -m venv venv
     .\venv\Scripts\Activate.ps1
     ```

2. **Установите зависимости:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Запустите приложение:**
   ```bash
   python main.py
   ```

После запуска в консоли отобразится:
```text
[INFO] Initializing database...
[INFO] Default Origin Point A: Фархадский базар (Farhod bozori) (lat: 41.2858, lon: 69.2036)
[INFO] Starting FastAPI WebApp server on http://0.0.0.0:8000
[INFO] Starting Telegram Bot long-polling...
```

---

### Шаг 4. Локальное тестирование Mini App через HTTPS-туннель

Telegram требует, чтобы Mini App открывался строго по безопасному протоколу **HTTPS**. Для тестирования с локального компьютера запустите туннель.

#### Вариант А: Через бесплатный Cloudflare Tunnel (рекомендуется, без регистрации)
1. Установите [cloudflared](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/):
   - Windows: `winget install Cloudflare.cloudflared`
   - macOS: `brew install cloudflared`
   - Linux: `sudo apt install cloudflared`
2. Запустите туннель к порту 8000:
   ```bash
   cloudflared tunnel --url http://localhost:8000
   ```
3. Cloudflare выдаст временный публичный адрес, например:
   `https://random-words-subdomain.trycloudflare.com`
4. Вставьте этот адрес в параметр `WEBAPP_URL` в файле `.env`:
   ```env
   WEBAPP_URL=https://random-words-subdomain.trycloudflare.com
   ```
5. Перезапустите `python main.py`.

#### Вариант Б: Через ngrok
1. Запустите:
   ```bash
   ngrok http 8000
   ```
2. Скопируйте `Forwarding https://...ngrok-free.app` и укажите в `WEBAPP_URL` в `.env`.

---

### Шаг 5. Деплой в интернет

#### Способ 1: Бесплатный деплой на Render.com + UptimeRobot (Рекомендуется)

1. Загрузите проект в свой GitHub-репозиторий (Private или Public).
2. Зарегистрируйтесь на [Render.com](https://render.com) и создайте **New Web Service**:
   - Подключите ваш GitHub репозиторий.
   - **Environment:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python main.py`
   - **Instance Type:** `Free`
3. Во вкладке **Environment Variables** добавьте переменные:
   - `BOT_TOKEN`: ваш токен бота от @BotFather
   - `ADMIN_IDS`: ваш Telegram ID
   - `WEBAPP_URL`: URL вашего сервиса на Render (например, `https://suv-bot.onrender.com`)
   - `DEFAULT_ORIGIN_LAT`: `41.2858`
   - `DEFAULT_ORIGIN_LON`: `69.2036`
   - `DEFAULT_ORIGIN_NAME`: `Фархадский базар (Farhod bozori)`
4. Нажмите **Create Web Service**.
5. **Настройка UptimeRobot (чтобы сервис не засыпал):**
   - Зарегистрируйтесь на [UptimeRobot.com](https://uptimerobot.com) (бесплатно).
   - Нажмите **Add New Monitor**:
     - **Monitor Type:** `HTTP(s)`
     - **Friendly Name:** `Suv Bot KeepAlive`
     - **URL (or IP):** `https://your-service-name.onrender.com/api/health`
     - **Monitoring Interval:** `5 minutes` (или 10 minutes)
   - UptimeRobot будет регулярно опрашивать `/api/health`, поддерживая бота и Mini App активными 24/7 без засыпания!

#### Способ 2: Деплой через Docker & Docker Compose (на VPS)

1. Клонируйте проект на сервер:
   ```bash
   git clone <URL_РЕПОЗИТОРИЯ> /opt/suv-bot
   cd /opt/suv-bot
   ```
2. Создайте и заполните `.env` (укажите реальный `WEBAPP_URL=https://ваш-домен.com`).
3. Запустите контейнер:
   ```bash
   docker compose up -d --build
   ```
4. Проверьте логи:
   ```bash
   docker compose logs -f
   ```

#### Способ 2: Деплой через systemd + Nginx + Certbot (SSL)

1. **Установите Nginx и Certbot:**
   ```bash
   sudo apt update
   sudo apt install -y nginx certbot python3-certbot-nginx
   ```

2. **Настройте конфигурацию Nginx (`/etc/nginx/sites-available/suv-bot`):**
   ```nginx
   server {
       server_name bot.yourdomain.com;

       location / {
           proxy_pass http://127.0.0.1:8000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
       }
   }
   ```
   Активируйте сайт и выпустите SSL-сертификат:
   ```bash
   sudo ln -s /etc/nginx/sites-available/suv-bot /etc/nginx/sites-enabled/
   sudo nginx -t && sudo systemctl reload nginx
   sudo certbot --nginx -d bot.yourdomain.com
   ```

3. **Создайте systemd сервис (`/etc/systemd/system/suv-bot.service`):**
   ```ini
   [Unit]
   Description=Suv Telegram Bot & Mini App
   After=network.target

   [Service]
   Type=simple
   User=root
   WorkingDirectory=/opt/suv-bot
   ExecStart=/opt/suv-bot/venv/bin/python main.py
   Restart=always
   RestartSec=5
   EnvironmentFile=/opt/suv-bot/.env

   [Install]
   WantedBy=multi-user.target
   ```
   Запустите сервис:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable --now suv-bot
   sudo systemctl status suv-bot
   ```

---

## 🛠 Руководство пользователя и команды бота

### Пользовательские действия
- `/start` — начало работы, приветствие и выбор языка (🇷🇺 Русский / 🇺🇿 O‘zbekcha).
- `/lang` — изменение языка интерфейса.
- **Отправка геопозиции:** нажмите 📎 (Скрепка) → **«Геопозиция»** и отправьте текущее местоположение или выберите точку на карте. Бот автоматически построит маршрут и пришлет кнопку Mini App.
- Отправка любого текста вне FSM — бот напомнит прислать именно геопозицию.

### Админские команды (доступны пользователям из `ADMIN_IDS`)
- `/origin` — показывает текущую Точку А (название, координаты в текстовом виде и отправляет интерактивную точку на карте в чат).
- `/set_origin` — запуск FSM смены Точки А:
  1. Бот запрашивает геопозицию новой точки отправления.
  2. Бот запрашивает текстовое название (например, `Главный склад, Юнусабад`) или предлагает кнопку **«⏩ Оставить без названия»**.
  3. Новая точка моментально сохраняется в базу SQLite и становится Точкой А для всех последующих маршрутов.

---

## 🌐 API Эндпоинты бэкенда

- `GET /` — главная страница Telegram Mini App (`index.html`).
- `GET /api/health` — проверка работоспособности сервиса (`{"status": "ok"}`).
- `GET /api/origin` — текущая Точка А (`lat`, `lon`, `name`).
- `GET /api/route?dest_lat=...&dest_lon=...` — расчет автомобильного маршрута от актуальной Точки А до Точки Б. Возвращает:
  - `distance_km` — расстояние в километрах;
  - `duration_min` — время в пути на автомобиле в минутах;
  - `coordinates` — массив пар `[lat, lon]`, готовый для отрисовки полилинии Leaflet.

---

## 📄 Лицензия

Проект распространяется под лицензией MIT.
