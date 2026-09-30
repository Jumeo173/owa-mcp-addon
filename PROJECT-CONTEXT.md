# Контекст проекта: OWA Exchange MCP на Home Assistant

Этот файл — полный контекст для LLM-ассистента, который продолжит работу над проектом. Прочитай его целиком, прежде чем что-то менять.

## Что это за проект

Цифровой секретарь для корпоративного Microsoft Exchange. MCP-сервер отдаёт данные календаря (встречи, участники, организатор) через Model Context Protocol. Подключён к агенту "Секретарь" в Yandex AI Studio.

Работает полностью в Home Assistant (Supervised на Debian ARM64, Armbian). Mac нужен только для периодического обновления cookies.

## Архитектура

    [Yandex AI Studio: агент "Секретарь", модель DeepSeek 4 Flash]
              |
              | HTTPS (SSE)
              v
    [CloudPub Tunnel addon] --> https://XXX.cloudpub.ru
              |
              | HTTP на 172.30.32.1:8765
              v
    [OWA Exchange MCP addon] --HTTPS--> [Exchange OWA mail.lvlmed.ru]

Оба аддона работают в HA, автозапуск через Supervisor (boot: auto).

## Репозитории

- owa-mcp-addon (этот) — https://github.com/Jumeo173/owa-mcp-addon
  Содержит два аддона: owa-mcp/ и cloudpub/
- owa-exchange-mcp (апстрим + патч) — на Mac в ~/owa-exchange-mcp/
  Это fork nhype/owa-exchange-mcp с патчем recurring-fix.

## Структура репозитория owa-mcp-addon

    repository.yaml             # визитка репозитория для HA
    README.md                   # пользовательская документация
    PROJECT-CONTEXT.md          # этот файл
    owa-mcp/                    # аддон MCP-сервера
      config.yaml               # манифест
      Dockerfile                # сборка образа
      run.sh                    # точка входа
      run_http.py               # обёртка SSE + monkey-patch cookies
      owa-exchange-mcp/         # копия апстрима с патчем
    cloudpub/                   # аддон CloudPub-туннеля
      config.yaml
      Dockerfile
      run.sh

## Обязательные внешние файлы (в /app_configs/ в HA)

Папка /app_configs/225c5dff_owa-mcp/:

1. owa-mcp.env — текстовый, ровно две строки без export и кавычек:
       EXCHANGE_OWA_URL=https://mail.lvlmed.ru
       EXCHANGE_MASTER_PASSWORD=<мастер-пароль>

2. session-cookies.txt — зашифрованные cookies (AES-256)
3. .salt — 16 байт, соль для расшифровки cookies
4. .credentials.enc — ~120 байт, зашифрованный email/пароль

Все три бинарных файла (cookies + .salt + .credentials.enc) обязательны.
Без любого из них get_calendar_events вернёт пустой список.

Папка /app_configs/225c5dff_cloudpub/:

1. token — токен cloudpub.ru (одна строка)

## Как это работает

### run_http.py — обёртка MCP

Три ключевые роли:

1. Меняет транспорт stdio -> SSE (для AI Studio)
2. Отключает DNS-rebinding защиту, добавляет CloudPub URL в allowed_hosts
3. Monkey-patch OWAClient._load_cookies:
   - Расшифровывает cookies через decrypt_cookie_file(MASTER_PASSWORD, ...)
   - Загружает их через load_cookies_from_string
   - Извлекает user_email через decrypt_credentials(MASTER_PASSWORD)
   - Устанавливает self.user_email (без него get_calendar_events возвращает пустой список)

### Ограничения OWA JSON API (важно!)

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

## Что уже сделано (v0.1.8)

- Полностью работающий стенд в HA
- Recurring-встречи корректно отдают участников, организатора, body
- Одиночные встречи работают
- Автозапуск через Supervisor
- CloudPub-туннель в HA (URL меняется при переустановке аддона)
- Документация в README.md
- Патч recurring-fix в owa-exchange-mcp/exchange_mcp/tools/calendar.py

## Правила работы (важно!)

### 1. Никогда не использовать print() в calendar.py

stdout занят MCP-протоколом. Любой print ломает JSON-RPC.
Для отладки — только print(..., file=sys.stderr, flush=True).

### 2. Не редактировать Python через TextEdit

TextEdit ломает отступы, склеивает строки, ломает while True.
Использовать cat > file.py << 'EOF' или скрипты.

### 3. Heredoc-маркеры должны быть уникальными

При записи файлов через heredoc (cat > file << 'END') следить, чтобы END не встречалось в содержимом. Иначе heredoc оборвётся рано.

### 4. Shell zsh не интерпретирует # в интерактиве

При копировании многострочных блоков с # в zsh — ошибки типа
command not found: #. Оборачивать в bash << 'EOF' ... EOF или запускать через сохранённый скрипт.

### 5. Патч всегда пересоздавать после правок calendar.py

    cd ~/owa-exchange-mcp
    git show HEAD:exchange_mcp/tools/calendar.py > /tmp/calendar_orig.py
    diff -u /tmp/calendar_orig.py exchange_mcp/tools/calendar.py > ~/owa-mcp-addon/patches/recurring-fix.patch

### 6. Секреты в git не публиковать

.gitignore включает env, .env, logs/, session-cookies.txt, .venv/, __pycache__/, .salt, .credentials.enc, *.bak.
Перед push проверять:

    git status --short
    git ls-files | grep -E "env|salt|credential|cookie|venv|session"

### 7. Версия аддона — бампить при каждой правке

owa-mcp/config.yaml содержит version: "X.Y.Z".
При изменении Dockerfile, run.sh, run_http.py или кода — поднять версию, иначе HA не увидит обновление.

## Известные технические решения (грабли HA Supervised + Armbian)

### Supervisor не создаёт /var/log/journal

Advanced SSH & Web Terminal не запускается с ошибкой
bind source path does not exist: /var/log/journal.
Мы не используем Advanced SSH — работаем через core-ssh.

### bashio::addon.slug не существует

В run.sh нельзя использовать $(bashio::addon.slug).
Использовать ADDON_CONFIG="/config" — папка монтируется туда автоматически.

### ARG BUILD_FROM может не подставиться

Supervisor иногда не передаёт BUILD_FROM в Dockerfile.
Решение — явно:

    FROM ghcr.io/home-assistant/aarch64-base:latest

### MCP SDK 2.x ломает FastMCP

Версия mcp >= 2.0.0 переименовала mcp.server.fastmcp -> mcp.server.mcpserver.
Пин в pyproject.toml:

    "mcp>=1.0.0,<2.0.0",

### Chromium на ARM64 — тяжёлый и хрупкий

В Dockerfile не ставим chromium. Он нужен только для login.py
(получение cookies), а cookies переносятся с Mac вручную.

### venv внутри контейнера — эфемерный

При каждом запуске аддона .venv создаётся заново, pip install -e . занимает 2-5 минут. Это нормально для HA-аддона.
Можно вынести в /config/.venv, но пока не сделано.

## Roadmap

1. Автообновление cookies — LaunchAgent на Mac раз в N часов заходит в OWA, копирует три файла в HA через SCP, перезапускает MCP-аддон
2. Telegram-фронт — бот через Yandex AI Studio Responses API
3. Monthly/Yearly recurrence — формулы в _compute_instance_index
4. Кеш мастер-серий в OWAClient (TTL 5-10 минут)
5. Дополнительные поля в get_calendar_events (attachments, importance, categories)
6. Секреты в macOS Keychain — вместо ~/.config/owa-mcp/env
7. GHCR-образ — автосборка через GitHub Actions, image: в config.yaml вместо локальной сборки

## Как продолжить работу

### Первый запуск в новом чате с LLM

Скопируй этот файл целиком и добавь в начало диалога. LLM прочитает контекст и сможет продолжить без пересказа.

### Склонировать репозиторий на новом Mac

    git clone git@github-jumeo:Jumeo173/owa-mcp-addon.git

### Проверить, что всё работает

1. Открыть AI Studio -> агент "Секретарь" -> новый чат
2. Написать: "Покажи мои встречи на эту неделю"
3. Ожидать список событий с участниками, организатором

Если пусто — смотреть Журнал аддона OWA Exchange MCP:
- [startup] _patched: decrypted OK, len=... — cookies расшифровались
- [startup] _patched: user_email=... — email установлен
- Если нет user_email — проблема с .credentials.enc
- Если decrypt returned EMPTY/None — проблема с .salt или паролем

### Часто задаваемые вопросы

Где URL CloudPub?
В Журнале аддона CloudPub Tunnel:
    Сервис опубликован: http://172.30.32.1:8765 -> https://XXX.cloudpub.ru:443

Как обновить cookies?
На Mac: cd ~/owa-exchange-mcp && python login.py
Скопировать три файла (.salt, .credentials.enc, session-cookies.txt) в /app_configs/225c5dff_owa-mcp/.
Перезапустить аддон OWA Exchange MCP.

Что делать, если recurring-встречи отдают пустых участников?
Проверить, применён ли патч:

    cd ~/owa-exchange-mcp
    git apply --check ~/owa-mcp-addon/patches/recurring-fix.patch

Аддон долго собирается при обновлении.
Это нормально. Первая сборка ~5-15 мин. Перезапуск без изменений — мгновенный.

## Полезные команды

### На Mac

    cd ~/owa-mcp-addon
    git pull                               # подтянуть последнее из репо
    git status --short                     # проверить, что нет секретов
    git log --oneline -10                  # последние коммиты

### В HA через core-ssh

    ha addons list | grep -iE "owa|cloud"  # список аддонов
    ha addons info 225c5dff_owa-mcp        # детали
    ha addons logs 225c5dff_owa-mcp        # логи
    ha store reload                        # перечитать репозитории

### Проверить, что MCP работает

    curl -sI http://172.30.32.1:8765/sse   # должен вернуть 200 или 400

## Контакты и ключевые пути

- GitHub: https://github.com/Jumeo173/owa-mcp-addon
- HA: 192.168.31.194 (HA Supervised на Armbian aarch64)
- OWA: https://mail.lvlmed.ru
- Мастер-пароль: в /app_configs/225c5dff_owa-mcp/owa-mcp.env
- CloudPub токен: в /app_configs/225c5dff_cloudpub/token
- Mac: ykashkarov@MacBook-Pro, ~/owa-exchange-mcp (апстрим + патч)
