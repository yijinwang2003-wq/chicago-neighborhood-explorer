"""Streamlit widgets used to collect query parameters.

This module has one main job: given the selected query key, show the correct
Streamlit inputs and return the selected values in a plain Python dictionary.
"""

import streamlit as st

from db import get_connection
from queries import get_wards


def load_ward_options():
    """Load ward IDs from the database for the Q14 dropdown."""

    conn = None

    try:
        conn = get_connection()

        # get_wards() returns a pandas DataFrame with one ward_id column.
        wards = get_wards(conn)

        ward_options = []
        for _, row in wards.iterrows():
            ward_options.append(int(row["ward_id"]))

        return ward_options
    finally:
        if conn is not None and conn.is_connected():
            conn.close()


def build_parameter_widgets(query_key):
    """Show parameter widgets for the selected query.

    Args:
        query_key (str): Stable query key from config.QUERY_OPTIONS.

    Returns:
        dict: Parameter names and values selected by the user.

    These dictionary keys should match the function parameters in queries.py.
    For example, Q1 calls:
        query_affordable_safe(connection, min_units=params["min_units"])
    """

    # Start with an empty dictionary. Each query branch adds only the
    # parameters that its query function will need.
    params = {}

    if query_key == "q1_affordable_safe":
        params["min_units"] = st.slider(
            "Minimum affordable housing units",
            min_value=0,
            max_value=100,
            value=10,
        )

    elif query_key == "q2_housing_near_transit":
        params["max_distance_meters"] = st.slider(
            "Maximum station distance (meters)",
            min_value=100,
            max_value=2000,
            value=800,
            step=100,
        )
        params["top_n"] = st.slider(
            "Maximum rows to show",
            min_value=10,
            max_value=200,
            value=100,
            step=10,
        )

    elif query_key == "q3_transit_usage":
        st.info("This query uses the project's 2025 rail ridership data.")

    elif query_key == "q5_high_demand_efficient":
        st.info("This query uses the project's 2025 official 311 data.")
        params["max_avg_hours"] = st.slider(
            "Maximum average service hours",
            min_value=0,
            max_value=2000,
            value=720,
        )

    elif query_key == "q6_most_accessible":
        params["top_n"] = st.slider(
            "Number of neighborhoods to show",
            min_value=5,
            max_value=77,
            value=15,
        )

    elif query_key == "q7_crime_near_housing":
        st.info("This query uses the project's 2025 crime data.")
        params["min_housing_units"] = st.slider(
            "Minimum housing units",
            min_value=0,
            max_value=100,
            value=10,
        )

    elif query_key == "q8_transit_popularity":
        params["top_n"] = st.slider(
            "Number of neighborhoods to show",
            min_value=5,
            max_value=77,
            value=20,
        )
        st.info("This query uses the project's 2025 rail ridership data.")

    elif query_key == "q9_service_delays":
        st.info("This query uses the project's 2025 official 311 data.")
        params["top_n"] = st.slider(
            "Number of neighborhoods to show",
            min_value=5,
            max_value=77,
            value=20,
        )

    elif query_key == "q10_demographics_vs_crime":
        st.info("This query does not need any parameters.")

    elif query_key == "q11_neighborhood_ranking":
        params["top_n"] = st.slider(
            "Number of neighborhoods to show",
            min_value=5,
            max_value=77,
            value=20,
        )

    elif query_key == "q12_housing_availability":
        st.info("This query does not need any parameters.")

    elif query_key == "q14_ward_overlap":
        try:
            ward_options = load_ward_options()
        except Exception as error:
            # The real dropdown should come from get_wards(conn). This fallback
            # keeps the page visible if the database is temporarily unavailable.
            st.error(f"Could not load wards from database: {error}")
            ward_options = list(range(1, 51))

        if not ward_options:
            st.error("No wards were found in the database.")
            ward_options = list(range(1, 51))

        default_index = 0
        if 27 in ward_options:
            default_index = ward_options.index(27)

        params["ward_id"] = st.selectbox(
            "Ward",
            ward_options,
            index=default_index,
        )

    return params
