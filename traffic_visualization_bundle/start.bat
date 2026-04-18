@echo off
setlocal

set ROOT_DIR=%~dp0
set APP_DIR=%ROOT_DIR%app
set VENV_DIR=%APP_DIR%\.venv

where py >nul 2>nul
if %errorlevel%==0 (
  set PYTHON_CMD=py -3
) else (
  where python >nul 2>nul
  if %errorlevel% neq 0 (
    echo Python not found. Install Python 3.10+ first.
    exit /b 1
  )
  set PYTHON_CMD=python
)

cd /d "%APP_DIR%"

if not exist "%VENV_DIR%" (
  call %PYTHON_CMD% -m venv .venv
)

call "%VENV_DIR%\Scripts\activate.bat"
call python -m pip install --upgrade pip
call pip install -r requirements-visualization.txt
call python manage.py migrate

echo.
echo Open: http://127.0.0.1:8000/
echo Login: http://127.0.0.1:8000/users/login/
echo.

call python manage.py runserver 0.0.0.0:8000
