#!/usr/bin/env python3
"""
Startup script for the Agentic AI Resume Matcher.
This script ensures all ChromaDB telemetry is disabled before starting the app.
"""

import os
import sys
import warnings

def setup_environment():
    """Setup environment to disable all ChromaDB telemetry."""
    
    print("🔧 Setting up environment for ChromaDB telemetry suppression...")
    
    # Disable all ChromaDB telemetry
    telemetry_vars = {
        "ANONYMIZED_TELEMETRY": "false",
        "CHROMA_TELEMETRY_ENABLED": "false", 
        "CHROMA_ANONYMIZED_TELEMETRY": "false",
        "ALLOW_RESET": "true"
    }
    
    for var, value in telemetry_vars.items():
        os.environ[var] = value
        print(f"✅ Set {var}={value}")
    
    # Suppress warnings
    warnings.filterwarnings("ignore", message=".*Failed to send telemetry event.*")
    warnings.filterwarnings("ignore", message=".*capture.*takes 1 positional argument but 3 were given.*")
    warnings.filterwarnings("ignore", message=".*telemetry.*")
    
    print("✅ Environment setup complete!")
    print("✅ ChromaDB telemetry warnings should be suppressed")

def start_streamlit():
    """Start the Streamlit application."""
    
    print("\n🚀 Starting Streamlit application...")
    print("📱 The app will open in your default web browser")
    print("🔒 ChromaDB telemetry is disabled")
    print("=" * 50)
    
    try:
        # Import and run streamlit
        import streamlit.web.cli as stcli
        
        # Set streamlit arguments
        sys.argv = [
            "streamlit", "run", "app.py",
            "--server.port", "8501",
            "--server.address", "localhost",
            "--browser.gatherUsageStats", "false"
        ]
        
        # Start streamlit
        sys.exit(stcli.main())
        
    except ImportError:
        print("❌ Streamlit not found. Installing...")
        os.system("pip install streamlit")
        print("✅ Streamlit installed. Please run this script again.")
        
    except Exception as e:
        print(f"❌ Error starting Streamlit: {e}")
        print("Try running manually: streamlit run app.py")

if __name__ == "__main__":
    setup_environment()
    start_streamlit()
