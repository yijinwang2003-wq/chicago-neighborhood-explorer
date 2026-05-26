"""Shared configuration for the Streamlit app.

This file should contain values that are reused across the frontend, such as
query labels, query descriptions, and fixed dropdown options.
"""


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
        "description": "Find affordable housing developments within a selected distance of CTA rail stations.",
    },
    "q3_transit_usage": {
        "label": "Q3 Transit Usage",
        "description": "Compare 2025 transit usage by neighborhood.",
    },
    "q5_high_demand_efficient": {
        "label": "Q5 High Demand + Efficient",
        "description": "Find 2025 areas with strong demand and efficient service response.",
    },
    "q6_most_accessible": {
        "label": "Q6 Most Accessible",
        "description": "Rank the most transit-accessible neighborhoods.",
    },
    "q7_crime_near_housing": {
        "label": "Q7 Crime Near Housing",
        "description": "Compare 2025 crime patterns near affordable housing.",
    },
    "q8_transit_popularity": {
        "label": "Q8 Transit Popularity",
        "description": "Rank 2025 transit popularity.",
    },
    "q9_service_delays": {
        "label": "Q9 Service Delays",
        "description": "Find 2025 neighborhoods with the longest service delay patterns.",
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
    "q14_ward_overlap": {
        "label": "Q14 Ward Overlap",
        "description": "Show which community areas overlap with a selected ward.",
    },
}
