# Modal Pricing & Packaging Analyzer

A Streamlit app for exploring Modal's serverless GPU pricing model — built as a
demo for a BizOps Manager application at Modal.

## What it does

Three tabs:

**Workload Cost Modeler** — configure a GPU workload (GPU type, CPU, memory, job
runtime, jobs/day) and apply Modal's production multipliers (region up to 2.5×,
non-preemptible 3×). Shows cost per job, daily, monthly, and the component
breakdown. The main output is the "naive estimate vs production reality" delta —
the number customers get surprised by when they see their first real bill.

**Breakeven vs Reserved Instances** — plots Modal's per-second cost (flat line)
against a representative reserved-instance cost (decreasing curve) across the
0–100% utilization range. The key insight: Modal wins at low/bursty utilization
and loses above the breakeven point, which falls around 50–65% depending on GPU
tier and the reserved benchmark. The chart marks the breakeven and the user's
current utilization so the trade-off is immediately visible.

**Packaging Strategy Notes** — four BizOps observations on where the per-second
model is a competitive moat, the multiplier-stacking transparency problem, the
committed-use gap that causes churn at sustained utilization, and GPU tier mix
as a packaging lever.

## Key insight

Modal's per-second billing is structurally cheaper for bursty workloads and
penalizes sustained high-utilization loads. Compounding production multipliers
(region × guaranteed execution) can push a $1,000/mo base estimate to $6,000/mo
or more — without the customer necessarily expecting it. The breakeven with
reserved instances sits in the 50–65% utilization range for H100-class GPUs at
common reserved benchmarks.

## How to run

```bash
pip install -r requirements.txt
streamlit run app.py
```

Then open http://localhost:8501 in your browser. No API keys or environment
variables required — all computation is on user inputs.

## Deployment

Deploy directly to [Streamlit Cloud](https://streamlit.io/cloud): connect the
repo, set `app.py` as the main file, no secrets needed.

## Pricing source

All GPU, CPU, and memory rates are from **modal.com/pricing** as of May 2026.
The reserved-instance benchmark rate in Tab 2 is user-adjustable and clearly
labeled as illustrative — it is not a real vendor quote.
