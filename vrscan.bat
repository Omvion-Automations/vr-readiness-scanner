@echo off
rem Drag a game folder onto this file (or double-click and paste a Steam link).
python "%~dp0vrscan.py" %* || py "%~dp0vrscan.py" %*
echo.
pause
