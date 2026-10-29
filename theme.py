"""SPARK brand theme. Change the PALETTE values to match the website's exact hex codes."""
import html, streamlit as st

PALETTE = dict(ink="#0B1F3A", spark="#F5A524", teal="#0E9F8E", blue="#2F6FED", violet="#7C5CFC", rose="#E0527A", red="#D64545", green="#2E9E5B", slate="#5B6B82", bg="#F6F8FB")
MOD = {"Inventory": "#0E9F8E", "Sales": "#2F6FED", "Quality": "#7C5CFC", "Collections": "#F5A524", "Cash": "#E0527A"}
PILL = {"proposed": "#F5A524", "approved": "#0E9F8E", "rejected": "#D64545", "accepted": "#2E9E5B", "declined": "#8896AB"}
esc = html.escape

CSS = """<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Fraunces:ital,wght@1,500;1,600&display=swap');
html,body,[class*="css"],.stApp{font-family:'Inter',sans-serif}
.block-container{padding-top:1.2rem;max-width:1500px;padding-bottom:3rem}
[data-testid="stMetric"],[data-testid="stVerticalBlockBorderWrapper"]{border-radius:12px}
[data-testid="stTabs"] button{font-weight:600;color:#526174}
[data-testid="stTabs"] button[aria-selected="true"]{color:#0E9F8E;border-bottom-color:#0E9F8E}
[data-testid="stDataFrame"]{border:1px solid #E3E9F2;border-radius:10px;overflow:hidden}
.panel-title{font-size:1rem;font-weight:700;color:#0B1F3A;border-bottom:1px solid #E8EDF3;padding-bottom:.45rem;margin-bottom:.65rem}
[data-testid="stAlert"]{border-radius:10px}
[data-testid=stSidebar]{background:#0B1F3A}
[data-testid=stSidebar] label p,[data-testid=stSidebar] h1,[data-testid=stSidebar] .stRadio p,[data-testid=stSidebar] .stCheckbox p{color:#E8EEF7!important}
.brand{font-size:1.55rem;font-weight:700;color:#fff;letter-spacing:.5px}.brand b{color:#F5A524}
.brand small{display:block;font-size:.72rem;font-weight:500;color:#9FB0C8;letter-spacing:.6px}
.hero{background:linear-gradient(120deg,#0B1F3A 0%,#16355F 100%);border-radius:16px;padding:26px 32px;margin-bottom:18px;color:#fff}
.hero .eb{font-size:.72rem;letter-spacing:1.4px;text-transform:uppercase;color:#F5A524;font-weight:600}
.hero h1{font-size:2rem;font-weight:700;margin:.2rem 0;color:#fff;padding:0}
.hero h1 i{font-family:'Fraunces',serif;color:#F5A524;font-weight:600}.hero p{color:#C7D3E5;margin:0;max-width:680px}
.kpi{background:#fff;border:1px solid #E3E9F2;border-radius:12px;padding:14px 16px;box-shadow:0 1px 3px rgba(11,31,58,.06)}
.kpi .l{font-size:.74rem;color:#5B6B82;text-transform:uppercase;letter-spacing:.6px;font-weight:600}.kpi .n{font-size:1.65rem;font-weight:700}
.card{background:#fff;border:1px solid #E3E9F2;border-radius:12px;padding:12px 16px;margin:8px 0;box-shadow:0 1px 3px rgba(11,31,58,.05)}
.card .t{font-weight:600;color:#0B1F3A;margin-top:4px}.card .r{color:#5B6B82;font-size:.9rem}.card .v{font-weight:700;color:#0B1F3A;font-size:.9rem;margin-top:2px}
.chip,.pill{display:inline-block;border-radius:20px;padding:2px 10px;font-size:.7rem;font-weight:600;margin-right:6px}.pill{color:#fff}
.steps{display:flex;gap:6px;margin:0 0 16px}.step{flex:1;text-align:center;padding:8px 4px;border-radius:8px;font-size:.8rem;font-weight:600;background:#E9EEF5;color:#8896AB}
.step.done{background:#D7F0EC;color:#0E9F8E}.step.on{background:#0B1F3A;color:#F5A524}
.stButton>button,.stFormSubmitButton>button,.stDownloadButton>button{background:#0B1F3A;color:#fff;border:0;border-radius:8px;font-weight:600}
.stButton>button:hover,.stFormSubmitButton>button:hover,.stDownloadButton>button:hover{background:#F5A524;color:#0B1F3A}
h2,h3{color:#0B1F3A;font-weight:700}
</style>"""


def inject(): st.markdown(CSS, unsafe_allow_html=True)
def brand(): st.sidebar.markdown('<div class="brand">SPARK<b>.</b><small>CONSULTING · DECISION INTELLIGENCE<br>Powered by Anviksha</small></div>', unsafe_allow_html=True)


def hero(pre, accent, sub, eyebrow="Anviksha · Analytics platform"):
    st.markdown(f'<div class="hero"><div class="eb">{eyebrow}</div><h1>{esc(pre)} <i>{esc(accent)}</i></h1><p>{esc(sub)}</p></div>', unsafe_allow_html=True)


def stepper(i):
    S = ["Upload", "Clean & check", "Analyse", "Explain", "Review", "Decide"]
    st.markdown('<div class="steps">' + "".join(f'<div class="step {"done" if n < i else "on" if n == i else ""}">{n + 1} · {s}</div>' for n, s in enumerate(S)) + "</div>", unsafe_allow_html=True)


def kpi(label, value, color="#0B1F3A"):
    v = value if isinstance(value, str) else f"{value:,.0f}"
    return f'<div class="kpi" style="border-top:4px solid {color}"><div class="l">{esc(label)}</div><div class="n" style="color:{color}">{esc(v)}</div></div>'


def pill(s): return f'<span class="pill" style="background:{PILL.get(s, "#8896AB")}">{esc(s)}</span>'


def card(module, text, reason, value, status=None):
    c = MOD.get(module, "#5B6B82")
    return (f'<div class="card" style="border-left:5px solid {c}"><span class="chip" style="background:{c}22;color:{c}">{esc(module)}</span>{pill(status) if status else ""}'
            f'<div class="t">{esc(text)}</div><div class="r">{esc(reason)}</div><div class="v">Rs {value:,.0f}</div></div>')
