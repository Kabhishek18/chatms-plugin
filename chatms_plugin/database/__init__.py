
"""
Database module for the ChatMS plugin.
"""

# Import handlers
from .base import DatabaseHandler
from .mongodb import MongoDBCompleteHandler as MongoDBHandler
from .postgresql import PostgreSQLHandler

# Define what to export
__all__ = [
    "DatabaseHandler",
    "MongoDBHandler",
    "PostgreSQLHandler",
]