# OWA Exchange MCP — Home Assistant Add-ons

## Возможности агента «Секретарь»

### Календарь
- Показ встреч за период (одиночные и recurring)
- Создание, перенос, отмена встреч
- Поиск свободного времени (своё и общее с коллегами)
- Поиск сотрудников в AD
- Ссылки и вложения из встреч

### Почта
- Непрочитанные письма за период
- Полный текст письма (body в plain text)
- Ссылки из HTML-тела
- Список папок
- Дайджест / протокол по письмам от адресата

### Связь почты и календаря
- Письма от участников встречи
- Создание события из тела письма-приглашения

### Запрещено (на уровне инструкции агенту)
- Отправка / ответ / пересылка писем
- Удаление / перемещение писем
- Пометка прочитанным без явной просьбы

Инструкция агента живёт в Yandex AI Studio.
MCP-сервер отдаёт сырые данные; фильтрация и матчинг — на LLM.


Цифровой секретарь для корпоративного Exchange через MCP-протокол.
Подключён к агенту "Секретарь" в Yandex AI Studio (включая Telegram-канал).
Работает полностью в Home Assistant. Mac не нужен.

## Архитектура

    [AI Studio] --HTTPS--> [CloudPub Tunnel] --HTTP--> [OWA MCP] --> [Exchange]
                                                          |
                                                          v
                                                  [Browserless Chromium]

Три аддона работают в HA, автозапуск через Supervisor.

## ОБЯЗАТЕЛЬНЫЕ АДДОНЫ

Для работы нужно ТРИ аддона:

### 1. OWA Exchange MCP (из этого репозитория)
Мозг системы. Отдаёт календарь через MCP.

### 2. CloudPub Tunnel (из этого репозитория)
Публичный HTTPS-туннель к MCP-серверу.
Требует токен CloudPub в Configuration.

### 3. Browserless Chromium (ВНЕШНИЙ)
Источник: https://github.com/alexbelgium/hassio-addons
Слот: db21ed7f_browserless-chrome
Нужен для авто-логина в OWA (когда cookies протухают).
Без него MCP не сможет войти в Exchange автоматически.

## Установка

### Шаг 1. Установить browserless_chrome

1. Настройки -> Дополнения -> Магазин -> три точки -> Репозитории
2. Добавить: https://github.com/alexbelgium/hassio-addons
3. Найти Browserless Chromium -> Установить -> Запустить
4. Узнать IP:
   core-ssh: `nslookup db21ed7f-browserless-chrome`
   Запомнить IP (например 172.30.33.8)

### Шаг 2. Установить наш репозиторий

1. Репозитории -> добавить: https://github.com/Jumeo173/owa-mcp-addon
2. Установить OWA Exchange MCP
3. Установить CloudPub Tunnel

### Шаг 3. Настроить OWA Exchange MCP

Открыть Configuration, заполнить:
- exchange_owa_url: https://mail.lvlmed.ru
- exchange_master_password: <мастер-пароль для AES-256>
- exchange_email: <email>
- exchange_password: <пароль от OWA>
- browserless_ws: ws://172.30.33.8:3000 (подставить IP из шага 1)
- log_level: info

Сохранить, запустить. Первый запуск долгий (сборка образа + venv).

### Шаг 4. Настроить CloudPub Tunnel

Configuration: вставить токен CloudPub (получить в аккаунте cloudpub.ru).
Запустить, скопировать URL из Журнала.
Обновить URL в AI Studio (Agent Atelier -> MCP-серверы -> exchange-calendar).

## Как это работает

### Авто-логин (browserless)

Cookies OWA живут ограниченное время. Когда протухают:
1. run.sh видит, что cookies не расшифровываются
2. Запускает login.py
3. login.py подключается к Chromium в browserless по CDP
4. Открывает OWA, вводит email/password из env
5. Сохраняет свежие cookies в /data/
6. MCP перезапускается и работает дальше

**Всё автоматически, без Mac и без человека.**

### Секреты

Все секреты (пароли, токены) — в Configuration аддонов.
Хранятся в /data/options.json — приватная папка, не видна в File editor
и Samba.

Cookies, .salt, .credentials.enc — в /data/ контейнера, тоже не видны.

## Диагностика

### Агент возвращает пустой список встреч

Журнал OWA Exchange MCP. Должны быть:
- [startup] _patched: decrypted OK
- [startup] _patched: user_email=<email>

Если нет user_email — проблема с .credentials.enc.
Если "Credentials not decryptable" — мастер-пароль не тот.
Если "getaddrinfo ENOTFOUND" — неверный IP browserless.

### CloudPub URL не отвечает

Журнал CloudPub-аддона. Если URL сменился — обновить в AI Studio.
Если "Token not found" — не заполнено поле token в Configuration.

### Аддон долго собирается

Первая сборка 5-10 минут (Debian + playwright). Перезапуск без изменений —
мгновенный.

## Прочее

Полный технический контекст — в PROJECT-CONTEXT.md.

## Лицензия

MIT
