# Anviksha / SPARK MVP (updated)

## Included capabilities
- Existing services retained: inventory and demand analytics; sales/customer analytics; owner's weekly scorecard; collections and 13-week cash outlook; quality and batch analytics.
- New AI decision assistant page: uses calculated KPIs and open-invoice / inventory context. Optional local Ollama-compatible endpoint can rephrase grounded results.
- New Forecast & Optimization page: 13-week cash scenarios plus budget-constrained inventory reorder prioritization.
- Existing consultant review, owner decision and outcome tracker remain the SME decision workflow.

## Run
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Important notes
- Use anonymized/demo data first. Review privacy, authentication, tenant isolation, and deployment security before exposing this to real customers.
- The inventory replenishment routine is a transparent priority heuristic, not a mathematically guaranteed global optimum.
- Cash projections depend on the accuracy of invoices, payment history, opening cash and weekly inflow/outflow assumptions.
- The optional local LLM URL expects an Ollama-compatible `/api/generate` endpoint. Leave it blank to use rule-based explanations.


## Visual analytics upgrade
- Overview dashboard now includes monthly sales trend, receivables risk bands, inventory stock-cover/demand scatter plot, and top-customer revenue concentration.
- Inventory analysis includes stock-vs-reorder-point and stock-cover-vs-demand charts.
- Sales/customer and collections views use a consistent visual style, formatted axes, hover tooltips and risk-weighted exposure.
- Charts are interactive Altair visuals and respond to the uploaded client dataset.


## Dashboard depth upgrade
- Added revenue vs gross-profit trend and monthly gross-margin trend to overview.
- Added customer profitability map and discount-leakage ranking.
- Added manufacturing quality KPI cards, reject-rate ranking and production-vs-reject scatter plot.
- Added receivables ageing bands alongside risk-weighted collection prioritization.
- Applied shared chart typography, axis formatting, tooltips, tab styling and wider responsive workspace.
- Visuals use uploaded data; modules remain conditional where source data is absent.
