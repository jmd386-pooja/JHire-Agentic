@echo off
echo 🔧 Setting up environment for ChromaDB telemetry suppression...
echo.

REM Disable ChromaDB telemetry
set ANONYMIZED_TELEMETRY=false
set CHROMA_TELEMETRY_ENABLED=false
set CHROMA_ANONYMIZED_TELEMETRY=false
set ALLOW_RESET=true

echo ✅ Environment variables set successfully
echo ✅ ChromaDB telemetry warnings should be suppressed
echo.

echo 🚀 Starting Streamlit application...
echo 📱 The app will open in your default web browser
echo 🔒 ChromaDB telemetry is disabled
echo ================================================
echo.

REM Start Streamlit
streamlit run app.py

pause
