# OpenAI Subagent App

Тестовое приложение на Python, совместимое с OpenAI Apps SDK, реализующее простой MCP-сервер с виджетом.

## Функциональность

- **Инструмент "setvar"**: Принимает задачу для субагента и записывает её в файл `tasks.txt`.
- **Виджет**: После рендеринга через 3 секунды отправляет follow-up сообщение через host bridge с текстом "Responce from sub-agent: task completed".

## Установка

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Запуск

Запустите сервер:
```bash
uvicorn app:app --host 0.0.0.0 --port 8000
```

Сервер будет доступен на `http://localhost:8000`.

## Использование в ChatGPT (или другом MCP-хосте)

1. Зарегистрируйте сервер в конфигурации вашего OpenAI App.
2. Вызовите инструмент `setvar` с аргументом `task`, например:
   - Имя: setvar
   - Аргументы: `{"task": "Анализировать новый датасет"}`
3. Сервер сохранит задачу в `tasks.txt` и вернёт метаданные для рендеринга виджета.
4. Виджет отобразит задачу и через ~3 секунды отправит follow-up сообщение.

## Структура файлов

- `app.py`: Основной код MCP-сервера.
- `assets/setvar-widget.html`: HTML-виджет.
- `tasks.txt`: Файл для хранения задач (создаётся автоматически).
- `requirements.txt`: Зависимости Python.

## Зависимости

- `mcp[server]`: Для MCP-сервера.
- `starlette`: ASGI-фреймворк.
- `uvicorn`: ASGI-сервер.
- `pydantic`: Валидация данных.