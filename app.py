"""SPARK · Anviksha decision-intelligence MVP.  Run: pip install -r requirements.txt && streamlit run app.py"""
import json
import altair as alt, pandas as pd, streamlit as st
import core as C, theme as T

P = T.PALETTE
st.set_page_config("SPARK · Anviksha", "⚡", layout="wide"); T.inject(); C.ROOT.mkdir(exist_ok=True)
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
            st.dataframe(ivt.round(1).style.apply(lambda r: ["background:#FDECEC" if r.stock <= r.rop and r.fc > 0 else "" for _ in r], axis=1), use_container_width=True)
    with TB[1]:
        g, a = C.sales_cust(s); acts += a; g = g.reset_index()
        st.altair_chart(alt.Chart(g).mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4).encode(x=alt.X("customer", sort="-y"), y="rev", color=alt.Color("margin_pct", scale=alt.Scale(range=["#F5A524", "#0E9F8E"]), title="Margin %"), tooltip=["customer", "rev", "margin_pct", "disc_pct"]), use_container_width=True)
        st.dataframe(g.round(1), use_container_width=True)
    with TB[2]:
        if b is None: st.info("Upload batch data.")
        else: g, a = C.quality(b); acts += a; st.dataframe(g.round(1), use_container_width=True)
    with TB[3]:
        st.caption(f"Late-payment risk model in use: {meth}"); acts += C.collections(op)
        st.dataframe(op[["invoice", "customer", "amount", "due_date", "p_late"]].sort_values("p_late", ascending=False).round(2), use_container_width=True)
    with TB[4]:
        c1, c2, c3 = st.columns(3)
        o0, ow, iw = c1.number_input("Opening cash (Rs)", 0.0), c2.number_input("Weekly outflow (Rs)", 0.0), c3.number_input("Other weekly inflow (Rs)", 0.0)
        cf = C.cash13(op, paid, o0, ow, iw); d = cf.reset_index(names="week")
        st.altair_chart(alt.Chart(d).mark_area(opacity=.2, color=P["teal"]).encode(x=alt.X("week:O", title="Week"), y=alt.Y("P10:Q", title="Cash (Rs)"), y2="P90:Q")
                        + alt.Chart(d).mark_line(color=P["ink"], strokeWidth=3).encode(x="week:O", y="P50:Q")
                        + alt.Chart(pd.DataFrame({"y": [0]})).mark_rule(color=P["red"], strokeDash=[4, 4]).encode(y="y:Q"), use_container_width=True)
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

else:
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
