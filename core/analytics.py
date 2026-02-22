from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from collections import Counter

import numpy as np

from .utils import safe_str, to_datetime, try_float, is_blank


# =============================================================================
# Data Classes for Analytics Results
# =============================================================================

@dataclass(frozen=True)
class RateMetrics:
    """Collision rate calculations with exposure adjustments."""
    # Base counts
    total_collisions: int
    fatal: int
    injury: int
    pdo: int
    ksi: int  # Fatal + Injury (Killed or Seriously Injured)
    
    # Exposure values (inputs)
    entering_vehicles: Optional[float] = None  # Annual or total entering vehicles
    roadway_km: Optional[float] = None  # Roadway segment length in km
    intersection_count: Optional[int] = None  # Number of intersections
    days: Optional[int] = None  # Number of days in period
    
    # Rate calculations (per million entering vehicles)
    collision_rate_per_mev: Optional[float] = field(default=None)
    ksi_rate_per_mev: Optional[float] = field(default=None)
    fatal_rate_per_mev: Optional[float] = field(default=None)
    
    # Rate calculations (per km)
    collisions_per_km: Optional[float] = field(default=None)
    ksi_per_km: Optional[float] = field(default=None)
    
    # Rate calculations (per intersection)
    collisions_per_intersection: Optional[float] = field(default=None)
    ksi_per_intersection: Optional[float] = field(default=None)
    
    # Daily rates
    collisions_per_day: Optional[float] = field(default=None)
    ksi_per_day: Optional[float] = field(default=None)
    
    def __post_init__(self):
        # Calculate rates that can be computed from available data
        object.__setattr__(self, 'ksi', self.fatal + self.injury)
        
        # Per million entering vehicles
        if self.entering_vehicles and self.entering_vehicles > 0:
            mev_factor = 1_000_000 / self.entering_vehicles
            object.__setattr__(self, 'collision_rate_per_mev', self.total_collisions * mev_factor)
            object.__setattr__(self, 'ksi_rate_per_mev', self.ksi * mev_factor)
            object.__setattr__(self, 'fatal_rate_per_mev', self.fatal * mev_factor)
        
        # Per km rates
        if self.roadway_km and self.roadway_km > 0:
            object.__setattr__(self, 'collisions_per_km', self.total_collisions / self.roadway_km)
            object.__setattr__(self, 'ksi_per_km', self.ksi / self.roadway_km)
        
        # Per intersection rates
        if self.intersection_count and self.intersection_count > 0:
            object.__setattr__(self, 'collisions_per_intersection', self.total_collisions / self.intersection_count)
            object.__setattr__(self, 'ksi_per_intersection', self.ksi / self.intersection_count)
        
        # Daily rates
        if self.days and self.days > 0:
            object.__setattr__(self, 'collisions_per_day', self.total_collisions / self.days)
            object.__setattr__(self, 'ksi_per_day', self.ksi / self.days)


@dataclass(frozen=True)
class TrendResult:
    """Linear trend analysis result for time series data."""
    years: Tuple[int, ...]
    counts: Tuple[int, ...]
    
    # Linear regression results
    slope: float  # Change per year
    intercept: float
    r_squared: float  # Goodness of fit (0-1)
    p_value: Optional[float] = None  # Statistical significance
    
    # Derived metrics
    percent_change_per_year: Optional[float] = None  # Average annual % change
    trend_direction: str = "stable"  # "increasing", "decreasing", "stable"
    
    # Forecast (if requested)
    forecast_years: Optional[Tuple[int, ...]] = None
    forecast_values: Optional[Tuple[float, ...]] = None
    
    def __post_init__(self):
        # Determine trend direction based on slope and significance
        if self.p_value is not None and self.p_value < 0.05:
            if self.slope > 0:
                object.__setattr__(self, 'trend_direction', 'increasing')
            elif self.slope < 0:
                object.__setattr__(self, 'trend_direction', 'decreasing')
        elif self.slope > 0.5:  # Practical significance threshold
            object.__setattr__(self, 'trend_direction', 'increasing')
        elif self.slope < -0.5:
            object.__setattr__(self, 'trend_direction', 'decreasing')
        
        # Calculate average percent change per year
        if len(self.counts) >= 2 and self.counts[0] > 0:
            total_pct_change = ((self.counts[-1] - self.counts[0]) / self.counts[0]) * 100
            years_span = len(self.counts) - 1
            if years_span > 0:
                object.__setattr__(self, 'percent_change_per_year', total_pct_change / years_span)


@dataclass(frozen=True)
class BeforeAfterComparison:
    """Statistical comparison between two time periods."""
    # Period identifiers
    before_label: str
    after_label: str
    
    # Collision counts
    before_total: int
    after_total: int
    before_ksi: int
    after_ksi: int
    before_fatal: int
    after_fatal: int
    
    # Percent changes
    total_pct_change: float
    ksi_pct_change: float
    fatal_pct_change: float
    
    # Statistical tests
    chi2_statistic: Optional[float] = None
    chi2_p_value: Optional[float] = None
    is_significant: bool = False  # p < 0.05
    
    # Confidence intervals (95%)
    total_pct_ci_lower: Optional[float] = None
    total_pct_ci_upper: Optional[float] = None
    
    # Interpretation
    interpretation: str = ""
    
    def __post_init__(self):
        # Generate interpretation
        if abs(self.total_pct_change) < 5:
            interp = "Minimal change observed"
        elif self.total_pct_change < -20:
            interp = "Substantial reduction in collisions"
        elif self.total_pct_change < 0:
            interp = "Moderate reduction in collisions"
        elif self.total_pct_change > 20:
            interp = "Substantial increase in collisions"
        else:
            interp = "Moderate increase in collisions"
        
        if self.is_significant:
            interp += " (statistically significant)"
        else:
            interp += " (not statistically significant)"
        
        object.__setattr__(self, 'interpretation', interp)


@dataclass(frozen=True)
class SeverityDistribution:
    """Detailed severity breakdown with risk metrics."""
    fatal: int
    injury: int
    pdo: int
    unknown: int
    total: int
    
    # Proportions
    fatal_pct: float = field(default=0.0)
    injury_pct: float = field(default=0.0)
    pdo_pct: float = field(default=0.0)
    unknown_pct: float = field(default=0.0)
    
    # Risk ratios
    ksi_rate: float = field(default=0.0)  # (Fatal + Injury) / Total
    severe_rate: float = field(default=0.0)  # Same as KSI rate
    
    def __post_init__(self):
        if self.total > 0:
            object.__setattr__(self, 'fatal_pct', (self.fatal / self.total) * 100)
            object.__setattr__(self, 'injury_pct', (self.injury / self.total) * 100)
            object.__setattr__(self, 'pdo_pct', (self.pdo / self.total) * 100)
            object.__setattr__(self, 'unknown_pct', (self.unknown / self.total) * 100)
            object.__setattr__(self, 'ksi_rate', ((self.fatal + self.injury) / self.total) * 100)
            object.__setattr__(self, 'severe_rate', self.ksi_rate)


@dataclass(frozen=True)
class AnalyticsResult:
    """Complete analytics results for a filtered dataset."""
    # Input metadata
    total_records: int
    date_range: Optional[Tuple[date, date]] = None
    
    # Core metrics
    severity: Optional[SeverityDistribution] = None
    rates: Optional[RateMetrics] = None
    
    # Time-based analysis
    annual_counts: Optional[Dict[int, int]] = None
    trend: Optional[TrendResult] = None
    
    # Comparison (if before/after periods specified)
    before_after: Optional[BeforeAfterComparison] = None
    
    # Risk flags and insights
    risk_flags: List[str] = field(default_factory=list)
    insights: List[str] = field(default_factory=list)
    
    # Raw data for further analysis
    yearly_ksi_counts: Optional[Dict[int, int]] = None


# =============================================================================
# Core Analytics Functions
# =============================================================================

def calculate_severity_distribution(
    rows: List[Dict[str, Any]],
    accident_class_field: str,
    decode_fn: Optional[Callable[[Any], str]] = None
) -> SeverityDistribution:
    """Calculate severity distribution from collision records.
    
    Args:
        rows: Filtered collision records
        accident_class_field: Field name for accident classification
        decode_fn: Optional function to decode raw values to severity labels
    
    Returns:
        SeverityDistribution with counts and percentages
    """
    fatal = injury = pdo = unknown = 0
    
    for r in rows:
        raw = r.get(accident_class_field)
        if decode_fn:
            val = decode_fn(raw)
        else:
            val = safe_str(raw).strip()
        
        val_lower = val.lower()
        if 'fatal' in val_lower:
            fatal += 1
        elif 'injury' in val_lower:
            injury += 1
        elif 'pdo' in val_lower or 'property' in val_lower:
            pdo += 1
        else:
            unknown += 1
    
    total = fatal + injury + pdo + unknown
    return SeverityDistribution(
        fatal=fatal,
        injury=injury,
        pdo=pdo,
        unknown=unknown,
        total=total
    )


def calculate_rate_metrics(
    rows: List[Dict[str, Any]],
    accident_class_field: str,
    entering_vehicles: Optional[float] = None,
    roadway_km: Optional[float] = None,
    intersection_count: Optional[int] = None,
    days: Optional[int] = None,
    decode_fn: Optional[Callable[[Any], str]] = None
) -> RateMetrics:
    """Calculate collision rates with various exposure measures.
    
    Args:
        rows: Filtered collision records
        accident_class_field: Field name for accident classification
        entering_vehicles: Annual or total entering vehicles (for rate per MEV)
        roadway_km: Total roadway length in km
        intersection_count: Number of intersections
        days: Number of days in analysis period
        decode_fn: Optional function to decode severity values
    
    Returns:
        RateMetrics with all calculable rates
    """
    severity = calculate_severity_distribution(rows, accident_class_field, decode_fn)
    
    return RateMetrics(
        total_collisions=severity.total,
        fatal=severity.fatal,
        injury=severity.injury,
        pdo=severity.pdo,
        ksi=severity.fatal + severity.injury,
        entering_vehicles=entering_vehicles,
        roadway_km=roadway_km,
        intersection_count=intersection_count,
        days=days
    )


def calculate_annual_counts(
    rows: List[Dict[str, Any]],
    date_field: str,
    accident_class_field: Optional[str] = None,
    severity_filter: Optional[str] = None,
    decode_fn: Optional[Callable[[Any], str]] = None
) -> Dict[int, int]:
    """Calculate collision counts by year.
    
    Args:
        rows: Filtered collision records
        date_field: Field name containing date
        accident_class_field: Optional field for severity filtering
        severity_filter: Optional severity to filter by (e.g., 'Fatal', 'Injury', 'KSI')
        decode_fn: Optional function to decode severity values
    
    Returns:
        Dictionary mapping year to count
    """
    counts: Counter = Counter()
    
    for r in rows:
        # Get date
        raw_date = r.get(date_field)
        dt = to_datetime(raw_date)
        if dt is None:
            continue
        
        # Optional severity filtering
        if accident_class_field and severity_filter:
            raw_sev = r.get(accident_class_field)
            if decode_fn:
                sev = decode_fn(raw_sev)
            else:
                sev = safe_str(raw_sev).strip()
            
            sev_lower = sev.lower()
            if severity_filter.lower() == 'ksi':
                if not ('fatal' in sev_lower or 'injury' in sev_lower):
                    continue
            elif severity_filter.lower() not in sev_lower:
                continue
        
        counts[dt.year] += 1
    
    return dict(sorted(counts.items()))


def calculate_trend(
    annual_counts: Dict[int, int],
    forecast_years: int = 0
) -> TrendResult:
    """Calculate linear trend from annual collision counts.
    
    Args:
        annual_counts: Dictionary of year -> count
        forecast_years: Number of years to forecast (optional)
    
    Returns:
        TrendResult with slope, significance, and optional forecast
    """
    if len(annual_counts) < 2:
        years = tuple(annual_counts.keys()) if annual_counts else (datetime.now().year,)
        counts = tuple(annual_counts.values()) if annual_counts else (0,)
        return TrendResult(
            years=years,
            counts=counts,
            slope=0.0,
            intercept=counts[0] if counts else 0.0,
            r_squared=0.0,
            p_value=None,
            trend_direction='stable'
        )
    
    years = np.array(list(annual_counts.keys()), dtype=float)
    counts = np.array(list(annual_counts.values()), dtype=float)
    
    # Linear regression
    coeffs = np.polyfit(years, counts, 1)
    slope, intercept = coeffs[0], coeffs[1]
    
    # Calculate R-squared
    y_pred = slope * years + intercept
    ss_res = np.sum((counts - y_pred) ** 2)
    ss_tot = np.sum((counts - np.mean(counts)) ** 2)
    r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0
    
    # Calculate p-value (two-tailed t-test for slope)
    n = len(years)
    if n > 2:
        # Standard error of slope
        x_mean = np.mean(years)
        ss_x = np.sum((years - x_mean) ** 2)
        if ss_x > 0:
            s_err = np.sqrt(ss_res / (n - 2))
            se_slope = s_err / np.sqrt(ss_x)
            if se_slope > 0:
                from scipy import stats
                t_stat = slope / se_slope
                p_value = 2 * (1 - stats.t.cdf(abs(t_stat), n - 2))
            else:
                p_value = None
        else:
            p_value = None
    else:
        p_value = None
    
    # Forecast if requested
    forecast_years_tuple = None
    forecast_values_tuple = None
    if forecast_years > 0 and len(years) > 0:
        last_year = int(years[-1])
        forecast_years_list = list(range(last_year + 1, last_year + 1 + forecast_years))
        forecast_values_list = [slope * y + intercept for y in forecast_years_list]
        forecast_years_tuple = tuple(forecast_years_list)
        forecast_values_tuple = tuple(forecast_values_list)
    
    return TrendResult(
        years=tuple(int(y) for y in years),
        counts=tuple(int(c) for c in counts),
        slope=float(slope),
        intercept=float(intercept),
        r_squared=float(r_squared),
        p_value=float(p_value) if p_value is not None else None,
        forecast_years=forecast_years_tuple,
        forecast_values=forecast_values_tuple
    )


def compare_before_after(
    before_rows: List[Dict[str, Any]],
    after_rows: List[Dict[str, Any]],
    accident_class_field: str,
    before_label: str = "Before",
    after_label: str = "After",
    decode_fn: Optional[Callable[[Any], str]] = None
) -> BeforeAfterComparison:
    """Compare collision data between two time periods with statistical testing.
    
    Args:
        before_rows: Collision records from before period
        after_rows: Collision records from after period
        accident_class_field: Field name for accident classification
        before_label: Label for before period
        after_label: Label for after period
        decode_fn: Optional function to decode severity values
    
    Returns:
        BeforeAfterComparison with percent changes and statistical significance
    """
    before_sev = calculate_severity_distribution(before_rows, accident_class_field, decode_fn)
    after_sev = calculate_severity_distribution(after_rows, accident_class_field, decode_fn)
    
    before_ksi = before_sev.fatal + before_sev.injury
    after_ksi = after_sev.fatal + after_sev.injury
    
    # Calculate percent changes
    def pct_change(before: int, after: int) -> float:
        if before == 0:
            return float('inf') if after > 0 else 0.0
        return ((after - before) / before) * 100
    
    total_pct = pct_change(before_sev.total, after_sev.total)
    ksi_pct = pct_change(before_ksi, after_ksi)
    fatal_pct = pct_change(before_sev.fatal, after_sev.fatal)
    
    # Chi-square test for significance
    chi2_stat = None
    chi2_p = None
    is_sig = False
    
    try:
        from scipy.stats import chi2_contingency
        
        # Create contingency table
        # Rows: before/after, Cols: KSI/PDO
        before_pdo = before_sev.pdo + before_sev.unknown
        after_pdo = after_sev.pdo + after_sev.unknown
        
        contingency = np.array([
            [before_ksi, before_pdo],
            [after_ksi, after_pdo]
        ])
        
        # Only run test if we have sufficient data
        if np.all(contingency > 0) and np.sum(contingency) > 20:
            chi2, p_val, _, _ = chi2_contingency(contingency)
            chi2_stat = float(chi2)
            chi2_p = float(p_val)
            is_sig = p_val < 0.05
    except ImportError:
        # scipy not available, skip statistical test
        pass
    except Exception:
        # Any error in statistical test, skip it
        pass
    
    # Calculate confidence interval for total change
    ci_lower = ci_upper = None
    if before_sev.total > 0:
        # Simple 95% CI using normal approximation
        # This is a simplification; proper Poisson CI is more complex
        before_rate = before_sev.total
        after_rate = after_sev.total
        if after_rate > 0:
            se = math.sqrt((1 / before_rate) + (1 / after_rate))
            log_ratio = math.log(after_rate / before_rate)
            ci_lower = (math.exp(log_ratio - 1.96 * se) - 1) * 100
            ci_upper = (math.exp(log_ratio + 1.96 * se) - 1) * 100
    
    return BeforeAfterComparison(
        before_label=before_label,
        after_label=after_label,
        before_total=before_sev.total,
        after_total=after_sev.total,
        before_ksi=before_ksi,
        after_ksi=after_ksi,
        before_fatal=before_sev.fatal,
        after_fatal=after_sev.fatal,
        total_pct_change=total_pct,
        ksi_pct_change=ksi_pct,
        fatal_pct_change=fatal_pct,
        chi2_statistic=chi2_stat,
        chi2_p_value=chi2_p,
        is_significant=is_sig,
        total_pct_ci_lower=ci_lower,
        total_pct_ci_upper=ci_upper
    )


def identify_risk_flags(
    severity: SeverityDistribution,
    rates: Optional[RateMetrics] = None,
    trend: Optional[TrendResult] = None,
    thresholds: Optional[Dict[str, float]] = None
) -> List[str]:
    """Identify risk flags based on analytics results.
    
    Args:
        severity: Severity distribution
        rates: Rate metrics (optional)
        trend: Trend result (optional)
        thresholds: Custom thresholds for flagging
    
    Returns:
        List of risk flag descriptions
    """
    flags = []
    
    # Default thresholds
    thresh = thresholds or {}
    severe_rate_threshold = thresh.get('severe_rate', 20.0)  # 20% KSI rate
    fatal_threshold = thresh.get('fatal_count', 1)  # Any fatal
    unknown_threshold = thresh.get('unknown_rate', 5.0)  # 5% unknown
    trend_threshold = thresh.get('trend_increase', 10.0)  # 10% annual increase
    
    # Fatal collisions
    if severity.fatal >= fatal_threshold:
        flags.append(f"🚨 Fatal collisions present: {severity.fatal} in dataset")
    
    # High severe rate
    if severity.severe_rate >= severe_rate_threshold:
        flags.append(f"⚠️ High severe collision rate: {severity.severe_rate:.1f}% Fatal+Injury (≥{severe_rate_threshold}%)")
    
    # Data quality
    if severity.unknown_pct >= unknown_threshold:
        flags.append(f"📊 Data quality risk: {severity.unknown} unknown/blank severity ({severity.unknown_pct:.1f}% ≥ {unknown_threshold}%)")
    
    # Trend analysis
    if trend and trend.trend_direction == 'increasing':
        if trend.percent_change_per_year and trend.percent_change_per_year > trend_threshold:
            flags.append(f"📈 Increasing trend: ~{trend.percent_change_per_year:.1f}% per year")
        else:
            flags.append(f"📈 Increasing trend detected")
    
    # Rate-based flags
    if rates:
        if rates.ksi_rate_per_mev and rates.ksi_rate_per_mev > 50:  # >50 KSI per MEV
            flags.append(f"⚠️ High KSI rate: {rates.ksi_rate_per_mev:.1f} per million entering vehicles")
    
    return flags


def generate_insights(
    severity: SeverityDistribution,
    trend: Optional[TrendResult] = None,
    before_after: Optional[BeforeAfterComparison] = None,
    rates: Optional[RateMetrics] = None
) -> List[str]:
    """Generate practitioner-focused insights from analytics.
    
    Args:
        severity: Severity distribution
        trend: Trend result (optional)
        before_after: Before/after comparison (optional)
        rates: Rate metrics (optional)
    
    Returns:
        List of insight statements
    """
    insights = []
    
    # Severity insights
    if severity.total > 0:
        if severity.fatal > 0:
            fatal_rate = (severity.fatal / severity.total) * 100
            insights.append(f"Fatal collisions represent {fatal_rate:.1f}% of total ({severity.fatal} of {severity.total})")
        
        if severity.ksi_rate > 0:
            insights.append(f"KSI (Killed/Seriously Injured) rate: {severity.ksi_rate:.1f}% of collisions")
    
    # Trend insights
    if trend:
        if trend.trend_direction == 'decreasing':
            if trend.percent_change_per_year:
                insights.append(f"Positive trend: Collisions decreasing by ~{abs(trend.percent_change_per_year):.1f}% annually")
            else:
                insights.append("Positive trend: Collisions are decreasing over time")
        elif trend.trend_direction == 'increasing':
            if trend.percent_change_per_year:
                insights.append(f"Concern: Collisions increasing by ~{trend.percent_change_per_year:.1f}% annually")
            else:
                insights.append("Concern: Collisions are increasing over time")
        else:
            insights.append("Stable trend: No significant change in collision frequency")
        
        if trend.r_squared > 0.7:
            insights.append(f"Strong linear trend (R² = {trend.r_squared:.2f})")
        elif trend.r_squared > 0.4:
            insights.append(f"Moderate trend pattern (R² = {trend.r_squared:.2f})")
    
    # Before/after insights
    if before_after:
        if before_after.is_significant:
            direction = "decrease" if before_after.total_pct_change < 0 else "increase"
            insights.append(f"Statistically significant {direction}: {abs(before_after.total_pct_change):.1f}% change (p < 0.05)")
        
        if abs(before_after.ksi_pct_change) > abs(before_after.total_pct_change):
            if before_after.ksi_pct_change < 0:
                insights.append(f"KSI reduction outpacing overall reduction ({before_after.ksi_pct_change:.1f}% vs {before_after.total_pct_change:.1f}%)")
            else:
                insights.append(f"KSI increase exceeding overall increase ({before_after.ksi_pct_change:.1f}% vs {before_after.total_pct_change:.1f}%)")
    
    # Rate insights
    if rates:
        if rates.collision_rate_per_mev:
            insights.append(f"Collision rate: {rates.collision_rate_per_mev:.2f} per million entering vehicles")
        if rates.ksi_rate_per_mev:
            insights.append(f"KSI rate: {rates.ksi_rate_per_mev:.2f} per million entering vehicles")
        if rates.collisions_per_km:
            insights.append(f"Collision density: {rates.collisions_per_km:.2f} per km")
        if rates.collisions_per_intersection:
            insights.append(f"Collisions per intersection: {rates.collisions_per_intersection:.2f}")
    
    return insights


# =============================================================================
# Main Analytics API
# =============================================================================

def analyze_collisions(
    rows: List[Dict[str, Any]],
    field_map: Dict[str, str],
    # Exposure inputs
    entering_vehicles: Optional[float] = None,
    roadway_km: Optional[float] = None,
    intersection_count: Optional[int] = None,
    # Date range for the dataset
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    # Before/after periods (optional)
    before_start: Optional[date] = None,
    before_end: Optional[date] = None,
    after_start: Optional[date] = None,
    after_end: Optional[date] = None,
    # Decode functions
    severity_decode_fn: Optional[Callable[[Any], str]] = None,
    # Options
    calculate_trend_flag: bool = True,
    forecast_years: int = 0,
    custom_thresholds: Optional[Dict[str, float]] = None
) -> AnalyticsResult:
    """Main analytics function - comprehensive analysis of collision data.
    
    This is the primary API for collision analytics. Provide filtered rows
    and field mapping to get complete analytics results.
    
    Args:
        rows: Filtered collision records (list of attribute dictionaries)
        field_map: Mapping of concept keys to field names
        entering_vehicles: Annual/total entering vehicles for rate calculations
        roadway_km: Roadway length in km
        intersection_count: Number of intersections
        start_date: Analysis period start
        end_date: Analysis period end
        before_start: Before period start (for comparison)
        before_end: Before period end
        after_start: After period start
        after_end: After period end
        severity_decode_fn: Function to decode severity values
        calculate_trend_flag: Whether to calculate trend
        forecast_years: Years to forecast
        custom_thresholds: Custom thresholds for risk flags
    
    Returns:
        AnalyticsResult with all calculated metrics
    """
    # Get required fields
    accident_class_field = field_map.get('accident_class')
    date_field = field_map.get('date')
    
    if not accident_class_field:
        raise ValueError("Field map must include 'accident_class'")
    
    # Calculate severity distribution
    severity = calculate_severity_distribution(rows, accident_class_field, severity_decode_fn)
    
    # Calculate days in period
    days = None
    if start_date and end_date:
        days = (end_date - start_date).days + 1
    
    # Calculate rate metrics
    rates = calculate_rate_metrics(
        rows, accident_class_field,
        entering_vehicles=entering_vehicles,
        roadway_km=roadway_km,
        intersection_count=intersection_count,
        days=days,
        decode_fn=severity_decode_fn
    )
    
    # Calculate annual counts and trend
    annual_counts = None
    trend = None
    yearly_ksi = None
    
    if date_field and calculate_trend_flag:
        annual_counts = calculate_annual_counts(rows, date_field)
        if annual_counts:
            trend = calculate_trend(annual_counts, forecast_years)
            yearly_ksi = calculate_annual_counts(
                rows, date_field, accident_class_field, 'KSI', severity_decode_fn
            )
    
    # Before/after comparison
    before_after = None
    if date_field and all(d is not None for d in [before_start, before_end, after_start, after_end]):
        before_rows = []
        after_rows = []
        
        for r in rows:
            raw_date = r.get(date_field)
            dt = to_datetime(raw_date)
            if dt is None:
                continue
            r_date = dt.date() if isinstance(dt, datetime) else dt
            
            if before_start <= r_date <= before_end:
                before_rows.append(r)
            elif after_start <= r_date <= after_end:
                after_rows.append(r)
        
        if before_rows or after_rows:
            before_after = compare_before_after(
                before_rows, after_rows, accident_class_field,
                before_label=f"{before_start.year}-{before_end.year}",
                after_label=f"{after_start.year}-{after_end.year}",
                decode_fn=severity_decode_fn
            )
    
    # Identify risk flags
    risk_flags = identify_risk_flags(severity, rates, trend, custom_thresholds)
    
    # Generate insights
    insights = generate_insights(severity, trend, before_after, rates)
    
    return AnalyticsResult(
        total_records=len(rows),
        date_range=(start_date, end_date) if start_date and end_date else None,
        severity=severity,
        rates=rates,
        annual_counts=annual_counts,
        trend=trend,
        before_after=before_after,
        risk_flags=risk_flags,
        insights=insights,
        yearly_ksi_counts=yearly_ksi
    )


def quick_summary(
    rows: List[Dict[str, Any]],
    accident_class_field: str,
    decode_fn: Optional[Callable[[Any], str]] = None
) -> Dict[str, Any]:
    """Quick summary statistics without full analytics.
    
    Args:
        rows: Filtered collision records
        accident_class_field: Field name for accident classification
        decode_fn: Optional decode function
    
    Returns:
        Dictionary with key summary statistics
    """
    severity = calculate_severity_distribution(rows, accident_class_field, decode_fn)
    ksi = severity.fatal + severity.injury
    
    return {
        'total': severity.total,
        'fatal': severity.fatal,
        'injury': severity.injury,
        'pdo': severity.pdo,
        'ksi': ksi,
        'ksi_rate': severity.ksi_rate,
        'severe_rate': severity.severe_rate
    }


# =============================================================================
# Utility Functions for UI Integration
# =============================================================================

def format_rate(value: Optional[float], unit: str = "per MEV") -> str:
    """Format a rate value for display."""
    if value is None:
        return "N/A"
    if math.isinf(value):
        return "∞"
    if value < 0.01:
        return f"{value:.4f} {unit}"
    if value < 1:
        return f"{value:.3f} {unit}"
    if value < 10:
        return f"{value:.2f} {unit}"
    return f"{value:.1f} {unit}"


def format_percent(value: Optional[float], precision: int = 1) -> str:
    """Format a percentage value for display."""
    if value is None:
        return "N/A"
    if math.isinf(value):
        return "∞%"
    fmt = f"{{:.{precision}f}}%"
    return fmt.format(value)


def format_change(value: float, precision: int = 1) -> str:
    """Format a change percentage with sign indicator."""
    if math.isinf(value):
        return "+∞%" if value > 0 else "-∞%"
    prefix = "+" if value > 0 else ""
    return f"{prefix}{value:.{precision}f}%"


def rate_summary_text(rates: RateMetrics) -> str:
    """Generate a human-readable summary of rate metrics."""
    lines = []
    
    if rates.collision_rate_per_mev is not None:
        lines.append(f"Collision rate: {format_rate(rates.collision_rate_per_mev)}")
    
    if rates.ksi_rate_per_mev is not None:
        lines.append(f"KSI rate: {format_rate(rates.ksi_rate_per_mev)}")
    
    if rates.collisions_per_km is not None:
        lines.append(f"Collisions per km: {rates.collisions_per_km:.2f}")
    
    if rates.collisions_per_intersection is not None:
        lines.append(f"Collisions per intersection: {rates.collisions_per_intersection:.2f}")
    
    if rates.collisions_per_day is not None:
        lines.append(f"Daily average: {rates.collisions_per_day:.2f} collisions/day")
    
    return "\n".join(lines) if lines else "No rate data available"


def trend_summary_text(trend: TrendResult) -> str:
    """Generate a human-readable summary of trend analysis."""
    if len(trend.years) < 2:
        return "Insufficient data for trend analysis"
    
    direction_icon = {
        'increasing': '📈',
        'decreasing': '📉',
        'stable': '➡️'
    }.get(trend.trend_direction, '➡️')
    
    lines = [
        f"{direction_icon} Trend: {trend.trend_direction.title()}",
        f"   Slope: {trend.slope:+.2f} collisions/year",
        f"   R²: {trend.r_squared:.3f}",
    ]
    
    if trend.percent_change_per_year is not None:
        change = format_change(trend.percent_change_per_year)
        lines.append(f"   Avg. annual change: {change}")
    
    if trend.p_value is not None:
        sig = "significant" if trend.p_value < 0.05 else "not significant"
        lines.append(f"   Statistical significance: {sig} (p = {trend.p_value:.3f})")
    
    return "\n".join(lines)
