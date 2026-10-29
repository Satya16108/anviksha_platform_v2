"""SPARK · Anviksha decision-intelligence MVP.  Run: pip install -r requirements.txt && streamlit run app.py"""
import json
import altair as alt, pandas as pd, streamlit as st
import core as C, theme as T

P = T.PALETTE

st.set_page_config("SPARK · Anviksha", "⚡", layout="wide")
T.inject()

# Hide Streamlit's top header and toolbar
st.markdown("""
<style>
    header[data-testid="stHeader"] {
        display: none !important;
    }

    [data-testid="stToolbar"] {
        display: none !important;
    }

    [data-testid="stDecoration"] {
        display: none !important;
    }

    .block-container {
        padding-top: 0rem !important;
    }
</style>
""", unsafe_allow_html=True)

C.ROOT.mkdir(exist_ok=True)

PAGES = ["Overview", "1 · Upload & clean", "2 · Analyse & explain", "3 · Consultant review", "4 · Owner decisions", "5 · Tracker & outcomes"]
STEP = dict(zip(PAGES[1:], (0, 2, 4, 5, 6)))
with st.sidebar:
    T.brand(); st.write("")
    new = st.text_input("New client ID")
    if new and st.button("Create client"): (C.ROOT / new).mkdir(exist_ok=True)
    client = st.selectbox("Client", sorted(p.name for p in C.ROOT.iterdir() if p.is_dir()) or ["demo"])
    page = st.radio("Workspace", PAGES)
    names = st.checkbox("Reveal customer names (consultant only)")
    llm = st.text_input("Local LLM URL (optional)", help="e.g. http://localhost:11434/api/generate. Blank = wording built from computed figures only.")
    st.caption("© 2026 SPARK Decision Intelligence Consulting")
con, wk = C.store(client), C.week()
if page in STEP: T.stepper(STEP[page])
H = lambda h: st.markdown(h, unsafe_allow_html=True)


def polish_chart(chart, height=280):
    """Consistent styling for analytics visualizations."""
    return chart.properties(height=height, background="white").configure_view(
        strokeOpacity=0
    ).configure_axis(
        labelColor="#526174", titleColor="#24364B", gridColor="#E8EDF3",
        domainColor="#D8E0E9", tickColor="#D8E0E9", labelFont="Aptos",
        titleFont="Aptos", labelFontSize=11, titleFontSize=12
    ).configure_legend(labelColor="#526174", titleColor="#24364B",
                       labelFont="Aptos", titleFont="Aptos", orient="bottom")


def section_note(text):
    st.markdown(f"<div style='color:#68778A;font-size:0.88rem;margin:-.35rem 0 .8rem'>{text}</div>", unsafe_allow_html=True)


def panel_title(title, subtitle=None):
    st.markdown(f"<div class='panel-title'>{title}</div>", unsafe_allow_html=True)
    if subtitle:
        section_note(subtitle)


def show(t, on=None):
    mp = C.ROOT / client / "map.json"
    if (names if on is None else on) and mp.exists():
        for k, v in json.loads(mp.read_text()).items(): t = t.replace(v, k)
    return t


def load(n):
    p = C.ROOT / client / f"{n}.csv"
    return pd.read_csv(p, parse_dates=[c for c in pd.read_csv(p, nrows=0).columns if "date" in c]) if p.exists() else None


def save(n, df):
    d, score, notes = C.clean(df)
    if "customer" in d: d = C.pseudo(d, client)
    d.to_csv(C.ROOT / client / f"{n}.csv", index=False)
    H(T.kpi(f"{n} · data-quality score", f"{score}/100", P["green"] if score >= 85 else P["spark"] if score >= 65 else P["red"]))
    for x in notes: st.caption("· " + x)
    st.dataframe(d.head(5), use_container_width=True)


if page == PAGES[0]:
    T.hero("Transform data into", "confident decisions", "Upload your Tally or Excel exports. Anviksha prepares a short list of actions, your SPARK consultant reviews it, and the owner decides.")
    a, o = C.q(con, "select * from actions"), C.q(con, "select * from outcomes")
    for col, (l, v, c) in zip(st.columns(5), [("Awaiting review", (a.status == "proposed").sum(), P["spark"]), ("Approved", (a.status == "approved").sum(), P["teal"]),
                                              ("Accepted by owner", (a.owner_decision == "accepted").sum(), P["green"]), ("Completed", a.done.sum(), P["blue"]), ("Value realised (Rs)", a.realised.sum(), P["ink"])]):
        col.markdown(T.kpi(l, v, c), unsafe_allow_html=True)
    sales, stock, batches = load("sales"), load("stock"), load("batches")
    if sales is not None:
        sales = C.ensure(sales)
        inv = C.invoices(sales)
        open_inv, paid, model_name = C.late_model(inv)
        stock_table = C.inventory(sales, stock)[0] if stock is not None else None
        kp = C.kpis(sales, open_inv, stock_table)
        st.markdown("### Business health at a glance")
        kcols = st.columns(min(4, max(1, len(kp))))
        for i, (label, value) in enumerate(kp.items()):
            kcols[i % len(kcols)].markdown(T.kpi(label, value, P["teal"]), unsafe_allow_html=True)

        left, right = st.columns(2)
        with left:
            st.markdown("#### Sales trend")
            trend = sales.assign(revenue=sales.qty * sales.price).groupby(sales.date.dt.to_period("M").astype(str)).revenue.sum().reset_index(name="revenue")
            trend.columns = ["month", "revenue"]
            ch = alt.Chart(trend).mark_line(point=alt.OverlayMarkDef(size=55, filled=True), strokeWidth=3, color="#168F86").encode(
                x=alt.X("month:N", title=None, sort=None), y=alt.Y("revenue:Q", title="Revenue (₹)", axis=alt.Axis(format="~s")),
                tooltip=["month", alt.Tooltip("revenue:Q", format=",.0f")])
            st.altair_chart(polish_chart(ch, 250), use_container_width=True)
        with right:
            st.markdown("#### Receivables risk")
            if not open_inv.empty:
                risk = open_inv.assign(risk_band=pd.cut(open_inv.p_late, [-0.001, .35, .65, 1.001], labels=["Lower", "Medium", "Higher"], include_lowest=True)).groupby("risk_band", observed=False).amount.sum().reset_index()
                ch = alt.Chart(risk).mark_bar(cornerRadiusTopRight=5, cornerRadiusBottomRight=5).encode(
                    x=alt.X("amount:Q", title="Open invoice value (₹)", axis=alt.Axis(format="~s")),
                    y=alt.Y("risk_band:N", title=None, sort=["Higher", "Medium", "Lower"]),
                    color=alt.Color("risk_band:N", scale=alt.Scale(domain=["Higher","Medium","Lower"], range=["#D94B68","#F2B84B","#168F86"]), legend=None),
                    tooltip=["risk_band", alt.Tooltip("amount:Q", format=",.0f")])
                st.altair_chart(polish_chart(ch, 250), use_container_width=True)
            else:
                st.info("No open receivables are currently available for risk analysis.")
        # Revenue and margin trend provide more depth than a single headline KPI.
        st.markdown("### Commercial performance")
        monthly = sales.assign(revenue=sales.qty * sales.price, gross_profit=sales.qty * (sales.price - sales.cost), month=sales.date.dt.to_period("M").astype(str)).groupby("month", as_index=False).agg(revenue=("revenue", "sum"), gross_profit=("gross_profit", "sum"))
        monthly["margin_pct"] = 100 * monthly.gross_profit / monthly.revenue.replace(0, pd.NA)
        ltrend, rtrend = st.columns([1.35, 1])
        with ltrend:
            panel_title("Revenue vs gross profit", "Calculated from uploaded quantity, selling price and cost fields")
            long_month = monthly.melt(id_vars="month", value_vars=["revenue", "gross_profit"], var_name="series", value_name="amount")
            ch = alt.Chart(long_month).mark_line(point=True, strokeWidth=2.6).encode(
                x=alt.X("month:N", title=None, sort=None), y=alt.Y("amount:Q", title="Amount (₹)", axis=alt.Axis(format="~s")),
                color=alt.Color("series:N", scale=alt.Scale(domain=["revenue","gross_profit"], range=["#356FE8","#168F86"]), title=None),
                tooltip=["month", "series", alt.Tooltip("amount:Q", format=",.0f")])
            st.altair_chart(polish_chart(ch, 250), use_container_width=True)
        with rtrend:
            panel_title("Gross margin trend", "Monitor margin erosion across periods")
            ch = alt.Chart(monthly).mark_area(line={"color":"#7C5CFC"}, color="#7C5CFC", opacity=.16).encode(
                x=alt.X("month:N", title=None, sort=None), y=alt.Y("margin_pct:Q", title="Gross margin (%)", axis=alt.Axis(format=".1f")),
                tooltip=["month", alt.Tooltip("margin_pct:Q", format=".1f")])
            st.altair_chart(polish_chart(ch, 250), use_container_width=True)

        left, right = st.columns(2)
        with left:
            st.markdown("#### Inventory health")
            if stock_table is not None and not stock_table.empty:
                iv = stock_table.reset_index().copy()
                iv["status"] = iv.apply(lambda r: "Reorder" if r.stock <= r.rop and r.fc > 0 else ("Slow / no demand" if r.fc <= 0 else "Healthy"), axis=1)
                ch = alt.Chart(iv).mark_circle(size=115, opacity=.85).encode(
                    x=alt.X("fc:Q", title="Estimated daily demand"), y=alt.Y("cover:Q", title="Stock cover (days)"),
                    color=alt.Color("status:N", scale=alt.Scale(domain=["Reorder","Slow / no demand","Healthy"], range=["#D94B68","#F2B84B","#168F86"])),
                    tooltip=["item:N", "stock:Q", "rop:Q", "fc:Q", "cover:Q", "status:N"])
                st.altair_chart(polish_chart(ch, 250), use_container_width=True)
            else:
                section_note("Upload stock data to enable inventory health analysis.")
        with right:
            st.markdown("#### Customer revenue concentration")
            cust = sales.assign(revenue=sales.qty * sales.price).groupby("customer", as_index=False).revenue.sum().nlargest(8, "revenue")
            ch = alt.Chart(cust).mark_bar(cornerRadiusTopRight=5, color="#356FE8").encode(
                x=alt.X("revenue:Q", title="Revenue (₹)", axis=alt.Axis(format="~s")),
                y=alt.Y("customer:N", title=None, sort="-x"),
                tooltip=["customer:N", alt.Tooltip("revenue:Q", format=",.0f")])
            st.altair_chart(polish_chart(ch, 250), use_container_width=True)

    if o.empty: st.info("No data yet. Start with step 1 · Upload & clean (the sample-data button gives a demo).")
    else:
        st.subheader(f"Latest business KPIs · {o.week.max()}")
        L = o[o.week == o.week.max()]
        for col, r in zip(st.columns(len(L)), L.itertuples()): col.markdown(T.kpi(r.metric, r.value, P["ink"]), unsafe_allow_html=True)
        if o.week.nunique() > 1: st.line_chart(o.pivot(index="week", columns="metric", values="value"))

elif page == PAGES[1]:
    T.hero("Bring your data,", "we clean it", "Customer names are replaced with IDs before any analysis, and every client's data is stored separately.", "Steps 1–2 · Upload and clean")
    if st.button("Load sample data (demo)"):
        for n, d in zip(("sales", "stock", "batches"), C.sample()): save(n, d)
    for col, (n, hint) in zip(st.columns(3), (("sales", "Sales invoices · date, invoice, customer, item, qty, price"), ("stock", "Stock · item, stock, lead_days"), ("batches", "Batches · batch, date, item, produced, rejected"))):
        with col:
            f = st.file_uploader(hint, type=["csv", "xlsx"], key=n)
            if f: save(n, pd.read_csv(f) if f.name.endswith("csv") else pd.read_excel(f))

elif page == PAGES[2]:
    T.hero("Every number,", "explained", "Five analysis modules feed one short list of recommended actions, colour-coded by module.", "Steps 3–4 · Analyse and explain")
    s, k, b = load("sales"), load("stock"), load("batches")
    if s is None: st.info("Upload sales data first."); st.stop()
    s = C.ensure(s); inv = C.invoices(s); op, paid, meth = C.late_model(inv); acts, ivt = [], None
    TB = st.tabs(["Inventory & demand", "Sales & customers", "Quality & batches", "Collections", "13-week cash"])
    with TB[0]:
        if k is None: st.info("Upload stock data.")
        else:
            ivt, a = C.inventory(s, k); acts += a; st.caption("Red rows are at or below their reorder point.")
            invplot = ivt.reset_index().copy()
            invplot["status"] = invplot.apply(lambda r: "Reorder" if r.stock <= r.rop and r.fc > 0 else ("Slow / no demand" if r.fc <= 0 else "Healthy"), axis=1)
            left, right = st.columns(2)
            with left:
                st.markdown("**Stock vs. reorder point**")
                plot = invplot.melt(id_vars="item", value_vars=["stock", "rop"], var_name="measure", value_name="units")
                ch = alt.Chart(plot).mark_bar().encode(x=alt.X("item:N", title=None, axis=alt.Axis(labelAngle=-30)), y=alt.Y("units:Q", title="Units"),
                    xOffset="measure:N", color=alt.Color("measure:N", scale=alt.Scale(range=["#356FE8", "#F2B84B"])),
                    tooltip=["item", "measure", "units"])
                st.altair_chart(polish_chart(ch, 260), use_container_width=True)
            with right:
                st.markdown("**Stock cover vs. demand**")
                ch = alt.Chart(invplot).mark_circle(size=120).encode(x=alt.X("fc:Q", title="Estimated daily demand"),
                    y=alt.Y("cover:Q", title="Stock cover (days)"), color=alt.Color("status:N",
                    scale=alt.Scale(domain=["Reorder","Slow / no demand","Healthy"], range=["#D94B68","#F2B84B","#168F86"])),
                    tooltip=["item", "stock", "rop", "fc", "cover", "status"])
                st.altair_chart(polish_chart(ch, 260), use_container_width=True)
            st.dataframe(ivt.round(1).style.apply(lambda r: ["background:#FDECEC" if r.stock <= r.rop and r.fc > 0 else "" for _ in r], axis=1), use_container_width=True)
    with TB[1]:
        g, a = C.sales_cust(s); acts += a; g = g.reset_index()
        ch = alt.Chart(g).mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4).encode(
            x=alt.X("customer:N", sort="-y", title=None), y=alt.Y("rev:Q", title="Revenue (₹)", axis=alt.Axis(format="~s")),
            color=alt.Color("margin_pct:Q", scale=alt.Scale(range=["#F2B84B", "#168F86"]), title="Margin %"),
            tooltip=["customer", alt.Tooltip("rev:Q", format=",.0f"), "margin_pct", "disc_pct"])
        st.altair_chart(polish_chart(ch, 300), use_container_width=True)
        lcol, rcol = st.columns(2)
        with lcol:
            panel_title("Customer profitability map", "Revenue versus margin; bubble size represents order count")
            gplot = g.copy()
            if "orders" in gplot.columns:
                ch = alt.Chart(gplot).mark_circle(opacity=.82, stroke="#FFFFFF", strokeWidth=1).encode(
                    x=alt.X("rev:Q", title="Customer revenue (₹)", axis=alt.Axis(format="~s")),
                    y=alt.Y("margin_pct:Q", title="Gross margin (%)"), size=alt.Size("orders:Q", title="Orders", scale=alt.Scale(range=[80,700])),
                    color=alt.Color("margin_pct:Q", scale=alt.Scale(scheme="redyellowgreen", domainMid=0), title="Margin %"),
                    tooltip=[alt.Tooltip("rev:Q", format=",.0f"), alt.Tooltip("mar:Q", format=",.0f"), "orders:Q", alt.Tooltip("margin_pct:Q", format=".1f"), alt.Tooltip("disc_pct:Q", format=".1f")])
                st.altair_chart(polish_chart(ch, 280), use_container_width=True)
        with rcol:
            panel_title("Discount leakage", "Customers with the highest discount percentage")
            disc = g.sort_values("disc_pct", ascending=False).head(10).reset_index()
            ch = alt.Chart(disc).mark_bar(cornerRadiusTopRight=4, color="#F2B84B").encode(
                x=alt.X("disc_pct:Q", title="Discount (%)"), y=alt.Y("customer:N", sort="-x", title=None),
                tooltip=["customer", alt.Tooltip("disc_pct:Q", format=".1f"), alt.Tooltip("disc:Q", format=",.0f")])
            st.altair_chart(polish_chart(ch, 280), use_container_width=True)
        st.dataframe(g.round(1), use_container_width=True)
    with TB[2]:
        if b is None: st.info("Upload batch data.")
        else:
            g, a = C.quality(b); acts += a
            panel_title("Reject rate by product", "Compare quality performance; investigate outliers before assigning root cause")
            qplot = g.reset_index().sort_values("reject_pct", ascending=False)
            q1, q2, q3 = st.columns(3)
            total_prod = float(qplot.produced.sum()) if not qplot.empty else 0
            total_rej = float(qplot.rejected.sum()) if not qplot.empty else 0
            q1.markdown(T.kpi("Units produced", f"{total_prod:,.0f}", P["blue"]), unsafe_allow_html=True)
            q2.markdown(T.kpi("Units rejected", f"{total_rej:,.0f}", P["red"]), unsafe_allow_html=True)
            q3.markdown(T.kpi("Overall reject rate", f"{(100*total_rej/total_prod if total_prod else 0):.2f}%", P["spark"]), unsafe_allow_html=True)
            qc1, qc2 = st.columns(2)
            with qc1:
                ch = alt.Chart(qplot).mark_bar(cornerRadiusTopRight=4, color="#D94B68").encode(
                    x=alt.X("reject_pct:Q", title="Reject rate (%)"), y=alt.Y("item:N", sort="-x", title=None),
                    tooltip=["item", "produced", "rejected", alt.Tooltip("reject_pct:Q", format=".2f")])
                st.altair_chart(polish_chart(ch, 280), use_container_width=True)
            with qc2:
                ch = alt.Chart(qplot).mark_circle(size=150, color="#7C5CFC", opacity=.8).encode(
                    x=alt.X("produced:Q", title="Units produced", axis=alt.Axis(format="~s")),
                    y=alt.Y("reject_pct:Q", title="Reject rate (%)"),
                    size=alt.Size("rejected:Q", title="Rejected units", scale=alt.Scale(range=[80,650])),
                    tooltip=["item", "produced", "rejected", alt.Tooltip("reject_pct:Q", format=".2f")])
                st.altair_chart(polish_chart(ch, 280), use_container_width=True)
            st.dataframe(qplot.round(2), use_container_width=True)
    with TB[3]:
        st.caption(f"Late-payment risk model in use: {meth}"); acts += C.collections(op)
        riskview = op[["invoice", "customer", "amount", "due_date", "p_late"]].sort_values("p_late", ascending=False).copy()
        if not riskview.empty:
            st.markdown("**Collection priority — value exposed × late-payment risk**")
            riskview["exposure"] = riskview.amount * riskview.p_late
            plot = riskview.head(12)
            ch = alt.Chart(plot).mark_bar(cornerRadiusTopRight=4, color="#D94B68").encode(
                x=alt.X("exposure:Q", title="Risk-weighted exposure (₹)", axis=alt.Axis(format="~s")),
                y=alt.Y("invoice:N", title=None, sort="-x"),
                tooltip=["invoice", "customer", alt.Tooltip("amount:Q", format=",.0f"),
                         alt.Tooltip("p_late:Q", format=".0%"), alt.Tooltip("exposure:Q", format=",.0f")])
            st.altair_chart(polish_chart(ch, 280), use_container_width=True)
        st.dataframe(riskview.round(2), use_container_width=True)
        if not op.empty:
            aged = op.copy()
            aged["days_past_due"] = (pd.Timestamp.now().normalize() - pd.to_datetime(aged.due_date)).dt.days.clip(lower=0)
            aged["age_band"] = pd.cut(aged.days_past_due, [-1, 0, 30, 60, 90, 100000], labels=["Not overdue", "1–30 days", "31–60 days", "61–90 days", "90+ days"])
            age_summary = aged.groupby("age_band", observed=False).amount.sum().reset_index()
            panel_title("Receivables ageing", "Invoice value grouped by days past due")
            ch = alt.Chart(age_summary).mark_bar(cornerRadiusTopRight=4).encode(
                x=alt.X("amount:Q", title="Invoice value (₹)", axis=alt.Axis(format="~s")), y=alt.Y("age_band:N", title=None),
                color=alt.Color("age_band:N", scale=alt.Scale(domain=["Not overdue","1–30 days","31–60 days","61–90 days","90+ days"], range=["#168F86","#F2B84B","#F59E0B","#E8793D","#D94B68"]), legend=None),
                tooltip=["age_band", alt.Tooltip("amount:Q", format=",.0f")])
            st.altair_chart(polish_chart(ch, 240), use_container_width=True)
    with TB[4]:
        c1, c2, c3 = st.columns(3)
        o0, ow, iw = c1.number_input("Opening cash (Rs)", 0.0), c2.number_input("Weekly outflow (Rs)", 0.0), c3.number_input("Other weekly inflow (Rs)", 0.0)
        cf = C.cash13(op, paid, o0, ow, iw); d = cf.reset_index(names="week")
        ch = (alt.Chart(d).mark_area(opacity=.18, color=P["teal"]).encode(x=alt.X("week:O", title="Week"), y=alt.Y("P10:Q", title="Cash (₹)", axis=alt.Axis(format="~s")), y2="P90:Q")
              + alt.Chart(d).mark_line(color=P["ink"], strokeWidth=3, point=True).encode(x="week:O", y="P50:Q", tooltip=["week", alt.Tooltip("P10:Q", format=",.0f"), alt.Tooltip("P50:Q", format=",.0f"), alt.Tooltip("P90:Q", format=",.0f")])
              + alt.Chart(pd.DataFrame({"y": [0]})).mark_rule(color=P["red"], strokeDash=[4, 4]).encode(y="y:Q"))
        st.altair_chart(polish_chart(ch, 320), use_container_width=True)
        st.caption("Shaded band = pessimistic (P10) to optimistic (P90); line = middle case. Counts collections from invoices already raised only.")
        neg = cf.index[cf.P10 < 0].tolist()
        if neg:
            st.warning(f"Cash may go negative in weeks {neg} (pessimistic case).")
            acts.append(dict(module="Cash", text=f"Arrange cash cover for weeks {neg[0]}-{neg[-1]}", value=-cf.P10.min(), reason=f"In the pessimistic case cash falls to Rs {cf.P10.min():,.0f}."))
    kp = C.kpis(s, op, ivt); st.subheader("This week's KPIs")
    for col, (m, v) in zip(st.columns(len(kp)), kp.items()): col.markdown(T.kpi(m, v, P["ink"]), unsafe_allow_html=True)
    st.subheader(f"Recommended actions ({len(acts)})")
    for a in acts: H(T.card(a["module"], show(a["text"]), show(a["reason"]), a["value"]))
    if st.button("Send brief to consultant review →"):
        C.add_actions(con, wk, C.explain(acts, llm or None)); C.log_kpis(con, wk, kp); st.success(f"{len(acts)} actions sent for review.")

elif page == PAGES[3]:
    T.hero("Judgement before", "every recommendation", "Edit the wording, then approve or reject. A reason is always recorded.", "Step 5 · Consultant review")
    q = C.q(con, "select * from actions where status='proposed' and week=?", (wk,))
    if q.empty: st.info("Nothing to review this week.")
    for r in q.itertuples():
        H(T.card(r.module, show(r.text), show(r.reason), r.value, "proposed"))
        with st.form(f"r{r.id}"):
            txt, why = st.text_input("Final wording", show(r.text)), st.text_input("Reason for your decision")
            a, b_ = st.columns(2); ok, no = a.form_submit_button("✓ Approve"), b_.form_submit_button("✕ Reject")
        if (ok or no) and not why: st.error("Please add a reason.")
        elif ok or no: C.upd(con, r.id, status="approved" if ok else "rejected", final_text=txt, review_reason=why); st.rerun()

elif page == PAGES[4]:
    T.hero("Your business,", "your decision", "Each action below was checked by your SPARK consultant. Accept what you will do and decline the rest.", "Step 6 · Owner decisions")
    q = C.q(con, "select * from actions where status='approved' and owner_decision is null")
    if q.empty: st.info("No actions waiting for the owner.")
    for r in q.itertuples():
        H(T.card(r.module, show(r.final_text or r.text, True), show(r.reason, True), r.value, "approved"))
        with st.form(f"o{r.id}"):
            note = st.text_input("Note (optional)"); a, b_ = st.columns(2); ok, no = a.form_submit_button("✓ Accept"), b_.form_submit_button("✕ Decline")
        if ok or no: C.upd(con, r.id, owner_decision="accepted" if ok else "declined", owner_note=note); st.rerun()

elif page == PAGES[5]:
    T.hero("From prediction to", "measured outcome", "Prediction → recommendation → consultant review → client action → outcome.", "Tracker & outcomes")
    a, o = C.q(con, "select * from actions order by id desc"), C.q(con, "select * from outcomes")
    for col, (l, v, c) in zip(st.columns(3), [("Actions accepted", (a.owner_decision == "accepted").sum(), P["green"]), ("Completed", a.done.sum(), P["blue"]), ("Value realised (Rs)", a.realised.sum(), P["ink"])]):
        col.markdown(T.kpi(l, v, c), unsafe_allow_html=True)
    for r in a[(a.owner_decision == "accepted") & (a.done == 0)].itertuples():
        H(T.card(r.module, show(r.final_text or r.text, True), show(r.reason, True), r.value, "accepted"))
        with st.form(f"t{r.id}"):
            d, v = st.checkbox("Done"), st.number_input("Cash freed / value realised (Rs)", 0.0, value=float(r.realised))
            if st.form_submit_button("Save outcome"): C.upd(con, r.id, done=int(d), realised=v); st.rerun()
    if not o.empty: st.subheader("KPI trend"); st.line_chart(o.pivot(index="week", columns="metric", values="value"))
    st.subheader("Action log"); st.dataframe(a[["week", "module", "final_text", "status", "owner_decision", "done", "realised", "value"]], use_container_width=True)
    sel = a[(a.week == wk) & (a.status == "approved") & (a.owner_decision != "declined")]
    st.download_button("⬇ Weekly PDF one-pager", C.one_pager(client, wk, dict(o[o.week == wk].set_index("metric").value) if not o.empty else {}, sel), f"{client}_{wk}.pdf")


elif page == PAGES[6]:
    T.hero("Ask your business data,", "get grounded answers",
           "The assistant answers from calculated platform metrics and uploaded records. It does not replace professional judgement.",
           "AI decision assistant")
    sdata, stock, batches = load("sales"), load("stock"), load("batches")
    if sdata is None:
        st.info("Upload sales/invoice data first. The assistant can then use available sales, collections, stock and quality metrics.")
    else:
        sdata = C.ensure(sdata)
        inv = C.invoices(sdata)
        open_inv, paid, model_name = C.late_model(inv)
        stock_table = None
        if stock is not None:
            stock_table, _ = C.inventory(sdata, stock)
        metrics = C.kpis(sdata, open_inv, stock_table)
        st.subheader("Verified context available to the assistant")
        cols = st.columns(min(4, max(1, len(metrics))))
        for i, (m, v) in enumerate(metrics.items()):
            cols[i % len(cols)].markdown(T.kpi(m, v, P["teal"]), unsafe_allow_html=True)
        question = st.text_area("Ask a question", placeholder="Example: What should I focus on this week to reduce cash pressure?", height=90)
        if st.button("Analyse question", type="primary") and question.strip():
            # Construct a bounded context from computed values and module summaries.
            context = [f"{k}: {v}" for k, v in metrics.items()]
            context.append(f"Collections risk method: {model_name}")
            if not open_inv.empty:
                top = open_inv.assign(risk_value=open_inv.amount * open_inv.p_late).sort_values("risk_value", ascending=False).head(5)
                context.append("Highest priority open invoices: " + "; ".join(
                    f"invoice {r.invoice}, customer {r.customer}, amount Rs {r.amount:,.0f}, due {r.due_date}, late risk {r.p_late:.0%}"
                    for r in top.itertuples()))
            if stock_table is not None:
                low = stock_table[stock_table.stock <= stock_table.rop].sort_values("fc", ascending=False).head(5)
                context.append("Items at/below reorder point: " + ("; ".join(
                    f"{idx}: stock {r.stock:.0f}, reorder point {r.rop:.0f}, estimated demand/day {r.fc:.2f}"
                    for idx, r in low.iterrows()) if not low.empty else "None flagged by current rule"))
            facts = "\\n".join(context)
            answer = None
            if llm.strip():
                try:
                    import urllib.request
                    payload = json.dumps({"model": "llama3", "stream": False,
                        "prompt": "You are the Anviksha SME decision assistant. Answer the question using ONLY the verified context below. State uncertainty and missing data clearly. Do not invent numbers, claim causation, or recommend automatic payments/purchases. Give 2-4 concise actions and cite the figures used.\\nVERIFIED CONTEXT:\\n" + facts + "\\nQUESTION: " + question}).encode()
                    req = urllib.request.Request(llm.strip(), payload, {"Content-Type": "application/json"})
                    answer = json.loads(urllib.request.urlopen(req, timeout=30).read()).get("response", "").strip()
                except Exception as e:
                    st.warning(f"Local LLM unavailable; showing a rule-based summary instead. ({e})")
            if not answer:
                answer = "Based on the available calculated data:\\n\\n" + "\\n".join(f"- **{k}:** {v}" for k, v in metrics.items())
                if not open_inv.empty:
                    r = open_inv.assign(risk_value=open_inv.amount * open_inv.p_late).sort_values("risk_value", ascending=False).iloc[0]
                    answer += f"\\n- **First collection review:** invoice {r.invoice}, customer {r.customer}, Rs {r.amount:,.0f}; estimated late-payment risk {r.p_late:.0%}. Verify the expected payment date before acting."
                answer += "\\n\\nThis is a rules-based summary, not a generated forecast beyond the platform's stated assumptions. Review source records before taking action."
            st.markdown(answer)
            with st.expander("View the figures supplied to the assistant"):
                st.code(facts)
    st.caption("Privacy: customer names are pseudonymized during processing by default. Use a local LLM endpoint if you want to avoid sending business context to an external model.")

elif page == PAGES[7]:
    T.hero("Forecast the future,", "compare decisions",
           "Use forecast outputs and transparent assumptions to plan cash and inventory. Recommendations require human approval.",
           "Forecasting & optimization")
    sdata, stock, batches = load("sales"), load("stock"), load("batches")
    if sdata is None:
        st.info("Upload sales data first, or use the demo dataset in Upload & clean.")
    else:
        sdata = C.ensure(sdata)
        inv = C.invoices(sdata)
        open_inv, paid, model_name = C.late_model(inv)
        st.subheader("13-week cash outlook")
        c1, c2, c3 = st.columns(3)
        opening = c1.number_input("Opening cash (Rs)", min_value=0.0, value=500000.0, step=25000.0, key="opt_opening")
        weekly_outflow = c2.number_input("Weekly outflow (Rs)", min_value=0.0, value=100000.0, step=10000.0, key="opt_outflow")
        other_inflow = c3.number_input("Other weekly inflow (Rs)", min_value=0.0, value=25000.0, step=5000.0, key="opt_inflow")
        cf = C.cash13(open_inv, paid, opening, weekly_outflow, other_inflow)
        d = cf.reset_index(names="week")
        st.altair_chart(alt.Chart(d).mark_area(opacity=.2, color=P["teal"]).encode(
            x=alt.X("week:O", title="Week"), y=alt.Y("P10:Q", title="Projected cash (Rs)"), y2="P90:Q")
            + alt.Chart(d).mark_line(color=P["ink"], strokeWidth=3).encode(x="week:O", y="P50:Q")
            + alt.Chart(pd.DataFrame({"y": [0]})).mark_rule(color=P["red"], strokeDash=[4, 4]).encode(y="y:Q"),
            use_container_width=True)
        st.caption("P10 = downside scenario, P50 = central scenario, P90 = upside scenario. Includes open invoices and user-entered weekly inflows/outflows.")
        risk_weeks = cf.index[cf.P10 < 0].tolist()
        if risk_weeks:
            st.warning(f"Downside scenario shows negative cash in weeks: {', '.join(map(str, risk_weeks))}. Consider validating collections, delaying discretionary spending or arranging a credit buffer with your finance adviser.")
        else:
            st.success("No negative cash balance appears in the downside scenario under the current assumptions.")
        st.divider()
        st.subheader("Inventory reorder planning")
        if stock is None:
            st.info("Upload stock data to see reorder planning.")
        else:
            ivt, actions = C.inventory(sdata, stock)
            budget = st.number_input("Available replenishment budget (Rs)", min_value=0.0, value=200000.0, step=10000.0, key="opt_budget")
            plan = ivt.copy()
            plan["suggested_qty"] = (plan.rop - plan.stock).clip(lower=0).apply(lambda x: int(round(x)))
            plan["estimated_cost"] = plan.suggested_qty * plan.price.fillna(0)
            plan["priority_score"] = plan.fc.fillna(0) * plan.price.fillna(0) / (plan.stock.fillna(0) + 1)
            plan = plan[plan.suggested_qty > 0].sort_values("priority_score", ascending=False)
            chosen, spent = [], 0.0
            for idx, row in plan.iterrows():
                cost = float(row.estimated_cost)
                if cost <= max(0.0, budget - spent):
                    chosen.append(idx); spent += cost
            plan["within_budget"] = plan.index.isin(chosen)
            plan["decision"] = plan["within_budget"].map({True: "Within budget", False: "Defer / review"})
            st.metric("Estimated selected replenishment", f"Rs {spent:,.0f}")
            st.dataframe(plan[["stock", "fc", "lead_days", "rop", "suggested_qty", "price", "estimated_cost", "priority_score", "decision"]].round(2), use_container_width=True)
            st.caption("This is a simple priority heuristic, not a globally optimal procurement solution. Confirm pack sizes, supplier minimums, storage limits and actual costs before ordering.")
