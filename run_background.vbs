' run_background.vbs
' Launches the AI Trading Agents Streamlit app in a completely hidden window.
' No Command Prompt window will appear. Access the app at http://localhost:8501

Dim oShell
Set oShell = CreateObject("WScript.Shell")

' WindowStyle 0 = hidden (no visible window)
' bWaitOnReturn False = don't block; script returns immediately
oShell.Run "cmd /c cd /d C:\Users\jjstu\trading-agents && streamlit run app.py --server.headless true", 0, False

Set oShell = Nothing
