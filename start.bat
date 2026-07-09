@echo off
REM ============================================================
REM  JDO 车机自动化测试平台 一键启动（双击运行，独立于开发会话）
REM  访问: http://127.0.0.1:8770   登录: admin / 123456
REM  注意: 8765 被并行的 Codex 平台占用，本平台固定 8770
REM ============================================================
chcp 65001 >nul
cd /d %~dp0
python -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8770
pause
