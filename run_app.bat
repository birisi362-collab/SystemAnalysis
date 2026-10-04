@echo off
cd /d "%~dp0"
if exist ".venv-workbench\Scripts\python.exe" (
  ".venv-workbench\Scripts\python.exe" run_workbench.py
) else if exist "venv\Scripts\python.exe" (
  "venv\Scripts\python.exe" run_workbench.py
) else (
  python run_workbench.py
)
pause
