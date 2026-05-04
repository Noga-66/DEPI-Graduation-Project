import streamlit as st
import pandas as pd
import numpy as np
import keras
import joblib
from sklearn.metrics import mean_absolute_error, mean_squared_error

st.set_page_config(page_title="Wind Power Prediction", layout="wide")
st.title("Wind Power Prediction Dashboard")


FEATURES = [
    'Wind Speed (m/s)', 'Theoretical_Power_Curve (KWh)', 'Wind Direction (°)', 
    'hour', 'day_of_week', 'month', 'day_of_year', 
    'wind_direction_sin', 'wind_direction_cos', 'power_deviation'
]

@st.cache_resource
def load_assets():
    loaded_model: keras.Model = keras.models.load_model('best_model.keras') # type: ignore
    loaded_scaler = joblib.load('scaler_X.pkl') 
    return loaded_model, loaded_scaler

model, scaler = load_assets()
input_method = st.radio("Choose Input Method:", ("Upload CSV", "Manual Entry"))

X_processed = None
y_actual = None

if input_method == "Upload CSV":
    uploaded_file = st.file_uploader("Upload wind data (CSV)", type=["csv"])
    if uploaded_file:
        df = pd.read_csv(uploaded_file)
        target_col = st.selectbox("Select Actual Power Column:", df.columns)
        
        num_seq = len(df) // 144
        if num_seq > 0:
            X_raw = df[FEATURES].iloc[:num_seq * 144]
            X_scaled = scaler.transform(X_raw) 
            X_processed = X_scaled.reshape(num_seq, 144, 10)
            y_actual = df[target_col].values[143::144][:num_seq]
        else:
            st.error("CSV must have at least 144 rows.")

else:
    st.write("### Manual Entry")
    manual_data = {f: st.number_input(f, value=0.0) for f in FEATURES}
    single_row = pd.DataFrame([manual_data])[FEATURES]
    single_scaled = scaler.transform(single_row)
    X_processed = np.repeat(single_scaled[np.newaxis, :, :], 144, axis=1)

if st.button("Run Prediction"):
    if model is not None and X_processed is not None:
        try:
            raw_preds = model.predict(X_processed, verbose="0")
            predictions = np.array(raw_preds).flatten() * 3600 
            
            if input_method == "Manual Entry":
                st.success(f"Rescaled Predicted Power: {predictions[0]:.2f} kW")
            else:
                res_df = pd.DataFrame({'Actual': y_actual, 'Predicted': predictions})
                mae = mean_absolute_error(res_df['Actual'], res_df['Predicted'])
                st.metric("MAE (Rescaled)", f"{mae:.2f}")
                st.line_chart(res_df)
        except Exception as e:
            st.error(f"Prediction Error: {e}")