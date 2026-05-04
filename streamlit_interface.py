import streamlit as st
import pandas as pd
import tensorflow as tf
from sklearn.metrics import mean_absolute_error, mean_squared_error
import numpy as np

st.title("Wind Power Prediction Dashboard")
st.write("Upload wind data to test the model and view prediction errors.")
uploaded_file = st.file_uploader("Upload your wind data (CSV)", type=["csv"])

@st.cache_resource
def load_model():
    return tf.keras.models.load_model('best_model.keras')

model = load_model()

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)
    st.write("### Data Preview", df.head())
    target_col = st.selectbox("Select the actual Power column for error calculation:", df.columns)
    
    feature_cols = [col for col in df.columns if col != target_col]
    X_test = df[feature_cols]
    y_actual = df[target_col]

    if st.button("Run Predictions"):
        predictions = model.predict(X_test)
        df['Predicted_Power'] = predictions
        
        mae = mean_absolute_error(y_actual, predictions)
        rmse = np.sqrt(mean_squared_error(y_actual, predictions))
        
        col1, col2 = st.columns(2)
        col1.metric("Mean Absolute Error (MAE)", f"{mae:.2f}")
        col2.metric("Root Mean Squared Error (RMSE)", f"{rmse:.2f}")

        st.write("### Prediction Results", df[['Predicted_Power', target_col]])
        st.line_chart(df[['Predicted_Power', target_col]])
