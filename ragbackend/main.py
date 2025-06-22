"""Main entry point for the RAG Backend application."""
from ragbackend.server import APP

# Export the app for uvicorn
app = APP

__all__ = ["app"] 