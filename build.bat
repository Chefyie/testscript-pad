@echo off
rem Builds dist\Testscript-Pad.exe (a single file that runs without Python installed).
rem Needs Python 3 for the build itself; the build tools go in .venv-build.
cd /d "%~dp0"

if not exist .venv-build\Scripts\python.exe (
    echo Creating the build environment...
    python -m venv .venv-build || goto :error
    .venv-build\Scripts\python -m pip install --disable-pip-version-check pyinstaller || goto :error
)

if not exist assets\icon.ico .venv-build\Scripts\python tools\make_icon.py

.venv-build\Scripts\python -m PyInstaller --noconfirm --clean --onefile --windowed ^
    --name Testscript-Pad --icon "%~dp0assets\icon.ico" --add-data "%~dp0assets\icon.ico;assets" ^
    --distpath dist --workpath build\pyinstaller --specpath build ^
    testscript_pad.py || goto :error

echo.
echo Built dist\Testscript-Pad.exe
exit /b 0

:error
echo.
echo Build failed.
exit /b 1
