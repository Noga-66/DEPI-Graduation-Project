import os
import time
import json
import pandas as pd
import threading
from confluent_kafka import Producer
from datetime import datetime, timezone

KAFKA_BROKER = "localhost:9092"
WIND_TOPIC = "wind_telemetry"
SOLAR_TOPIC = "solar_telemetry"
WEATHER_TOPIC = "weather_telemetry"

WIND_CSV = r"Datasets/Simulation/Wind_Simulation.csv" 
SOLAR_CSV = r"Datasets/Simulation/Solar_Simulation.csv"
WEATHER_CSV = r"Datasets/Simulation/Weather_Simulation.csv"

SIMULATION_SPEED = 1.0  

def delivery_report(err, msg):
    if err is not None:
        print(f"Delivery failed: {err}")

def stream_data(csv_path, topic, stream_name, key_field):
    print(f"Starting {stream_name} Stream from {csv_path}...")
    try:
        df = pd.read_csv(csv_path)
        producer = Producer({'bootstrap.servers': KAFKA_BROKER, 'client.id': f'depi_{stream_name.lower()}'})
        
        while True:  
            for _, row in df.iterrows():
                payload = row.to_dict()
                

                live_ts = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
                payload['ts'] = live_ts
                

                if stream_name == 'Wind':
                    print(f"[{stream_name}] -> Turbine: {payload.get('turbine_id', 1)} | Speed: {payload.get('wind_speed', 0)} | Vib: {payload.get('vibration_freq', 0)}")
                elif stream_name == 'Solar':
                    print(f"[{stream_name}] -> Panel: {payload.get('panel_id', 1)} | DC Power: {payload.get('voltage', 0)} | Irrad: {payload.get('irradiance', 0)}")
                elif stream_name == 'Weather':
                    print(f"[{stream_name}] -> Region: {payload.get('region_id', 'Grid')} | Temp: {payload.get('temperature', 0)}C | Clouds: {payload.get('cloud_cover', 0)}%")
                
                partition_key = str(payload.get(key_field, '1')).encode('utf-8')
                
                producer.produce(
                    topic=topic, 
                    key=partition_key, 
                    value=json.dumps(payload).encode('utf-8'), 
                    callback=delivery_report
                )
                producer.poll(0)
                time.sleep(SIMULATION_SPEED)
                
            print(f"--- {stream_name} Stream reached end of CSV. Looping simulation... ---")
            
    except Exception as e:
        print(f"{stream_name} Stream Error: {e}")

def start_multi_sender():
    print("Initializing DEPI Grid Tri-Stream Engine...")
    threads = [
        threading.Thread(target=stream_data, args=(WIND_CSV, WIND_TOPIC, 'Wind', 'turbine_id'), daemon=True),
        threading.Thread(target=stream_data, args=(SOLAR_CSV, SOLAR_TOPIC, 'Solar', 'panel_id'), daemon=True),
        threading.Thread(target=stream_data, args=(WEATHER_CSV, WEATHER_TOPIC, 'Weather', 'region_id'), daemon=True)
    ]
    for t in threads: t.start()
    for t in threads: t.join()

if __name__ == "__main__":
    start_multi_sender()
