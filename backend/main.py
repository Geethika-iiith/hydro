import math
import httpx
import pandas as pd
import numpy as np
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from scipy.optimize import minimize
from sklearn.linear_model import LinearRegression
import warnings
import os
import joblib
warnings.filterwarnings('ignore')

app = FastAPI(title="Himayat Sagar Flood Management API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Constants & Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
RAIN_CSV = os.path.join(DATA_DIR, "rainfall_2020.csv")
FLOW_CSV = os.path.join(DATA_DIR, "observed_flow.csv")

# Model state
optimal_cn = 82.0
optimal_lambda = 0.2
model_rmse = 0.0

from sklearn.ensemble import RandomForestRegressor
rainfall_predictor = None
predictor_ready = False
MODEL_PATH = os.path.join(BASE_DIR, "rf_model.pkl")

# Watershed parameters (Verified by Hiten)
AREA_KM2 = 264.597
AREA_M2 = AREA_KM2 * 1e6
DAM_SURFACE_AREA_KM2 = 24.0
DAM_SURFACE_AREA_M2 = DAM_SURFACE_AREA_KM2 * 1e6


def calculate_runoff(P, CN, lambda_ia):
    if CN <= 0 or CN > 100:
        return 0.0
    S = (25400.0 / CN) - 254.0
    Ia = lambda_ia * S
    if P > Ia:
        return ((P - Ia) ** 2) / (P + (1 - lambda_ia) * S)
    return 0.0


def calculate_hydrological_metrics(CN, lambda_ia, rain_data, obs_data):
    seconds_in_month = 30 * 24 * 3600
    simulated_flows = []
    
    for P in rain_data:
        Q_mm = calculate_runoff(P, CN, lambda_ia)
        Q_m = Q_mm / 1000.0
        volume = Q_m * AREA_M2
        discharge = volume / seconds_in_month
        simulated_flows.append(discharge)
    
    simulated_flows = np.array(simulated_flows)
    obs_data = np.array(obs_data)
    rmse = np.sqrt(np.mean((simulated_flows - obs_data) ** 2))
    return rmse, simulated_flows


@app.on_event("startup")
async def startup_event():
    global optimal_cn, optimal_lambda, model_rmse, predictor_ready, rainfall_predictor
    
    # 1. Optimize Model Parameters (Assignment 3 Polish)
    try:
        rain_df = pd.read_csv(RAIN_CSV)
        flow_df = pd.read_csv(FLOW_CSV)
        rain_vals = rain_df['Rainfall'].values
        obs_vals = flow_df['Observed'].values
        
        def objective(x):
            return calculate_hydrological_metrics(x[0], x[1], rain_vals, obs_vals)[0]
        
        # Initial guess and bounds: CN [50, 95], Lambda [0.05, 0.3]
        res = minimize(objective, [75, 0.2], bounds=[(50, 95), (0.05, 0.3)], method='L-BFGS-B')
        optimal_cn = res.x[0]
        optimal_lambda = res.x[1]
        model_rmse = res.fun
        print(f"Optimized Parameters: CN = {optimal_cn:.2f}, Lambda = {optimal_lambda:.3f}, RMSE = {model_rmse:.2f} m3/s")
    except Exception as e:
        print(f"Error optimizing model: {e}")

    # 2. Train or Load Improved Rainfall Predictor (Aniket's RF Model)
    try:
        if os.path.exists(MODEL_PATH):
            rainfall_predictor = joblib.load(MODEL_PATH)
            predictor_ready = True
            print("Successfully loaded RandomForest model from rf_model.pkl")
        else:
            async with httpx.AsyncClient() as client:
                res = await client.get(
                    "https://archive-api.open-meteo.com/v1/archive?latitude=17.33&longitude=78.30&start_date=2020-01-01&end_date=2024-01-01&daily=precipitation_sum&timezone=auto"
                )
                data = res.json()["daily"]["precipitation_sum"]
                # Fill Nones with 0
                data = [0 if v is None else v for v in data]
                
                # Create pairs (T-3, T-2, T-1) -> T (Improved context)
                X, Y = [], []
                for i in range(3, len(data) - 1):
                    X.append([data[i-3], data[i-2], data[i-1]])
                    Y.append(data[i])
                
                if X and Y:
                    rainfall_predictor = RandomForestRegressor(n_estimators=150, max_depth=10, random_state=42)
                    rainfall_predictor.fit(X, Y)
                    joblib.dump(rainfall_predictor, MODEL_PATH)
                    predictor_ready = True
                    print("Rainfall predictor model trained successfully and saved to rf_model.pkl.")
    except Exception as e:
        print(f"Error handling rainfall predictor: {e}")


@app.get("/api/model_info")
def get_model_info():
    """Returns the improved Assignments 2 & 3 model details."""
    return {
        "optimized_cn": optimal_cn,
        "optimized_lambda": optimal_lambda,
        "rmse": model_rmse,
        "area_km2": AREA_KM2,
        "dam_area_km2": DAM_SURFACE_AREA_KM2
    }


@app.get("/api/pipeline")
async def run_pipeline():
    """
    Executes the continuous pipeline requested:
    - Get last 3 days weather
    - Predict today's/tomorrow's precipitation
    - Run modified CS-SCN runoff model
    - Calculate Dam Water Level Increase
    - Issue Alert
    """
    
    # 1. Fetch current and previous 2 days weather
    try:
        async with httpx.AsyncClient() as client:
            res = await client.get(
                "https://api.open-meteo.com/v1/forecast?latitude=17.33&longitude=78.30&daily=precipitation_sum&past_days=3&forecast_days=1&timezone=auto"
            )
            data = res.json()
            precip = data["daily"]["precipitation_sum"]
            # precip length is 4: [T-3, T-2, T-1, Today]
            past_3_days = precip[:3]
            actual_today = precip[3]
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to fetch weather data")
    
    # 2. Predict Precipitation using the trained AR model
    predicted_precip = 0.0
    if predictor_ready:
        predicted_precip = max(0.0, rainfall_predictor.predict([past_3_days])[0])
    else:
        # Fallback heuristic
        predicted_precip = sum(past_3_days) / len(past_3_days) if past_3_days else 0.0
    
    # Let's consider a generic storm event by compounding actual and predicted
    design_rainfall = max(predicted_precip, actual_today) * 1.5 # Add safely factory
    
    # 3. Simulate Runoff Area (Assignment 2 + 3 combined)
    runoff_mm = calculate_runoff(design_rainfall, optimal_cn, optimal_lambda)
    
    # 4. Impact on Himayat Sagar
    # Volume in m3 = Runoff (m) * Area (m2)
    volume_m3 = (runoff_mm / 1000.0) * AREA_M2
    
    # Water Level Increase = Volume / Dam Surface Area
    water_level_increase_m = volume_m3 / DAM_SURFACE_AREA_M2
    
    # 5. Alert Logic
    alert_status = "OKAY"
    alert_color = "Green"
    message = "Water level okay, no action required."
    
    if water_level_increase_m > 2.0:
        alert_status = "CRITICAL"
        alert_color = "Red"
        message = "High likelihood of flooding, evacuate the area immediately!"
    elif water_level_increase_m > 0.5:
        alert_status = "WARNING"
        alert_color = "Yellow"
        message = "Water level increasing beyond safe level, prepare to open dam gates."
        
    return {
        "weather_data": {
            "past_3_days_precipitation_mm": past_3_days,
            "actual_today_precipitation_mm": actual_today,
            "predicted_precipitation_mm": predicted_precip,
            "design_rainfall_used_mm": design_rainfall
        },
        "model_parameters": {
            "cn": optimal_cn,
            "lambda_ia": optimal_lambda
        },
        "simulation": {
            "runoff_mm": runoff_mm,
            "inflow_volume_m3": volume_m3,
            "dam_water_level_increase_meters": water_level_increase_m
        },
        "alert": {
            "level": alert_status,
            "color": alert_color,
            "message": message
        }
    }

class CustomPredictionRequest(BaseModel):
    rainfall_mm: float
    cn: float = None
    lambda_ia: float = None

@app.post("/api/predict_custom")
def predict_custom(request: CustomPredictionRequest):
    """
    Sandbox prediction page API endpoint: Allows custom rainfall, cn, lambda input 
    and predicts runoff and water level increase
    """
    cn = request.cn if request.cn is not None else optimal_cn
    lambda_ia = request.lambda_ia if request.lambda_ia is not None else optimal_lambda
    
    runoff_mm = calculate_runoff(request.rainfall_mm, cn, lambda_ia)
    volume_m3 = (runoff_mm / 1000.0) * AREA_M2
    water_level_increase_m = volume_m3 / DAM_SURFACE_AREA_M2
    
    return {
        "input": {
            "rainfall_mm": request.rainfall_mm,
            "cn": cn,
            "lambda_ia": lambda_ia
        },
        "simulation": {
            "runoff_mm": runoff_mm,
            "inflow_volume_m3": volume_m3,
            "dam_water_level_increase_meters": water_level_increase_m
        }
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
