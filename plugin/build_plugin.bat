@echo off
rem Builds plugin\bin\testscript_pad.dll, the Testscript-Pad server plugin for TF2 (Orange Box, 32-bit).
rem Needs Visual Studio 2019+ with "Desktop development with C++", and git (to fetch the Orange Box SDK once).
setlocal
cd /d "%~dp0"
set SDK=%~dp0..\.sdk\hl2sdk-ob

if not exist "%SDK%\public\eiface.h" (
    echo Fetching the Orange Box SDK headers into .sdk ...
    git clone --depth 1 --filter=blob:none --sparse -b orangebox https://github.com/alliedmodders/hl2sdk.git "%SDK%" || goto :error
    git -C "%SDK%" sparse-checkout set public lib/public tier1 game/shared || goto :error
)

rem find a Visual Studio with the C++ tools and set up the 32-bit compiler
set VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe
set VSDIR=
for /f "usebackq delims=" %%i in (`"%VSWHERE%" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath`) do set VSDIR=%%i
if "%VSDIR%"=="" (
    echo.
    echo No Visual Studio C++ compiler found.
    echo Open the Visual Studio Installer, choose Modify and tick "Desktop development with C++".
    goto :error
)
call "%VSDIR%\VC\Auxiliary\Build\vcvarsall.bat" x86 >nul || goto :error

if not exist bin mkdir bin
if not exist obj mkdir obj

cl /nologo /c /O2 /MT /EHsc /GR /W3 /Zc:wchar_t- /Zc:forScope /Zc:threadSafeInit- ^
   /D WIN32 /D _WIN32 /D _WINDOWS /D NDEBUG /D _USRDLL /D COMPILER_MSVC /D COMPILER_MSVC32 ^
   /D _CRT_SECURE_NO_DEPRECATE /D _CRT_NONSTDC_NO_DEPRECATE /D _CRT_NO_VA_START_VALIDATION ^
   /D _ALLOW_RUNTIME_LIBRARY_MISMATCH /D _ALLOW_ITERATOR_DEBUG_LEVEL_MISMATCH /D _ALLOW_MSC_VER_MISMATCH ^
   /I "%SDK%\public" /I "%SDK%\public\tier0" /I "%SDK%\public\tier1" /I "%SDK%\game\shared" ^
   /Fo"obj\\" testscript_pad_plugin.cpp || goto :error

link /nologo /DLL /OUT:bin\testscript_pad.dll /SAFESEH:NO /NODEFAULTLIB:libc /NODEFAULTLIB:libcd /NODEFAULTLIB:libcmtd ^
   obj\testscript_pad_plugin.obj ^
   "%SDK%\lib\public\tier0.lib" "%SDK%\lib\public\tier1.lib" "%SDK%\lib\public\vstdlib.lib" ^
   legacy_stdio_definitions.lib user32.lib advapi32.lib || goto :error

copy /y testscript_pad.vdf bin\testscript_pad.vdf >nul
echo.
echo Built plugin\bin\testscript_pad.dll
exit /b 0

:error
echo.
echo Plugin build failed.
exit /b 1
