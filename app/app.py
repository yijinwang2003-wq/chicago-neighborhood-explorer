"""Main Streamlit app for the Chicago Neighborhood Explorer project.

This file is intentionally focused on page layout and user flow.  Supporting
details live in nearby modules:
    config.py        query labels and shared constants
    widgets.py       Streamlit parameter widgets
    queries.py       real SQL query functions
    db.py            MySQL connection helper
"""

import streamlit as st

from config import QUERY_OPTIONS
from db import get_connection
from queries import (
    get_community_areas,
    insert_housing_unit,
    query_affordable_safe,
    query_housing_near_transit,
    query_transit_usage,
    query_high_demand_efficient,
    query_most_accessible,
    query_crime_near_housing,
    query_transit_popularity,
    query_service_delays,
    query_demographics_vs_crime,
    query_neighborhood_ranking,
    query_housing_availability,
    query_peak_transit_days,
)
from widgets import build_parameter_widgets


# This dictionary connects each stable frontend query key to the matching
# function in queries.py. Keeping the mapping here makes the Streamlit flow
# easy to read: the selected key chooses the function, and widgets.py supplies
# the parameters for that function.
QUERY_FUNCTIONS = {
    "q1_affordable_safe": query_affordable_safe,
    "q2_housing_near_transit": query_housing_near_transit,
    "q3_transit_usage": query_transit_usage,
    "q5_high_demand_efficient": query_high_demand_efficient,
    "q6_most_accessible": query_most_accessible,
    "q7_crime_near_housing": query_crime_near_housing,
    "q8_transit_popularity": query_transit_popularity,
    "q9_service_delays": query_service_delays,
    "q10_demographics_vs_crime": query_demographics_vs_crime,
    "q11_neighborhood_ranking": query_neighborhood_ranking,
    "q12_housing_availability": query_housing_availability,
    "q14_peak_transit_days": query_peak_transit_days,
}


def execute_query(query_key, params):
    """Run the selected query function and return its pandas DataFrame.

    Args:
        query_key (str): Stable key selected in the sidebar.
        params (dict): Values collected by widgets.py for that query.

    Returns:
        pandas.DataFrame: Results returned by the selected function in
        queries.py.

    The connection is opened only when the user clicks Run Query, then closed
    immediately after the SQL finishes. This keeps the UI simple and avoids
    leaving old database connections open between Streamlit reruns.
    """

    conn = None

    try:
        # Create the real MySQL connection that every query function expects
        # as its first argument.
        conn = get_connection()

        # Dispatch to the selected query function. The **params syntax expands
        # the widget dictionary into named function arguments, for example:
        # {"year": 2024, "top_n": 20} becomes year=2024, top_n=20.
        results = QUERY_FUNCTIONS[query_key](conn, **params)
        return results
    finally:
        # Always close the connection when we are done, even if the query
        # raises an error. mysql.connector exposes is_connected() so we can
        # avoid closing an object that never connected successfully.
        if conn is not None and conn.is_connected():
            conn.close()


def show_database_status():
    """Show a small optional database connection test in the sidebar.

    This button is only a quick helper for checking whether the database
    credentials are set correctly.
    """

    with st.sidebar.expander("Database connection"):
        st.caption("Uses MYSQL_* environment variables or a local .env file.")

        if st.button("Test connection"):
            connection = None

            try:
                connection = get_connection()
                st.success("Connected to MySQL.")
            except Exception as error:
                st.error(f"Connection failed: {error}")
            finally:
                if connection is not None and connection.is_connected():
                    connection.close()


def load_community_area_options():
    """Load community areas from MySQL for the insert dropdown.

    Returns:
        list: Tuples in the format (community_id, community_area_name).

    This helper keeps the database connection code out of the Streamlit form
    itself. The form only needs a simple list of choices.
    """

    conn = None

    try:
        conn = get_connection()

        # get_community_areas() already returns a pandas DataFrame with
        # community_id and name columns.
        community_areas = get_community_areas(conn)

        # Convert the DataFrame rows into simple tuples. The ID is what goes
        # into the database, while the name is what the user sees.
        options = []
        for _, row in community_areas.iterrows():
            options.append((int(row["community_id"]), row["name"]))

        return options
    finally:
        if conn is not None and conn.is_connected():
            conn.close()


def show_insert_housing_unit_section():
    """Show a simple form for adding one affordable housing unit."""

    st.markdown("---")
    st.subheader("Insert Housing Unit")

    try:
        community_area_options = load_community_area_options()
    except Exception as error:
        st.error(f"Could not load community areas: {error}")
        return

    if not community_area_options:
        st.error("No community areas were found in the database.")
        return

    with st.form("insert_housing_unit_form"):
        # All requested fields use text inputs to keep the form simple and
        # beginner-friendly. Numeric values are converted after submission.
        unit_id = st.text_input("Unit ID")

        selected_community_area = st.selectbox(
            "Community area",
            options=community_area_options,
            format_func=lambda option: option[1],
        )

        property_name = st.text_input("Property name")
        property_type = st.text_input("Property type")
        units = st.text_input("Units")
        address = st.text_input("Address")
        management_company = st.text_input("Management company (optional)")

        submitted = st.form_submit_button("Insert Housing Unit")

    if submitted:
        conn = None

        try:
            # Convert text input values into the integer types expected by the
            # database insert function.
            unit_id_value = int(unit_id)
            units_value = int(units)
            community_id = selected_community_area[0]

            # Treat a blank optional field as NULL in the database.
            if management_company.strip() == "":
                management_company_value = None
            else:
                management_company_value = management_company

            conn = get_connection()
            insert_housing_unit(
                conn,
                unit_id=unit_id_value,
                community_id=community_id,
                property_name=property_name,
                property_type=property_type,
                units=units_value,
                address=address,
                management_company=management_company_value,
            )

            st.success("Housing unit inserted successfully.")
        except Exception as error:
            st.error(f"Insert failed: {error}")
        finally:
            if conn is not None and conn.is_connected():
                conn.close()


def main():
    """Render the Streamlit dashboard."""

    st.set_page_config(
        page_title="Chicago Neighborhood Explorer",
        page_icon="C",
        layout="wide",
    )

    st.title("Chicago Neighborhood Explorer")
    st.write(
        "Welcome! Use this dashboard to explore Chicago neighborhoods by "
        "housing, transit, crime, demographics, and service response patterns."
    )

    st.sidebar.header("Query Controls")

    # The selectbox displays friendly labels, while selected_query_key keeps
    # the stable internal key used by widgets.py and QUERY_FUNCTIONS.
    selected_query_key = st.sidebar.selectbox(
        "Choose a query",
        options=list(QUERY_OPTIONS.keys()),
        format_func=lambda key: QUERY_OPTIONS[key]["label"],
    )

    selected_query = QUERY_OPTIONS[selected_query_key]

    st.subheader(selected_query["label"])
    st.write(selected_query["description"])

    st.markdown("### Parameters")
    params = build_parameter_widgets(selected_query_key)

    run_query = st.button("Run Query", type="primary")

    if run_query:
        try:
            # Use a shorter local name inside this block so the dispatch line
            # reads the same way for every query.
            query_key = selected_query_key

            with st.spinner("Running SQL query..."):
                results = execute_query(query_key, params)

            st.markdown("### Results")
            st.dataframe(results, use_container_width=True)
        except Exception as error:
            st.error(f"Query failed: {error}")
    else:
        st.info("Select parameters, then click Run Query to see results.")

    show_database_status()
    show_insert_housing_unit_section()


if __name__ == "__main__":
    main()
