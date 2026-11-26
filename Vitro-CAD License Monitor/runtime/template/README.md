# Локальный мониторинг лицензий Vitro-CAD

Проект создан из публичного плагина ROSECO. Он читает занятость WEB- и PRO-лицензий через REST API и хранит только агрегаты.

## Запуск

```text
python -m vitro_license_monitor.cli configure
python -m vitro_license_monitor.cli login
python -m vitro_license_monitor.cli collect
python -m vitro_license_monitor.cli dashboard
python -m vitro_license_monitor.cli status
```

Дашборд по умолчанию создаётся в `output/license-dashboard.html`.

Пароль и токен не записываются в проект. Токен хранится в macOS Keychain или Windows DPAPI.
