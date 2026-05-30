"""Database dependencies for the FastAPI backend."""

from collections.abc import Generator

from mysql.connector import MySQLConnection

from app.db import get_connection


def get_db() -> Generator[MySQLConnection, None, None]:
    """Yield a MySQL connection and close it after the request."""
    connection = get_connection()
    try:
        yield connection
    finally:
        if connection.is_connected():
            connection.close()
