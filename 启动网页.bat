@echo off
cd /d "%~dp0"
python run_workspace.py
if errorlevel 1 pause
