"""Streamlit widgets used to collect query parameters.

This module has one main job: given the selected query key, show the correct
Streamlit inputs and return the selected values in a plain Python dictionary.
"""

import streamlit as st

from config import DAY_TYPE_OPTIONS, DEFAULT_YEAR_INDEX, YEARS


def build_parameter_widgets(query_key):
    """Show parameter widgets for the selected query.

    Args:
        query_key (str): Stable query key from config.QUERY_OPTIONS.

    Returns:
        dict: Parameter names and values selected by the user.

    These dictionary keys should match the future function parameters in
    queries.py where possible. For example, Q1 can later call:
        queries.affordable_safe(connection, min_units=params["min_units"])
    """

    # Start with an empty dictionary. Each query branch adds only the
    # parameters that its future SQL function will need.
    params = {}

    if query_key == "q1_affordable_safe":
        params["min_units"] = st.slider(
            "Minimum affordable housing units",
            min_value=0,
            max_value=100,
            value=10,
        )

    elif query_key == "q2_housing_near_transit":
        params["min_stops"] = st.slider(
            "Minimum nearby transit stops",
            min_value=1,
            max_value=10,
            value=1,
        )

    elif query_key == "q3_transit_usage":
        params["year"] = st.selectbox(
            "Year",
            YEARS,
            index=DEFAULT_YEAR_INDEX,
        )

        # The user sees readable labels, but queries.py will receive the
        # compact CTA code stored in params["day_type"].
        selected_day_type = st.selectbox(
            "Day type",
            list(DAY_TYPE_OPTIONS.keys()),
        )
        params["day_type"] = DAY_TYPE_OPTIONS[selected_day_type]

    elif query_key == "q5_high_demand_efficient":
        params["year"] = st.selectbox(
            "Year",
            YEARS,
            index=DEFAULT_YEAR_INDEX,
        )
        params["max_avg_days"] = st.slider(
            "Maximum average service days",
            min_value=0,
            max_value=100,
            value=30,
        )

    elif query_key == "q6_most_accessible":
        params["top_n"] = st.slider(
            "Number of neighborhoods to show",
            min_value=5,
            max_value=77,
            value=15,
        )

    elif query_key == "q7_crime_near_housing":
        params["year"] = st.selectbox(
            "Year",
            YEARS,
            index=DEFAULT_YEAR_INDEX,
        )
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
        params["year"] = st.selectbox(
            "Year",
            YEARS,
            index=DEFAULT_YEAR_INDEX,
        )

    elif query_key == "q9_service_delays":
        params["year"] = st.selectbox(
            "Year",
            YEARS,
            index=DEFAULT_YEAR_INDEX,
        )
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

    elif query_key == "q14_peak_transit_days":
        params["year"] = st.selectbox(
            "Year",
            YEARS,
            index=DEFAULT_YEAR_INDEX,
        )

    return params
