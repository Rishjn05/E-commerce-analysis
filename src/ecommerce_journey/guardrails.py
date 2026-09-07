"""Guardrail metrics for the cart-recovery experiment.

The Retailrocket source has no notification, refund, margin, or delivery
fields, so guardrails cannot be computed from the historical data — the
README and docs/experiment_design.md say this explicitly. This module does
two honest things instead of pretending otherwise:

1. Defines each guardrail metric precisely (formula + decision threshold),
   so the definitions are ready to wire up the day the real event stream
   exists.
2. Runs a labeled *synthetic* Monte Carlo simulation of what monitoring
   these guardrails during the test would look like, so the experiment
   dashboard and stopping rules can be built and rehearsed before launch.
   Every value produced here is synthetic and must never be reported as an
   observed result.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

GUARDRAIL_METRICS = {
    "notification_opt_out_rate_pct": {
        "definition": (
            "Recipients who opt out of reminder notifications within 7 days "
            "of receipt / recipients who received a reminder."
        ),
        "direction": "lower is better",
        "stop_threshold": "treatment arm exceeds control arm by >1.0pp",
        "required_fields": ["notification_sent", "notification_opt_out"],
    },
    "complaint_rate_pct": {
        "definition": (
            "Recipients filing a support complaint referencing the reminder "
            "within 7 days / recipients who received a reminder."
        ),
        "direction": "lower is better",
        "stop_threshold": "treatment arm exceeds control arm by >0.5pp",
        "required_fields": ["support_ticket", "ticket_reason_tag"],
    },
    "refund_or_cancellation_rate_pct": {
        "definition": (
            "Orders refunded or canceled within 14 days / orders placed, "
            "among the 7-day conversion cohort."
        ),
        "direction": "lower is better",
        "stop_threshold": "treatment arm exceeds control arm by >2.0pp",
        "required_fields": ["order_id", "refund_flag", "cancellation_flag"],
    },
    "gross_margin_per_order": {
        "definition": (
            "(Order revenue - COGS - discount value) / orders placed, among "
            "the 7-day conversion cohort."
        ),
        "direction": "should not drop materially vs. control",
        "stop_threshold": "treatment arm margin/order falls >10% below control",
        "required_fields": ["order_id", "revenue", "cogs", "discount_value"],
    },
    "delivery_failure_rate_pct": {
        "definition": (
            "Orders marked failed/undeliverable / orders placed, among the "
            "7-day conversion cohort."
        ),
        "direction": "lower is better",
        "stop_threshold": "treatment arm exceeds control arm by >1.5pp",
        "required_fields": ["order_id", "delivery_status"],
    },
}


def guardrail_definitions_table() -> pd.DataFrame:
    rows = []
    for name, spec in GUARDRAIL_METRICS.items():
        rows.append({"metric": name, **spec})
    return pd.DataFrame(rows)


def simulate_guardrail_monitoring(
    sample_size_per_arm: int,
    weeks: int = 9,
    seed: int = 42,
) -> pd.DataFrame:
    """Synthetic weekly guardrail monitoring feed for dashboard rehearsal.

    Assumes no true guardrail degradation (control and treatment drawn from
    the same underlying rate) so this simulation should show occasional
    noise-driven flags but no persistent trend — that is the expected,
    healthy pattern the dashboard should be able to distinguish from a real
    regression once live data is wired in.
    """
    rng = np.random.default_rng(seed)
    baseline_rates = {
        "notification_opt_out_rate_pct": 3.0,
        "complaint_rate_pct": 0.4,
        "refund_or_cancellation_rate_pct": 5.0,
        "delivery_failure_rate_pct": 1.2,
    }

    rows = []
    weekly_n = max(sample_size_per_arm // weeks, 1)
    for week in range(1, weeks + 1):
        for metric, baseline_pct in baseline_rates.items():
            control_events = rng.binomial(weekly_n, baseline_pct / 100)
            treatment_events = rng.binomial(weekly_n, baseline_pct / 100)
            control_rate = 100 * control_events / weekly_n
            treatment_rate = 100 * treatment_events / weekly_n
            rows.append(
                {
                    "week": week,
                    "metric": metric,
                    "arm_n": weekly_n,
                    "control_rate_pct": round(control_rate, 3),
                    "treatment_rate_pct": round(treatment_rate, 3),
                    "delta_pp": round(treatment_rate - control_rate, 3),
                    "is_synthetic": True,
                }
            )

    return pd.DataFrame(rows)
