import os
import uvicorn
import psycopg2
import psycopg2.extras
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types
from fastapi import FastAPI, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from inference import (
    detect_wind_anomaly, 
    detect_solar_anomaly,
    predict_wind_power,
    predict_solar_yield,
    predict_grid_demand
)
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import FAISS
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(dotenv_path=BASE_DIR / ".env")

VECTOR_STORE_PATH = os.getenv("VECTOR_STORE_PATH", str(BASE_DIR / "Models" / "vector_store"))

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "sensor_telemetry")
DB_USER = os.getenv("DB_USER", "depi_admin")
DB_PASSWORD = os.getenv("DB_PASSWORD", "admin_password")

api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    raise RuntimeError("CRITICAL: GOOGLE_API_KEY is not set.")

client = genai.Client(api_key=api_key)
GEMINI_MODEL = "gemini-flash-latest"

knowledge_base = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global knowledge_base
    logger.info("Booting DEPI Grid API Orchestrator")
    try:
        embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")
        knowledge_base = FAISS.load_local(
            VECTOR_STORE_PATH, 
            embeddings, 
            allow_dangerous_deserialization=True
        )
        logger.info("Knowledge Base Mounted Successfully.")
    except Exception as e:
        logger.error(f"Vector store failed to load: {e}")
        knowledge_base = None
    
    yield
    knowledge_base = None

app = FastAPI(title="DEPI Grid API Orchestrator", version="1.0", lifespan=lifespan)

class DiagnosticResponse(BaseModel):
    asset_id: str
    asset_type: str
    anomaly_type: str
    shap_explanation: dict
    rag_repair_blueprint: str

class ForecastResponse(BaseModel):
    wind_forecast_kw: float
    solar_forecast_kw: float
    grid_demand_kw: float
    net_grid_status: str

def get_db_connection():
    return psycopg2.connect(
        host=DB_HOST, port=DB_PORT, database=DB_NAME, user=DB_USER, password=DB_PASSWORD,connect_timeout = 10
    )

def _rows_to_dicts(rows) -> list:
    """Safely convert RealDictRow to standard dict for inference pipeline."""
    return [dict(row) for row in rows] if rows else []

@app.get("/")
def health_check():
    return {"status": "DEPI Grid API Orchestrator is active and monitoring."}

@app.get("/grid/live")
def get_live_telemetry():
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("""
            SELECT ts, turbine_id as asset_id, wind_speed, vibration_freq, blade_pitch, 'wind' as type 
            FROM (SELECT * FROM wind_telemetry ORDER BY ts DESC LIMIT 30) sub
            ORDER BY ts ASC;
        """)
        wind_data = _rows_to_dicts(cursor.fetchall())

        cursor.execute("""
            SELECT ts, panel_id as asset_id, voltage, string_current, irradiance, 'solar' as type 
            FROM (SELECT * FROM solar_telemetry ORDER BY ts DESC LIMIT 30) sub
            ORDER BY ts ASC;
        """)
        solar_data = _rows_to_dicts(cursor.fetchall())
        
        return {"data": wind_data + solar_data}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

@app.get("/grid/forecast", response_model=ForecastResponse)
def get_grid_forecast():
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        cursor.execute("SELECT * FROM (SELECT * FROM wind_telemetry ORDER BY ts DESC LIMIT 24) sub ORDER BY ts ASC;")
        wind_data = _rows_to_dicts(cursor.fetchall())
        
        cursor.execute("SELECT * FROM (SELECT * FROM solar_telemetry ORDER BY ts DESC LIMIT 24) sub ORDER BY ts ASC;")
        solar_data = _rows_to_dicts(cursor.fetchall())
        
        cursor.execute("SELECT * FROM (SELECT * FROM weather_telemetry ORDER BY ts DESC LIMIT 24) sub ORDER BY ts ASC;")
        weather_data = _rows_to_dicts(cursor.fetchall())

        if not wind_data or not solar_data or not weather_data:
            raise HTTPException(status_code=503, detail="Insufficient telemetry data for forecasting.")

        wind_forecast = predict_wind_power(wind_data)
        solar_forecast = predict_solar_yield(solar_data)
        demand_forecast = predict_grid_demand(weather_data)

        total_generation = wind_forecast + solar_forecast
        status = "Surplus" if total_generation >= demand_forecast else "Deficit"

        return ForecastResponse(
            wind_forecast_kw=round(wind_forecast, 2),
            solar_forecast_kw=round(solar_forecast, 2),
            grid_demand_kw=round(demand_forecast, 2),
            net_grid_status=status
        )
        
    except Exception as e:
        logger.error(f"Forecast Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

@app.post("/diagnose/{asset_type}/{asset_id}", response_model=DiagnosticResponse)
async def trigger_diagnostics(asset_type: str, asset_id: str):
    if asset_type not in ("wind", "solar"):
        raise HTTPException(status_code=400, detail="Invalid asset type.")

    if asset_type == "wind":
        try:
            wind_asset_id = int(asset_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Wind asset_id must be numeric.")

    def _fetch_latest():
        conn = None
        cursor = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            if asset_type == "wind":
                cursor.execute(
                    "SELECT * FROM wind_telemetry WHERE turbine_id = %s ORDER BY ts DESC LIMIT 1;",
                    (wind_asset_id,)
                )
            else:
                cursor.execute(
                    "SELECT * FROM solar_telemetry WHERE panel_id = %s ORDER BY ts DESC LIMIT 1;",
                    (str(asset_id),)
                )
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            if cursor: cursor.close()
            if conn: conn.close()

    try:
        latest_data = await run_in_threadpool(_fetch_latest)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if not latest_data:
        raise HTTPException(status_code=404, detail="No telemetry found.")

    if asset_type == "wind":
        is_anomaly, anomaly_reason, shap_data = await run_in_threadpool(detect_wind_anomaly, latest_data)
        context = f"Wind Speed: {latest_data.get('wind_speed')}, Vibration: {latest_data.get('vibration_freq')}, Pitch: {latest_data.get('blade_pitch')}"
    else:
        is_anomaly = await run_in_threadpool(detect_solar_anomaly, latest_data)
        anomaly_reason = "Solar Yield Deviation" if is_anomaly else "Normal"
        shap_data = {"irradiance": "Calculated variance", "ambient_temp": "Calculated variance"}
        context = f"Voltage: {latest_data.get('voltage')}, Current: {latest_data.get('string_current')}, Irradiance: {latest_data.get('irradiance')}"

    if not is_anomaly:
        return DiagnosticResponse(
            asset_id=asset_id,
            asset_type=asset_type,
            anomaly_type="None",
            shap_explanation=shap_data,
            rag_repair_blueprint="System operating within normal parameters. No maintenance required."
        )

    manual_context = ""
    if knowledge_base:
        retrieved_docs = knowledge_base.similarity_search(anomaly_reason, k=4)
        manual_context = "\n\n---\n\n".join([doc.page_content for doc in retrieved_docs])

    prompt = f"""
    You are the Chief Diagnostic AI for the DEPI Renewable Grid. An anomaly has been detected.
    
    **ASSET DETAILS:**
    - Type: {asset_type.capitalize()} Asset
    - ID: {asset_id}
    - Anomaly Flag: {anomaly_reason}
    - Live Telemetry: {context}

    **RETRIEVED TECHNICAL MANUAL EXCERPTS:**
    {manual_context if manual_context else "No specific manual excerpt found. Use general engineering best practices."}

    **YOUR TASK:**
    Based strictly on the manual excerpts and telemetry provided, generate a highly detailed, structured repair blueprint. 
    Do not explain the problem, jump straight to the solution. 

    Format your response EXACTLY like this:

    🔧 **ROOT CAUSE HYPOTHESIS**
    (One concise sentence explaining why the telemetry triggered this anomaly)

    🛠 **REQUIRED TOOLS & SAFETY GEAR**
    - (List 2-3 specific tools or PPE required)

    📝 **STEP-BY-STEP REPAIR BLUEPRINT**
    1. **[Step Name]**: (Detailed technical instruction on what to inspect, adjust, or replace)
    2. **[Step Name]**: (Detailed technical instruction)
    3. **[Step Name]**: (Detailed technical instruction)

    ✅ **POST-REPAIR VALIDATION**
    (One sentence explaining what telemetry values should return to normal after the fix)
    """
    
    try:
        response = await client.aio.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.2,          
                max_output_tokens=2000,   
            ),
        )
        rag_blueprint = response.text
    except Exception as e:
        rag_blueprint = f"Specialist diagnostic offline. Error: {str(e)}"
    return DiagnosticResponse(
        asset_id=asset_id,
        asset_type=asset_type,
        anomaly_type=anomaly_reason,
        shap_explanation=shap_data,
        rag_repair_blueprint=rag_blueprint
    )

@app.post("/grid/inject_anomaly/{asset_type}")
def inject_chaos_anomaly(asset_type: str):
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        future_now = (datetime.now(timezone.utc) + timedelta(seconds=30)).strftime('%Y-%m-%d %H:%M:%S')
        
        if asset_type == "wind":
            cursor.execute("""
                INSERT INTO wind_telemetry 
                (ts, turbine_id, vibration_freq, blade_pitch, wind_speed, oil_temp, power_deviation, wind_direction_sin, wind_direction_cos) 
                VALUES (%s, 1, 185.5, 15.0, 10.0, 85.0, -450.0, 0.5, 0.866)
            """, (future_now,))
        elif asset_type == "solar":
            cursor.execute("""
                INSERT INTO solar_telemetry 
                (ts, panel_id, voltage, string_current, irradiance, ambient_temp) 
                VALUES (%s, '1BY6WEcLGh8j5v7', 12.0, 0.5, 1050.0, 85.0)
            """, (future_now,))
        else:
            raise HTTPException(status_code=400, detail="Invalid chaos asset.")
            
        conn.commit()
        return {"status": "Success"}
    except Exception as e:
        if conn: conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
