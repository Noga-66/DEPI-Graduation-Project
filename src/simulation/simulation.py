import os
import time
import random
import psycopg2
import math
from datetime import datetime, timezone
from dotenv import load_dotenv
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(dotenv_path=BASE_DIR / ".env")

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "sensor_telemetry")
DB_USER = os.getenv("DB_USER", "depi_admin")
DB_PASSWORD = os.getenv("DB_PASSWORD", "admin_password")

def get_db_connection():
    return psycopg2.connect(
        host=DB_HOST, port=DB_PORT, database=DB_NAME, user=DB_USER, password=DB_PASSWORD
    )

def get_solar_irradiance(hour):
    """Simulate solar irradiance based on hour of day (peak at noon)."""
    if 6 <= hour <= 18:
        return max(0, 1000 * math.sin((hour - 6) * math.pi / 12) + random.uniform(-50, 50))
    return 0.0

def simulate_and_insert():
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        ts = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        hour = datetime.now(timezone.utc).hour

        wind_speed = random.uniform(5.0, 15.0)
        vibration_freq = random.uniform(20.0, 50.0)
        blade_pitch = random.uniform(10.0, 20.0)
        oil_temp = random.uniform(60.0, 80.0)
        power_deviation = random.uniform(-50.0, 50.0)
        wind_direction_sin = random.uniform(-1.0, 1.0)
        wind_direction_cos = random.uniform(-1.0, 1.0)
        
        cursor.execute("""
            INSERT INTO wind_telemetry 
            (ts, turbine_id, wind_speed, vibration_freq, blade_pitch, oil_temp, power_deviation, wind_direction_sin, wind_direction_cos) 
            VALUES (%s, 1, %s, %s, %s, %s, %s, %s, %s)
        """, (ts, wind_speed, vibration_freq, blade_pitch, oil_temp, power_deviation, wind_direction_sin, wind_direction_cos))
        
        wind_log = f"[Wind Node] Sent -> {{'ts': '{ts}', 'turbine_id': 1, 'wind_speed': {wind_speed:.2f}, 'vibration_freq': {vibration_freq:.2f}}}"

        # --- WEATHER TELEMETRY ---
        temperature = random.uniform(15.0, 30.0)
        humidity = random.uniform(40.0, 70.0)
        pressure = random.uniform(1010.0, 1020.0)
        cloud_cover = random.uniform(0.0, 30.0)
        wind_gust = wind_speed + random.uniform(0.0, 5.0)
        
        cursor.execute("""
            INSERT INTO weather_telemetry 
            (ts, region_id, temperature, humidity, pressure, cloud_cover, wind_gust) 
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (ts, 'Cairo_Grid_1', temperature, humidity, pressure, cloud_cover, wind_gust))
        
        weather_log = f"[Weather Node] Sent -> {{'ts': '{ts}', 'region_id': 'Cairo_Grid_1', 'temperature': {temperature:.1f}, 'cloud_cover': {cloud_cover:.1f}}}"

        # --- SOLAR TELEMETRY ---
        irradiance = get_solar_irradiance(hour)
        ambient_temp = temperature + random.uniform(0, 5)
        voltage = (irradiance * 0.08) + random.uniform(-2, 2)
        string_current = (irradiance * 0.1) + random.uniform(-1, 1)
        
        cursor.execute("""
            INSERT INTO solar_telemetry 
            (ts, panel_id, voltage, string_current, irradiance, ambient_temp) 
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (ts, '1BY6WEcLGh8j5v7', max(0, voltage), max(0, string_current), max(0, irradiance), ambient_temp))
        
        solar_log = f"[Solar Node] Sent -> {{'ts': '{ts}', 'panel_id': '1BY6WEcLGh8j5v7', 'irradiance': {irradiance:.2f}, 'ambient_temp': {ambient_temp:.1f}}}"
        
        conn.commit()
        
        logger.info(wind_log)
        logger.info(weather_log)
        logger.info(solar_log)
        logger.info("-" * 50)

    except Exception as e:
        logger.error(f"Simulation Error: {e}")
        if conn:
            conn.rollback()
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

if __name__ == "__main__":
    logger.info("Starting Synchronized Telemetry Simulation...")
    while True:
        simulate_and_insert()
        time.sleep(10)  