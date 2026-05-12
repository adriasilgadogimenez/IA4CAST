@echo off
REM ============================================================
REM IA4CAST - Script de empaquetado completo
REM
REM Ejecuta: build_all.bat
REM
REM Resultado: installer\IA4CAST_Setup_v1.0.exe
REM ============================================================

echo.
echo === IA4CAST - Build completo ===
echo.

REM 1) Verificar que el venv existe
if not exist .venv\Scripts\activate.bat (
    echo [ERROR] No se encuentra .venv\
    echo Crealo con:
    echo    python -m venv .venv
    echo    .venv\Scripts\activate
    echo    pip install -r requirements.txt
    exit /b 1
)

call .venv\Scripts\activate.bat

REM 2) PyInstaller
echo.
echo [1/2] Empaquetando con PyInstaller...
pyinstaller IA4CAST.spec --clean --noconfirm
if errorlevel 1 (
    echo [ERROR] PyInstaller fallo.
    exit /b 1
)

if not exist dist\IA4CAST.exe (
    echo [ERROR] No se ha generado dist\IA4CAST.exe
    exit /b 1
)

echo OK - dist\IA4CAST.exe generado.

REM 3) Inno Setup (requiere ISCC.exe en PATH)
echo.
echo [2/2] Compilando instalador con Inno Setup...
where ISCC >nul 2>nul
if errorlevel 1 (
    echo [AVISO] ISCC.exe no esta en PATH.
    echo Instala Inno Setup 6 desde https://jrsoftware.org/isdl.php
    echo y luego abre setup.iss con Inno Setup Compiler manualmente.
    exit /b 0
)

if not exist installer mkdir installer
ISCC setup.iss
if errorlevel 1 (
    echo [ERROR] Inno Setup fallo.
    exit /b 1
)

echo.
echo === BUILD COMPLETO ===
echo Instalador en: installer\IA4CAST_Setup_v1.0.exe
echo.
