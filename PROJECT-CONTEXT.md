# Контекст проекта: OWA Exchange MCP на Home Assistant

Этот файл — полный контекст для LLM-ассистента, который продолжит работу
над проектом. Прочитай его целиком, прежде чем что-то менять.

## Что это за проект

Цифровой секретарь для корпоративного Microsoft Exchange.
MCP-сервер отдаёт данные календаря (встречи, участники, организатор) через
Model Context Protocol. Подключён к агенту "Секретарь" в Yandex AI Studio
и к Telegram через AI Studio.

Работает полностью в Home Assistant (Supervised на Debian ARM64, Armbian).
**Mac не нужен** — всё, включая авто-логин в OWA, происходит внутри HA.

## Архитектура

    [Yandex AI Studio: агент "Секретарь" + Telegram-канал]
              |
              | HTTPS (SSE)
              v
    [CloudPub Tunnel addon] --> https://XXX.cloudpub.ru
              |
              | HTTP на 172.30.32.1:8765
              v
    [OWA Exchange MCP addon] --HTTPS--> [Exchange OWA mail.lvlmed.ru]
              |
              | CDP по ws://172.30.33.8:3000
              v
    [Browserless Chromium addon] (alexbelgium/hassio-addons)

Три аддона работают в HA, автозапуск через Supervisor (boot: auto).

## Обязательные аддоны в HA

### 1. OWA Exchange MCP (этот репозиторий)
- Источник: https://github.com/Jumeo173/owa-mcp-addon
- Слот: owa-mcp

### 2. CloudPub Tunnel (этот репозиторий)
- Источник: тот же репозиторий
- Слот: cloudpub
- Требует токен CloudPub в поле "token" (Configuration)

### 3. Browserless Chromium (ВНЕШНИЙ, ОБЯЗАТЕЛЬНЫЙ)
- Источник: https://github.com/alexbelgium/hassio-addons
- Слот: db21ed7f_browserless-chrome
- Используется для авто-логина в OWA через Playwright CDP
- **Без него login.py не сможет войти в OWA, когда cookies протухнут**
- IP-адрес: узнаётся через `nslookup db21ed7f-browserless-chrome`
  в core-ssh. На момент настройки: 172.30.33.8
- IP стабилен между перезапусками, но может измениться при пересоздании
  сети HA. Если login.py падает с ENOTFOUND — проверить IP и обновить
  поле browserless_ws в Configuration OWA Exchange MCP.

## Структура репозитория owa-mcp-addon

    repository.yaml             # визитка репозитория
    README.md                   # пользовательская документация
    PROJECT-CONTEXT.md          # этот файл
    owa-mcp/                    # MCP-аддон
      config.yaml               # манифест + options/schema
      Dockerfile                # Debian base + playwright
      run.sh                    # миграция, авто-setup, авто-логин
      check_secrets.py          # проверка расшифровки credentials/cookies
      run_http.py               # обёртка SSE + monkey-patch
      owa-exchange-mcp/         # копия апстрима с патчем
    cloudpub/                   # CloudPub-аддон
      config.yaml
      Dockerfile
      run.sh

## Секреты — ГДЕ ЛЕЖАТ (важно!)

**Все секреты — в UI аддона (Configuration), хранятся в /data/options.json.**
Файл /data/options.json НЕ виден в File editor и Samba — приватная папка.

Поля в Configuration OWA Exchange MCP:
- exchange_owa_url: "https://mail.lvlmed.ru"
- exchange_master_password: "password" (мастер-пароль для AES-256)
- exchange_email: "email" (ykash@lvlmed.ru)
- exchange_password: "password" (пароль от OWA)
- browserless_ws: "str" (ws://172.30.33.8:3000)
- log_level: "info"

Cookies, .salt, .credentials.enc — генерируются автоматически и лежат в
/data/ контейнера (тоже приватная папка, не видна снаружи).

Старая папка /app_configs/225c5dff_owa-mcp/ (она же /config/ внутри аддона)
больше НЕ ИСПОЛЬЗУЕТСЯ. Legacy-файлы после миграции переименованы в .old.
Их можно удалить через File editor.

## Как это работает

### run_http.py — обёртка MCP

Три ключевые роли:
1. Меняет транспорт stdio -> SSE (для AI Studio)
2. Отключает DNS-rebinding защиту, добавляет CloudPub URL в allowed_hosts
3. Monkey-patch OWAClient._load_cookies:
   - Расшифровывает cookies через decrypt_cookie_file(MASTER_PASSWORD, ...)
   - Загружает их через load_cookies_from_string
   - Извлекает user_email через decrypt_credentials(MASTER_PASSWORD)
   - Устанавливает self.user_email (без него get_calendar_events возвращает [])

### run.sh — оркестратор

При каждом запуске:
1. Читает env из UI (bashio::config)
2. Проверяет, расшифровывается ли .credentials.enc мастер-паролем
   - Если нет — запускает login.py --setup (из env) для пересоздания
3. Проверяет, расшифровываются ли cookies
   - Если нет — запускает login.py через browserless для получения свежих
4. Копирует свежие файлы обратно в /data/
5. Запускает run_http.py

### login.py — авто-логин через browserless

- Подключается к удалённому Chromium по CDP: ws://172.30.33.8:3000
- Открывает OWA, вводит email/password из env
- Ждёт редирект на OWA (2FA не требуется в текущей конфигурации)
- Сохраняет cookies, зашифрованные мастер-паролем
- **НЕ требует интерактивного ввода** — всё через env

## Ограничения OWA JSON API (важно!)

1. Restriction не работает -> OwaSerializationException
2. SortOrder не работает -> 0 items или ошибка
3. IndexedPageItemView без сортировки возвращает одни и те же items
4. FindItem с CalendarView не отдаёт Recurrence у master series
5. CalendarItemType в CalendarView = RecurringMaster для мастер-серий

### Формат данных (грабли)

- DaysOfWeek — строка с пробелами: "Monday Tuesday Wednesday", не список
- StartDate в RecurrenceRange — с TZ: "2017-02-09+03:00", не ISO
- GetItem возвращает Start в UTC (Z), GetUserAvailability — в локальном
- Date vs datetime — сравнение падает, нужен .date()

## Правила работы

### 1. Никогда не использовать print() в calendar.py
stdout занят MCP-протоколом. Для отладки — только file=sys.stderr.

### 2. Не редактировать Python через TextEdit
Ломает отступы. Только cat > file.py << 'EOF' или через Python-скрипты.

### 3. Heredoc-маркеры должны быть уникальными
Внутри Python-скриптов вложенные heredoc ломают парсер.
Использовать отдельные .py-файлы с проверками (check_secrets.py).

### 4. Shell zsh не интерпретирует # в интерактиве
Оборачивать в bash << 'EOF' или запускать через скрипт.
При вставке больших блоков в zsh возможен bracketed paste — использовать
короткие команды или разбивать на несколько скриптов.

### 5. Патч пересоздавать после правок calendar.py
    cd ~/owa-exchange-mcp
    git show HEAD:exchange_mcp/tools/calendar.py > /tmp/calendar_orig.py
    diff -u /tmp/calendar_orig.py exchange_mcp/tools/calendar.py > ~/owa-mcp-addon/patches/recurring-fix.patch

### 6. Секреты в git не публиковать
.gitignore включает env, cookies, .salt, .credentials.enc, *.bak.

### 7. Версия аддона — бампить при каждой правке
В owa-mcp/config.yaml поле version. HA сравнивает его и показывает
кнопку "Обновить" только если версия изменилась.

## Известные технические решения

### Alpine vs Debian
Изначально был ghcr.io/home-assistant/aarch64-base:latest (Alpine).
Playwright не ставится на Alpine ARM64 (нет wheel). Перешли на
ghcr.io/home-assistant/aarch64-base-debian:latest — playwright ставится
с manylinux_2_17_aarch64 wheel.

### Supervisor не создаёт /var/log/journal
Advanced SSH & Web Terminal не запускается. Мы его НЕ используем.

### bashio::addon.slug не существует
Использовать ADDON_CONFIG="/config" — папка монтируется автоматически.

### ARG BUILD_FROM может не подставиться
Решение — явно: FROM ghcr.io/home-assistant/aarch64-base-debian:latest

### MCP SDK 2.x ломает FastMCP
Пин в pyproject.toml: "mcp>=1.0.0,<2.0.0",

### Chromium на ARM64 — тяжёлый и хрупкий
Не ставим chromium в MCP-аддон. Используем внешний browserless_chrome.


### Чек-лист tools в AI Studio (коннектор exchange-calendar)

**Включить (агент должен их видеть):**
- Почта (чтение): get_emails, get_email, get_email_links
- Папки: get_folders
- Календарь (чтение): get_calendar_events, get_event_links
- Люди: find_person
- Аналитика: find_free_time, find_meeting_time, get_meeting_stats, get_meeting_contacts

**Выключить (по техническим причинам):**
- login, check_session — из tools/auth.py. Агент НЕ знает мастер-пароль,
  передаёт None → падает с «Invalid master password» → пересказывает как
  «сессия истекла». Сессия восстанавливается автоматически (см. ниже).
- mark_email_read — только по явной просьбе (в инструкции агента)
- download_attachments, download_event_attachments — пишут в /tmp
  контейнера, путь агенту бесполезен (технический долг, см. Roadmap)
- send_email, reply_email, forward_email — ЗАПРЕЩЕНЫ инструкцией агента
- move_email, delete_email, respond_to_meeting — по инструкции не нужны
- create_meeting, update_meeting, cancel_meeting — на усмотрение
  (если агент только читает — выключить)
- create_folder, rename_folder, empty_folder, delete_folder,
  move_folder — управление папками, агенту не нужно

### Жизненный цикл OWA-сессии (v2.1.0)

**Три независимых состояния**, которые нужно различать:

| Состояние | Что значит | Как проверить | Стоимость |
|---|---|---|---|
| Файл cookies расшифровывается | мастер-пароль совпадает | check_secrets.py cookies | ~50 мс, локально |
| Cookies+creds согласованы | salt+creds+cookies от одного --setup | check_secrets.py creds+cookies | ~100 мс, локально |
| Cookies валидны на OWA | серверная сессия жива | check_secrets.py session | ~500 мс, по сети |

**Раньше** проверялось только ПЕРВОЕ — cookies расшифровываются мастер-паролем.
Но OWA-сессия на СЕРВЕРЕ живёт своей жизнью: она истекает (HTTP 440)
НЕЗАВИСИМО от того, что файл cookies на диске ещё расшифровывается.

Отсюда ДВА уровня защиты:

**Уровень 1 — проактивный (run.sh + check_secrets.py session)**
При СТАРТЕ аддона, после копирования cookies в /app/owa-exchange-mcp/,
запускается check_secrets.py session — делает лёгкий GetFolder к OWA.
Если 440 → login.py через browserless → свежие cookies.
Симптом в логе:
  [..] WARNING: OWA session expired (HTTP 440), running login.py
  [..] INFO: Running login.py via browserless...

**Уровень 2 — реактивный (run_http.py патч OWAClient.request)**
Если сессия умрёт В СЕРЕДИНЕ ДНЯ (аддон не перезапускался, проактивный не
сработал), при первом же SessionExpiredError:
  [startup] SessionExpiredError on action=GetItem: ...
  [startup] Running login.py via browserless (reactive re-login)...
  [startup] login.py OK — cookies refreshed
  [startup] retrying action=GetItem with fresh cookies...
Плюс threading.Lock + cooldown 60 сек — параллельные SSE-сессии
не запускают логин одновременно.

**Скрытый баг v1.1.1**: reload_cookies() ставил _loaded=False, но наш
патч _load_cookies смотрит на _cookies_loaded — перезагрузка фактически
не происходила. В v2.1.0 при re-login сбрасываются ОБА флага.

**Антипаттерны (НЕ делать):**
- Проверять только расшифровку cookies — серверная сессия может быть
  мертва, а cookies на диске всё ещё расшифровываются
- Запускать login.py --setup при каждом старте — это ломает salt,
  cookies становятся нерасшифровываемыми, получается цикл
- Патчить OWAClient.request до OWAClient._load_cookies — порядок
  в run_http.py важен: _load_cookies (v1.1.0) → request (v2.1.0)
  → decrypt_* (v1.1.1) → from exchange_mcp.server import mcp

**Диагностика в логе:**
| Строка в логе | Что значит |
|---|---|
| _patched: decrypted OK | cookies расшифровались, мастер-пароль ок |
| WARNING: OWA session expired (HTTP 440) | проактивный: сессия мертва на старте, запускается login |
| OWAClient.request patched: reactive re-login on 440 | реактивный патч загружен |
| SessionExpiredError on action=... | сессия умерла в рантайме, запускается реактивный re-login |
| login cooldown (Ns < 60.0s), skip | параллельная сессия уже логинится, ждём |
| Credentials not decryptable, recreating | БАГ — salt разошёлся, смотреть check_secrets.py |


## Roadmap

### Готово
- MCP-сервер в HA
- CloudPub-туннель в HA
- Telegram через Yandex AI Studio
- Авто-логин через browserless
- Секреты в UI аддона (/data/options.json)
- Авто-пересоздание .credentials.enc из env
- Авто-логин при протухании cookies
- Форсирование MASTER_PASSWORD для decrypt_* (v1.1.1)
- Отключены tools/auth.py в AI Studio (агент не дёргает login-tool)
- check_secrets.py в образе + реальные decrypt_* (v1.1.3)
- venv в образе, старт ~2s вместо ~90s (v2.0.0)
- Legacy-мусор из /config вычищен (v2.0.0)
- Проактивная проверка OWA-сессии при старте (v2.1.0)
- Реактивный re-login на HTTP 440 в рантайме (v2.1.0)

### Приоритет 1 — Работа с почтой (ЗАКРЫТО в v1.1.0)

Все 4 сценария работают без правок кода.

Сценарии:
1. Непрочитанные письма за период — get_emails(unread_only=True)
2. Связь с календарём — агент матчит по email участников
3. Встреча из письма — get_email(item_id) + LLM-парсинг тела
4. Дайджест от адресата — get_emails + get_email пачкой

Tool-ы (в апстриме email.py, регистрируются автоматически через
server.py:49):
- get_emails(folder, limit, offset, include_body, unread_only, ids_only)
- get_email(item_id)
- get_email_links(item_id)
- download_attachments(item_id, target_folder) — пока не используем
- get_folders / check_session (folders.py)
- send_email / reply_email / forward_email — ЗАПРЕЩЕНЫ в инструкции
- mark_email_read / move_email / delete_email — не отмечены в AI Studio

В AI Studio (коннектор exchange-calendar) отмечены:
get_emails, get_email, get_email_links, get_folders.

Архитектурное решение:
email.py НЕ патчим. Заявленные дыры (since/until/from_filter/
conversation_id/internet_message_id) закрываются LLM-фильтрацией
на стороне агента. Restriction в OWA JSON API хрупкий. LLM-фильтрация
надёжнее и работает.

Правило проекта:
> Тяжёлую логику фильтрации/матчинга несёт LLM. MCP-сервер
> отдаёт сырые данные как есть. Патчим Python только там, где
> LLM принципиально не справится (массовые операции, recurrence,
> парсинг бинарных вложений).

Инструкция агента «Секретарь» в AI Studio расширена:
- блок ВОЗМОЖНОСТИ — ПОЧТА
- блок ПРАВИЛА — ПОЧТА (запреты send/reply/forward/delete/move,
  mark_email_read только по явной просьбе)
- блок СВЯЗЬ ПОЧТА ↔ КАЛЕНДАРЬ (сценарии 2 и 3)
- формат ответа для писем и дайджеста

Известный технический долг (отложено):
- health-route / → 200 в run_http.py: FastMCP.run(transport="sse")
  не даёт API для доп. маршрутов. Сейчас CloudPub живёт с GET / 404 —
  не критично.
- download_attachments пишет в /tmp контейнера — путь агенту
  бесполезен, нужен tool с base64/text содержимым.
- флаги OWA_DISABLE_SEND для send/reply/forward (сейчас только
  запрет в инструкции).

### Приоритет 2 — Удаление событий календаря
В апстриме НЕТ удаления. Добавить delete_calendar_event со scope:
- single — одно вхождение
- thisAndFollowing — это и будущие
- allInSeries — вся серия
Использовать DeleteItem, RecurringMasterItemId, OccurrenceItemId.
Инфраструктура уже есть в патче recurring-fix.

### Приоритет 3 — Долгосрочное
- Monthly/Yearly recurrence
- Кеш мастер-серий в OWAClient
- Доп. поля в get_calendar_events (attachments, importance, categories)
- GHCR-образ (автосборка через GitHub Actions)

## Как продолжить работу

### Первый запуск в новом чате с LLM
Скопируй этот файл целиком и добавь в начало диалога.

### Проверить, что всё работает
1. AI Studio -> агент "Секретарь" -> новый чат
2. "Покажи мои встречи на этой неделе"
3. Ожидать список событий

Если пусто — смотреть Журнал аддона OWA Exchange MCP:
- [startup] _patched: decrypted OK — cookies расшифровались
- [startup] _patched: user_email=... — email установлен
- Если "Credentials not decryptable" — проблема с .credentials.enc
- Если "getaddrinfo ENOTFOUND" — неверный IP browserless в Configuration

### Часто задаваемые вопросы

**Где URL CloudPub?**
Журнал CloudPub-аддона: "Сервис опубликован: ... -> https://XXX.cloudpub.ru:443"

**Что делать, если cookies протухли?**
Ничего. run.sh автоматически запустит login.py через browserless.
Главное — чтобы browserless_chrome был запущен и IP в Configuration совпадал.

**Что делать, если login.py падает с ENOTFOUND?**
1. core-ssh: nslookup db21ed7f-browserless-chrome
2. Обновить поле browserless_ws в Configuration OWA Exchange MCP
3. Перезапустить аддон

**Что делать, если OWA поменяет вёрстку?**
login.py сломается на page.fill('input[name="username"]').
Смотреть Журнал, обновлять селекторы в login.py.

**Как удалить legacy-файлы?**
File editor -> /app_configs/225c5dff_owa-mcp/ -> удалить все .old.
Папка останется как точка монтирования, но будет пустой.

## Ключевые пути

- GitHub: https://github.com/Jumeo173/owa-mcp-addon
- HA: 192.168.31.194 (HA Supervised на Armbian aarch64)
- OWA: https://mail.lvlmed.ru
- Мастер-пароль / OWA email / OWA password: Configuration аддона OWA Exchange MCP
- CloudPub токен: Configuration аддона CloudPub Tunnel
- browserless IP: узнать через `nslookup db21ed7f-browserless-chrome` в core-ssh

## Контакты

Jumeo — github.com/Jumeo173

### check_secrets.py должен попадать в образ (v1.1.3)
`run.sh` вызывает `/app/owa-exchange-mcp/check_secrets.py` для проверки
расшифровки credentials/cookies. Если файла нет в образе — python падает
с exit 2, `run.sh` считает, что расшифровка не удалась, и **при каждом
старте** запускает `login.py --setup`. Это ломает salt: cookies,
зашифрованные старым salt, становятся нерасшифровываемыми. Цикл
повторяется.

**Симптом:** `WARNING: Credentials not decryptable, recreating` +
`Running login.py --setup...` при **каждом** старте аддона.

**Фикс:** `COPY check_secrets.py /app/owa-exchange-mcp/check_secrets.py`
в `Dockerfile` (после `COPY run.sh`). Плюс `check_secrets.py` должен
использовать **реальные** `decrypt_credentials`/`decrypt_cookie_file`
из `login.py`/`exchange_mcp.auth`, а не дублировать PBKDF2 — иначе
проверка разойдётся с реальной расшифровкой.

### venv в образе, а не в run.sh (v2.0.0)
Изначально `run.sh` при **каждом** старте создавал `.venv` и ставил
`mcp`/`playwright` (~90 секунд). Это потому, что `.venv` создаётся в
`/app/owa-exchange-mcp/.venv` — внутри контейнера, а `/app` не
persistent.

**Фикс:** `pip install` перенесён в `Dockerfile`:
```
WORKDIR /app/owa-exchange-mcp
RUN python3 -m venv .venv && .venv/bin/pip install --no-cache-dir -e . && .venv/bin/pip install --no-cache-dir playwright
```
`run.sh` оставляет fallback (на случай если образ собран неправильно),
но он **не должен** срабатывать. Старт сократился с ~90 секунд до ~2.

### Legacy-миграция из /config завершена (v2.0.0)
Блок `Legacy files renamed to .old` в `run.sh` удалён — миграция из
`/config` в `/data` завершена, файлы переименованы. Меньше шума в
логах.

### Реактивный и проактивный re-login на HTTP 440 (v2.1.0)
Upstream `OWAClient.request` делает retry со **теми же** cookies из
файла — это не помогает, если серверная сессия истекла. Cookies
расшифровываются (мастер-пароль тот же), но **отвергаются** OWA
с HTTP 440.

**Два уровня:**
1. **Проактивный** (`check_secrets.py session` + `run.sh`): при
   старте аддона делаем лёгкий `GetFolder` к OWA. Если 440 — сразу
   `login.py` через browserless, ещё до первого запроса агента.
2. **Реактивный** (`run_http.py`): патч `OWAClient.request` — при
   `SessionExpiredError` (после встроенных двух попыток) запускаем
   `login.py`, форсим `_cookies_loaded=False`, `reload_cookies()`,
   retry. Плюс `threading.Lock` + cooldown 60 сек, чтобы
   параллельные SSE-сессии не логинились одновременно.

**Скрытый баг v1.1.1**: `reload_cookies()` ставил `_loaded=False`,
а наш патч `_load_cookies` смотрит на `_cookies_loaded` — перезагрузка
фактически не происходила. В v2.1.0 при re-login сбрасываем оба флага.

### tools/auth.py нельзя давать агенту в AI Studio
В `exchange_mcp/tools/auth.py` есть tool `login`, принимающий
`master_password` как аргумент tool-вызова. Агент не знает мастер-пароль
(он в UI аддона) и передаёт None/пустую строку → `decrypt_credentials`
падает → агент видит `Invalid master password — could not decrypt
credentials` и пересказывает как «сессия истекла, нужен мастер-пароль».

Фикс двойной:
1. В AI Studio, в коннекторе exchange-calendar, снять галочки со всех
   tools из `exchange_mcp/tools/auth.py` (`login` и т.п.). Сессия всё
   равно восстанавливается автоматически: `_patched_load_cookies` в
   run_http.py + `run.sh` с login.py через browserless.
2. В run_http.py пропатчены `exchange_mcp.auth.decrypt_credentials` и
   `decrypt_cookie_file` — форсируют `MASTER_PASSWORD` из env, игнорируя
   аргумент. Импорт в tools/auth.py — function-local (строка 147),
   поэтому патч модуля подхватывается без правок потребителей.
