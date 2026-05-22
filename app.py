import streamlit as st
import plotly.graph_objects as go
import numpy as np

st.set_page_config(
    page_title="Modal Pricing & Packaging Analyzer",
    page_icon="⚡",
    layout="wide",
)

# ── BRAND ─────────────────────────────────────────────────────────────────────
GREEN = "#7FEE64"
GREEN_DIM = "#4DBF40"
AMBER = "#FFB347"
RED = "#FF6B6B"
CARD_BG = "#1A1A1A"
BORDER = "#2A2A2A"

st.markdown(f"""
<style>
  /* cards */
  .modal-card {{
    background: {CARD_BG};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 14px 18px;
    text-align: center;
    margin-bottom: 4px;
  }}
  .modal-card .label {{ color: #888; font-size: 0.78em; margin-bottom: 4px; }}
  .modal-card .value {{ font-size: 1.6em; font-weight: 700; line-height: 1.1; }}
  .modal-card .sub {{ font-size: 0.75em; margin-top: 2px; }}
  .green {{ color: {GREEN}; }}
  .amber {{ color: {AMBER}; }}
  .red   {{ color: {RED}; }}

  /* breakeven verdict box */
  .verdict-box {{
    background: #111;
    border-left: 4px solid {GREEN};
    padding: 12px 16px;
    border-radius: 0 8px 8px 0;
    margin-top: 12px;
  }}

  /* tab accent */
  button[data-baseweb="tab"][aria-selected="true"] {{
    color: {GREEN} !important;
    border-bottom: 2px solid {GREEN} !important;
  }}

  /* section divider */
  .section-label {{
    color: #555;
    font-size: 0.72em;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    margin: 18px 0 6px 0;
  }}

  /* make st.metric delta red when going up (cost increase = bad) */
  [data-testid="stMetricDelta"] svg {{ display: none; }}
</style>
""", unsafe_allow_html=True)

# ── REAL MODAL PRICING (modal.com/pricing) ────────────────────────────────────
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
    """Format dollar values with precision appropriate to the magnitude."""
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


def plotly_base() -> dict:
    return dict(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(20,20,20,0.6)",
        font=dict(color="white", family="sans-serif"),
        xaxis=dict(gridcolor="#222", linecolor="#333", zerolinecolor="#333"),
        yaxis=dict(gridcolor="#222", linecolor="#333", zerolinecolor="#333"),
        margin=dict(l=10, r=10, t=30, b=10),
        legend=dict(bgcolor="rgba(0,0,0,0.4)", bordercolor="#333", borderwidth=1),
    )


# ── PAGE HEADER ───────────────────────────────────────────────────────────────
st.markdown(f"""
<h1 style="color:{GREEN}; margin-bottom:2px;">⚡ Modal Pricing & Packaging Analyzer</h1>
<p style="color:#666; margin-top:0; font-size:0.88em;">
  Real published Modal pricing (modal.com/pricing, May 2026) · No API keys · Pure computation on inputs
</p>
""", unsafe_allow_html=True)
st.divider()

tab1, tab2, tab3 = st.tabs([
    "🔧  Workload Cost Modeler",
    "📊  Breakeven vs Reserved Instances",
    "📋  Packaging Strategy Notes",
])


# ═══════════════════════════════════════════════════════════════════════════════
#  TAB 1 – WORKLOAD COST MODELER
# ═══════════════════════════════════════════════════════════════════════════════
with tab1:
    st.markdown("Configure a GPU workload, then apply production multipliers to see the real bill.")
    st.markdown("")

    left, right = st.columns([1, 1.6], gap="large")

    with left:
        st.markdown('<div class="section-label">Compute Resources</div>', unsafe_allow_html=True)
        gpu_type = st.selectbox("GPU", list(GPU_RATES.keys()), index=0)
        cpu_cores = st.number_input(
            "CPU Cores (min 0.125)", min_value=0.125, max_value=64.0,
            value=2.0, step=0.125, format="%.3f",
        )
        memory_gib = st.number_input(
            "Memory (GiB)", min_value=1.0, max_value=512.0, value=8.0, step=1.0,
        )

        st.markdown('<div class="section-label">Job Profile</div>', unsafe_allow_html=True)
        runtime_sec = st.number_input(
            "Avg Job Runtime (seconds)", min_value=1, max_value=86400, value=30,
        )
        jobs_per_day = st.number_input(
            "Jobs per Day", min_value=1, max_value=10_000_000, value=500,
        )

        st.markdown('<div class="section-label">Production Multipliers</div>', unsafe_allow_html=True)
        region_mult = st.slider(
            "Region Multiplier",
            min_value=1.0, max_value=2.5, value=1.0, step=0.05,
            help="US default = 1.0×. Certain EU / compliance regions reach 2.5×.",
        )
        non_preempt = st.toggle(
            "Non-Preemptible (Guaranteed Execution)", value=False,
            help="Guaranteed instances cost 3× the preemptible rate.",
        )
        preempt_mult = 3.0 if non_preempt else 1.0
        combined_mult = region_mult * preempt_mult

    with right:
        # ── calculations ──────────────────────────────────────────────────────
        gpu_rate = GPU_RATES[gpu_type]
        jobs_per_month = jobs_per_day * 30

        # per-job base (US preemptible, no region)
        gpu_per_job   = gpu_rate   * runtime_sec
        cpu_per_job   = CPU_RATE   * cpu_cores * runtime_sec
        mem_per_job   = MEM_RATE   * memory_gib * runtime_sec
        base_per_job  = gpu_per_job + cpu_per_job + mem_per_job

        # with multipliers
        prod_per_job  = base_per_job  * combined_mult
        base_monthly  = base_per_job  * jobs_per_month
        prod_monthly  = prod_per_job  * jobs_per_month
        region_monthly = base_per_job * region_mult * jobs_per_month

        # component shares (production)
        gpu_prod = gpu_per_job * combined_mult
        cpu_prod = cpu_per_job * combined_mult
        mem_prod = mem_per_job * combined_mult
        total_prod = gpu_prod + cpu_prod + mem_prod

        # ── per-job / daily / monthly metrics ─────────────────────────────────
        st.markdown(f"#### Workload Costs — {gpu_type}")
        cols = st.columns(3)
        with cols[0]:
            st.metric("Cost / Job (base)", fmt(base_per_job))
            st.metric("Daily (base)", fmt(base_per_job * jobs_per_day))
        with cols[1]:
            st.metric("Cost / Job (prod)", fmt(prod_per_job))
            st.metric("Daily (prod)", fmt(prod_per_job * jobs_per_day))
        with cols[2]:
            ratio = prod_monthly / base_monthly if base_monthly > 0 else 1.0
            st.metric(
                "Monthly (prod)",
                f"${prod_monthly:,.0f}",
                delta=f"×{ratio:.1f} vs base" if ratio > 1 else None,
                delta_color="inverse",
            )
            st.metric("Monthly (base)", f"${base_monthly:,.0f}")

        # ── multiplier warning ─────────────────────────────────────────────────
        if combined_mult > 1.0:
            parts = []
            if region_mult > 1.0:
                parts.append(f"{region_mult:.2f}× region")
            if preempt_mult > 1.0:
                parts.append(f"{preempt_mult:.0f}× non-preemptible")
            mult_str = " × ".join(parts)
            delta_dollars = prod_monthly - base_monthly
            st.markdown(f"""
<div style="background:#1A0A0A; border:1px solid #5A2A2A; border-radius:8px;
     padding:12px 16px; margin:10px 0;">
  <span style="color:{RED}; font-weight:700;">⚠ Multiplier stack: {mult_str} = {combined_mult:.2f}× total</span><br>
  <span style="color:#bbb;">
    That's <strong style="color:{RED};">${delta_dollars:,.0f}/mo</strong> more than
    the base US-preemptible rate — the number customers get surprised by.
  </span>
</div>
""", unsafe_allow_html=True)

        # ── naive vs production callout ────────────────────────────────────────
        st.markdown("#### Naive Estimate vs Production Reality")
        c1, c2, c3 = st.columns(3)

        def card(label, value, color, sub=""):
            return f"""
<div class="modal-card">
  <div class="label">{label}</div>
  <div class="value {color}">{value}</div>
  {'<div class="sub ' + color + '">' + sub + '</div>' if sub else ''}
</div>"""

        with c1:
            st.markdown(card("US Preemptible (base)", f"${base_monthly:,.0f}/mo", "green"), unsafe_allow_html=True)
        with c2:
            st.markdown(card(
                f"+ Region ({region_mult:.2f}×)",
                f"${region_monthly:,.0f}/mo",
                "amber",
                f"+{region_mult:.2f}× base" if region_mult > 1 else "no change",
            ), unsafe_allow_html=True)
        with c3:
            st.markdown(card(
                f"+ Non-Preemptible ({combined_mult:.2f}× total)",
                f"${prod_monthly:,.0f}/mo",
                "red" if combined_mult > 1 else "green",
                f"×{ratio:.1f} base" if combined_mult > 1 else "no multipliers",
            ), unsafe_allow_html=True)

        # ── component breakdown bar ────────────────────────────────────────────
        st.markdown("#### Component Breakdown (per job, production pricing)")

        if total_prod > 0:
            gpu_pct = gpu_prod / total_prod * 100
            cpu_pct = cpu_prod / total_prod * 100
            mem_pct = mem_prod / total_prod * 100

            fig_bar = go.Figure(go.Bar(
                x=[gpu_pct, cpu_pct, mem_pct],
                y=["GPU", "CPU", "Memory"],
                orientation="h",
                marker_color=[GREEN, GREEN_DIM, "#1E7A14"],
                text=[
                    f"{gpu_pct:.1f}%  ({fmt(gpu_prod)})",
                    f"{cpu_pct:.1f}%  ({fmt(cpu_prod)})",
                    f"{mem_pct:.1f}%  ({fmt(mem_prod)})",
                ],
                textposition="auto",
                textfont=dict(color="white"),
                hovertemplate="%{y}: %{x:.1f}%<extra></extra>",
            ))
            fig_bar.update_layout(
                **plotly_base(),
                height=180,
                xaxis_title="% of per-job cost",
                margin=dict(l=0, r=0, t=10, b=0),
            )
            st.plotly_chart(fig_bar, use_container_width=True)

        # ── GPU rate reference ─────────────────────────────────────────────────
        with st.expander("GPU rate card (all tiers, per-second)"):
            rate_rows = [(g, r, r * 3600, r * 3600 * HOURS_PER_MONTH)
                         for g, r in GPU_RATES.items()]
            cols_r = st.columns([2, 1.2, 1.2, 1.4])
            headers = ["GPU", "$/sec", "$/hr", "$/mo (720 hr)"]
            for col, h in zip(cols_r, headers):
                col.markdown(f"**{h}**")
            for gpu, ps, ph, pm in rate_rows:
                cols_r[0].write(gpu)
                cols_r[1].write(f"${ps:.6f}")
                cols_r[2].write(f"${ph:.4f}")
                cols_r[3].write(f"${pm:,.2f}")


# ═══════════════════════════════════════════════════════════════════════════════
#  TAB 2 – BREAKEVEN VS RESERVED INSTANCES
# ═══════════════════════════════════════════════════════════════════════════════
with tab2:
    st.markdown(
        "Modal's per-second billing is cheaper at low/variable utilization and loses "
        "to reserved instances above the breakeven point. Find yours."
    )
    st.markdown("")

    left2, right2 = st.columns([1, 1.7], gap="large")

    with left2:
        st.markdown('<div class="section-label">Workload</div>', unsafe_allow_html=True)
        gpu_type_2 = st.selectbox("GPU Type", list(GPU_RATES.keys()), key="gpu2")
        monthly_gpu_hours = st.number_input(
            "Monthly GPU-Hours Needed", min_value=10, max_value=50_000,
            value=500, step=10,
            help="The total GPU compute you need each month, regardless of how you provision it.",
        )

        st.markdown('<div class="section-label">Reserved Instance Benchmark</div>', unsafe_allow_html=True)
        reserved_rate = st.number_input(
            "Reserved Rate ($/hr)  — illustrative",
            min_value=0.10, max_value=20.0, value=2.00, step=0.10,
            help="Flat hourly rate for a comparable reserved GPU instance. "
                 "Not a real vendor quote — adjust to match your alternatives.",
        )
        st.caption(
            "For H100-class, cloud reserved pricing typically ranges $1.80–$3.20/hr "
            "depending on term and provider. Default $2.00 is a reasonable mid-point."
        )

        st.markdown('<div class="section-label">Your Situation</div>', unsafe_allow_html=True)
        current_util = st.slider(
            "Your Current Utilization (%)", min_value=1, max_value=100, value=40,
            help="What fraction of reserved capacity would actually run your jobs? "
                 "100% = always busy, 10% = bursty workload.",
        )

        st.markdown('<div class="section-label">Production Multipliers (Modal)</div>', unsafe_allow_html=True)
        region_mult_2 = st.slider(
            "Region Multiplier", min_value=1.0, max_value=2.5, value=1.0,
            step=0.05, key="region2",
        )
        non_preempt_2 = st.toggle("Non-Preemptible", value=False, key="np2")
        prod_mult_2 = region_mult_2 * (3.0 if non_preempt_2 else 1.0)

    with right2:
        # ── math ──────────────────────────────────────────────────────────────
        modal_hr_rate = GPU_RATES[gpu_type_2] * 3600 * prod_mult_2

        # Modal: flat — pay only for what you run
        modal_monthly_cost = monthly_gpu_hours * modal_hr_rate

        # Reserved: to get `monthly_gpu_hours` at `u` utilization, you need
        # monthly_gpu_hours/u reserved hours.  Cost = that × reserved_rate.
        utils = np.linspace(0.01, 1.0, 600)
        reserved_costs = (monthly_gpu_hours / utils) * reserved_rate
        modal_costs_line = np.full_like(utils, modal_monthly_cost)

        # Breakeven: modal_hourly = reserved_rate / u  →  u = reserved_rate / modal_hr_rate
        be_util = reserved_rate / modal_hr_rate  # fraction
        be_util_pct = be_util * 100

        # user's costs
        u_frac = current_util / 100
        user_reserved_cost = (monthly_gpu_hours / u_frac) * reserved_rate
        user_modal_cost = modal_monthly_cost

        # chart y-axis cap: 4× the Modal cost, so the curve doesn't go infinite
        y_cap = modal_monthly_cost * 5
        reserved_costs_capped = np.minimum(reserved_costs, y_cap)

        # ── chart ─────────────────────────────────────────────────────────────
        fig_be = go.Figure()

        # Modal flat line
        fig_be.add_trace(go.Scatter(
            x=utils * 100,
            y=modal_costs_line,
            name="Modal Serverless",
            line=dict(color=GREEN, width=3),
            hovertemplate="Utilization: %{x:.0f}%<br>Modal: $%{y:,.0f}/mo<extra></extra>",
        ))

        # Reserved curve
        fig_be.add_trace(go.Scatter(
            x=utils * 100,
            y=reserved_costs_capped,
            name=f"Reserved Instance (~${reserved_rate:.2f}/hr, illustrative)",
            line=dict(color=RED, width=3),
            hovertemplate="Utilization: %{x:.0f}%<br>Reserved: $%{y:,.0f}/mo<extra></extra>",
        ))

        # Breakeven vertical
        if 1 < be_util_pct < 100:
            fig_be.add_vline(
                x=be_util_pct,
                line_dash="dash",
                line_color=AMBER,
                line_width=2,
                annotation_text=f"  Breakeven: {be_util_pct:.0f}%",
                annotation_font_color=AMBER,
                annotation_font_size=13,
                annotation_yref="paper",
                annotation_y=0.95,
            )

        # User's current utilization
        fig_be.add_vline(
            x=current_util,
            line_dash="dot",
            line_color="white",
            line_width=1.5,
            annotation_text=f"  You: {current_util}%",
            annotation_font_color="white",
            annotation_font_size=12,
            annotation_yref="paper",
            annotation_y=0.75,
        )

        # Shade the "Modal wins" region (left of breakeven)
        if 1 < be_util_pct < 100:
            be_x = min(be_util_pct, 100)
            fill_x = list(utils[utils * 100 <= be_x] * 100) + [be_x]
            fill_y_modal = [modal_monthly_cost] * (len(fill_x))
            fill_y_reserved = list(reserved_costs_capped[utils * 100 <= be_x]) + [modal_monthly_cost]
            fig_be.add_trace(go.Scatter(
                x=fill_x + fill_x[::-1],
                y=fill_y_modal + fill_y_reserved[::-1],
                fill="toself",
                fillcolor=f"rgba(127, 238, 100, 0.07)",
                line=dict(width=0),
                name="Modal advantage zone",
                hoverinfo="skip",
                showlegend=True,
            ))

        fig_be.update_layout(
            **plotly_base(),
            height=420,
            xaxis=dict(
                title="GPU Utilization (%)",
                range=[0, 100],
                gridcolor="#222",
                linecolor="#333",
            ),
            yaxis=dict(
                title="Monthly Cost (USD)",
                tickprefix="$",
                tickformat=",.0f",
                gridcolor="#222",
                linecolor="#333",
            ),
            legend=dict(
                bgcolor="rgba(0,0,0,0.5)", bordercolor="#333", borderwidth=1,
                yanchor="top", y=0.99, xanchor="left", x=0.01,
            ),
        )
        st.plotly_chart(fig_be, use_container_width=True)

        # ── verdict ────────────────────────────────────────────────────────────
        if be_util_pct <= 0:
            verdict_text = (
                f"Modal is always more expensive than the reserved rate at ${reserved_rate:.2f}/hr — "
                "consider the reserved path for any sustained workload."
            )
            verdict_icon = "⚠"
            verdict_color = RED
        elif be_util_pct >= 100:
            verdict_text = (
                "Modal's per-second rate is cheaper than the reserved benchmark even at 100% utilization — "
                "the per-second model dominates here."
            )
            verdict_icon = "✅"
            verdict_color = GREEN
        else:
            if current_util < be_util_pct:
                delta_mo = user_reserved_cost - user_modal_cost
                verdict_text = (
                    f"Below {be_util_pct:.0f}% utilization, Modal's per-second model is cheaper. "
                    f"Above it, a reserved instance wins. "
                    f"At your {current_util}% utilization, Modal saves ~${delta_mo:,.0f}/mo."
                )
                verdict_icon = "✅"
                verdict_color = GREEN
            else:
                delta_mo = user_modal_cost - user_reserved_cost
                verdict_text = (
                    f"Below {be_util_pct:.0f}% utilization, Modal's per-second model is cheaper. "
                    f"Above it, a reserved instance wins. "
                    f"At your {current_util}% utilization, a reserved instance saves ~${delta_mo:,.0f}/mo."
                )
                verdict_icon = "⚠"
                verdict_color = AMBER

        st.markdown(f"""
<div class="verdict-box">
  <span style="font-size:1.1em;">{verdict_icon}</span>
  <span style="color:#ccc;"> {verdict_text}</span>
</div>
""", unsafe_allow_html=True)

        # ── cost comparison metrics ────────────────────────────────────────────
        st.markdown("#### Your Cost at Current Utilization")
        mc1, mc2, mc3 = st.columns(3)

        with mc1:
            st.markdown(card("Modal Serverless", f"${user_modal_cost:,.0f}/mo", "green",
                             "pays only for jobs run"), unsafe_allow_html=True)
        with mc2:
            st.markdown(card("Reserved Instance", f"${user_reserved_cost:,.0f}/mo", "red",
                             f"at {current_util}% utilization"), unsafe_allow_html=True)
        with mc3:
            diff = user_reserved_cost - user_modal_cost
            if diff > 0:
                st.markdown(card("Modal Saves", f"${diff:,.0f}/mo", "green"), unsafe_allow_html=True)
            else:
                st.markdown(card("Reserved Saves", f"${-diff:,.0f}/mo", "amber"), unsafe_allow_html=True)

        # ── breakeven summary row ──────────────────────────────────────────────
        st.markdown("")
        bec1, bec2, bec3 = st.columns(3)
        with bec1:
            be_label = f"{be_util_pct:.0f}%" if 0 < be_util_pct < 100 else ("N/A" if be_util_pct <= 0 else "Never")
            st.markdown(card("Breakeven Utilization", be_label, "amber",
                             "Modal cheaper below this"), unsafe_allow_html=True)
        with bec2:
            st.markdown(card(f"Modal Rate ({gpu_type_2})", f"${modal_hr_rate:.4f}/hr",
                             "green", "per-second billing"), unsafe_allow_html=True)
        with bec3:
            st.markdown(card("Reserved Rate", f"${reserved_rate:.2f}/hr",
                             "red", "illustrative benchmark"), unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
#  TAB 3 – PACKAGING STRATEGY NOTES
# ═══════════════════════════════════════════════════════════════════════════════
with tab3:
    st.markdown(f"""
<h3 style="color:{GREEN}; margin-bottom:4px;">Packaging Strategy Notes</h3>
<p style="color:#666; font-size:0.85em; margin-top:0;">
  BizOps findings from working through the pricing model. Written for internal use — not copy.
</p>
""", unsafe_allow_html=True)

    st.markdown("""
---

### 1 · Where per-second billing is a genuine competitive moat

Modal's per-second model structurally wins anywhere the workload is **bursty, batch, or short-duration**:
inference endpoints that handle variable traffic, data processing pipelines that run overnight and sit
idle during business hours, developer workflows where a GPU might be needed for 45 seconds ten times
a day. In those cases the customer pays only for actual compute — a reserved instance would be charging
for all the quiet time too.

The moat gets harder to defend as jobs get longer and workload predictability improves. A model-training
run that consumes 2,000 GPU-hours in a month at high sustained utilization is not the natural Modal
customer — or shouldn't be priced the same way. The model that benefits most from per-second billing
is the one doing many short, irregular jobs. That's also the customer who is hardest for a traditional
cloud to serve well, which is where Modal should concentrate the narrative.

---

### 2 · The multiplier-stacking problem: pricing opacity as a trust issue

The way Modal's published pricing works, a customer can read the headline GPU rate, run the math on
their expected volume, get a number that looks reasonable — and then discover in production that their
actual bill is 3×–7× higher because they needed guaranteed execution in a non-US region. Neither
multiplier is hidden, but they are presented separately from the headline rate. A customer who doesn't
read carefully will stack two surprises.

This is a customer-trust problem as much as a pricing problem. The customers who get surprised are
often the ones who just signed up and ran their first real workload. That's the worst moment to surprise
them. A few concrete fixes would help: (a) make the cost estimator on the pricing page default to
**production-realistic inputs** (non-US region, guaranteed execution) rather than the cheapest config,
(b) show the multiplied rate inline when a customer selects a region or instance type in the console,
(c) include a "production reality check" in onboarding emails for new accounts spending above some
threshold. None of these require changing the pricing model — they just close the perception gap.

---

### 3 · The committed-use gap: a retention problem above ~50–60% utilization

The breakeven analysis makes clear that somewhere around **50–65% sustained utilization** (depending
on the GPU tier and the reserved benchmark being compared against), a customer is better off on
a reserved instance. Modal currently has no product that captures that customer — they either stay
because of the ergonomics, or they migrate to AWS/GCP/CoreWeave when their finance team runs the
comparison.

A **committed-use discount tier** — pay upfront for X GPU-hours/month at a fixed rate, use them
however you want within Modal's infrastructure — would address this directly. It doesn't need to
match reserved-instance pricing exactly; it just needs to be close enough that the customer doesn't
feel they're being penalized for growth. The pitch to the customer is: "you get Modal's orchestration,
cold-start behavior, and developer experience, and you're not forced onto reserved instances just
because your workload got more predictable." The pitch internally is: it converts high-utilization
customers from churn risks into committed revenue.

The right trigger for offering this is probably a combination of monthly GPU-hours and utilization
trend. A customer averaging 400+ GPU-hours/month with utilization trending up over 90 days is the
natural cohort to reach out to before they run the reserved-instance math themselves.

---

### 4 · GPU tier mix as a packaging lever

Not all GPU demand is the same. An H100 at $0.001097/sec is 6.7× more expensive per second than
a T4 at $0.000164/sec. A customer building a serving system for a model that fits on a T4 has no
reason to pay H100 prices — but the per-second model doesn't help them navigate that choice; it just
exposes the full rate for whatever they pick.

A tiered product structure that groups GPUs into **value / standard / premium** tiers with bundled
credit allocations could make it easier for customers to right-size without requiring them to benchmark
every GPU themselves. This also creates a clear upsell path: start on the value tier, migrate to
premium when latency matters enough to justify it. The per-second granularity stays intact underneath;
the packaging layer just makes the decision surface simpler.

---

*All rates from modal.com/pricing as of May 2026. Breakeven figures are sensitive to the reserved
benchmark rate used — the calculator in Tab 2 lets you adjust it.*
""")

    # GPU rate reference table at the bottom of tab 3
    with st.expander("Full GPU pricing reference ($/sec, $/hr, $/mo)"):
        cols_h = st.columns([2, 1.4, 1.4, 1.6, 2.2])
        for col, h in zip(cols_h, ["GPU", "$/sec", "$/hr", "$/mo (720h)", "3× non-preemptible /mo"]):
            col.markdown(f"**{h}**")
        for gpu, rate in GPU_RATES.items():
            hr = rate * 3600
            mo = hr * HOURS_PER_MONTH
            cols_h[0].write(gpu)
            cols_h[1].write(f"${rate:.6f}")
            cols_h[2].write(f"${hr:.4f}")
            cols_h[3].write(f"${mo:,.2f}")
            cols_h[4].write(f"${mo * 3:,.2f}")
