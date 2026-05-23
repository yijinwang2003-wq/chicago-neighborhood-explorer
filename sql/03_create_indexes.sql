CREATE INDEX idx_crime_community_date
    ON CrimeRecord (community_id, crime_date);

CREATE INDEX idx_housing_community
    ON HousingDevelopment (community_id);

CREATE INDEX idx_station_community
    ON CTARailStation (community_id);

CREATE INDEX idx_ridership_month_station
    ON RailRidershipMonthly (month_beginning, station_id);

CREATE INDEX idx_service_source_date_community
    ON ServiceRequest (record_source, created_date, community_id, closed_date);
