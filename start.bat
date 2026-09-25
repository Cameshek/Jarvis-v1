@echo off
chcp 65001 >nul
title Jarvis Launcher

echo ============================================
echo   Запуск Jarvis v1...
echo ============================================
echo.

cd /d "%~dp0"

py voice_launcher.py

if errorlevel 1 (
    echo.
    echo ============================================
    echo   Программа завершилась с ошибкой!
    echo   Скинь текст выше разработчику.
    echo ============================================
)

echo.
pause >nul
