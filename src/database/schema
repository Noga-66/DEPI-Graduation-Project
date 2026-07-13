-- wind tele.
CREATE TABLE IF NOT EXISTS wind_telemetry (
    ts TIMESTAMPTZ NOT NULL,
    turbine_id INT NOT NULL,
    vibration_freq DOUBLE PRECISION,
    blade_pitch DOUBLE PRECISION,
    wind_speed DOUBLE PRECISION,
    oil_temp DOUBLE PRECISION
);

SELECT create_hypertable('wind_telemetry', 'ts', if_not_exists => TRUE);

-- model insights 
CREATE TABLE IF NOT EXISTS ml_insights (
    ts TIMESTAMPTZ NOT NULL,
    asset_id INT NOT NULL,
    asset_type VARCHAR(50) NOT NULL, -- 'wind' or 'solar'
    forecasted_power DOUBLE PRECISION,
    anomaly_flag BOOLEAN DEFAULT FALSE,
    anomaly_reason TEXT
);

SELECT create_hypertable('ml_insights', 'ts', if_not_exists => TRUE);


CREATE TABLE IF NOT EXISTS solar_telemetry (
    ts TIMESTAMPTZ NOT NULL,
    panel_id VARCHAR(50) NOT NULL,
    voltage DOUBLE PRECISION,
    string_current DOUBLE PRECISION,
    irradiance DOUBLE PRECISION,
    ambient_temp DOUBLE PRECISION
);

SELECT create_hypertable('solar_telemetry', 'ts', if_not_exists => TRUE);

CREATE TABLE IF NOT EXISTS weather_telemetry (
    ts TIMESTAMPTZ NOT NULL,
    region_id VARCHAR(50) NOT NULL,
    temperature DOUBLE PRECISION,
    humidity DOUBLE PRECISION,
    pressure DOUBLE PRECISION,
    cloud_cover DOUBLE PRECISION,
    wind_gust DOUBLE PRECISION
);

SELECT create_hypertable('weather_telemetry', 'ts', if_not_exists => TRUE);

ALTER TABLE wind_telemetry ADD COLUMN power_deviation FLOAT;
ALTER TABLE wind_telemetry ADD COLUMN wind_direction_sin FLOAT;
ALTER TABLE wind_telemetry ADD COLUMN wind_direction_cos FLOAT;
