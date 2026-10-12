"""Alerting and notification module for micro-reservoir storage changes.

Translates comparison results into structured operational alerts with severity
ratings, quality-aware safeguards, and actionable advisory recommendations.
"""

from __future__ import annotations

from typing import List, Optional

from config import (
    DEFAULT_CONFIG,
    STATUS_INSUFFICIENT_DATA,
    STATUS_INVALID_COMPARISON,
    STATUS_POTENTIAL_DECLINE,
    STATUS_POTENTIAL_INCREASE,
    STATUS_STABLE,
    AppConfig,
)
from src.microreservoir.schemas import (
    AlertItem,
    AlertSeverity,
    ChangeComparisonResult,
)


def generate_alerts(
    comparison: ChangeComparisonResult,
    cfg: Optional[AppConfig] = None,
) -> List[AlertItem]:
    """Generate operational alerts based on reservoir surface water transitions.

    Safeguards:
      1. A potential-decline alert is NOT issued as reliable when quality checks fail,
         valid coverage is insufficient, or comparisons are invalid.
      2. Surface-water changes must not infer groundwater depletion or regional
         drought without external corroboration; explicit caveats are included.
      3. Safely handles None delta percentages (e.g. from zero baseline).

    Args:
        comparison: ChangeComparisonResult from bi-temporal analysis.
        cfg: Optional application configuration with alert threshold cutoffs.

    Returns:
        List of AlertItem instances ordered by operational severity.
    """
    config = cfg or DEFAULT_CONFIG
    alerts: List[AlertItem] = []

    # 1. Invalid Comparison Handling
    if comparison.status == STATUS_INVALID_COMPARISON:
        alerts.append(
            AlertItem(
                severity=AlertSeverity.WARNING,
                title="Invalid Observation Comparison",
                message=(
                    f"Temporal comparison rejected due to spatial or temporal incompatibility: "
                    f"{comparison.details} Surface water change could not be assessed."
                ),
                action_recommended=(
                    "Verify identical CRS, aligned pixel grid, strict temporal order, and valid metadata."
                ),
            )
        )
        return alerts

    # 2. Insufficient Data Handling
    if comparison.status == STATUS_INSUFFICIENT_DATA:
        alerts.append(
            AlertItem(
                severity=AlertSeverity.WARNING,
                title="Insufficient Data For Reliable Assessment",
                message=(
                    f"Excessive cloud cover or nodata values prevented conclusive comparison: "
                    f"{comparison.details} Reliable change detection cannot be performed."
                ),
                action_recommended=(
                    "Acquire next cloud-free scene or query alternate sensor constellation (e.g. Landsat-8/9)."
                ),
            )
        )
        return alerts

    # 3. Potential Decline Alerts (Quality-Aware)
    if comparison.status == STATUS_POTENTIAL_DECLINE:
        # Safeguard: suppress unqualified decline alert if quality checks failed
        if not comparison.quality_passed:
            alerts.append(
                AlertItem(
                    severity=AlertSeverity.WARNING,
                    title="Unverified Potential Water Decline (Quality Checks Failed)",
                    message=(
                        f"Apparent water shrinkage of {abs(comparison.area_delta_ha):.3f} ha observed, "
                        f"but quality checks failed or data is unverified ({comparison.details}). "
                        f"This decline cannot be confirmed as reliable surface-water loss. "
                        f"Note: Surface-water extent shifts do not infer groundwater depletion or drought."
                    ),
                    action_recommended=(
                        "Do not execute operational restrictions. Perform ground validation and re-analyze "
                        "with cloud-free imagery passing all quality checks."
                    ),
                )
            )
        elif (
            comparison.area_delta_percent is not None
            and comparison.area_delta_percent <= config.critical_decline_threshold_percent
        ):
            # Critical Decline
            m2_lost = abs(comparison.area_delta_m2) if comparison.area_delta_m2 is not None else 0.0
            alerts.append(
                AlertItem(
                    severity=AlertSeverity.CRITICAL,
                    title="Critical Reservoir Surface Area Depletion",
                    message=(
                        f"Severe water shrinkage detected: {comparison.area_delta_percent:.1f}% reduction "
                        f"({abs(comparison.area_delta_ha):.3f} ha / {m2_lost:,.0f} m² lost) between "
                        f"{comparison.baseline_date} and {comparison.comparison_date}. "
                        f"Note: Surface-water decline reflects open surface extent only and must NOT be used "
                        f"to infer groundwater depletion or confirmed drought without external hydrological data."
                    ),
                    action_recommended=(
                        "Trigger priority on-ground ground-truthing; inspect reservoir bunds for seepage; "
                        "restrict non-essential agricultural discharge."
                    ),
                )
            )
        else:
            # Moderate Decline
            pct_str = (
                f"{comparison.area_delta_percent:.1f}%"
                if comparison.area_delta_percent is not None
                else "unquantified"
            )
            alerts.append(
                AlertItem(
                    severity=AlertSeverity.WARNING,
                    title="Potential Surface Water Decline Observed",
                    message=(
                        f"Moderate water contraction detected: {pct_str} change "
                        f"({abs(comparison.area_delta_ha):.3f} ha lost) from baseline {comparison.baseline_date}. "
                        f"Note: Surface-water decline alone does not infer groundwater depletion or regional drought."
                    ),
                    action_recommended=(
                        "Monitor evaporation trajectory in next satellite overpass; cross-check with local "
                        "rainfall records."
                    ),
                )
            )
        return alerts

    # 4. Storage Increase / Expansion Alert
    if comparison.status == STATUS_POTENTIAL_INCREASE:
        pct_str = (
            f"{comparison.area_delta_percent:+.1f}%"
            if comparison.area_delta_percent is not None
            else "new storage observed"
        )
        m2_gain = comparison.area_delta_m2 if comparison.area_delta_m2 is not None else 0.0
        alerts.append(
            AlertItem(
                severity=AlertSeverity.INFO,
                title="Reservoir Storage Expansion Detected",
                message=(
                    f"Water surface expanded by {pct_str} (+{comparison.area_delta_ha:.3f} ha / "
                    f"+{m2_gain:,.0f} m²) on {comparison.comparison_date}."
                ),
                action_recommended=(
                    "Inflow replenishment noted (post-rain/canal feed); log updated capacity baseline."
                ),
            )
        )
        return alerts

    # 5. Stable State Notification
    if comparison.status == STATUS_STABLE:
        pct_str = (
            f"{comparison.area_delta_percent:+.1f}%"
            if comparison.area_delta_percent is not None
            else "0.0%"
        )
        alerts.append(
            AlertItem(
                severity=AlertSeverity.INFO,
                title="Reservoir Area Stable",
                message=(
                    f"Water surface area remains stable within expected variation bounds "
                    f"({pct_str} shift)."
                ),
                action_recommended="Continue routine temporal monitoring cycle.",
            )
        )
        return alerts

    return alerts
