@echo off
REM dev.cmd - PowerShell / CMD entry point, delegates to dev.sh in the same dir.
REM Usage: dev.cmd start|stop|restart|status|logs server|web
REM Locates Git Bash via git.exe location or well-known install dirs
REM (bash.exe is normally NOT in PATH even when Git for Windows is installed).
chcp 65001 >nul
setlocal EnableDelayedExpansion
set "SCRIPT_DIR=%~dp0"
set "BASH="

REM 1) derive bash.exe from every git.exe found in PATH
for /f "usebackq delims=" %%i in (`where git 2^>nul`) do (
  if not defined BASH if exist "%%~dpi..\bin\bash.exe" set "BASH=%%~dpi..\bin\bash.exe"
  if not defined BASH if exist "%%~dpi..\..\bin\bash.exe" set "BASH=%%~dpi..\..\bin\bash.exe"
  if not defined BASH if exist "%%~dpi..\..\usr\bin\bash.exe" set "BASH=%%~dpi..\..\usr\bin\bash.exe"
)

REM 2) fallback to well-known install locations
if not defined BASH if exist "%ProgramFiles%\Git\bin\bash.exe" set "BASH=%ProgramFiles%\Git\bin\bash.exe"
if not defined BASH if exist "%ProgramFiles(x86)%\Git\bin\bash.exe" set "BASH=%ProgramFiles(x86)%\Git\bin\bash.exe"
if not defined BASH if exist "%LOCALAPPDATA%\Programs\Git\bin\bash.exe" set "BASH=%LOCALAPPDATA%\Programs\Git\bin\bash.exe"

if not defined BASH (
  echo [dev] Git Bash not found. Install Git for Windows, or run dev.sh inside Git Bash.
  exit /b 1
)

"%BASH%" "%SCRIPT_DIR%dev.sh" %*
exit /b %errorlevel%
