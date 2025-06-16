@echo off
set "BOT_DIR=C:\Users\sashulya\Desktop\бот расписание коледж"
set "PYTHON_EXE=C:\Users\sashulya\miniconda3\python.exe"
set "BOT_SCRIPT=%BOT_DIR%\bot.py"

cd /d "%BOT_DIR%"
call "%PYTHON_EXE%" "%BOT_SCRIPT%" 