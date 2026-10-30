@echo off
setlocal
cd /d "%~dp0"

set "MARIADB_HOME=%~dp0..\mariadb"
set "MARIADB_DATA=%~dp0..\mariadb-data"

powershell -NoProfile -Command "$listener=Get-NetTCPConnection -LocalPort 3306 -State Listen -ErrorAction SilentlyContinue; if($listener){exit 0}else{exit 1}"
if not errorlevel 1 (
    echo [DataPaper] MariaDB is already running.
    exit /b 0
)

if not exist "%MARIADB_HOME%\bin\mariadbd.exe" (
    echo [DataPaper] MariaDB executable is missing: %MARIADB_HOME%
    exit /b 1
)

start "DataPaper MariaDB" /min "%MARIADB_HOME%\bin\mariadbd.exe" --defaults-file="%MARIADB_DATA%\my.ini" --bind-address=127.0.0.1 --console

for /l %%I in (1,1,20) do (
    powershell -NoProfile -Command "$listener=Get-NetTCPConnection -LocalPort 3306 -State Listen -ErrorAction SilentlyContinue; if($listener){exit 0}else{exit 1}"
    if not errorlevel 1 (
        echo [DataPaper] MariaDB is ready on 127.0.0.1:3306.
        exit /b 0
    )
    ping 127.0.0.1 -n 2 >nul
)

echo [DataPaper] MariaDB startup timed out.
exit /b 1
