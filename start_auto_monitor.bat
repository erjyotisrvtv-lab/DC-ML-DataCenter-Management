@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" auto_routing_monitor.py --interval 30
) else (
    python auto_routing_monitor.py --interval 30
)
pause
