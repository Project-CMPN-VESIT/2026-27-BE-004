# WaterWallet research visualisations

Generated from `WaterWallet_Research_Visualisations.ipynb` on 2026-10-27T18:05:12.613961+00:00.

## Successfully generated
- `waterwallet_figures/fig1_monthly_rainfall_seasonality.png`
- `waterwallet_figures/fig2_holdout_actual_vs_predicted.png`
- `waterwallet_figures/fig3_model_metrics_comparison.png`
- `waterwallet_figures/fig4_autosarima_12_month_forecast.png`
- `waterwallet_figures/fig5_tank_capacity_sensitivity.png` (controlled engineering sensitivity)

## Data and evaluation
Observed daily precipitation is sourced from the documented Open-Meteo request recorded in `metadata.json`. The expected 2010-01-01 to 2025-12-31 window contains 5,844 days and aggregates to 192 months. The chronological holdout is 2022-01 through 2025-12. Metrics are calculated from the predictions saved in `holdout_actual_and_predictions_2022_2025.csv`.

Auto-SARIMA follows the current backend service's bounded AIC search. The prior paper's benchmark used a different, unconstrained notebook call, so previous reported metrics are comparison references only—not targets.

## Re-run
Run the notebook from the repository root with a Python environment containing pandas, NumPy, Matplotlib, requests, scikit-learn, pmdarima, and the backend dependencies. It reuses the saved daily CSV when present; delete that CSV only if you intentionally want to retrieve a fresh Open-Meteo response.

## Limitations
The forecast is based on gridded/reanalysis precipitation, not a roof gauge. Forecast intervals are model-based, not guarantees. The capacity figure is a documented controlled simulation using the production daily water balance; it is not a field measurement or tank recommendation.
