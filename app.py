import streamlit as st
import plotly.graph_objects as go
import numpy as np

st.set_page_config(
    page_title="Modal Pricing Analyzer",
    page_icon="modal",
    layout="wide",
)

# ── BRAND ─────────────────────────────────────────────────────────────────────
GREEN = "#7FEE64"
GREEN_DIM = "#4DBF40"
AMBER = "#F5A623"
RED = "#E05252"
CARD_BG = "#161616"
BORDER = "#272727"

st.markdown(f"""
<style>
  /* Global font */
  html, body, [class*="css"] {{
    font-family: -apple-system, BlinkMacSystemFont, "Inter", "Segoe UI", sans-serif;
  }}

  /* Cards */
  .m-card {{
    background: {CARD_BG};
    border: 1px solid {BORDER};
    border-radius: 12px;
    padding: 16px 20px;
    text-align: center;
    height: 100%;
  }}
  .m-card .m-label {{
    color: #666;
    font-size: 0.75em;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    margin-bottom: 6px;
  }}
  .m-card .m-value {{
    font-size: 1.65em;
    font-weight: 700;
    line-height: 1.1;
    letter-spacing: -0.02em;
  }}
  .m-card .m-sub {{
    font-size: 0.74em;
    margin-top: 4px;
    color: #555;
  }}
  .green {{ color: {GREEN}; }}
  .amber {{ color: {AMBER}; }}
  .red   {{ color: {RED}; }}
  .muted {{ color: #888; }}

  /* Alert box */
  .m-alert {{
    background: #1C1212;
    border: 1px solid #3A2020;
    border-left: 3px solid {RED};
    border-radius: 8px;
    padding: 12px 16px;
    margin: 12px 0;
    font-size: 0.9em;
    color: #ccc;
  }}

  /* Verdict box */
  .m-verdict {{
    background: #111;
    border: 1px solid {BORDER};
    border-left: 3px solid {GREEN};
    border-radius: 8px;
    padding: 14px 18px;
    margin-top: 14px;
    font-size: 0.92em;
    color: #ccc;
    line-height: 1.6;
  }}

  /* Section label */
  .m-section {{
    color: #444;
    font-size: 0.7em;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    margin: 20px 0 6px 0;
  }}

  /* Metric overrides — hide arrow icons */
  [data-testid="stMetricDelta"] svg {{ display: none; }}

  /* Active tab underline */
  button[data-baseweb="tab"][aria-selected="true"] {{
    color: {GREEN} !important;
    border-bottom: 2px solid {GREEN} !important;
  }}

  /* Header subtitle */
  .m-subtitle {{
    color: #555;
    font-size: 0.82em;
    margin-top: 0;
    margin-bottom: 0;
  }}
</style>
""", unsafe_allow_html=True)

# ── REAL MODAL PRICING (modal.com/pricing, May 2026) ──────────────────────────
GPU_RATES = {           # $/second
    "H100":           0.001097,
    "RTX PRO 6000":   0.000842,
    "A100 80GB":      0.000694,
    "A100 40GB":      0.000583,
    "L40S":           0.000542,
    "A10":            0.000306,
    "L4":             0.000222,
    "T4":             0.000164,
}
CPU_RATE = 0.0000131    # $/core/sec (min 0.125 cores/container)
MEM_RATE = 0.00000222   # $/GiB/sec
HOURS_PER_MONTH = 720   # 30 days


def fmt(val: float) -> str:
    if val == 0:
        return "$0.00"
    if val < 0.0001:
        return f"${val:.7f}"
    if val < 0.001:
        return f"${val:.6f}"
    if val < 0.01:
        return f"${val:.5f}"
    if val < 0.1:
        return f"${val:.4f}"
    if val < 10:
        return f"${val:.3f}"
    if val < 1000:
        return f"${val:.2f}"
    return f"${val:,.0f}"


def chart_base(fig: go.Figure, height: int = 380, margin: dict | None = None) -> go.Figure:
    """Apply shared dark-theme layout to a Plotly figure."""
    m = margin or dict(l=8, r=8, t=28, b=8)
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(18,18,18,0.8)",
        font=dict(color="#ccc", family="-apple-system, BlinkMacSystemFont, 'Inter', sans-serif", size=12),
        height=height,
        margin=m,
    )
    fig.update_xaxes(gridcolor="#1E1E1E", linecolor="#333", zerolinecolor="#333")
    fig.update_yaxes(gridcolor="#1E1E1E", linecolor="#333", zerolinecolor="#333")
    return fig


def card(label: str, value: str, color: str = "green", sub: str = "") -> str:
    sub_html = f'<div class="m-sub">{sub}</div>' if sub else ""
    return f"""
<div class="m-card">
  <div class="m-label">{label}</div>
  <div class="m-value {color}">{value}</div>
  {sub_html}
</div>"""


# ── PAGE HEADER ───────────────────────────────────────────────────────────────
st.markdown(f"""
<h2 style="color:{GREEN}; font-weight:700; letter-spacing:-0.03em; margin-bottom:2px;">
  Modal Pricing &amp; Packaging Analyzer
</h2>
<p class="m-subtitle">
  Real published rates from modal.com/pricing &middot; May 2026 &middot; No API keys required
</p>
""", unsafe_allow_html=True)
st.divider()

tab1, tab2, tab3 = st.tabs([
    "Cost Calculator",
    "Breakeven Analysis",
    "Strategy Notes",
])


# ═══════════════════════════════════════════════════════════════════════════════
#  TAB 1 – COST CALCULATOR
# ═══════════════════════════════════════════════════════════════════════════════
with tab1:
    st.markdown(
        "Configure your workload to see what it actually costs — "
        "then layer on pricing multipliers to see what the bill looks like in production."
    )
    st.markdown("")

    left, right = st.columns([1, 1.6], gap="large")

    with left:
        st.markdown('<div class="m-section">Hardware</div>', unsafe_allow_html=True)
        gpu_type = st.selectbox("GPU", list(GPU_RATES.keys()), index=0)
        cpu_cores = st.number_input(
            "CPU Cores", min_value=0.125, max_value=64.0,
            value=2.0, step=0.125, format="%.3f",
            help="Minimum 0.125 cores per container",
        )
        memory_gib = st.number_input(
            "Memory (GiB)", min_value=1.0, max_value=512.0, value=8.0, step=1.0,
        )

        st.markdown('<div class="m-section">Job Volume</div>', unsafe_allow_html=True)
        runtime_sec = st.number_input(
            "Average Job Duration (seconds)", min_value=1, max_value=86400, value=30,
        )
        jobs_per_day = st.number_input(
            "Jobs per Day", min_value=1, max_value=10_000_000, value=500,
        )

        st.markdown('<div class="m-section">Pricing Adjustments</div>', unsafe_allow_html=True)
        region_mult = st.slider(
            "Region surcharge",
            min_value=1.0, max_value=2.5, value=1.0, step=0.05,
            help="US default = 1.0×. EU data-residency or compliance regions can reach 2.5×.",
        )
        non_preempt = st.toggle(
            "Guaranteed execution (non-preemptible)", value=False,
            help="Locks a GPU exclusively to your job. Costs 3× the standard rate.",
        )
        preempt_mult = 3.0 if non_preempt else 1.0
        combined_mult = region_mult * preempt_mult

    with right:
        gpu_rate = GPU_RATES[gpu_type]
        jobs_per_month = jobs_per_day * 30

        gpu_per_job  = gpu_rate  * runtime_sec
        cpu_per_job  = CPU_RATE  * cpu_cores * runtime_sec
        mem_per_job  = MEM_RATE  * memory_gib * runtime_sec
        base_per_job = gpu_per_job + cpu_per_job + mem_per_job

        prod_per_job   = base_per_job * combined_mult
        base_monthly   = base_per_job * jobs_per_month
        region_monthly = base_per_job * region_mult * jobs_per_month
        prod_monthly   = prod_per_job * jobs_per_month
        ratio = prod_monthly / base_monthly if base_monthly > 0 else 1.0

        gpu_prod   = gpu_per_job  * combined_mult
        cpu_prod   = cpu_per_job  * combined_mult
        mem_prod   = mem_per_job  * combined_mult
        total_prod = gpu_prod + cpu_prod + mem_prod

        # ── cost metrics ───────────────────────────────────────────────────────
        st.markdown(f"#### {gpu_type} — Cost Breakdown")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Cost per Job", fmt(base_per_job), help="Base US preemptible rate")
        with c2:
            st.metric("Daily Cost", fmt(base_per_job * jobs_per_day))
        with c3:
            st.metric("Monthly Cost", f"${base_monthly:,.0f}")

        if combined_mult > 1.0:
            parts = []
            if region_mult > 1.0:
                parts.append(f"{region_mult:.2f}× region surcharge")
            if preempt_mult > 1.0:
                parts.append("3× guaranteed execution")
            mult_str = " + ".join(parts)
            delta = prod_monthly - base_monthly
            st.markdown(f"""
<div class="m-alert">
  <strong style="color:{RED};">Pricing adjustments active: {mult_str} = {combined_mult:.2f}× total.</strong><br>
  Your adjusted monthly cost is <strong style="color:{RED};">${prod_monthly:,.0f}</strong> —
  that's <strong>${delta:,.0f} more</strong> than the base US rate. This compounding is
  the number customers most often get surprised by.
</div>
""", unsafe_allow_html=True)

        # ── naive vs production cards ──────────────────────────────────────────
        st.markdown("#### Base Rate vs Production Reality")
        p1, p2, p3 = st.columns(3)
        with p1:
            st.markdown(card(
                "US Preemptible",
                f"${base_monthly:,.0f}/mo",
                "green",
                "starting point",
            ), unsafe_allow_html=True)
        with p2:
            region_color = "amber" if region_mult > 1 else "muted"
            st.markdown(card(
                f"+ Region ({region_mult:.2f}×)",
                f"${region_monthly:,.0f}/mo",
                region_color,
                "no change" if region_mult == 1 else f"+{region_mult:.2f}× vs base",
            ), unsafe_allow_html=True)
        with p3:
            final_color = "red" if combined_mult > 1 else "green"
            st.markdown(card(
                f"+ Guaranteed ({combined_mult:.2f}× total)",
                f"${prod_monthly:,.0f}/mo",
                final_color,
                "no multipliers active" if combined_mult == 1 else f"×{ratio:.1f} vs base",
            ), unsafe_allow_html=True)

        # ── component breakdown chart ──────────────────────────────────────────
        st.markdown("#### Where the Money Goes (per job)")
        if total_prod > 0:
            gpu_pct = gpu_prod / total_prod * 100
            cpu_pct = cpu_prod / total_prod * 100
            mem_pct = mem_prod / total_prod * 100

            fig_bar = go.Figure(go.Bar(
                x=[gpu_pct, cpu_pct, mem_pct],
                y=["GPU", "CPU", "Memory"],
                orientation="h",
                marker_color=[GREEN, GREEN_DIM, "#1A6B10"],
                text=[
                    f"{gpu_pct:.0f}%  ·  {fmt(gpu_prod)}",
                    f"{cpu_pct:.0f}%  ·  {fmt(cpu_prod)}",
                    f"{mem_pct:.0f}%  ·  {fmt(mem_prod)}",
                ],
                textposition="auto",
                textfont=dict(color="white", size=12),
                hovertemplate="%{y}: %{x:.1f}%<extra></extra>",
            ))
            chart_base(fig_bar, height=175, margin=dict(l=0, r=0, t=4, b=0))
            fig_bar.update_xaxes(title_text="% of per-job cost", title_font_size=11)
            st.plotly_chart(fig_bar, use_container_width=True)

        with st.expander("See full GPU rate card"):
            cols_r = st.columns([2, 1.3, 1.3, 1.5])
            for col, h in zip(cols_r, ["GPU", "per second", "per hour", "per month (720 hr)"]):
                col.markdown(f"<span style='color:#555; font-size:0.8em;'>{h.upper()}</span>",
                             unsafe_allow_html=True)
            for gpu, rate in GPU_RATES.items():
                cols_r[0].write(gpu)
                cols_r[1].write(f"${rate:.6f}")
                cols_r[2].write(f"${rate * 3600:.4f}")
                cols_r[3].write(f"${rate * 3600 * HOURS_PER_MONTH:,.2f}")


# ═══════════════════════════════════════════════════════════════════════════════
#  TAB 2 – BREAKEVEN ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════════
with tab2:
    st.markdown(
        "Modal's pay-per-second model wins at low or unpredictable utilization. "
        "A reserved instance wins above a certain threshold. This chart shows you where that line is."
    )
    st.markdown("")

    left2, right2 = st.columns([1, 1.7], gap="large")

    with left2:
        st.markdown('<div class="m-section">Your Workload</div>', unsafe_allow_html=True)
        gpu_type_2 = st.selectbox("GPU", list(GPU_RATES.keys()), key="gpu2")
        monthly_gpu_hours = st.number_input(
            "GPU-Hours Needed per Month", min_value=10, max_value=50_000,
            value=500, step=10,
            help="Total GPU compute you need each month, regardless of how you provision it.",
        )

        st.markdown('<div class="m-section">Comparison Benchmark</div>', unsafe_allow_html=True)
        reserved_rate = st.number_input(
            "Reserved instance rate ($/hr)",
            min_value=0.10, max_value=20.0, value=2.00, step=0.10,
            help="Illustrative only — not a real vendor quote. Adjust to match your alternatives.",
        )
        st.caption(
            "H100-class reserved pricing typically ranges $1.80–$3.20/hr depending "
            "on provider and commitment term. $2.00 is a reasonable starting point."
        )

        st.markdown('<div class="m-section">Your Current Situation</div>', unsafe_allow_html=True)
        current_util = st.slider(
            "Current GPU utilization (%)", min_value=1, max_value=100, value=40,
            help="How much of your reserved capacity would actually be running jobs? "
                 "100% = fully saturated, 10% = mostly idle.",
        )

        st.markdown('<div class="m-section">Modal Pricing Adjustments</div>', unsafe_allow_html=True)
        region_mult_2 = st.slider(
            "Region surcharge", min_value=1.0, max_value=2.5,
            value=1.0, step=0.05, key="region2",
        )
        non_preempt_2 = st.toggle("Guaranteed execution", value=False, key="np2")
        prod_mult_2 = region_mult_2 * (3.0 if non_preempt_2 else 1.0)

    with right2:
        modal_hr_rate = GPU_RATES[gpu_type_2] * 3600 * prod_mult_2
        modal_monthly_cost = monthly_gpu_hours * modal_hr_rate

        utils = np.linspace(0.01, 1.0, 600)
        reserved_costs = (monthly_gpu_hours / utils) * reserved_rate
        y_cap = modal_monthly_cost * 5
        reserved_costs_capped = np.minimum(reserved_costs, y_cap)

        be_util = reserved_rate / modal_hr_rate
        be_util_pct = be_util * 100

        u_frac = current_util / 100
        user_reserved_cost = (monthly_gpu_hours / u_frac) * reserved_rate
        user_modal_cost = modal_monthly_cost

        # ── chart ─────────────────────────────────────────────────────────────
        fig_be = go.Figure()

        fig_be.add_trace(go.Scatter(
            x=utils * 100,
            y=np.full_like(utils, modal_monthly_cost),
            name="Modal (pay-per-second)",
            line=dict(color=GREEN, width=3),
            hovertemplate="Utilization: %{x:.0f}%<br>Modal: $%{y:,.0f}/mo<extra></extra>",
        ))

        fig_be.add_trace(go.Scatter(
            x=utils * 100,
            y=reserved_costs_capped,
            name=f"Reserved instance (~${reserved_rate:.2f}/hr, illustrative)",
            line=dict(color=RED, width=3),
            hovertemplate="Utilization: %{x:.0f}%<br>Reserved: $%{y:,.0f}/mo<extra></extra>",
        ))

        if 1 < be_util_pct < 100:
            fig_be.add_vline(
                x=be_util_pct,
                line_dash="dash", line_color=AMBER, line_width=2,
                annotation_text=f"  Breakeven: {be_util_pct:.0f}%",
                annotation_font_color=AMBER, annotation_font_size=13,
                annotation_yref="paper", annotation_y=0.96,
            )

            # shade Modal-wins zone
            be_x = min(be_util_pct, 100)
            mask = utils * 100 <= be_x
            fill_x = list(utils[mask] * 100) + [be_x]
            fill_y_top = list(reserved_costs_capped[mask]) + [modal_monthly_cost]
            fill_y_bot = [modal_monthly_cost] * len(fill_x)
            fig_be.add_trace(go.Scatter(
                x=fill_x + fill_x[::-1],
                y=fill_y_top + fill_y_bot[::-1],
                fill="toself",
                fillcolor="rgba(127,238,100,0.07)",
                line=dict(width=0),
                name="Modal cheaper zone",
                hoverinfo="skip",
                showlegend=True,
            ))

        fig_be.add_vline(
            x=current_util,
            line_dash="dot", line_color="white", line_width=1.5,
            annotation_text=f"  You: {current_util}%",
            annotation_font_color="white", annotation_font_size=12,
            annotation_yref="paper", annotation_y=0.78,
        )

        chart_base(fig_be, height=420)
        fig_be.update_layout(
            legend=dict(
                bgcolor="rgba(0,0,0,0.5)", bordercolor="#333", borderwidth=1,
                yanchor="top", y=0.99, xanchor="left", x=0.01,
            ),
        )
        fig_be.update_xaxes(title_text="GPU Utilization (%)", range=[0, 100])
        fig_be.update_yaxes(title_text="Monthly Cost (USD)", tickprefix="$", tickformat=",.0f")
        st.plotly_chart(fig_be, use_container_width=True)

        # ── verdict ────────────────────────────────────────────────────────────
        if be_util_pct <= 0:
            verdict = (
                f"At this reserved benchmark (${reserved_rate:.2f}/hr), Modal is always more expensive. "
                "A reserved instance is the better choice for any sustained workload at these settings."
            )
        elif be_util_pct >= 100:
            verdict = (
                "Modal's per-second rate is cheaper than this reserved benchmark even at 100% utilization. "
                "The pay-per-second model wins across the board here."
            )
        elif current_util < be_util_pct:
            delta = user_reserved_cost - user_modal_cost
            verdict = (
                f"Below {be_util_pct:.0f}% utilization, Modal is cheaper. Above it, a reserved instance wins. "
                f"At your current {current_util}% utilization, Modal saves approximately ${delta:,.0f}/mo."
            )
        else:
            delta = user_modal_cost - user_reserved_cost
            verdict = (
                f"Below {be_util_pct:.0f}% utilization, Modal is cheaper. Above it, a reserved instance wins. "
                f"At your current {current_util}% utilization, a reserved instance saves approximately ${delta:,.0f}/mo."
            )

        st.markdown(f'<div class="m-verdict">{verdict}</div>', unsafe_allow_html=True)

        # ── summary cards ──────────────────────────────────────────────────────
        st.markdown("")
        mc1, mc2, mc3 = st.columns(3)
        with mc1:
            st.markdown(card(
                "Modal Monthly Cost", f"${user_modal_cost:,.0f}",
                "green", "pay only for jobs run",
            ), unsafe_allow_html=True)
        with mc2:
            st.markdown(card(
                f"Reserved Monthly Cost", f"${user_reserved_cost:,.0f}",
                "red", f"at {current_util}% utilization",
            ), unsafe_allow_html=True)
        with mc3:
            diff = user_reserved_cost - user_modal_cost
            if diff >= 0:
                st.markdown(card("Modal Saves", f"${diff:,.0f}/mo", "green"), unsafe_allow_html=True)
            else:
                st.markdown(card("Reserved Saves", f"${-diff:,.0f}/mo", "amber"), unsafe_allow_html=True)

        st.markdown("")
        bec1, bec2, bec3 = st.columns(3)
        with bec1:
            if 0 < be_util_pct < 100:
                be_label = f"{be_util_pct:.0f}%"
            elif be_util_pct <= 0:
                be_label = "N/A"
            else:
                be_label = "> 100%"
            st.markdown(card("Breakeven Point", be_label, "amber",
                             "Modal cheaper below this"), unsafe_allow_html=True)
        with bec2:
            st.markdown(card(
                f"Modal Rate ({gpu_type_2})", f"${modal_hr_rate:.4f}/hr",
                "green", "pay-per-second billing",
            ), unsafe_allow_html=True)
        with bec3:
            st.markdown(card(
                "Reserved Rate", f"${reserved_rate:.2f}/hr",
                "red", "illustrative benchmark",
            ), unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
#  TAB 3 – STRATEGY NOTES
# ═══════════════════════════════════════════════════════════════════════════════
with tab3:
    st.markdown(f"""
<h3 style="color:{GREEN}; font-weight:700; letter-spacing:-0.02em; margin-bottom:4px;">
  Packaging Strategy Notes
</h3>
<p style="color:#555; font-size:0.84em; margin-top:0;">
  BizOps analysis from working through the pricing model. Written as internal findings, not marketing copy.
</p>
""", unsafe_allow_html=True)

    st.markdown("""
---

### 1 · Where the per-second model is a genuine competitive moat

Modal's billing model structurally wins for **bursty, batch, and short-duration workloads** —
inference endpoints with variable traffic, data pipelines that run at night and sit idle during the day,
developer workflows where a GPU is needed for 45 seconds ten times a day. In all of these cases,
the customer pays only for actual compute. A reserved instance charges for all the quiet time too.

The moat narrows as jobs get longer and workload shape becomes more predictable. A model-training
run consuming 2,000 GPU-hours a month at sustained utilization is not the natural Modal customer
under the current pricing structure. The per-second model benefits most the customer doing many
short, irregular jobs — which is also the customer hardest for a traditional cloud to serve well.
That's where the positioning should concentrate.

---

### 2 · The multiplier-stacking problem: a pricing-transparency issue

A customer can read the headline GPU rate, estimate their volume, arrive at a number that looks
reasonable — and then find their first real bill is 3×–7× higher because they needed guaranteed
execution in a non-US region. Neither multiplier is hidden, but they are presented separately
from the headline rate and the compounding effect isn't made obvious anywhere in the purchase flow.

This is a customer-trust problem as much as a pricing problem. The customers who get surprised tend
to be the ones who just signed up and ran their first real workload — exactly the wrong moment.
A few targeted fixes would close most of the gap: (a) make the pricing page estimator default to
**production-realistic inputs** rather than the cheapest configuration, (b) show the multiplied
effective rate inline whenever a customer selects a region or instance type in the console, (c)
add a cost projection to onboarding for new accounts that exceed a spending threshold in their
first week. None of these require changing the pricing model itself.

---

### 3 · The committed-use gap: a retention problem above ~50–60% utilization

The breakeven analysis shows that somewhere around **50–65% sustained GPU utilization** — depending
on the tier and the reserved benchmark — a customer is better off economically on a reserved instance.
Modal currently has nothing that captures that customer. They either stay because of the developer
experience, or they migrate to AWS/GCP/CoreWeave the moment their finance team runs the comparison.

A **committed-use discount tier** — pay upfront for a fixed number of GPU-hours per month at a
discounted rate, consume them however you want inside Modal's infrastructure — would address this
directly. It doesn't need to match reserved-instance pricing exactly; it just needs to be close
enough that the customer doesn't feel penalized for growth. The pitch to the customer: Modal's
orchestration and developer experience without the economic penalty for predictable workloads.
The pitch internally: converts high-utilization customers from churn risks into committed revenue.

The natural trigger for this offer is a customer averaging 400+ GPU-hours/month with utilization
trending upward over 90 days — before they run the reserved-instance math themselves.

---

### 4 · GPU tier mix as a packaging lever

An H100 at $0.001097/sec is 6.7× more expensive per second than a T4 at $0.000164/sec. A customer
running inference for a model that fits on a T4 has no reason to pay H100 prices, but the current
pricing surface doesn't help them make that decision — it just exposes the full rate for whatever
they pick.

A tiered product structure grouping GPUs into **value / standard / performance** tiers with
bundled credit allocations would simplify the decision surface without changing the underlying
per-second billing. It also creates a natural upsell path: start on the value tier, move to
performance when latency becomes the constraint. The per-second granularity stays intact underneath;
the packaging layer just makes the choice legible to a buyer who isn't benchmarking GPUs.

---

*All rates from modal.com/pricing as of May 2026. Breakeven figures vary with the reserved benchmark
rate — use the Breakeven Analysis tab to test your specific alternatives.*
""")

    with st.expander("Full GPU pricing reference"):
        cols_h = st.columns([2, 1.4, 1.4, 1.6, 2.0])
        headers = ["GPU", "$/sec", "$/hr", "$/mo (720 hr)", "Guaranteed ×3 /mo"]
        for col, h in zip(cols_h, headers):
            col.markdown(
                f"<span style='color:#555; font-size:0.78em; font-weight:600; text-transform:uppercase;"
                f"letter-spacing:0.06em;'>{h}</span>",
                unsafe_allow_html=True,
            )
        for gpu, rate in GPU_RATES.items():
            hr = rate * 3600
            mo = hr * HOURS_PER_MONTH
            cols_h[0].write(gpu)
            cols_h[1].write(f"${rate:.6f}")
            cols_h[2].write(f"${hr:.4f}")
            cols_h[3].write(f"${mo:,.2f}")
            cols_h[4].write(f"${mo * 3:,.2f}")
