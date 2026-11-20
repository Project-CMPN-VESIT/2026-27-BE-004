# WaterWallet: A Storage-Constrained Decision-Support Prototype for Rooftop Rainwater Harvesting

## Abstract and Keywords

WaterWallet is a web-based decision-support prototype for preliminary rooftop rainwater-harvesting (RWH) planning in residential societies. It combines household-demand estimation, map-based rooftop measurement, historical rainfall retrieval, storage-aware yield simulation, cost estimation, and financial analysis. This revision documents the implemented system rather than an idealised design. Its central engineering calculation is a daily water balance: rainfall-derived inflow is first reduced by a configurable first-flush factor, combined with carried storage, used to meet eligible non-potable demand, then limited by tank capacity; excess is classified as recharge overflow or lost overflow. The same balance is used by tank sizing, site-specific deterministic ROI, and daily-rainfall Monte Carlo simulation. The fixed RWH demand policy is 65 litres per capita per day (LPCD) for eligible non-potable use; distribution-loss and peak allowances remain visible only as total-system planning quantities. The implementation was evaluated through 28 targeted backend tests (plus 5 parameterised subtests), 56 frontend tests, and a reproducible capacity-sensitivity experiment. In the latter, a 10,000 L tank delivered 6,840 L from a one-storm synthetic year, while a 100 L tank delivered 1,100 L under identical inflow and demand. This verifies that storage constraints affect usable water. The ML components are retained as prototype decision aids: their reported offline metrics evaluate rule-derived or formula-derived targets and are not evidence of real-world predictive performance. WaterWallet is therefore appropriate for an academic demonstration and preliminary scenario exploration, but requires observed meter, rainfall, yield, cost, and groundwater data before operational deployment.

**Keywords—** rainwater harvesting; water balance; rooftop catchment; tank sizing; return on investment; Monte Carlo simulation; decision support.

## Introduction

Rooftop RWH feasibility depends on more than annual rainfall or roof area. Rain occurs unevenly, storage is finite, demand is seasonal, and the financial value of a litre depends on the water source it offsets. A tool that credits every annual litre of rainfall as usable can overstate savings, especially in monsoon climates. WaterWallet addresses this planning problem with a browser-based workflow that carries user inputs from demand estimation and roof delineation to physically constrained storage and financial scenarios.

The project adopts a **planning** interpretation of domestic demand. The Virtual Meter calculates total domestic demand using the project’s 135 LPCD baseline and can apply 15% unaccounted-for-water and 10% peak-design allowances. These allowances are not treated as household end use. The RWH system is instead capped at a fixed eligible non-potable target of 65 LPCD (with the complementary 70 LPCD shown as potable). This avoids representing a buffered 82.225 LPCD allocation as a strict 65 LPCD target. IS 1172 is cited only as the source of the project’s 135-LPCD domestic baseline; the 70/65 split is a WaterWallet modelling policy, not a claim about the standard [1].

This paper makes four restrained contributions: (i) an end-to-end, three-phase RWH planning workflow; (ii) one canonical daily storage balance shared by sizing and finance; (iii) explicit treatment of rainfall and financial uncertainty; and (iv) transparent separation of physics-based calculations from prototype ML outputs. It does not claim field-validated yield prediction, hydrogeological approval, potable-water design, or construction-ready costing.

## Related Work

RWH design commonly combines catchment yield, demand, storage, and local rainfall. Historical gridded weather products offer a practical source of site-coordinate precipitation where on-site gauges are unavailable. Open-Meteo’s historical service exposes daily precipitation from reanalysis-based products and documents their spatial and observational limitations [2]. Such data are useful for screening, but are not a substitute for a calibrated roof gauge or tank meter.

The project also uses standard supervised-learning evaluation terms such as MAE, \(R^2\), accuracy, balanced accuracy, and macro-F1. These metrics are meaningful only when predictions are compared with independent observed targets appropriate to the decision [3]. Accordingly, WaterWallet treats its generated-label classifier and formula-target yield regressor as prototypes. The physical catchment equation and daily balance remain authoritative for engineering and finance.

## System Architecture and Methodology

### A. Three application phases and data flow

The deployed application is a React/Vite frontend communicating with a FastAPI backend. PostgreSQL/SQLAlchemy persistence and JWT-based authentication support application data where configured; the core calculation services are stateless for a request. External inputs include Open-Meteo historical daily precipitation, optional map/geocoding services, and an optional advisory service. Figure 1 summarises the operational flow.

```text
Phase 1: Virtual Meter                 Phase 2: Map Studio                  Phase 3: ROI Dashboard
flats, occupants, bills ──►            address + roof polygon ──►           costs + selected tank ──►
135-LPCD total planning load           Turf geodesic area                    deterministic ROI
65-LPCD RWH end-use cap                Open-Meteo daily rainfall             Monte Carlo distribution
          │                                      │                            tank-size comparison
          └──────────── WaterWallet client context┴───────────────┐            │
                                                                    ▼            ▼
                                                              FastAPI services
                                              demand | rainfall | water balance | cost | ML advisory
                                                                    │
                                                                    ▼
                                                    API responses, charts, and report inputs
```

**Phase 1—Virtual Meter.** The client obtains society attributes and, optionally, bill records. The backend demand engine returns occupants, base demand, buffered total demand, the 70/65 potable/non-potable split, and separately labelled buffered split. For \(N\) occupants, the RWH demand passed downstream is

\[
D_{RWH}=65N\quad [\mathrm{L/day}].
\]

Total planning demand is separately calculated as

\[
D_{plan}=\operatorname{round}(135N\,(1+u)\,(1+p)),
\]

where \(u=0.15\) when losses are included and \(p=0.10\). The two values answer different questions and must not be interchanged.

**Phase 2—Map Studio.** A user draws or supplies a roof geometry. The frontend computes geodesic roof area and communicates gross roof area, location, roof type, and rainfall context. The backend applies a usable-area factor \(f_u=0.80\) and roof-specific runoff coefficient \(C_r\). The theoretical inflow for rainfall \(r_t\) in mm on day \(t\) is

\[
I_t=\max(0,r_t) A_g f_u C_r(1-f_{ff})\quad [\mathrm{L}],
\]

because 1 mm over 1 m² equals 1 L. The current implementation applies the configurable first-flush fraction \(f_{ff}\), default 0.05, to every rainy day’s inflow. This is a simplified loss factor, not an event-based first-flush hydraulic model.

**Phase 3—ROI Dashboard.** The dashboard requests itemised CAPEX, deterministic financial analysis, Monte Carlo uncertainty analysis, and candidate tank sizing. Cost defaults (for example, per-area collection cost, per-litre storage cost, and 3% annual maintenance) are editable planning assumptions, not vendor quotes. Savings first offset recorded tanker volume, then eligible municipal demand. Therefore the monetary result depends on user-provided bill volume, tariff, tanker spend, CAPEX, operating cost, and escalation assumptions.

### B. Canonical daily water balance

For a tank of capacity \(K\), opening storage \(S_{t-1}\), inflow \(I_t\), and eligible demand \(D_{RWH}\), the implementation executes

\[
V_t=S_{t-1}+I_t,\qquad U_t=\min(V_t,D_{RWH}),
\]
\[
S_t=\min(K,V_t-U_t),\qquad O_t=\max(0,V_t-U_t-K).
\]

Here \(U_t\) is useful harvested water and \(O_t\) is overflow. If recharge is enabled, only up to the configured daily recharge-pit capacity is recorded as recharge; the remainder is lost overflow. Unmet demand is \(D_{RWH}-U_t\). The engine reports yearly and monthly inflow, useful water, unmet demand, overflow classes, ending storage, and reliability \(100\sum_tU_t/\sum_tD_{RWH}\).

The `simulate_tank_year` function is the common engine. Tank sizing evaluates candidate capacities over complete historical daily years. When latitude, longitude, and roof area are supplied, deterministic ROI averages daily-balance useful water over retrieved complete years before applying the financial model. Monte Carlo samples a complete historical daily year with a multiplicative rainfall perturbation of 0.8–1.2 and uses the same balance. Older monthly/percentile paths remain compatibility fallbacks; they spread a monthly total uniformly across calendar days and therefore should not be interpreted as storm-resolving site analysis.

### C. Forecasting and ML components

The rainfall forecasting service validates at least 36 consecutive monthly observations, fits a seasonal Auto-SARIMA model with 12-month seasonality, and returns non-negative 12-month point forecasts and 95% confidence intervals. It rejects missing, non-finite, negative, or insufficient input rather than returning invented values. Forecasts are informative scenarios, not evidence of local forecast skill until evaluated chronologically against held-out observations.

The ML recommendation path contains a rule-derived configuration classifier and a random-forest yield regressor. A deterministic safety gate is applied before the classifier; its thresholds are project heuristics and require local hydrogeological and regulatory verification. The classifier’s 600 synthetic samples are labelled by engineering rules. The regressor is trained against yield labels generated by the same roof-area × rainfall × usability × runoff equation used by production calculations. ML yield output is therefore displayed as a prototype diagnostic; it does not alter the physics-based financial yield.

## Experimental Setup and Evaluation

Evaluation used the checked-out implementation and its test suites, not screenshots or historical paper values. The executed commands were `python -m pytest tests/test_monte_carlo_integration.py tests/test_tank_sizer.py tests/test_roi_engine.py -q` from `backend/`, and `npm test -- --run` plus `npm run build` from the repository root. The backend command completed with **28 passed tests and 5 passed parameterised subtests**; the frontend command completed with **12 files and 56 tests passed**; the production build completed. A full endpoint test run did not complete during the audit window and is not claimed here. The lint command still reports pre-existing Node-global errors in legacy Express files and React-hook warnings in Map Studio; it is not a clean deployment gate.

Table I consolidates the evidence types. “Artifact metric” means a value read from the saved model metadata, not rerun against independently collected field observations.

| Component / evaluation | Data and design | Metric or outcome | Interpretation |
|---|---|---:|---|
| Daily balance and ROI regression | Targeted backend tests | 28 tests + 5 subtests passed | Confirms implemented invariants and financial/balance integration; not field validation. |
| Frontend constants and UI logic | Vitest suite | 56 tests in 12 files passed | Confirms tested client behaviour, including demand constants. |
| Build | Vite production build | Passed | Bundle can be produced in the audited environment. |
| Configuration classifier (artifact) | 600 synthetic, rule-labelled rows; held-out generated labels | accuracy/balanced accuracy/macro-F1 = 1.000 | Reproduces its labelling rule; does **not** measure real site-classification accuracy. |
| Yield regressor (artifact) | 2010–2021 training, 2022–2024 test; targets from physical equation | MAE = 4.8973 kL; \(R^2=0.9865\) | Approximates formula-generated labels; does **not** validate harvested-water prediction. |
| Auto-SARIMA forecast | Current code inspection | Input validation and 95% intervals implemented | No fresh chronological back-test was run; forecast accuracy is pending. |

An additional sensitivity experiment was run directly through `simulate_tank_year`. It uses a deliberately simple synthetic 365-day year: one 100-mm rain day, 80 m² usable roof, \(C_r=0.90\), 5% loss factor, and 1,000 L/day eligible demand. Its purpose is a controlled engineering invariant, not a site forecast. The total physical inflow is \(100\times80\times0.90\times0.95=6,840\) L.

## Results and Discussion

Table II gives the sensitivity result. With identical rainfall and demand, the larger tank can preserve water for subsequent dry days, while the smaller tank overflows after same-day service. This directly rules out the former error in which a small tank could receive credit for full-period inflow before the capacity limit was applied.

| Scenario (same 6,840 L inflow) | Tank capacity | Useful water | Lost overflow | Unmet demand | Reliability |
|---|---:|---:|---:|---:|---:|
| Controlled single-storm year | 100 L | 1,100 L | 5,740 L | 363,900 L | 0.30% |
| Controlled single-storm year | 10,000 L | 6,840 L | 0 L | 358,160 L | 1.87% |

The result is physically consistent: both configurations may serve 1,000 L on the storm day, but only the larger configuration carries the remaining water forward. The corresponding regression test also runs Monte Carlo with daily historical-style input and asserts a worse median break-even for the smaller tank under the test’s intentionally artificial price/CAPEX settings. That financial number is a regression oracle, not a recommendation for a real society.

For a live site, deterministic ROI and Monte Carlo need not have equal payback periods. They should differ because deterministic ROI averages usable water across observed historical daily years, while Monte Carlo resamples whole observed years and perturbs rainfall. Both now include tank capacity, carry-over, overflow, eligible demand, and the same 5% loss factor. The dashboard should present deterministic ROI as a baseline historical scenario and Monte Carlo as a distribution of rainfall scenarios—not as mutually inconsistent estimates of usable water.

The demand policy can be checked numerically. A 50-flat society with four occupants per flat has \(N=200\). Its RWH target is exactly \(200\times65=13,000\) L/day. With the project’s 15% loss and 10% peak allowance, total planning demand is \(200\times135\times1.15\times1.10=34,155\) L/day (subject to implementation rounding); the buffered non-potable allocation is reported separately. Financial and tank calculations use 13,000 L/day rather than the buffered allocation.

No live Open-Meteo scenario, user billing record, tank-meter observation, or construction quotation was collected during this revision. Consequently, the paper reports no site-specific annual yield, CAPEX, payback period, forecast MAE, or probability of break-even as an empirical result. These outputs are intentionally produced only when required inputs and complete daily rainfall records are available.

## Limitations and Future Work

First, historical rainfall is gridded/reanalysis data rather than an on-site gauge; roof shading, gutter loss, rainfall intensity, contamination events, leakage, pump energy, and tank downtime are not calibrated. The daily first-flush multiplier is a coarse simplification. A future model should represent event starts, diversion volume, water quality, and the relationship between intensity and runoff.

Second, the financial model is a planning calculator. It assumes bills correctly identify tanker volume, allows editable tariffs and escalation, and uses generic maintenance and component-cost assumptions. It excludes financing, tax, land/civil constraints, electricity, replacement schedules, water-quality treatment, and the value or permission status of recharge. Before a real pilot, obtain site quotations, meter inflow/outflow, and reconcile savings against bills.

Third, the rainfall forecaster has no recorded current rolling-origin evaluation. It should be assessed with date-preserving training/test splits, baseline comparisons, calibration/interval coverage, and a documented data version. Forecasts should not drive investment decisions until this is done.

Fourth, neither ML model has independent real-world ground truth. Replace synthetic rule labels with reviewed sites and replace formula targets with measured tank yield; use a geographically and temporally held-out evaluation, report uncertainty and class calibration, and retain the deterministic safety gate. Site suitability and recharge design must be approved through local survey, hydrogeological assessment, water-quality assessment, and applicable regulation.

Finally, a production deployment needs a clean lint gate, completed API/end-to-end tests, secrets management, access-control review, rate limits, monitoring, backups, CORS hardening, and failure handling for external services. The current project is a prototype, not a safety-critical control system.

## Conclusion

WaterWallet demonstrates a coherent workflow from society inputs and map-based catchment estimates to storage-constrained yield, tank selection, and financial scenarios. Its key correction is to treat rainfall as a sequence of daily inflows rather than annual credit: storage, demand, overflow, and carry-over are now shared by tank sizing, site-specific deterministic ROI, and daily-rainfall Monte Carlo analysis. The fixed 65-LPCD eligible non-potable policy avoids inflating RWH demand with planning allowances. Tests and the controlled capacity experiment support code-level physical consistency, while the paper deliberately limits ML claims to rule- and formula-derived prototypes. The next credible milestone is a monitored pilot with observed rainfall, tank levels, demand, bills, quality data, and independently reviewed site suitability.

## References

[1] Bureau of Indian Standards, *IS 1172:1993, Code of Basic Requirements for Water Supply, Drainage and Sanitation*, New Delhi, India, reaffirmed 2007. The standard is used here only for the project’s 135-LPCD baseline; the 70/65 split is an implementation policy.

[2] Open-Meteo, “Historical Weather API.” [Online]. Available: https://open-meteo.com/en/docs/historical-weather-api. Accessed: 2026-10-27. The documentation describes historical daily precipitation availability and reanalysis-based data sources.

[3] scikit-learn developers, “Metrics and scoring: quantifying the quality of predictions.” [Online]. Available: https://scikit-learn.org/stable/modules/model_evaluation.html. Accessed: 2026-10-27. Used for metric terminology, not as validation evidence for WaterWallet models.

[4] WaterWallet source evidence: `backend/services/tank_sizer.py`, `backend/services/monte_carlo.py`, `backend/services/roi_engine.py`, `backend/services/demand_engine.py`, `backend/services/rainfall_forecast.py`, `backend/ml_models/train_models.py`, `backend/ml_models/model_metadata.json`, and the executed test suites listed in Section IV. Revision audited 2026-10-27.
