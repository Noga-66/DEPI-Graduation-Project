import os
import json
import psycopg2
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime, timezone
from psycopg2.extras import execute_values
from confluent_kafka import Consumer

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(dotenv_path=BASE_DIR / ".env")

KAFKA_BROKER = os.getenv("KAFKA_BROKER", "localhost:9092")
GROUP_ID = "depi_db_writer"
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "sensor_telemetry")
DB_USER = os.getenv("DB_USER", "depi_admin")
DB_PASSWORD = os.getenv("DB_PASSWORD", "admin_password")
BATCH_SIZE = 5 

def start_receiver():
    print("Initializing DEPI Grid Tri-Stream Receiver")
    
    consumer = Consumer({
        'bootstrap.servers': KAFKA_BROKER, 
        'group.id': GROUP_ID, 
        'auto.offset.reset': 'earliest', 
        'enable.auto.commit': False
    })
    
    consumer.subscribe(['wind_telemetry', 'solar_telemetry', 'weather_telemetry'])

    try:
        db_conn = psycopg2.connect(host=DB_HOST, port=DB_PORT, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
        db_cursor = db_conn.cursor()
        print("Connected to TimescaleDB. Listening for Tri-Modal telemetry")
    except Exception as e:
        print(f"Database connection failed: {e}")
        return

    buffers = {
        'wind_telemetry': [],
        'solar_telemetry': [],
        'weather_telemetry': []
    }

    try:
        while True:
            msg = consumer.poll(timeout=1.0)
            if msg is None: 
                continue
            if msg.error(): 
                continue

            payload = json.loads(msg.value().decode('utf-8'))
            live_ts = payload.get('ts') or datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
            topic = msg.topic()

            if topic == 'wind_telemetry':
                record = (
                    live_ts, 
                    payload.get('turbine_id', 1), 
                    payload.get('vibration_freq', 0.0), 
                    payload.get('blade_pitch', 0.0), 
                    payload.get('wind_speed', 0.0), 
                    payload.get('oil_temp', 0.0),
                    payload.get('power_deviation', 0.0),
                    payload.get('wind_direction_sin', 0.0),
                    payload.get('wind_direction_cos', 0.0)
                )
                buffers[topic].append(record)
                
            elif topic == 'solar_telemetry':
                record = (
                    live_ts, 
                    payload.get('panel_id', '1BY6WEcLGh8j5v7'), 
                    payload.get('voltage', 0.0), 
                    payload.get('string_current', 0.0), 
                    payload.get('irradiance', 0.0), 
                    payload.get('ambient_temp', 0.0)
                )
                buffers[topic].append(record)
                
            elif topic == 'weather_telemetry':
                record = (
                    live_ts, 
                    payload.get('region_id', 'Cairo_Grid_1'), 
                    payload.get('temperature', 0.0), 
                    payload.get('humidity', 0.0), 
                    payload.get('pressure', 0.0), 
                    payload.get('cloud_cover', 0.0), 
                    payload.get('wind_gust', 0.0)
                )
                buffers[topic].append(record)

            if len(buffers[topic]) >= BATCH_SIZE:
                if topic == 'wind_telemetry':
                    query = """
                        INSERT INTO wind_telemetry 
                        (ts, turbine_id, vibration_freq, blade_pitch, wind_speed, oil_temp, power_deviation, wind_direction_sin, wind_direction_cos) 
                        VALUES %s
                    """
                elif topic == 'solar_telemetry':
                    query = "INSERT INTO solar_telemetry (ts, panel_id, voltage, string_current, irradiance, ambient_temp) VALUES %s"
                elif topic == 'weather_telemetry':
                    query = "INSERT INTO weather_telemetry (ts, region_id, temperature, humidity, pressure, cloud_cover, wind_gust) VALUES %s"

                try:
                    execute_values(db_cursor, query, buffers[topic])
                    db_conn.commit()
                    consumer.commit(message=msg, asynchronous=False)
                    
                    print(f"Bulk-inserted {len(buffers[topic])} {topic.split('_')[0].upper()} records @ {live_ts}")
                    buffers[topic].clear()
                except Exception as db_err:
                    print(f"DB Insert Error: {db_err}")
                    db_conn.rollback()

    except KeyboardInterrupt:
        print("\nReceiver stopped manually.")
    finally:
        db_cursor.close()
        db_conn.close()
        consumer.close()

if __name__ == "__main__":
    start_receiver()