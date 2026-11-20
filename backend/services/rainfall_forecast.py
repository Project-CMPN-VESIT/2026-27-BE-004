
"""Auto-SARIMA rainfall forecasting service."""

from copy import deepcopy
from functools import lru_cache
from typing import Any

import numpy as np


def forecast_monthly_rainfall(
    history: list[float],
    periods: int = 12,
) -> dict[str, Any]:
    """
    Forecast future monthly rainfall using seasonal Auto-SARIMA.

    `history` must contain consecutive monthly rainfall totals in
    chronological order, from oldest to newest, measured in millimetres.

    The function validates the supplied values but cannot detect missing
    calendar months because the existing API passes rainfall values without
    their associated dates.
    """

    if periods < 1 or periods > 24:
        raise ValueError("Forecast horizon must be between 1 and 24 months.")

    if len(history) < 36:
        raise ValueError(
            "At least 36 monthly observations are required for "
            "seasonal forecasting."
        )

    try:
        rainfall = np.asarray(history, dtype=float)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "Rainfall history must contain numeric monthly values."
        ) from exc

    if rainfall.ndim != 1:
        raise ValueError("Rainfall history must be a one-dimensional list.")

    if not np.isfinite(rainfall).all():
        raise ValueError(
            "Rainfall history contains missing or non-finite values. "
            "Resolve missing observations before forecasting."
        )

    if (rainfall < 0).any():
        raise ValueError("Rainfall values cannot be negative.")

    return deepcopy(_forecast_validated_history(tuple(float(value) for value in rainfall), periods))


@lru_cache(maxsize=32)
def _forecast_validated_history(history: tuple[float, ...], periods: int) -> dict[str, Any]:
    """Reuse a fitted forecast when the same rainfall series is requested again."""
    try:
        from pmdarima import auto_arima
    except ImportError as exc:
        raise RuntimeError(
            "Auto-SARIMA is unavailable because pmdarima is not installed. "
            "Install backend requirements and restart the API."
        ) from exc

    search_options = {
        "seasonal": True,
        "m": 12,
        "start_p": 1,
        "start_q": 1,
        "max_p": 5,
        "max_q": 5,
        "start_P": 1,
        "start_Q": 1,
        "max_P": 2,
        "max_Q": 2,
        "max_order": 5,
        "stepwise": True,
        "information_criterion": "aic",
        "with_intercept": "auto",
        "maxiter": 50,
        "suppress_warnings": True,
        "error_action": "ignore",
    }

    try:
        model = auto_arima(history, **search_options)
    except ValueError as exc:
        # Retry only with constrained differencing if the original search
        # fails. Do not hide unrelated failures by returning fake values.
        try:
            model = auto_arima(
                history,
                d=0,
                D=0,
                **search_options,
            )
        except Exception as retry_exc:
            raise RuntimeError(
                "Auto-SARIMA could not fit the rainfall history. "
                "Check the monthly data and model dependencies."
            ) from retry_exc

    try:
        forecast, confidence_interval = model.predict(
            n_periods=periods,
            return_conf_int=True,
            alpha=0.05,
        )
    except Exception as exc:
        raise RuntimeError(
            "Auto-SARIMA failed while generating the rainfall forecast."
        ) from exc

    forecast = np.asarray(forecast, dtype=float)
    confidence_interval = np.asarray(confidence_interval, dtype=float)

    if forecast.shape != (periods,):
        raise RuntimeError("Auto-SARIMA returned an unexpected forecast shape.")

    if confidence_interval.shape != (periods, 2):
        raise RuntimeError(
            "Auto-SARIMA returned unexpected confidence interval dimensions."
        )

    if (
        not np.isfinite(forecast).all()
        or not np.isfinite(confidence_interval).all()
    ):
        raise RuntimeError("Auto-SARIMA returned non-finite forecast values.")

    # Rainfall cannot be negative. Clip the point forecast and interval bounds
    # to zero, then ensure the displayed interval contains the point forecast.
    forecast = np.maximum(forecast, 0.0)
    lower = np.maximum(confidence_interval[:, 0], 0.0)
    upper = np.maximum(confidence_interval[:, 1], 0.0)

    lower = np.minimum(lower, forecast)
    upper = np.maximum(upper, forecast)

    forecast_values = np.round(forecast, 2).tolist()

    intervals = [
        {
            "lower_mm": round(float(low), 2),
            "upper_mm": round(float(high), 2),
        }
        for low, high in zip(lower, upper)
    ]

    return {
        "monthly_rainfall_mm": forecast_values,
        "confidence_intervals": intervals,
        "model_order": {
            "order": list(model.order),
            "seasonal_order": list(model.seasonal_order),
        },
        "training_months": len(history),
    }
