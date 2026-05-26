USE chicago_neighborhood_explorer;

CREATE INDEX idx_overlap_ward
    ON community_area_ward_overlap (ward_id, pct_of_ward);

CREATE INDEX idx_crime_community_date
    ON crime_records (community_id, crime_date);

CREATE INDEX idx_crime_type_date
    ON crime_records (primary_type, crime_date);

CREATE INDEX idx_housing_community
    ON housing_developments (community_id);

CREATE INDEX idx_housing_coordinates
    ON housing_developments (latitude, longitude);

CREATE INDEX idx_station_community
    ON cta_rail_stations (community_id);

CREATE INDEX idx_ridership_month_station
    ON rail_ridership_monthly (month_beginning, station_id);

CREATE INDEX idx_service_source_date_community
    ON service_requests (record_source, created_date, community_id, closed_date);
