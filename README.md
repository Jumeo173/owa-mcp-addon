# OWA Exchange MCP — Home Assistant Add-ons

Цифровой секретарь для корпоративного Exchange через MCP-протокол.
Работает полностью в Home Assistant 24/7. Mac не требуется.

## Архитектура

    [AI Studio] --HTTPS--> [CloudPub Tunnel addon] --HTTP--> [OWA Exchange MCP addon] --HTTPS--> [Exchange OWA]

Оба аддона работают на HA Supervised (Debian ARM64), автозапуск через Supervisor.

## Аддоны в репозитории

| Slug | Название | Что делает |
|---|---|---|
| owa-mcp | OWA Exchange MCP | MCP-сервер на порту 8765 (SSE) |
| cloudpub | CloudPub Tunnel | Публикует порт 8765 через cloudpub.ru |

## Установка

1. Home Assistant -> Настройки -> Дополнения -> Магазин
2. Три точки -> Репозитории -> добавить https://github.com/Jumeo173/owa-mcp-addon
3. Установить оба аддона: OWA Exchange MCP, CloudPub Tunnel

## Обязательные файлы конфигурации

После первого запуска аддона OWA Exchange MCP создаётся папка:
/app_configs/225c5dff_owa-mcp/

Туда нужно положить четыре файла.

### 1. owa-mcp.env (текстовый)

Ровно две строки, без export, без кавычек, без пробелов вокруг =:

EXCHANGE_OWA_URL=https://mail.lvlmed.ru
EXCHANGE_MASTER_PASSWORD=<мастер-пароль>

### 2. session-cookies.txt

Зашифрованный файл cookies из OWA. Получается через login.py на Mac.

### 3. .salt (бинарный, 16 байт)

Соль для расшифровки cookies. Лежит на Mac: ~/owa-exchange-mcp/.salt

Без .salt cookies не расшифруются, и get_calendar_events вернёт пустой список.

### 4. .credentials.enc (бинарный, ~120 байт)

Зашифрованный email + пароль от OWA. Лежит на Mac: ~/owa-exchange-mcp/.credentials.enc

Без .credentials.enc не установится user_email, и get_calendar_events вернёт пустой список.

## Обновление cookies

Cookies OWA живут ограниченное время. Когда агент начнёт отвечать
"Cookie file is encrypted. Call the login tool" — пора обновлять.

На Mac:

    cd ~/owa-exchange-mcp
    source .venv/bin/activate
    python login.py

Логин требует 2FA (подтверждение на телефоне).

Скопировать в HA три файла:
- ~/owa-exchange-mcp/session-cookies.txt
- ~/owa-exchange-mcp/.salt
- ~/owa-exchange-mcp/.credentials.enc

Способы переноса:
- File editor -> кнопка "Загрузить файл"
- Samba share (если установлен)
- core-ssh + base64

Важно: копировать все три файла вместе.

После копирования: Настройки -> Дополнения -> OWA Exchange MCP -> Перезапустить.

## CloudPub URL

URL публичного туннеля меняется при каждой переустановке аддона CloudPub Tunnel.

Актуальный URL виден в логе аддона:
Сервис опубликован: http://172.30.32.1:8765 -> https://XXX.cloudpub.ru:443

При смене URL обновить в AI Studio:
1. Agent Atelier -> MCP-серверы -> exchange-calendar
2. URL: https://XXX.cloudpub.ru/sse
3. Сохранить
4. Открыть новый чат с агентом

## Токен CloudPub

Аддон CloudPub Tunnel требует токен от аккаунта cloudpub.ru.
Лежит в: /app_configs/225c5dff_cloudpub/token

Получить токен на Mac:

    grep '^token' ~/Library/Application\ Support/cloudpub/client.toml

## Диагностика

### Агент возвращает пустой список встреч

Проверь Журнал аддона OWA Exchange MCP. Должны быть строки:

    [startup] _patched: decrypted OK, len=1495
    [startup] _patched: user_email=твой@email.com
    [startup] _patched: DONE, returning (cookies loaded)

Если нет user_email= — проблема с .credentials.enc
Если decrypt returned EMPTY/None — проблема с .salt или паролем

### URL CloudPub не отвечает

В core-ssh:

    curl -sI http://172.30.32.1:8765/sse

Должен вернуть 200 OK или 400 Bad Request.

### Аддон долго стартует

Каждый запуск pip install -e . занимает 2-5 минут. Это нормально.

## Хранение секретов

Все чувствительные файлы (.salt, .credentials.enc, cookies, env, token)
не коммитятся в git. .gitignore это гарантирует.

## Лицензия

MIT
