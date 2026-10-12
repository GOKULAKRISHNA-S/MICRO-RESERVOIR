"""Unit tests for operational alert generation, quality suppression, and severity classification.

Synthetic values are used for unit verification and strictly labelled as synthetic test data.
"""

from __future__ import annotations

from typing import Optional
import pytest

from config import (
    STATUS_INSUFFICIENT_DATA,
    STATUS_INVALID_COMPARISON,
    STATUS_POTENTIAL_DECLINE,
    STATUS_POTENTIAL_INCREASE,
    STATUS_STABLE,
)
from src.microreservoir.alerts import generate_alerts
from src.microreservoir.schemas import (
    AlertSeverity,
    ChangeComparisonResult,
)


def make_comparison_result(
    status: str,
    delta_percent: Optional[float],
    delta_ha: float = -1.5,
    quality_passed: bool = True,
    details: str = "Synthetic comparison result",
) -> ChangeComparisonResult:
    return ChangeComparisonResult(
        baseline_id="BASE",
        baseline_date="2023-10-01",
        comparison_id="COMP",
        comparison_date="2024-03-01",
        baseline_area_ha=5.0,
        comparison_area_ha=3.5,
        area_delta_ha=delta_ha,
        area_delta_percent=delta_percent,
        status=status,
        confidence_score=0.9 if quality_passed else 0.2,
        quality_passed=quality_passed,
        details=details,
        baseline_area_m2=50000.0,
        comparison_area_m2=35000.0,
        area_delta_m2=-15000.0,
    )


def test_alerts_critical_decline_with_quality_passed():
    """Verify that severe decline (<= -25%) with verified quality triggers CRITICAL alert."""
    comp = make_comparison_result(
        status=STATUS_POTENTIAL_DECLINE,
        delta_percent=-35.0,
        delta_ha=-2.5,
        quality_passed=True,
    )
    alerts = generate_alerts(comp)

    assert len(alerts) == 1
    assert alerts[0].severity == AlertSeverity.CRITICAL
    assert "Critical" in alerts[0].title
    # Verify cautionary disclaimer against inferring groundwater/drought
    assert "groundwater" in alerts[0].message.lower()


def test_alerts_failed_quality_suppresses_unqualified_decline():
    """Verify requirement: failed quality checks suppress an unqualified decline alert.

    Even if delta is -35% (ordinarily CRITICAL), failing quality checks must downgrade
    the alert to WARNING and label it as unverified.
    """
    comp = make_comparison_result(
        status=STATUS_POTENTIAL_DECLINE,
        delta_percent=-35.0,
        delta_ha=-2.5,
        quality_passed=False,
        details="Cloud cover 35% exceeded maximum limit; quality checks failed.",
    )
    alerts = generate_alerts(comp)

    assert len(alerts) == 1
    # Must NOT be CRITICAL!
    assert alerts[0].severity == AlertSeverity.WARNING
    assert "Unverified" in alerts[0].title
    assert "quality checks failed" in alerts[0].message.lower()


def test_alerts_moderate_decline():
    """Verify that moderate decline (e.g. -15%) triggers WARNING alert."""
    comp = make_comparison_result(
        status=STATUS_POTENTIAL_DECLINE,
        delta_percent=-15.0,
        delta_ha=-0.75,
        quality_passed=True,
    )
    alerts = generate_alerts(comp)

    assert len(alerts) == 1
    assert alerts[0].severity == AlertSeverity.WARNING
    assert "Decline" in alerts[0].title
    assert "groundwater" in alerts[0].message.lower()


def test_alerts_storage_increase():
    """Verify that storage increase triggers INFO alert."""
    comp = make_comparison_result(
        status=STATUS_POTENTIAL_INCREASE,
        delta_percent=40.0,
        delta_ha=2.0,
    )
    alerts = generate_alerts(comp)

    assert len(alerts) == 1
    assert alerts[0].severity == AlertSeverity.INFO
    assert "Expansion" in alerts[0].title


def test_alerts_zero_baseline_delta_none():
    """Verify that zero baseline (delta_percent=None) does not crash and generates safe alert."""
    comp = make_comparison_result(
        status=STATUS_POTENTIAL_INCREASE,
        delta_percent=None,  # undefined from zero baseline
        delta_ha=1.0,
    )
    alerts = generate_alerts(comp)

    assert len(alerts) == 1
    assert alerts[0].severity == AlertSeverity.INFO
    assert "Expansion" in alerts[0].title


def test_alerts_insufficient_data():
    """Verify that insufficient data produces a WARNING alert."""
    comp = make_comparison_result(
        status=STATUS_INSUFFICIENT_DATA,
        delta_percent=None,
        delta_ha=0.0,
        quality_passed=False,
    )
    alerts = generate_alerts(comp)

    assert len(alerts) == 1
    assert alerts[0].severity == AlertSeverity.WARNING
    assert "Insufficient Data" in alerts[0].title


def test_alerts_invalid_comparison():
    """Verify that invalid comparison produces a WARNING alert."""
    comp = make_comparison_result(
        status=STATUS_INVALID_COMPARISON,
        delta_percent=None,
        delta_ha=0.0,
        quality_passed=False,
    )
    alerts = generate_alerts(comp)

    assert len(alerts) == 1
    assert alerts[0].severity == AlertSeverity.WARNING
    assert "Invalid" in alerts[0].title


def test_alerts_stable():
    """Verify that stable status produces an INFO notification."""
    comp = make_comparison_result(
        status=STATUS_STABLE,
        delta_percent=-1.2,
        delta_ha=-0.05,
    )
    alerts = generate_alerts(comp)

    assert len(alerts) == 1
    assert alerts[0].severity == AlertSeverity.INFO
    assert "Stable" in alerts[0].title
