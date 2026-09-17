# E-commerce Journey Analytics

Product analysis of 2.76 million real e-commerce events: session funnel,
retention, behavioral segments, and the design of a cart-recovery experiment.

The project answers one decision question:

> Which next experiment is most defensible if the product team wants to
> increase purchase conversion with the event data currently available?

## Decision summary

The best-supported next step is a cart-recovery experiment for recognized,
contactable visitors. It is a testable recommendation, not a causal conclusion
from observational data.

- The fixed source contains 2,756,101 events from 1,407,580 anonymized visitor
  IDs. After removing 460 exact duplicate rows, a 30-minute inactivity rule
  produces 1,761,675 sessions.
- Only 0.81% of sessions contain a transaction. Returning sessions convert at
  1.91% versus 0.53% for first sessions, a 3.58x descriptive difference. After
  excluding visitors above the 99.9th percentile of session count, the rates
  are 1.56% and 0.53%, so the pattern is not explained only by the heaviest
  visitors.
- There are 31,992 sessions with a cart event and no transaction in the same
  session. Among first observed cart-abandonment cases with a complete
  seven-day follow-up, 1,369 of 27,784 visitors purchase later: a natural
  recovery rate of 4.93%.
- With about 1,483 newly eligible visitors per complete week, detecting a 25%
  relative lift over the 4.93% baseline requires approximately 5,416 visitors
  per arm and nine calendar weeks, including the outcome window.

The data do not contain checkout steps, acquisition source, device, revenue,
stock status, or experiment assignment. Therefore they support prioritizing a
test and improving instrumentation, but not claiming why a visitor abandoned a
cart or how much revenue an intervention would create.

## Main evidence

The largest observed loss is before an add-to-cart event, while 29.06% of
ordered view-to-cart sessions continue to a transaction in the same session.
This identifies the stage, but not the underlying friction.

![Observed within-session funnel conversion](outputs/figures/01_funnel_conversion.png)

Returning visitor IDs are substantially more likely to transact. The
sensitivity cut shows that a small group of unusually active visitors
strengthens, but does not create, this pattern.

![Transaction-session rate by visitor status](outputs/figures/03_visitor_status_conversion.png)

Cart abandoners form a smaller but high-intent audience with a measurable
post-session baseline. This makes a recovery intervention more specific and
testable than a broad redesign based on the current schema.

![Natural purchase recovery after cart abandonment](outputs/figures/05_cart_recovery.png)

Weekly retention is low and declines quickly. Because `visitor_id` is an
anonymous identifier, this is visitor-ID return activity rather than verified
person-level retention.

![Weekly visitor-ID retention](outputs/figures/04_cohort_retention.png)

## Behavioral segmentation

`sql/05_segmentation.sql` builds a visitor-level feature table (recency,
session frequency, average events per session, session duration, and
funnel-progression rates), and `src/ecommerce_journey/segmentation.py` fits a
k-means model on top of it. Cluster count is chosen by silhouette score over
k = 3..6 rather than fixed in advance, and segment labels (e.g. "high-intent
converters", "casual browsers", "lapsed / one-and-done") are assigned by
ranking cluster centroids on purchase and engagement behavior, not
hand-picked per run.

These are *behavioral* segments, not persona or taste segments — the fixed
source has no category, price, or demographic fields, so a visitor is
grouped only by how they browse and convert.

Run `python scripts/run_pipeline.py` to generate `outputs/tables/visitor_segments.csv`,
`outputs/tables/segment_profiles.csv`, and `outputs/figures/06_segment_profiles.png`
against the current data.

## Cart-abandonment diagnostics

`sql/06_abandonment_diagnostics.sql` breaks first-observed cart abandonment
and its 7-day recovery down by hour of day, weekday, session duration, cart
size, and visitor status at the time of abandonment. This is an associative
breakdown of observational data — it shows *where* abandonment and recovery
concentrate, not *why* a given visitor abandoned, since the source has no
checkout, price, or acquisition fields. Read it as a prioritization input for
the experiment above, not a causal explanation.

Run `python scripts/run_pipeline.py` to generate the `abandonment_by_*`
tables and `outputs/figures/07_abandonment_diagnostics.png`.

## Product and metric framework

The product is an anonymized multi-category e-commerce site. A visitor can
generate `view`, `addtocart`, and `transaction` events.

| Role | Metric | Definition |
|---|---|---|
| Outcome | Transaction-session rate | Sessions with at least one transaction / all sessions |
| Funnel driver | Ordered view-to-cart rate | View sessions with a later cart event / view sessions |
| Funnel driver | Ordered cart-to-transaction rate | Ordered view-to-cart sessions with a later transaction / ordered view-to-cart sessions |
| Retention | Weekly visitor-ID retention | Cohort visitors with any event in week W1-W8 / cohort size |
| Experiment outcome | Seven-day purchase conversion | Eligible assigned visitors with a transaction within seven days / all eligible assigned visitors |

For an actual cart-recovery test, product-quality guardrails should include
notification opt-outs or complaints, refunds or cancellations, gross margin,
and delivery failures. These fields are not present in the public dataset and
must be instrumented before the test. [docs/guardrail_metrics.md](docs/guardrail_metrics.md)
fixes the formula and stop rule for each guardrail now, and ships a labeled
*synthetic* monitoring simulation (`src/ecommerce_journey/guardrails.py`) so
the monitoring dashboard and stopping logic can be built and rehearsed before
the real fields exist — every simulated row is tagged `is_synthetic: true`.

## Data and quality controls

The project uses version 4 of the
[Retailrocket recommender system dataset](https://www.kaggle.com/datasets/retailrocket/ecommerce-dataset).
It contains anonymized behavior from 3 May to 18 September 2015.

Key controls:

- fixed source and `events.csv` SHA-256 checks;
- exact-row deduplication before metrics;
- required-field, event-domain, and transaction-ID consistency checks;
- UTC conversion of Unix timestamps;
- 15/30/60-minute session-gap sensitivity;
- exclusion of partial boundary weeks;
- right-censoring for retention and cart-recovery horizons;
- a concentration cut for visitors above the 99.9th percentile of session
  count.

The transaction rows are item-level: 22,457 transaction item events correspond
to 17,672 distinct transaction IDs. Session conversion therefore uses the
presence of a transaction rather than summing transaction rows.


## Repository structure

```text
ecommerce-journey-analytics/
├── data/                       
├── docs/
│   ├── experiment_design.md
│   └── guardrail_metrics.md
├── notebooks/
│   └── 01_ecommerce_journey_analysis.ipynb
├── outputs/
│   ├── figures/                
│   ├── tables/                
│   ├── summary_metrics.json
│   └── validation_report.txt
├── scripts/
│   ├── download_data.py
│   ├── run_pipeline.py
│   └── validate_project.py
├── sql/                        
│   ├── 00_build_model.sql ... 04_cart_recovery.sql
│   ├── 05_segmentation.sql             Visitor behavioral-feature table
│   └── 06_abandonment_diagnostics.sql  Abandonment/recovery cuts
└── src/ecommerce_journey/      Python pipeline, plots, power, validation
    ├── segmentation.py         K-means behavioral segmentation
    └── guardrails.py           Guardrail definitions + synthetic simulation
```


python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt

python scripts\download_data.py
python scripts\run_pipeline.py
```


To rerun validation separately:

```powershell
python scripts\validate_project.py
```

Open the executed notebook:

```powershell
jupyter lab notebooks\01_ecommerce_journey_analysis.ipynb
```


