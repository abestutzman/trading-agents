@echo off
title AI Trading Agents — Stop

echo Stopping AI Trading Agents...
echo.

REM Kill the streamlit process (covers both "streamlit" and "streamlit.exe")
taskkill /F /IM streamlit.exe >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo Streamlit process stopped.
) else (
    REM Streamlit sometimes runs under python.exe — find and kill the app.py process
    wmic process where "CommandLine like '%%streamlit%%app.py%%'" delete >nul 2>&1
    if %ERRORLEVEL% EQU 0 (
        echo Streamlit process stopped via wmic.
    ) else (
        echo No running Streamlit process found.
    )
)

REM Also free port 8501 in case something is still holding it
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8501 "') do (
    taskkill /F /PID %%a >nul 2>&1
)

echo.
echo AI Trading Agents has been stopped.
timeout /t 3 >nul
