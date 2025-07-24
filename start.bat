@echo off
echo 🔁 Запуск Ollama...
start cmd /c "ollama run llama3.2:1b"

echo 🚀 Запуск backend...
start cmd /c "cd backend && call venv\Scripts\activate && python server.py"

echo 🌐 Запуск frontend...
start cmd /c "cd frontend && npm start"

echo ✅ Все процессы запущены.
pause
