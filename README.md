# OOP with Python Assignment 2

Two small, independently runnable mini-projects for Advent 2026.

## Setup and run

Python 3.10 or newer is recommended. From this directory:

```powershell
python -m pip install -r requirements.txt
python -m pytest
```

`ipykernel` is included only to provide a Jupyter runtime; project calculations use the assignment-approved libraries.

Open `notebooks/project1_weather.ipynb` or `notebooks/project2_uganda_tax.ipynb` and choose **Restart & Run All**. The weather notebook makes a small number of live Open-Meteo requests. Its MET Norway comparison is skipped until the configuration cell contains your real university email; do not submit a placeholder as contact information. Weather parsing and failure examples use saved JSON or mocked requests and work offline.

## Findings

The captured Dresden forecast (Open-Meteo, 14 October 2026) reported a 16.4 °C maximum, 9.8 °C minimum, and slight rain showers for 14 October; the following two days were overcast with no forecast precipitation. Live forecasts change between runs. For PAYE, the implemented resident schedule is exactly the assignment's stated baseline; its 10,000,000 UGX threshold produces 2,888,250 UGX monthly tax before any higher-income surcharge. The tax notebook demonstrates the payroll, VAT, corporate tax, and scenario-comparison calculations.

## Layout

- `notebooks/`: the two requested executable reports.
- `src/weather.py`: direct HTTP clients, response parsing, and WMO descriptions.
- `src/tax_engine.py`: Decimal-only money, tax modules, payroll, and scenario comparison.
- `tests/`: offline weather parsing checks, PAYE boundaries, and Hypothesis properties.
- `tests/fixtures/`: saved Open-Meteo responses captured on 14 October 2026.

## Tax schedule scope

The PAYE resident thresholds and rates follow the assignment PDF, not a claim that the schedule has been legally verified for a real payroll. The assignment requires checking URA's current schedule, but the URA PAYE page redirected to a generic customer portal when checked on 14 October 2026. The official page search listing states that non-residents do not receive the tax-free threshold; the non-resident calculation uses the same marginal bands as the course baseline after applying a 10% first band. The modeled schedule starts 1 July 2026 solely to satisfy the assignment's Advent 2026 schedule-date example. Confirm the applicable Income Tax Act and current URA guidance before using these numbers outside this exercise.

References checked 14 October 2026:

- [URA PAYE rates](https://www.ura.go.ug/en/domestic-taxes/paye-rates/)
- [URA employment income](https://www.ura.go.ug/en/employment-income/)
- [Uganda Income Tax Act, Chapter 338, ULII version dated 23 December 2024](https://ulii.org/akn/ug/act/1997/11/eng@2024-12-23)
- [NSSF Uganda](https://www.nssfug.org/)

## Weather data terms

Open-Meteo's API data are CC BY 4.0 and require attribution; its free API is for non-commercial use and is rate-limited. MET Norway's data use NLOD 2.0 and CC BY 4.0 unless otherwise stated; identify the application with a real User-Agent, keep traffic low, and credit MET Norway. These APIs provide forecasts without an accuracy or availability guarantee. See the weather notebook for the privacy discussion and links to the terms.

## AI-use declaration

An AI coding assistant helped draft the module structure, implementation, tests, and report text. The student must review the rates and citations, run the notebooks, and be able to explain each calculation before submission.
