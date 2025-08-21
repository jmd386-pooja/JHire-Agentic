#!/usr/bin/env python3
"""
ChromaDB configuration to disable telemetry and suppress warnings.
"""

import os
import warnings
from chromadb.config import Settings

def get_chroma_settings():
    """Get ChromaDB settings with telemetry disabled."""
    return Settings(
        anonymized_telemetry=False,  # Disable telemetry
        allow_reset=True,
        is_persistent=True
    )

def suppress_chroma_warnings():
    """Suppress ChromaDB telemetry warnings."""
    # Suppress specific ChromaDB warnings
    warnings.filterwarnings("ignore", message=".*Failed to send telemetry event.*")
    warnings.filterwarnings("ignore", message=".*capture.*takes 1 positional argument but 3 were given.*")
    
    # Set environment variable to disable telemetry
    os.environ["ANONYMIZED_TELEMETRY"] = "false"
    os.environ["CHROMA_TELEMETRY_ENABLED"] = "false"

# Apply settings when module is imported
suppress_chroma_warnings()
