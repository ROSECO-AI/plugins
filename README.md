# ROSECO AI Plugins

Публичный репозиторий плагинов ROSECO AI для Codex.

## Доступные плагины

- [Archviz Revit Render](Archviz%20Revit%20Render/) версии **2.1.1** — подготовка фотореалистичных архитектурных рендеров по видам Revit/BIM, генпланам, чертежам и фотографиям.
- [Саммари совещаний](Meeting%20Summary%20RU/) версии **1.0.0** — русскоязычные саммари по стенограммам с решениями, поручениями, сроками, рисками и открытыми вопросами.

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

Маркетплейс описан в `.agents/plugins/marketplace.json`. Работа с изображениями зависит от доступности инструмента генерации изображений в вашем Codex.
