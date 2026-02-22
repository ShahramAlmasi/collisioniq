# Collision Analytics - Calculation Reference

This document describes the analytics calculations implemented in the Collision Analytics plugin.

## Table of Contents

1. [Rate Calculations](#rate-calculations)
2. [Severity Distribution](#severity-distribution)
3. [Trend Analysis](#trend-analysis)
4. [Before/After Comparison](#beforeafter-comparison)
5. [Statistical Significance](#statistical-significance)
6. [Risk Flags](#risk-flags)

---

## Rate Calculations

### Collision Rate per Million Entering Vehicles

The standard collision rate used in traffic safety engineering:

```
Collision Rate = (Collisions × 1,000,000) / Entering Vehicles
```

**Where:**
- **Collisions**: Total number of collisions in the analysis period
- **Entering Vehicles**: Total entering vehicles (AADT × 365 × years)

**Interpretation:**
- < 50 per MEV: Generally acceptable
- 50-100 per MEV: Moderate concern
- > 100 per MEV: High priority for investigation

### KSI Rate per Million Entering Vehicles

KSI = Killed or Seriously Injured (Fatal + Injury collisions)

```
KSI Rate = ((Fatal + Injury) × 1,000,000) / Entering Vehicles
```

**Interpretation:**
- < 10 per MEV: Generally acceptable
- 10-25 per MEV: Moderate concern
- > 25 per MEV: High priority for safety improvements

### Fatal Rate per Million Entering Vehicles

```
Fatal Rate = (Fatal × 1,000,000) / Entering Vehicles
```

### Collisions per Kilometer

For roadway segment analysis:

```
Collisions per km = Total Collisions / Roadway Length (km)
```

### Collisions per Intersection

For intersection-focused analysis:

```
Collisions per Intersection = Total Collisions / Number of Intersections
```

### Daily Collision Rate

```
Collisions per Day = Total Collisions / Number of Days in Period
```

---

## Severity Distribution

### Severity Categories

| Category | Description |
|----------|-------------|
| **Fatal** | Collision resulted in one or more fatalities |
| **Injury** | Collision resulted in injury but no fatalities |
| **PDO** | Property Damage Only - no injuries |
| **Unknown** | Severity not recorded or blank |

### Severity Rate Calculations

```
KSI Rate (%) = ((Fatal + Injury) / Total Collisions) × 100
Fatal Rate (%) = (Fatal / Total Collisions) × 100
Injury Rate (%) = (Injury / Total Collisions) × 100
PDO Rate (%) = (PDO / Total Collisions) × 100
```

---

## Trend Analysis

### Linear Regression

The trend analysis uses simple linear regression on annual collision counts:

```
y = mx + b

Where:
- y = predicted collision count
- m = slope (change per year)
- x = year
- b = intercept
```

### Slope Calculation

```
slope = Σ((x - x̄)(y - ȳ)) / Σ((x - x̄)²)
```

### R-Squared (Coefficient of Determination)

Measures how well the trend line fits the data (0 = no fit, 1 = perfect fit):

```
R² = 1 - (SS_res / SS_tot)

Where:
- SS_res = Σ(y_actual - y_predicted)²
- SS_tot = Σ(y_actual - ȳ)²
```

### P-Value

Tests whether the trend slope is statistically significant:

```
t = slope / SE_slope
p = 2 × (1 - CDF_t(|t|, n-2))
```

**Interpretation:**
- p < 0.05: Trend is statistically significant
- p ≥ 0.05: Trend may be due to random variation

### Percent Change Per Year

```
Total % Change = ((Final Count - Initial Count) / Initial Count) × 100
Avg % Change/Year = Total % Change / Number of Years
```

---

## Before/After Comparison

### Percent Change Calculation

```
% Change = ((After - Before) / Before) × 100
```

### Confidence Interval (95%)

For the percent change in collision counts:

```
CI = exp(log(After/Before) ± 1.96 × SE) - 1

Where:
SE = √((1/Before) + (1/After))
```

---

## Statistical Significance

### Chi-Square Test

Tests whether the before/after difference is statistically significant:

```
Contingency Table:
              KSI    PDO
Before        a      b
After         c      d

χ² = Σ((O - E)² / E)

Where:
- O = observed count
- E = expected count = (row total × column total) / grand total
```

**Interpretation:**
- χ² p-value < 0.05: Statistically significant difference
- χ² p-value ≥ 0.05: Difference may be due to chance

### Requirements for Chi-Square Test

The test is only performed when:
- All cells in contingency table > 0
- Total observations > 20
- scipy library is available

---

## Risk Flags

The analytics engine automatically identifies potential risk factors:

### Fatal Collisions Present

**Triggered when:** Fatal collisions ≥ 1

**Severity:** 🚨 Critical

### High Severe Collision Rate

**Triggered when:** KSI rate ≥ 20%

**Severity:** ⚠️ Warning

### Data Quality Risk

**Triggered when:** Unknown/blank severity ≥ 5%

**Severity:** 📊 Informational

### Increasing Trend

**Triggered when:** Trend slope indicates increase

**Severity:** 📈 Warning (if statistically significant)

### High KSI Rate

**Triggered when:** KSI rate > 50 per million entering vehicles

**Severity:** ⚠️ Warning

---

## API Reference

### Main Analytics Function

```python
from collision_analytics.core.analytics import analyze_collisions

result = analyze_collisions(
    rows=filtered_rows,
    field_map={'accident_class': 'severity_field', 'date': 'date_field'},
    entering_vehicles=10000000,  # Optional: for rate calculations
    roadway_km=5.2,              # Optional: for per-km rates
    intersection_count=12,       # Optional: for per-intersection rates
    start_date=date(2020, 1, 1),
    end_date=date(2024, 12, 31),
    # For before/after comparison:
    before_start=date(2020, 1, 1),
    before_end=date(2021, 12, 31),
    after_start=date(2022, 1, 1),
    after_end=date(2024, 12, 31),
    severity_decode_fn=decode_func  # Optional: to decode severity codes
)
```

### Result Object

```python
AnalyticsResult(
    total_records=int,                    # Total collisions analyzed
    date_range=(date, date),              # Analysis period
    severity=SeverityDistribution,        # Severity breakdown
    rates=RateMetrics,                    # All calculated rates
    annual_counts={year: count},          # Yearly collision counts
    trend=TrendResult,                    # Linear trend analysis
    before_after=BeforeAfterComparison,   # Statistical comparison
    risk_flags=[str],                     # Identified risk flags
    insights=[str]                        # Practitioner insights
)
```

### Quick Summary

```python
from collision_analytics.core.analytics import quick_summary

summary = quick_summary(rows, 'accident_class_field')
# Returns: {'total', 'fatal', 'injury', 'pdo', 'ksi', 'ksi_rate', 'severe_rate'}
```

---

## Implementation Notes

### Dependencies

- **numpy**: Required for trend analysis (linear regression)
- **scipy**: Optional, required for statistical significance testing (chi-square, p-values)

### Data Quality

- Records with blank/unknown dates are excluded from trend analysis
- Records with blank/unknown severity are counted as "Unknown"
- Rate calculations return `None` when exposure data is not provided

### Performance

- Analytics are computed on filtered datasets (not the full layer)
- Linear regression uses numpy's optimized polyfit
- All calculations are performed in-memory for responsiveness

---

## References

1. **Transportation Association of Canada (TAC)** - Canadian Road Safety Engineering Handbook
2. **AASHTO Highway Safety Manual** - Methods for predicting collision frequency
3. **FHWA** - SafetyAnalyst methodology
4. **ISO 39001** - Road traffic safety management systems
