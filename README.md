# ROSECO AI Plugins

Публичный репозиторий плагинов ROSECO AI для Codex.

## Доступные плагины

- [Vitro-CAD — локальный MCP](vitro-cad-local-mcp/) версии **1.0.0** — адрес своего портала, личный вход и подключение к Codex Desktop, Claude Code или Qwen Code на Windows.

- [Битрикс24 — локальный MCP](bitrix24-local-mcp/) версии **1.0.0** — Python-коннектор с универсальным REST-вызовом, собственным вебхуком пользователя и установкой на Windows/macOS/Linux. [Сравнение с официальным MCP](bitrix24-local-mcp/docs/comparison.md).
- [Archviz Revit Render](Archviz%20Revit%20Render/) версии **2.1.1** — подготовка фотореалистичных архитектурных рендеров по видам Revit/BIM, генпланам, чертежам и фотографиям.
- [Саммари совещаний](Meeting%20Summary%20RU/) версии **1.0.0** — русскоязычные саммари по стенограммам с решениями, поручениями, сроками, рисками и открытыми вопросами.
- [Мониторинг лицензий Vitro-CAD](Vitro-CAD%20License%20Monitor/) версии **1.0.0** — развёртывание локального read-only мониторинга WEB/PRO с SQLite-историей и HTML-дашбордом.

## Установка Vitro-CAD — локальный MCP

Скачайте [установщик для Windows](vitro-cad-local-mcp/README.md) и укажите в форме **адрес своего портала**, личные логин и пароль, а также нужный агент: Codex Desktop, Claude Code или Qwen Code. [Пошаговая инструкция](vitro-cad-local-mcp/INSTALL.md). Доступ ограничен вашей учётной записью Vitro-CAD.

## Установка Archviz Revit Render

Если вы впервые пользуетесь плагинами, откройте [пошаговую инструкцию](Archviz%20Revit%20Render/INSTALL.md). Она объясняет подготовку Codex, установку, проверку и первый запуск.

Для пользователей с уже установленным Codex CLI:

```text
codex plugin marketplace add ROSECO-AI/plugins --ref main
codex plugin add archviz-revit-render@roseco-ai-plugins
```

Проверьте установку командой `codex plugin list` и начните новый чат. [QR-код для презентации](Archviz%20Revit%20Render/assets/archviz-revit-render-plugins-qr.png) ведёт на страницу плагина с инструкцией.

## Установка «Саммари совещаний»

```text
codex plugin marketplace add ROSECO-AI/plugins --ref main
codex plugin add meeting-summary-ru@roseco-ai-plugins
```

Проверьте установку командой `codex plugin list` и начните новый чат. [QR-код плагина](Meeting%20Summary%20RU/assets/meeting-summary-ru-plugins-qr.png) ведёт на его страницу с инструкцией.

## Установка «Мониторинг лицензий Vitro-CAD»

```text
codex plugin marketplace add ROSECO-AI/plugins --ref main
codex plugin add vitro-cad-license-monitor@roseco-ai-plugins
```

После `codex plugin list` начните новый чат и попросите агента настроить read-only мониторинг. Пароль и токен не передаются в чат.

## Установка «Битрикс24 — локальный MCP»

```text
codex plugin marketplace add ROSECO-AI/plugins --ref main
codex plugin add bitrix24-local-mcp@roseco-ai-plugins
```

После установки поручите агенту настройку по [готовому промпту](bitrix24-local-mcp/PROMPT_FOR_AGENT.md).
Плагин включает Python-код и установщик; пользователь вводит собственный вебхук локально.
Установка плагина и успешное подключение к порталу — отдельные этапы.

Маркетплейс описан в `.agents/plugins/marketplace.json`. Работа с изображениями зависит от доступности инструмента генерации изображений в вашем Codex.
