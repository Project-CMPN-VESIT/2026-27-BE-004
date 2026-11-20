import unittest
from datetime import date, timedelta
from unittest.mock import patch

from services.rainfall_api import aggregate_monthly_rainfall


class RainfallAggregationTests(unittest.TestCase):
    def _one_year_data(self):
        day = date(2021, 1, 1)
        dates = []
        while day.year == 2021:
            dates.append(day.isoformat())
            day += timedelta(days=1)
        return {"daily": {"time": dates, "precipitation_sum": [1.0] * len(dates)}}

    def test_aggregates_complete_daily_data_to_monthly_totals(self):
        with patch("services.rainfall_api.RAINFALL_START_YEAR", 2021), patch(
            "services.rainfall_api.RAINFALL_END_YEAR", 2021
        ):
            monthly = aggregate_monthly_rainfall(self._one_year_data())

        self.assertEqual(monthly, [31.0, 28.0, 31.0, 30.0, 31.0, 30.0, 31.0, 31.0, 30.0, 31.0, 30.0, 31.0])

    def test_rejects_duplicate_dates_instead_of_treating_them_as_complete(self):
        data = self._one_year_data()
        data["daily"]["time"][-1] = data["daily"]["time"][-2]
        with patch("services.rainfall_api.RAINFALL_START_YEAR", 2021), patch(
            "services.rainfall_api.RAINFALL_END_YEAR", 2021
        ), self.assertRaisesRegex(ValueError, "duplicate date"):
            aggregate_monthly_rainfall(data)

    def test_rejects_missing_daily_observations(self):
        data = self._one_year_data()
        data["daily"]["time"].pop()
        data["daily"]["precipitation_sum"].pop()
        with patch("services.rainfall_api.RAINFALL_START_YEAR", 2021), patch(
            "services.rainfall_api.RAINFALL_END_YEAR", 2021
        ), self.assertRaisesRegex(ValueError, "incomplete"):
            aggregate_monthly_rainfall(data)


if __name__ == "__main__":
    unittest.main()
