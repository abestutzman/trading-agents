@echo off
title AI Trading Agents — Launcher

cd /d "C:\Users\jjstu\trading-agents"

echo Starting AI Trading Agents in the background...
echo The app will be available at http://localhost:8501
echo.

wscript.exe "C:\Users\jjstu\trading-agents\run_background.vbs"

echo Done. Open your browser and go to http://localhost:8501
echo (It may take a few seconds for Streamlit to start.)
echo.
echo To stop the app, run stop_trading.bat
timeout /t 4 >nul
