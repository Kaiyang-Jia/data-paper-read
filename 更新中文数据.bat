@echo off
cd /d "%~dp0"
python -X utf8 -m research.update_catalog
if errorlevel 1 (
  echo Update failed. See the message above. Completed cards are saved for retry.
) else (
  echo Update finished. Restart the workspace to load the new catalog and index.
)
pause
