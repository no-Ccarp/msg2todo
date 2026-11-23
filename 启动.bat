@echo off
chcp 65001 >nul
cd /d "%~dp0"
title 群消息待办整理 Agent

echo ================================================
echo   群消息待办整理 Agent - 本地启动
echo ================================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [1/3] 未找到虚拟环境，正在创建...
    py -3 -m venv .venv
    if errorlevel 1 (
        echo 创建失败：请先安装 Python 3.10+ 并确保 py 命令可用。
        pause & exit /b 1
    )
    echo [2/3] 安装依赖...
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
) else (
    echo [1/3] 虚拟环境已存在
)

if not exist ".env" (
    echo.
    echo ！未找到 .env 文件。请复制 .env.example 为 .env 并填入 LLM_API_KEY。
    echo.
)

if not exist "models\clf.pkl" (
    echo [2/3] 未找到模型，正在训练...
    ".venv\Scripts\python.exe" train.py
)

echo [3/3] 启动服务...
echo 浏览器将自动打开 http://127.0.0.1:8000
echo 关闭此窗口即可停止服务。
echo.
".venv\Scripts\python.exe" -m app.main
pause
