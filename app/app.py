"""Main Streamlit app for the Chicago Neighborhood Explorer project.

This file is intentionally focused on page layout and user flow.  Supporting
details live in nearby modules:
    config.py        query labels and shared constants
    widgets.py       Streamlit parameter widgets
    api_client.py    FastAPI HTTP client helper
"""

import streamlit as st

from api_client import (
    create_service_request,
    get_neighborhoods,
    health,
    run_query,
)
from config import QUERY_OPTIONS
from widgets import build_parameter_widgets


def execute_query(query_key, params):
    """Run the selected query through the FastAPI backend.

    Args:
        query_key (str): Stable key selected in the sidebar.
        params (dict): Values collected by widgets.py for that query.

    Returns:
        pandas.DataFrame: Results returned by the API.
    """
    return run_query(query_key, params)


def show_database_status():
    """Show a small optional backend connection test in the sidebar.

    This button is only a quick helper for checking whether the API and its
    database connection are available.
    """

    with st.sidebar.expander("Database connection"):
        st.caption("Uses MYSQL_* environment variables or a local .env file.")

        if st.button("Test connection"):
            try:
                result = health()
                st.success(f"Connected to MySQL through API: {result['database']}.")
            except Exception as error:
                st.error(f"Connection failed: {error}")


def load_community_area_options():
    """Load community areas from the FastAPI backend for the service request dropdown.

    Returns:
        list: Tuples in the format (community_id, community_area_name).

    This helper keeps the API response shape out of the Streamlit form
    itself. The form only needs a simple list of choices.
    """
    community_areas = get_neighborhoods()
    options = []
    for row in community_areas:
        options.append((int(row["community_id"]), row["community_name"]))

    return options


def show_insert_service_request_section():
    """Show a simple form for adding one 311 service request."""

    st.subheader("Insert Service Request")

    try:
        community_area_options = load_community_area_options()
    except Exception as error:
        st.error(f"Could not load community areas: {error}")
        return

    if not community_area_options:
        st.error("No community areas were found in the database.")
        return

    with st.form("insert_service_request_form"):
        request_type = st.text_input("Request type", value="Street Light Out")

        selected_community_area = st.selectbox(
            "Community area",
            options=community_area_options,
            format_func=lambda option: option[1],
        )

        status = st.text_input("Status", value="Open")

        submitted = st.form_submit_button("Insert Service Request")

    if submitted:
        try:
            community_id = selected_community_area[0]
            create_service_request(
                community_id=community_id,
                request_type=request_type,
                status=status,
            )

            st.success("Service request inserted successfully.")
        except Exception as error:
            st.error(f"Insert failed: {error}")


def show_query_section():
    """Show the query picker, parameter widgets, and results table."""

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
            st.dataframe(results, width="stretch")
        except Exception as error:
            st.error(f"Query failed: {error}")
    else:
        st.info("Select parameters, then click Run Query to see results.")


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

    st.sidebar.header("Navigation")
    selected_page = st.sidebar.radio(
        "Choose a page",
        ["Run Queries", "Insert Service Request"],
    )

    if selected_page == "Run Queries":
        show_query_section()
    else:
        show_insert_service_request_section()

    show_database_status()


if __name__ == "__main__":
    main()
