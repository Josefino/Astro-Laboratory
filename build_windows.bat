@echo off
setlocal
cd /d "%~dp0"
set "BUILD_PYTHON=%ASTRO_BUILD_PYTHON%"
if not defined BUILD_PYTHON set "BUILD_PYTHON=py"
if exist ".build-venv\Scripts\python.exe" goto checkvenv
if "%BUILD_PYTHON%"=="py" (
  py -3.12 -m venv .build-venv
) else (
  "%BUILD_PYTHON%" -m venv .build-venv
)
if errorlevel 1 goto failed
:checkvenv
.build-venv\Scripts\python.exe -c "import sys; assert sys.version_info >= (3,11), 'Use Python 3.11+ (recommended: 3.12)'"
if errorlevel 1 goto failed
.build-venv\Scripts\python.exe -m pip install --upgrade pip
if errorlevel 1 goto failed
.build-venv\Scripts\python.exe -m pip install -r requirements.txt -r packaging\requirements-build.txt
if errorlevel 1 goto failed
.build-venv\Scripts\python.exe packaging\build_app.py
if errorlevel 1 goto failed
set "INNO_COMPILER=%ISCC_PATH%"
if defined INNO_COMPILER goto compileinstaller
for /f "delims=" %%I in ('where ISCC.exe 2^>nul') do if not defined INNO_COMPILER set "INNO_COMPILER=%%I"
if defined INNO_COMPILER goto compileinstaller
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "INNO_COMPILER=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if defined INNO_COMPILER goto compileinstaller
if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "INNO_COMPILER=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not defined INNO_COMPILER (
  echo Inno Setup 6 was not found. Install it, or set ISCC_PATH to ISCC.exe.
  echo The portable application is already in dist\AstroLaboratory.
  goto failed
)
:compileinstaller
"%INNO_COMPILER%" packaging\installer.iss
if errorlevel 1 goto failed
echo.
echo DONE: release\AstroLaboratory-0.9.0-Windows-Setup.exe
pause
exit /b 0
:failed
echo.
echo Build failed. Read the first error above. No successful installer is claimed.
pause
exit /b 1
