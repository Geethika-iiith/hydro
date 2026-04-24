# Himayat Sagar Flood Management 

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/ashurudra09/hydro-final-project)

## Project Overview
This repository contains the Himayat Sagar Flood Management Dashboard, serving as a decision support system for flood management. The pipeline aims to predict the advent of floods by analyzing the water level increase/decrease at Himayat Sagar, utilizing predicted rainfall, runoff models, and geographic data.

## Pipeline Conceptual Validation
The entire end-to-end pipeline has been reviewed conceptually and validated:
1. **General Data Integration**: Uses LULC (for runoff coefficients/CN), DEM (for elevation), and geospatial vector boundaries.
2. **Rainfall Predictor (ML Model)**: Open-Meteo historical data trains an Autoregressive sequence (T-2, T-1, T -> T+1) using Linear Regression to predict the upcoming day's precipitation.
3. **Runoff Estimation**: Employs the SCS-CN (Soil Conservation Service Curve Number) formula, which correctly calculates estimated discharge from precipitation. Specifically `(P - Ia)^2 / (P - Ia + S)` optimized with locally valid optimal Curve Number and Initial Abstraction bounds.
4. **Water Level Change**: Using the peak Runoff mapping integrated with Himayat Sagar surface area constants (`24.0 km²`) against the total catchment basin volume (`1358.53 km²`).
5. **Flood Prediction Alert System**: Triggers distinct alerts based on quantitative water level increment rules (>0.5m = Warning, >2.0m = Critical/Evacuation).

## Latest Updates
- Checked formula-based predictions (CS-SCN). Algebraic formulations align perfectly with standardized hydrological methods.
- Added and validated the `/api/predict_custom` POST endpoint for "sandbox" custom rainfall testing. 

## Structure
- `/backend`: FastAPI Python backend for models and APIs. 
- `/frontend`: React + Leaflet UI Dashboard.
- `/hydro_code`: Legacy/vanilla HTML interactive dashboards.
