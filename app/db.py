"""Database connection helpers for the Streamlit app.

This file is intentionally small.  The goal is to keep all database connection
setup in one place so the Streamlit UI does not need to know the connection
details.
"""

import os

import mysql.connector
from dotenv import load_dotenv


def get_connection():
    """Create and return a reusable MySQL connection object.

    Expected environment variables:
        MYSQL_HOST      default: localhost
        MYSQL_PORT      default: 3306
        MYSQL_USER      default: root
        MYSQL_PASSWORD  default: empty string
        MYSQL_DATABASE  default: chicago_neighborhood

    You can place these values in a local .env file while developing.
    """

    # Load variables from .env if that file exists. If it does not exist,
    # this line is harmless and the app will use the defaults below.
    load_dotenv()

    # mysql.connector.connect returns a live MySQL connection object.
    # That object can later be passed into query functions in queries.py.
    connection = mysql.connector.connect(
        host=os.getenv("MYSQL_HOST", "localhost"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", ""),
        database=os.getenv("MYSQL_DATABASE", "chicago_neighborhood"),
    )

    return connection
