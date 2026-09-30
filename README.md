# OWA Exchange MCP — Home Assistant Add-on

Цифровой секретарь для корпоративного Exchange через MCP-протокол.
Работает как Home Assistant App (Add-on), управляется Supervisor.

## Установка

1. Home Assistant → Настройки → Дополнения → Магазин
2. Три точки → Репозитории → добавь:
   https://github.com/Jumeo173/owa-mcp-addon
3. Найди OWA Exchange MCP → Установить → Запустить

## Настройка

1. Подготовь файл owa-mcp.env с секретами (см. .env.example).
2. Положи его в /addon_configs/owa-mcp/ (создаётся после первого запуска).
3. Также положи туда session-cookies.txt (полученный с Mac через login.py).
4. Перезапусти аддон.
