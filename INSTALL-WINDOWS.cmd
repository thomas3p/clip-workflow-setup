@echo off
setlocal
where py >nul 2>nul
if not errorlevel 1 goto use_py
where python >nul 2>nul
if not errorlevel 1 goto use_python
echo Python 3.10 or newer is required. Install it from https://www.python.org/downloads/
pause
exit /b 1
:use_py
py -3 "%~dp0install.py" %*
goto finish
:use_python
python "%~dp0install.py" %*
:finish
set "taskExit=%errorlevel%"
if not "%taskExit%"=="0" pause
exit /b %taskExit%
