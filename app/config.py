"""Shared configuration for the Streamlit app.

This file should contain values that are reused across the frontend, such as
query labels, query descriptions, and fixed dropdown options.
"""


# The dashboard uses the same year choices in several queries.
YEARS = list(range(2020, 2027))
DEFAULT_YEAR_INDEX = YEARS.index(2024)


# User-friendly day names from the app, mapped to the compact codes used by
# the CTA ridership data and future SQL query function.
DAY_TYPE_OPTIONS = {
    "Weekday": "W",
    "Saturday": "A",
    "Sunday/Holiday": "U",
}


# Each query has a stable internal key, a user-facing label, and a short
# description.  The stable keys make it easier to connect each selection to a
# real function in queries.py later.
QUERY_OPTIONS = {
    "q1_affordable_safe": {
        "label": "Q1 Affordable + Safe",
        "description": "Find neighborhoods with affordable housing and lower safety risk.",
    },
    "q2_housing_near_transit": {
        "label": "Q2 Housing Near Transit",
        "description": "Find neighborhoods with housing options near CTA access.",
    },
    "q3_transit_usage": {
        "label": "Q3 Transit Usage",
        "description": "Compare transit usage by selected year and day type.",
    },
    "q5_high_demand_efficient": {
        "label": "Q5 High Demand + Efficient",
        "description": "Find areas with strong demand and efficient service response.",
    },
    "q6_most_accessible": {
        "label": "Q6 Most Accessible",
        "description": "Rank the most transit-accessible neighborhoods.",
    },
    "q7_crime_near_housing": {
        "label": "Q7 Crime Near Housing",
        "description": "Compare crime patterns near affordable housing.",
    },
    "q8_transit_popularity": {
        "label": "Q8 Transit Popularity",
        "description": "Rank neighborhoods by transit popularity.",
    },
    "q9_service_delays": {
        "label": "Q9 Service Delays",
        "description": "Find neighborhoods with the longest service delay patterns.",
    },
    "q10_demographics_vs_crime": {
        "label": "Q10 Demographics vs Crime",
        "description": "Compare demographic indicators with crime levels.",
    },
    "q11_neighborhood_ranking": {
        "label": "Q11 Neighborhood Ranking",
        "description": "Show an overall ranked list of neighborhoods.",
    },
    "q12_housing_availability": {
        "label": "Q12 Housing Availability",
        "description": "Summarize affordable housing availability.",
    },
    "q14_peak_transit_days": {
        "label": "Q14 Peak Transit Days",
        "description": "Find peak transit days for a selected year.",
    },
}
