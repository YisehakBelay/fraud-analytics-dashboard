# 📊 Fraud Analytics Dashboard

> **CIS 444 – Data Analytics Final Project** | Minnesota State University, Mankato  
> **Team:** Rob Kokx · James Kemp · Yisehak Belay  
> **Stack:** MongoDB · Python (pymongo, pandas) · Power BI · Star Schema

---

## Overview

A full end-to-end data analytics pipeline built over a **13.3 million transaction** financial dataset. The project answers 10 business-critical KPIs spanning customer segmentation, geographic spending behavior, and fraud/risk signals — all surfaced through an interactive Power BI dashboard.

The core challenge: Power BI cannot load 13.3M raw MongoDB documents efficiently. The solution was to push all aggregation logic into MongoDB pipelines, exporting small, pre-computed JSON files that Power BI loads instantly.

---

## Dataset

**Financial Transactions Dataset** (Kaggle) — synthetic but realistic, mirroring a mid-sized card issuer.

| Collection | Records | Description |
|---|---|---|
| `transactions_data` | ~13.3M | Fact table — every card swipe, online purchase, chip transaction |
| `cards_data` | ~6,000 | Card type, brand, credit limit, chips, issued count |
| `user_data` | ~2,000 | Client demographics, income, location, retirement status |

**Key data quirk:** All monetary fields are stored as strings with a leading `$` sign (e.g., `"$42.50"`). Every pipeline converts these via `$substr` + `$toDouble` before aggregating.

---

## Architecture

```
MongoDB (localhost:27017)
    └── finals_database_project
            ├── transactions_data  ← fact collection (13.3M docs)
            ├── cards_data         ← dimension
            └── user_data          ← dimension

        ↓ Python aggregation pipelines (pymongo)

JSON output files (one per KPI)

        ↓ Loaded into Power BI

Interactive Dashboard
    ├── Customer Segmentation
    ├── Geographic Behavior
    └── Fraud & Risk Signals
```

---

## The 10 KPIs

| # | Question | Visual Type |
|---|---|---|
| 1 | Compare client demographics (age/retirement/income) vs avg transaction | Clustered bar |
| 2 | Compare card type/brand/credit limit vs avg transaction | Matrix |
| 3 | Top 10 states by total & average transaction amount | Filled map |
| 4 | Top 10 states by transaction count | Filled map |
| 5 | Chip vs swipe vs online — count, total, average | Donut chart |
| 6 | Cards spending >80% of per-capita income in a year | Table |
| 7 | Day vs night transaction volume and value | KPI cards |
| 8 | Cards/users with more than 1 transaction error | Table |
| 9 | Negative transaction amounts ordered by state | Clustered bar |
| 10 | Overdraw rate: single-issued cards vs dual-issued cards | Donut chart |

---

## Pipeline Highlights

### Q6 — High Spenders (>80% of per-capita income)
```python
pipeline_totals = [
    { "$addFields": { "amountNum": { "$toDouble": { "$substr": ["$amount", 1, -1] } }}},
    { "$group": {
        "_id": {
            "card":      "$card_id",
            "client_id": "$client_id",
            "year":      { "$year": { "$dateFromString": { "dateString": "$date", "format": "%Y-%m-%d %H:%M:%S" } } }
        },
        "totalSpent": { "$sum": "$amountNum" }
    }}
]
# Then cross-reference against user per_capita_income in Python
```

### Q8 — Error Cards (`$lookup` join)
```python
query8 = [
    { "$match": { "errors": { "$exists": True } } },
    { "$group": { "_id": "$card_id", "errorCount": { "$sum": 1 }, ... } },
    { "$match": { "errorCount": { "$gt": 1 } } },
    { "$lookup": { "from": "user_data", "localField": "client_id", "foreignField": "id", "as": "customer" } },
    ...
]
```

---

## Project Structure

```
fraud-analytics-dashboard/
├── final_project.py                     # All 10 MongoDB aggregation pipelines
├── pipelines/
│   ├── demographics_avg_transaction.json
│   ├── card_type_avg_transaction.json
│   ├── top_states_amount.json
│   ├── top_states_count.json
│   ├── transaction_type_comparison.json
│   ├── high_spenders.json
│   ├── day_vs_night.json
│   ├── error_cards.json
│   ├── negative_transactions_by_state.json
│   └── overdraw_percentage.json
├── CS444_Visuals.pbix                   # Power BI dashboard file
└── docs/
    ├── Deliverable_1_Dataset_Questions.docx
    ├── Deliverable_3_KPI_Query_Lineage.docx
    ├── Deliverable_4_Final_Report.docx
    └── 444_project_plan_outline.docx
```

---

## How to Run

```bash
# 1. Install dependencies
pip install pymongo pandas

# 2. Start MongoDB and import your collections
mongoimport --db finals_database_project --collection transactions_data --file transactions_data.json
mongoimport --db finals_database_project --collection cards_data --file cards_data.json
mongoimport --db finals_database_project --collection user_data --file user_data.json

# 3. Run the pipeline (note: Q6 over 13.3M records takes several minutes)
python final_project.py

# 4. Open CS444_Visuals.pbix in Power BI Desktop
#    Refresh data sources pointing to the output JSON files
```

---

## Key Results

- **13.3M transactions** aggregated and summarized to under 100KB of JSON per KPI
- Identified cards spending **>80% of local per-capita income** as high-risk signals
- Dual-issued cards showed a measurably different overdraft rate than single-issued cards
- Night transactions (10pm–6am) had distinct volume and average-spend patterns vs daytime

---

## Dashboard Sections

| Section | KPIs Covered |
|---|---|
| **Customer Segmentation** | Demographics vs spend, card type vs spend |
| **Geographic Behavior** | Top states by amount, top states by count |
| **Fraud & Risk Signals** | High spenders, error cards, negative transactions, overdraft rates |
