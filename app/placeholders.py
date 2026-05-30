"""Fake data helpers used before real SQL queries are connected.

Nothing in this file talks to MySQL.  It only creates small pandas DataFrames
so the Streamlit interface can be tested while queries.py is still in progress.
"""

import pandas as pd

from config import QUERY_OPTIONS


def get_placeholder_dataframe(query_key, params):
    """Return fake data for the selected query.

    Args:
        query_key (str): Stable query key from config.QUERY_OPTIONS.
        params (dict): Parameters selected in the Streamlit widgets.

    Returns:
        pandas.DataFrame: Small fake result table for UI testing.

    Later, this function can be replaced with API-backed query calls.
    """

    selected_query = QUERY_OPTIONS[query_key]["label"]

    # Keep the fake data generic so every query can display something useful.
    # The params column makes it easy to confirm that widgets are working.
    return pd.DataFrame(
        {
            "rank": [1, 2, 3],
            "community_area": ["Lake View", "Hyde Park", "Logan Square"],
            "query": [selected_query, selected_query, selected_query],
            "selected_parameters": [str(params), str(params), str(params)],
            "placeholder_score": [95.4, 88.2, 81.7],
        }
    )
