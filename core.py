"""AVK MVP core: cleaning, privacy, analytics modules, closed-loop store, weekly PDF."""
import io, json, sqlite3, urllib.request
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path("data")  # one sub-folder (and one SQLite file) per client = isolated data
ALIAS = {"date": ["invoice_date", "voucher_date"], "customer": ["party", "party_name", "buyer"],
         "item": ["product", "item_name", "sku"], "qty": ["quantity"], "price": ["rate", "unit_price"],
         "invoice": ["invoice_no", "voucher_no", "bill_no"], "paid_date": ["payment_date", "paid_on"]}
today = lambda: pd.Timestamp.today().normalize()
week = lambda: today().strftime("%G-W%V")


# ---------- 1-2. upload, clean, privacy ----------
def clean(df):
    df = df.copy(); df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
    for k, al in ALIAS.items():
        for a in al:
            if a in df.columns and k not in df.columns: df = df.rename(columns={a: k})
    n, notes, merged = max(len(df), 1), [], 0
    for c in ("date", "due_date", "paid_date"):
        if c in df: df[c] = pd.to_datetime(df[c], errors="coerce", dayfirst=True)
    for c in ("qty", "price", "cost", "stock", "lead_days", "produced", "rejected"):
        if c in df: df[c] = pd.to_numeric(df[c], errors="coerce")
    for c in ("customer", "item"):  # merge 'Item-01', 'item 01 ' etc. into one name
        if c in df:
            s = df[c].astype(str).str.strip(); key = s.str.lower().str.replace(r"[^a-z0-9]", "", regex=True)
            canon = s.groupby(key).agg(lambda x: x.mode().iat[0]); merged += int((s != key.map(canon)).sum()); df[c] = key.map(canon)
    dup = int(df.duplicated().sum()); df = df.drop_duplicates()
    req = [c for c in ("date", "customer", "item", "qty", "price", "stock", "batch") if c in df]
    miss = float(df[req].isna().any(axis=1).mean()) if req else 0.0; df = df.dropna(subset=req)
    for t, v in (("duplicate rows removed", dup), ("inconsistent names merged", merged), ("rows with missing key fields removed", round(miss * n))):
        if v: notes.append(f"{v} {t}")
    return df, round(max(0, 100 - 60 * miss - min(20, 100 * dup / n) - min(20, 100 * merged / n))), notes


def pseudo(df, client):
    """Replace customer names with IDs before any modelling. The name map stays in the client folder."""
    p = ROOT / client / "map.json"; m = json.loads(p.read_text()) if p.exists() else {}
    for c in df.customer.unique(): m.setdefault(c, "C-%03d" % (len(m) + 1))
    p.write_text(json.dumps(m)); df["customer"] = df.customer.map(m); return df


def ensure(s):
    s = s.copy()
    if "cost" not in s: s["cost"] = s.price * .8  # assumption when cost is missing
    if "due_date" not in s: s["due_date"] = s.date + pd.Timedelta(days=30)
    if "paid_date" not in s: s["paid_date"] = pd.NaT
    if "invoice" not in s: s["invoice"] = s.date.dt.strftime("%Y%m%d") + "-" + s.customer
    return s


def invoices(s):
    return s.assign(amt=s.qty * s.price).groupby("invoice").agg(customer=("customer", "first"), date=("date", "first"),
        due_date=("due_date", "first"), paid_date=("paid_date", "first"), amount=("amt", "sum")).reset_index()


# ---------- 3. analysis modules (each returns a table and a list of actions) ----------
def ses(x, a=.2):
    f = x[0]
    for v in x[1:]: f = a * v + (1 - a) * f
    return f


def inventory(s, stock):  # demand forecasting + inventory analytics
    t = today(); w = s[s.date > t - pd.Timedelta(days=90)]
    piv = w.pivot_table(index="date", columns="item", values="qty", aggfunc="sum").reindex(pd.date_range(t - pd.Timedelta(days=89), t)).fillna(0)
    o = stock.set_index("item").join(pd.DataFrame({"fc": piv.apply(lambda c: ses(c.values)), "sd": piv.std()})).fillna({"fc": 0, "sd": 0})
    o["lead_days"] = o.lead_days.fillna(7) if "lead_days" in o else 7
    o["rop"] = o.fc * o.lead_days + 1.65 * o.sd * np.sqrt(o.lead_days)  # reorder point
    o["cover"] = o.stock / o.fc.replace(0, np.nan)
    rev = (s.qty * s.price).groupby(s.item).sum().sort_values(ascending=False); cum = rev.cumsum() / rev.sum()
    o["abc"] = pd.Series(np.where(cum <= .8, "A", np.where(cum <= .95, "B", "C")), index=rev.index)
    o["idle_days"] = (t - s.groupby("item").date.max()).dt.days
    o["price"] = s.groupby("item").price.mean(); o["tied"] = o.stock * s.groupby("item").cost.mean()
    A = []
    for i, r in o[(o.stock <= o.rop) & (o.fc > 0)].sort_values("fc", ascending=False).head(5).iterrows():
        A.append(dict(module="Inventory", text=f"Reorder {i} now", value=r.fc * max(r.lead_days - r.cover, 0) * r.price,
                      reason=f"Stock covers {r.cover:.0f} days of sales but the supplier needs {r.lead_days:.0f}. Reorder point is {r.rop:.0f} units; stock is {r.stock:.0f}."))
    for i, r in o[(o.idle_days > 90) & (o.stock > 0)].sort_values("tied", ascending=False).head(3).iterrows():
        A.append(dict(module="Inventory", text=f"Stop buying {i}; clear stock", value=r.tied, reason=f"No sale in {r.idle_days:.0f} days; Rs {r.tied:,.0f} is tied up."))
    return o, A


def sales_cust(s):  # customer ranking, drift, margin, discount leakage
    t = today(); lp = s.groupby("item").price.transform("max")
    s = s.assign(rev=s.qty * s.price, mar=s.qty * (s.price - s.cost), disc=(lp - s.price) * s.qty, lst=lp * s.qty)
    g = s.groupby("customer").agg(rev=("rev", "sum"), mar=("mar", "sum"), disc=("disc", "sum"), lst=("lst", "sum"), orders=("invoice", "nunique"), last=("date", "max"))
    g["share_pct"] = 100 * g.rev / g.rev.sum(); g["margin_pct"] = 100 * g.mar / g.rev; g["disc_pct"] = 100 * g.disc / g.lst
    first = s.drop_duplicates(["customer", "invoice"]).sort_values("date")
    g["gap"] = first.groupby("customer").date.apply(lambda d: d.diff().dt.days.median()); g["since"] = (t - g["last"]).dt.days
    A = []
    for i, r in g[(g.since > 2 * g.gap) & (g.gap > 0)].sort_values("rev", ascending=False).head(3).iterrows():
        A.append(dict(module="Sales", text=f"Call {i}", value=r.rev / r.orders, reason=f"Last order {r.since:.0f} days ago; usual gap is {r.gap:.0f} days. Typical order Rs {r.rev / r.orders:,.0f}."))
    med = g.disc_pct.median()
    for i, r in g[g.disc_pct > 2 * med].sort_values("disc", ascending=False).head(2).iterrows():
        A.append(dict(module="Sales", text=f"Review discounts to {i}", value=r.disc, reason=f"Average discount {r.disc_pct:.1f}% against {med:.1f}% typical; Rs {r.disc:,.0f} of margin given away."))
    return g, A


def quality(b):  # quality and batch module
    g = b.groupby("item").agg(produced=("produced", "sum"), rejected=("rejected", "sum")); g["reject_pct"] = 100 * g.rejected / g.produced
    base = 100 * b.rejected.sum() / b.produced.sum(); A = []
    for i, r in g[g.reject_pct > 1.5 * base].sort_values("reject_pct", ascending=False).head(3).iterrows():
        A.append(dict(module="Quality", text=f"Investigate rejects on {i}", value=r.rejected, reason=f"Reject rate {r.reject_pct:.1f}% against {base:.1f}% overall ({r.rejected:.0f} units rejected; value shown in units)."))
    return g, A


def late_model(inv):  # late-payment risk: XGBoost when enough history, otherwise a simple rule
    p = inv.dropna(subset=["paid_date"]).sort_values("date").copy(); o = inv[inv.paid_date.isna()].copy()
    for d in (p, o): d["terms"] = (d.due_date - d.date).dt.days; d["la"] = np.log1p(d.amount)
    p["delay"] = (p.paid_date - p.due_date).dt.days; p["late"] = (p.delay > 0).astype(int)
    if len(p) < 5: o["p_late"] = .3; return o, p, "rule fallback (too little payment history)"
    g = p.groupby("customer"); n = g.cumcount().replace(0, np.nan)  # history before each invoice only: no leakage
    p["c_rate"] = ((g.late.cumsum() - p.late) / n).fillna(p.late.mean()); p["c_delay"] = ((g.delay.cumsum() - p.delay) / n).fillna(p.delay.mean())
    o["c_rate"] = o.customer.map(p.groupby("customer").late.mean()).fillna(p.late.mean()); o["c_delay"] = o.customer.map(p.groupby("customer").delay.mean()).fillna(p.delay.mean())
    F, meth = ["c_rate", "c_delay", "la", "terms"], "rule fallback"
    o["p_late"] = (0.1 + 0.8 * o.c_rate).clip(.05, .95)
    if len(p) >= 200 and p.late.nunique() == 2:
        try:
            from xgboost import XGBClassifier
            from sklearn.metrics import roc_auc_score
            mk = lambda: XGBClassifier(n_estimators=120, max_depth=3, learning_rate=.1, verbosity=0); k = int(len(p) * .8)
            auc = roc_auc_score(p.late[k:], mk().fit(p[F][:k], p.late[:k]).predict_proba(p[F][k:])[:, 1]) if p.late[k:].nunique() == 2 else float("nan")
            if auc < .55: raise ValueError("no better than chance")
            o["p_late"] = mk().fit(p[F], p.late).predict_proba(o[F])[:, 1]; meth = f"XGBoost (holdout AUC {auc:.2f})"
        except Exception: pass
    return o, p, meth


def collections(o):  # cash collections module
    A = []
    for r in o.assign(k=o.amount * o.p_late).sort_values("k", ascending=False).head(5).itertuples():
        A.append(dict(module="Collections", text=f"Follow up invoice {r.invoice} ({r.customer})", value=r.amount,
                      reason=f"Rs {r.amount:,.0f} open; {max((today() - r.due_date).days, 0)} days overdue; late-payment risk {r.p_late:.0%}."))
    return A


def cash13(o, paid, opening, out_w, in_w, n=400):
    """13-week outlook: simulate each open invoice's payment date from the customer's own delay history."""
    r = np.random.default_rng(1); t = today(); wk = np.zeros((n, 13))
    h = {c: g.delay.values for c, g in paid.groupby("customer")}; allh = paid.delay.values
    for x in o.itertuples():
        d = h.get(x.customer, allh); late, ok = d[d > 0], d[d <= 0]
        late = late if len(late) else np.array([7]); ok = ok if len(ok) else np.array([0])
        off = (x.due_date - t).days; lt = r.random(n) < x.p_late
        if off < 0: lt[:] = True  # already overdue: it can only be paid late
        dl = np.where(lt, r.choice(late, n), r.choice(ok, n))
        if off < 0: dl = np.maximum(dl, -off + r.integers(1, 15, n))
        w = np.maximum(off + dl, 0) // 7; m = w < 13
        wk[np.arange(n)[m], w[m].astype(int)] += x.amount
    bal = opening + np.cumsum(wk + in_w - out_w, axis=1)
    return pd.DataFrame(np.percentile(bal, [10, 50, 90], axis=0).T, index=range(1, 14), columns=["P10", "P50", "P90"])


def kpis(s, o, ivt):
    r90 = (s.qty * s.price)[s.date > today() - pd.Timedelta(days=90)].sum()
    k = {"DSO (days)": round(o.amount.sum() / (r90 / 90), 1) if r90 else 0, "Open receivables (Rs)": round(o.amount.sum()), "Overdue (Rs)": round(o.amount[o.due_date < today()].sum())}
    if ivt is not None: k["Stock-out risk (items)"] = int(((ivt.cover < ivt.lead_days) | (ivt.stock <= 0)).sum()); k["Slow stock (Rs)"] = round(ivt.tied[ivt.idle_days > 90].sum())
    return k


def explain(acts, url=None, model="llama3"):
    """Reasons are written from computed figures. An optional LOCAL model (e.g. Ollama) may only reword them."""
    if url:
        for a in acts:
            try:
                body = json.dumps({"model": model, "stream": False, "prompt": "Rewrite in one plain sentence for a business owner. Use only these facts and add nothing: " + a["reason"]}).encode()
                a["reason"] = json.loads(urllib.request.urlopen(urllib.request.Request(url, body, {"Content-Type": "application/json"}), timeout=30).read())["response"].strip()
            except Exception: pass
    return acts


# ---------- consultant layer + closed loop ----------
def store(client):
    p = ROOT / client; p.mkdir(parents=True, exist_ok=True); con = sqlite3.connect(p / "loop.db", check_same_thread=False)
    con.executescript("""CREATE TABLE IF NOT EXISTS actions(id INTEGER PRIMARY KEY, week TEXT, module TEXT, text TEXT, reason TEXT, value REAL,
        status TEXT DEFAULT 'proposed', final_text TEXT, review_reason TEXT, owner_decision TEXT, owner_note TEXT, done INTEGER DEFAULT 0, realised REAL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS outcomes(week TEXT, metric TEXT, value REAL, PRIMARY KEY(week, metric));"""); return con


def q(con, sql, args=()): return pd.read_sql_query(sql, con, params=args)


def add_actions(con, wk, acts):
    for a in acts:
        if not con.execute("select 1 from actions where week=? and text=?", (wk, a["text"])).fetchone():
            con.execute("insert into actions(week,module,text,reason,value) values(?,?,?,?,?)", (wk, a["module"], a["text"], a["reason"], float(a["value"])))
    con.commit()


def upd(con, id, **kw):
    con.execute(f"update actions set {','.join(k + '=?' for k in kw)} where id=?", (*kw.values(), int(id))); con.commit()


def log_kpis(con, wk, k):
    for m, v in k.items(): con.execute("insert or replace into outcomes values(?,?,?)", (wk, m, float(v)))
    con.commit()


def one_pager(client, wk, k, acts):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table
    st, buf = getSampleStyleSheet(), io.BytesIO(); P = lambda t: Paragraph(str(t), st["BodyText"])
    rows = [["#", "Action", "Why", "Value (Rs)"]] + [[i + 1, P(a.final_text if isinstance(a.final_text, str) and a.final_text else a.text), P(a.reason), f"{a.value:,.0f}"] for i, a in enumerate(acts.itertuples())]
    SimpleDocTemplate(buf, pagesize=A4).build([Paragraph(f"Weekly decision brief - {client} - {wk}", st["Title"]), P(" | ".join(f"{m}: {v:,.0f}" for m, v in k.items())), Spacer(1, 12),
        Table(rows, colWidths=[20, 200, 210, 70], style=[("GRID", (0, 0), (-1, -1), .3, "grey"), ("VALIGN", (0, 0), (-1, -1), "TOP")])])
    return buf.getvalue()


# ---------- demo data ----------
def sample(seed=7):
    r = np.random.default_rng(seed); t = today(); items = [f"Item {i:02d}" for i in range(1, 16)]; cu = [f"Customer {c}" for c in "ABCDEFGHIJ"]
    late = dict(zip(cu, r.uniform(.05, .8, 10))); rows, n = [], 0
    for d in pd.date_range(t - pd.Timedelta(days=364), t):
        if d.weekday() == 6: continue
        for _ in range(r.integers(1, 4)):
            c = r.choice(cu)
            if c == "Customer J" and d > t - pd.Timedelta(days=45): continue
            n += 1; due = d + pd.Timedelta(days=30); paid = due + pd.Timedelta(days=int(r.integers(1, 40)) if r.random() < late[c] else -int(r.integers(0, 10)))
            for it in r.choice(items, 2, replace=False):
                if it in items[-2:] and d > t - pd.Timedelta(days=150): continue
                p = 100 + 9 * items.index(it); rows.append((d, f"INV{n}", c, it, int(r.integers(5, 40)), round(p * r.uniform(.88, 1), 2), p * .75, due, paid if paid <= t else pd.NaT))
    s = pd.DataFrame(rows, columns=["date", "invoice", "customer", "item", "qty", "price", "cost", "due_date", "paid_date"])
    k = pd.DataFrame({"item": items, "stock": r.integers(0, 600, 15), "lead_days": r.integers(5, 12, 15)})
    b = pd.DataFrame({"batch": range(60), "date": pd.date_range(t - pd.Timedelta(days=118), periods=60, freq="2D"), "item": r.choice(items[:6], 60), "produced": 500})
    b["rejected"] = r.poisson(np.where(b.item == "Item 03", 40, 8)); return s, k, b
