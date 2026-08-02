@echo off
setlocal
cd /d "%~dp0"
title PasteHub 剪贴板记录

echo.
echo   ============================================
echo      PasteHub 剪贴板记录工具
echo   ============================================
echo.

rem ---------- 1. 检测 Python ----------
set "PY="
where python >nul 2>nul
if errorlevel 1 goto try_py
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if errorlevel 1 goto try_py
set "PY=python"
goto py_ok

:try_py
where py >nul 2>nul
if errorlevel 1 goto no_python
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if errorlevel 1 goto no_python
set "PY=py -3"

:py_ok
echo   [1/4] 检测到 Python：%PY%
echo.
goto step2

:no_python
echo   [错误] 没有找到 Python 3.10 或更高版本。
echo.
echo   请先安装 Python（只需要装一次）：
echo     1. 打开 https://www.python.org/downloads/
echo     2. 下载最新版本并安装
echo     3. 安装时务必勾选 Add Python to PATH
echo     4. 装好后重新双击本文件即可
echo.
pause
exit /b 1

:step2
rem ---------- 2. 检查 / 安装 Pillow ----------
echo   [2/4] 正在检查 / 安装 Pillow（处理图片需要）...
%PY% -m pip install --disable-pip-version-check -q Pillow
if errorlevel 1 (
    echo.
    echo   [错误] Pillow 安装失败，请检查网络后重试。
    pause
    exit /b 1
)
echo   Pillow 已就绪。
echo.

rem ---------- 3. 准备数据文件夹 ----------
if not exist "data" mkdir "data"
echo   [3/4] 数据会自动保存在：%~dp0data
echo.

rem ---------- 4. 创建桌面快捷方式（已存在则跳过） ----------
set "PYW="
if "%PY%"=="py -3" (
    py -3 -c "import sys,os;print(os.path.join(os.path.dirname(sys.executable),'pythonw.exe'))" > "%TEMP%\pastehub_pyw.txt" 2>nul
) else (
    python -c "import sys,os;print(os.path.join(os.path.dirname(sys.executable),'pythonw.exe'))" > "%TEMP%\pastehub_pyw.txt" 2>nul
)
if exist "%TEMP%\pastehub_pyw.txt" (
    set /p PYW=<"%TEMP%\pastehub_pyw.txt"
    del "%TEMP%\pastehub_pyw.txt" >nul 2>nul
)
if not defined PYW set "PYW=pythonw"
set "PYW_SCRIPT=%~dp0clipboard_monitor.pyw"
set "PYW_WORK=%~dp0"
set "PYW_ICON=%~dp0app.ico"
powershell -NoProfile -ExecutionPolicy Bypass -EncodedCommand JABkACAAPQAgACQAZQBuAHYAOgBQAFkAVwBfAEQARQBTAEsAVABPAFAACgBpAGYAIAAoAC0AbgBvAHQAIAAkAGQAKQAgAHsAIAAkAGQAIAA9ACAAWwBFAG4AdgBpAHIAbwBuAG0AZQBuAHQAXQA6ADoARwBlAHQARgBvAGwAZABlAHIAUABhAHQAaAAoACcARABlAHMAawB0AG8AcAAnACkAIAB9AAoAJABsAG4AawAgAD0AIABKAG8AaQBuAC0AUABhAHQAaAAgACQAZAAgACcAUABhAHMAdABlAEgAdQBiAC4AbABuAGsAJwAKAGkAZgAgACgAVABlAHMAdAAtAFAAYQB0AGgAIAAkAGwAbgBrACkAIAB7ACAAJABzAHQAYQB0AGUAIAA9ACAAJwBFAFgASQBTAFQAUwAnACAAfQAgAGUAbABzAGUAIAB7AAoAIAAgACQAdwBzACAAPQAgAE4AZQB3AC0ATwBiAGoAZQBjAHQAIAAtAEMAbwBtAE8AYgBqAGUAYwB0ACAAVwBTAGMAcgBpAHAAdAAuAFMAaABlAGwAbAAKACAAIAAkAHMAIAA9ACAAJAB3AHMALgBDAHIAZQBhAHQAZQBTAGgAbwByAHQAYwB1AHQAKAAkAGwAbgBrACkACgAgACAAJABzAC4AVABhAHIAZwBlAHQAUABhAHQAaAAgAD0AIAAkAGUAbgB2ADoAUABZAFcACgAgACAAJABzAC4AQQByAGcAdQBtAGUAbgB0AHMAIAA9ACAAWwBjAGgAYQByAF0AMwA0ACAAKwAgACQAZQBuAHYAOgBQAFkAVwBfAFMAQwBSAEkAUABUACAAKwAgAFsAYwBoAGEAcgBdADMANAAKACAAIAAkAHMALgBXAG8AcgBrAGkAbgBnAEQAaQByAGUAYwB0AG8AcgB5ACAAPQAgACQAZQBuAHYAOgBQAFkAVwBfAFcATwBSAEsACgAgACAAJABzAC4ASQBjAG8AbgBMAG8AYwBhAHQAaQBvAG4AIAA9ACAAJABlAG4AdgA6AFAAWQBXAF8ASQBDAE8ATgAgACsAIAAnACwAMAAnAAoAIAAgACQAcwAuAFMAYQB2AGUAKAApAAoAIAAgACQAcwB0AGEAdABlACAAPQAgACcAQwBSAEUAQQBUAEUARAAnAAoAfQAKAFMAZQB0AC0AQwBvAG4AdABlAG4AdAAgAC0AUABhAHQAaAAgACgASgBvAGkAbgAtAFAAYQB0AGgAIAAkAGUAbgB2ADoAVABFAE0AUAAgACcAcABhAHMAdABlAGgAdQBiAF8AcwBjAC4AdAB4AHQAJwApACAALQBWAGEAbAB1AGUAIAAkAHMAdABhAHQAZQAgAC0ARQBuAGMAbwBkAGkAbgBnACAAQQBTAEMASQBJAA==
set "SC_STATE="
if exist "%TEMP%\pastehub_sc.txt" (
    set /p SC_STATE=<"%TEMP%\pastehub_sc.txt"
    del "%TEMP%\pastehub_sc.txt" >nul 2>nul
)
if "%SC_STATE%"=="CREATED" (
    echo   [4/4] 已在桌面创建 PasteHub 快捷方式
) else (
    echo   [4/4] 桌面 PasteHub 快捷方式已存在
)
echo.

rem ---------- 5. 启动 ----------
echo   正在启动 PasteHub ... 程序在后台运行，本窗口即将关闭。
echo   以后打开：双击桌面 PasteHub 快捷方式，或再次双击本文件。
echo.
if "%PY%"=="py -3" (
    start "" pyw -3 "clipboard_monitor.pyw"
) else (
    where pythonw >nul 2>nul
    if errorlevel 1 (
        start "" python "clipboard_monitor.pyw"
    ) else (
        start "" pythonw "clipboard_monitor.pyw"
    )
)
exit /b 0