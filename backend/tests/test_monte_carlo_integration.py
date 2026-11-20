import unittest

from models.schemas import (
    MLYieldRequest,
    MLRecommendRequest,
    MonteCarloRequest,
    TankSizerRequest,
)
from services.demand_engine import calculate_demand
from services.monte_carlo import run_monte_carlo


class MonteCarloIntegrationTests(unittest.TestCase):
    def test_local_tanker_rate_defaults_match_per_units(self):
        monte_carlo = MonteCarloRequest(
            rooftop_area_m2=100,
            monthly_demand_kl=10,
            capex_inr=100000,
        )
        tank_sizer = TankSizerRequest(
            latitude=19.22,
            longitude=72.97,
            gross_roof_area_sqm=100,
            daily_demand_litres=1000,
        )

        self.assertEqual(monte_carlo.tanker_rate_per_kl, 175.0)
        self.assertEqual(tank_sizer.tanker_rate_per_litre, 0.175)

    def _run(self, rainfall):
        return run_monte_carlo(
            rooftop_area_m2=1000,
            monthly_demand_kl=100,
            capex_inr=100000,
            tank_capacity_litres=50000,
            annual_tanker_volume_litres=0,
            n_scenarios=20,
            monthly_rainfall_mm=rainfall,
        )

    def test_phase_two_rainfall_is_used_and_reported(self):
        result = self._run([0.0] * 12)

        self.assertEqual(result["scenarios_used"], "phase2_monthly_rainfall")
        self.assertTrue(result["is_site_specific"])
        self.assertEqual(result["n_scenarios"], 20)

    def test_fallback_when_monthly_rainfall_is_none(self):
        result = self._run(None)

        self.assertEqual(result["scenarios_used"], "percentile_table")
        self.assertFalse(result["is_site_specific"])
        self.assertEqual(result["n_scenarios"], 20)
        self.assertIn("percentiles", result)

    def test_phase_two_rainfall_changes_downstream_result(self):
        dry = self._run([0.0] * 12)
        wet = self._run([1000.0] * 12)

        self.assertNotEqual(
            dry["never_break_even_pct"],
            wet["never_break_even_pct"],
        )

    def test_itemized_annual_opex_is_used_when_provided(self):
        low_opex = run_monte_carlo(
            rooftop_area_m2=1000,
            monthly_demand_kl=100,
            capex_inr=100000,
            annual_opex_inr=0,
            n_scenarios=100,
            monthly_rainfall_mm=[200.0] * 12,
        )
        high_opex = run_monte_carlo(
            rooftop_area_m2=1000,
            monthly_demand_kl=100,
            capex_inr=100000,
            annual_opex_inr=1000000,
            n_scenarios=100,
            monthly_rainfall_mm=[200.0] * 12,
        )

        self.assertLess(
            low_opex["never_break_even_pct"],
            high_opex["never_break_even_pct"],
        )

    def test_legacy_positional_call_keeps_tank_capacity_position(self):
        positional_result = run_monte_carlo(
            1000,
            100,
            100000,
            50000,
            0,
            175,
            0,
            15,
            0.08,
            100,
            [200.0] * 12,
        )
        keyword_result = run_monte_carlo(
            rooftop_area_m2=1000,
            monthly_demand_kl=100,
            capex_inr=100000,
            tank_capacity_litres=50000,
            rainfall_reduction_percent=0,
            tanker_rate_per_kl=175,
            annual_tanker_volume_litres=0,
            water_tariff_per_kl=15,
            inflation_rate=0.08,
            n_scenarios=100,
            monthly_rainfall_mm=[200.0] * 12,
        )

        self.assertEqual(
            positional_result["median_breakeven_year"],
            keyword_result["median_breakeven_year"],
        )

    def test_median_includes_scenarios_that_do_not_break_even(self):
        result = self._run([0.0] * 12)

        self.assertEqual(result["never_break_even_pct"], 100.0)
        self.assertEqual(result["median_breakeven_year"], 11.0)
        self.assertEqual(result["percentiles"]["p50"], 11.0)

    def test_phase_two_rainfall_requires_twelve_non_negative_values(self):
        with self.assertRaises(ValueError):
            self._run([10.0] * 11)
        with self.assertRaises(ValueError):
            self._run([10.0] * 11 + [-1.0])
        with self.assertRaises(ValueError):
            self._run([10.0] * 11 + [float("nan")])

    def test_fractional_year_breakeven_interpolation(self):
        # A steady high rainfall should interpolate a break-even within the horizon.
        res = self._run([200.0] * 12)
        self.assertIsNotNone(res["median_breakeven_year"])
        self.assertGreater(res["median_breakeven_year"], 0)
        self.assertLess(res["median_breakeven_year"], 10)
        self.assertNotEqual(res["median_breakeven_year"] % 1, 0)

    def test_fixed_rwh_target_is_not_inflated_by_system_design_allowances(self):
        result = calculate_demand(1, occupants_per_flat=1, include_losses=False)

        self.assertEqual(result["daily_demand_lpd"], 149.0)
        self.assertEqual(result["potable_demand_lpd"], 70.0)
        self.assertEqual(result["non_potable_demand_lpd"], 65.0)
        self.assertEqual(result["buffered_non_potable_demand_lpd"], 72.0)

    def test_daily_monte_carlo_respects_tank_capacity(self):
        # One 100 mm storm followed by a dry year: the 100 L tank cannot
        # serve the same annual demand as the 10,000 L tank.
        common = {
            "rooftop_area_m2": 100,
            "monthly_demand_kl": 12,
            "capex_inr": 1000,
            "annual_tanker_volume_litres": 1_000_000,
            "tanker_rate_per_kl": 1000,
            "annual_opex_inr": 0,
            "n_scenarios": 100,
            "rainfall_by_year": {2021: [100.0] + [0.0] * 364},
        }
        small = run_monte_carlo(**common, tank_capacity_litres=100)
        large = run_monte_carlo(**common, tank_capacity_litres=10_000)

        self.assertEqual(small["scenarios_used"], "historical_daily_bootstrap")
        self.assertTrue(small["is_site_specific"])
        self.assertGreater(small["median_breakeven_year"], large["median_breakeven_year"])

    def test_rainfall_and_coastal_schema_boundaries(self):
        rainfall = [1.0] * 11 + [0.0]
        MLYieldRequest(rooftop_area_m2=100, monthly_rainfall_mm=rainfall)
        MonteCarloRequest(
            rooftop_area_m2=100,
            monthly_demand_kl=10,
            capex_inr=100000,
            monthly_rainfall_mm=rainfall,
        )
        MLRecommendRequest(
            rooftop_area=100,
            borewell=0,
            borewell_depth=0,
            soil_perm=3,
            coastal_km=0,
            annual_rain_mm=1000,
            peak_day_mm=100,
        )
        for invalid in ([1.0] * 11 + [-1.0], [1.0] * 11 + [float("inf")]):
            with self.assertRaises(ValueError):
                MLYieldRequest(rooftop_area_m2=100, monthly_rainfall_mm=invalid)
            with self.assertRaises(ValueError):
                MonteCarloRequest(
                    rooftop_area_m2=100,
                    monthly_demand_kl=10,
                    capex_inr=100000,
                    monthly_rainfall_mm=invalid,
                )
        with self.assertRaises(ValueError):
            MonteCarloRequest(
                rooftop_area_m2=100,
                monthly_demand_kl=10,
                capex_inr=100000,
                annual_opex_inr=float("inf"),
            )

    def test_roof_runoff_coefficient_sensitivity(self):
        # Low runoff (gravel 0.45) vs high runoff (concrete 0.90)
        low_res = run_monte_carlo(
            rooftop_area_m2=500,
            monthly_demand_kl=50,
            capex_inr=50000,
            annual_tanker_volume_litres=500000,
            tanker_rate_per_kl=300,
            n_scenarios=20,
            monthly_rainfall_mm=[100.0] * 12,
            runoff_coeff=0.45,
        )
        high_res = run_monte_carlo(
            rooftop_area_m2=500,
            monthly_demand_kl=50,
            capex_inr=50000,
            annual_tanker_volume_litres=500000,
            tanker_rate_per_kl=300,
            n_scenarios=20,
            monthly_rainfall_mm=[100.0] * 12,
            runoff_coeff=0.90,
        )
        self.assertIsNotNone(low_res["median_breakeven_year"])
        self.assertIsNotNone(high_res["median_breakeven_year"])
        self.assertLessEqual(
            high_res["median_breakeven_year"],
            low_res["median_breakeven_year"],
        )


if __name__ == "__main__":
    unittest.main()
