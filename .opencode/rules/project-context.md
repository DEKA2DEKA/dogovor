# Проект: Монитор договоров

## Архитектура
- Flask-приложение (Python), SQLite (SQLAlchemy)
- Канбан-доски по разделам жизненного цикла договора
- Разделы: conclusion → execution → modification → storage → archive
- ДС (допсоглашения): contract_type='additional', проходят те же стадии, кроме modification

## Версионирование (semver)
- **MAJOR** (1.x.x) — существенные изменения (по указанию пользователя)
- **MINOR** (x.1.x) — новый функционал
- **PATCH** (x.x.1) — багфиксы и косметика
- Версия-источник: README.md
- VERSION в app.py синхронизировать с README
- Коммиты: "X.Y.Z - описание"
- Первая строка файлов: "Версия программы: X.Y.Z | Версия файла: A.B.C"

## Ветки Git
- **develop** — вся разработка, коммиты сюда
- **main** — продакшн, авто-деплой через Dokploy при push
- Merge develop → main для деплоя. TODO.md только в develop.

## Окружение
- Локально: `python app.py` (режим debug, ENVIRONMENT=development)
- Продакшн: Docker контейнер на VPS, ENVIRONMENT=production
- Dockerfile: `ENV ENVIRONMENT=production`
- docker-compose.yml: тоже содержит ENVIRONMENT=production
- Кнопка "Остановить сервер" скрыта в production

## Продакшн
- http://176.108.251.234:5000 (Docker, Dokploy)
- Dokploy UI: http://176.108.251.234:3000
- OpenCode Web: http://176.108.251.234:4096
- Volume dogovor_data:/app/instance для SQLite

## Модели данных
- **Contract**: id, title, number, date, amount, counterparty, description, section, step,
  sections (JSON), section_steps (JSON), contract_type, parent_id, sort_order (Float),
  created_at, updated_at
- **News**: id, date, title, body, tag, tag_color, is_active, created_at

## Ключевые решения
- sort_order (Float) для плавной вставки между соседями
- Drag-and-drop на HTML5 API (без SortableJS)
- get_display_columns(section_key) → список (step_key, label, color)
- CSS: .kanban-board (flexbox), .column-body (drop zone), .contract-card (draggable)
- main.js: SECTIONS, renderBoard, renderSection, drag-drop handlers

## Кодовые конвенции
- Никаких комментариев в коде (кроме версионных заголовков)
- Шаблоны: base.html (навигация, модалки), info.html (дашборд), section.html (канбан),
  board.html (доска разделов), database.html (таблица), reports.html (отчёты)
- Статика: static/css/style.css, static/js/main.js, static/images/logo.png
- Favicon и логотип: BRD (Бюро по работе с договорами)

## TODO (основное на данный момент)
- Редактирование/создание договоров
- Удаление договоров
- Журнал действий (аудит)
- Уведомления о просрочках
- Авторизация
- Карточка организации на info
- Уточнение логики стадий (ДС без Изменение, параллельное Исполнение)
