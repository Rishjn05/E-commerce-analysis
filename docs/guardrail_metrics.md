# Guardrail metrics for the cart-recovery experiment

`docs/experiment_design.md` names five guardrails and states plainly that the
public RetailRocket dataset contains none of the fields needed to compute
them. This document is the concrete follow-up: it fixes the formula and stop
rule for each guardrail now, and separately provides a labeled *synthetic*
monitoring simulation so the dashboard and stopping logic can be built and
rehearsed before the real event stream exists.

Both pieces are implemented in `src/ecommerce_journey/guardrails.py` and
exported by the pipeline to `outputs/tables/guardrail_metric_definitions.csv`
and `outputs/tables/guardrail_simulated_monitoring.csv`.

## Metric definitions

| Metric | Formula | Direction | Stop rule | Required fields (not in current source) |
|---|---|---|---|---|
| Notification opt-out rate | Recipients who opt out within 7 days of a reminder / recipients who received a reminder | Lower is better | Treatment exceeds control by >1.0pp | `notification_sent`, `notification_opt_out` |
| Complaint rate | Recipients filing a support complaint referencing the reminder within 7 days / recipients who received a reminder | Lower is better | Treatment exceeds control by >0.5pp | `support_ticket`, `ticket_reason_tag` |
| Refund / cancellation rate | Orders refunded or canceled within 14 days / orders placed, among the 7-day conversion cohort | Lower is better | Treatment exceeds control by >2.0pp | `order_id`, `refund_flag`, `cancellation_flag` |
| Gross margin per order | (Revenue − COGS − discount) / orders placed, among the 7-day conversion cohort | Should not drop materially vs. control | Treatment margin/order falls >10% below control | `order_id`, `revenue`, `cogs`, `discount_value` |
| Delivery failure rate | Orders marked failed/undeliverable / orders placed, among the 7-day conversion cohort | Lower is better | Treatment exceeds control by >1.5pp | `order_id`, `delivery_status` |

Stop thresholds are starting points for discussion with product and CRM
owners, not statistically derived bounds — the dataset doesn't contain
enough guardrail history to calibrate them empirically.

## Why a synthetic simulation, and not real numbers

The honest state of this project is: guardrail metrics are *defined*, not
*observed*. `simulate_guardrail_monitoring()` generates a synthetic
week-by-week feed, drawing control and treatment from the **same** assumed
baseline rate (i.e., simulating the "no true effect" null case), so that:

- the weekly monitoring table and any dashboard built on top of it can be
  built and tested before the real experiment ships;
- reviewers can see what normal noise looks like against each stop rule,
  which is a useful reference for calibrating alert sensitivity;
- every row is tagged `is_synthetic: true` so it can never be mistaken for
  an observed result.

None of the numbers in `guardrail_simulated_monitoring.csv` are measurements
of real user behavior. They should be replaced the moment the fields above
are instrumented and the test goes live.

## Wiring in real data later

Once `notification_sent`, `order_id`, `refund_flag`, etc. exist in the event
stream, replace `simulate_guardrail_monitoring()` with a query against those
tables using the same formulas and stop rules defined above and in
`GUARDRAIL_METRICS`, so the dashboard code and thresholds don't need to
change — only the data source does.
