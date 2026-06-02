# =====================================================================
# SALIENCE OS — Clinical Intelligence Workspace
# Production-Stabilized for Streamlit Cloud / Python 3.12
# =====================================================================

# ── audioop bridge (Python 3.13+ removes stdlib audioop) ─────────────
# Python 3.12 has audioop natively; this block is a no-op there.
# audioop-lts is NOT listed in requirements because it only supports
# Python >=3.13 and Streamlit Cloud runs 3.12.
import sys
try:
    import audioop  # noqa: F401 — present in Python ≤3.12
except ImportError:
    # Python 3.13+: audioop-lts must be installed separately
    try:
        import audioop_lts as audioop  # type: ignore
        sys.modules["audioop"] = audioop
    except ImportError:
        pass  # pydub will raise a clear error if audio is attempted

import streamlit as st
import os
import json
import time
from datetime import datetime

# ── Guard all optional heavy imports ─────────────────────────────────
try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False

try:
    import google.generativeai as genai  # type: ignore
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

try:
    from pydub import AudioSegment
    PYDUB_AVAILABLE = True
except ImportError:
    PYDUB_AVAILABLE = False

try:
    from fpdf import FPDF
    FPDF_AVAILABLE = True
except ImportError:
    FPDF_AVAILABLE = False


# =====================================================================
# CONSTANTS
# =====================================================================
SPECIALTY_OPTIONS = [
    "Cardiology", "General", "Emergency",
    "Neurology", "Pediatrics", "Orthopedics",
    "Psychiatry", "Oncology",
]
SPECIALTY_MAP = {
    "Cardiology":  "Cardiology Clinic",
    "General":     "General Internal Medicine",
    "Emergency":   "Emergency Trauma",
    "Neurology":   "Neurology",
    "Pediatrics":  "Pediatrics",
    "Orthopedics": "Orthopedic Surgery",
    "Psychiatry":  "Psychiatry & Behavioral Health",
    "Oncology":    "Oncology",
}
LANGUAGE_OPTIONS = ["Mixed", "English", "Arabic"]
LANGUAGE_MAP = {
    "Mixed":   "Mixed (Multi-lingual Code-Switching)",
    "English": "English (US/UK)",
    "Arabic":  "Arabic (Khaleeji/MSA)",
}
TEMP_AUDIO = "active_stream_input.wav"
COMP_AUDIO = "optimized_payload.mp3"


# =====================================================================
# PDF GENERATION
# =====================================================================
def sanitize_for_pdf(text: str) -> str:
    if not text:
        return ""
    char_map = {
        "•": "-", "—": "-", "–": "-",
        "\u201c": '"', "\u201d": '"',
        "\u2018": "'", "\u2019": "'",
        "™": "TM", "©": "(c)", "®": "(r)",
    }
    for uc, sc in char_map.items():
        text = text.replace(uc, sc)
    return text.encode("latin-1", errors="replace").decode("latin-1")


def generate_clinical_pdf(soap_text: str, specialty: str) -> bytes:
    """Generate PDF. Returns bytes on success, raises on failure."""
    if not FPDF_AVAILABLE:
        raise RuntimeError("fpdf2 is not installed.")
    pdf = FPDF()
    pdf.set_margins(left=15, top=10, right=15)
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_fill_color(2, 132, 199)
    pdf.rect(0, 0, 210, 38, "F")
    pdf.set_xy(0, 8)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(210, 12, "SALIENCE OS | CLINICAL NOTE MATRIX",
             new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.set_font("Helvetica", "I", 10)
    pdf.cell(210, 5,
             sanitize_for_pdf(f"Specialty: {specialty} | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"),
             new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.set_xy(15, 45)
    pdf.set_text_color(15, 23, 42)
    ew = pdf.w - pdf.l_margin - pdf.r_margin
    for line in soap_text.split("\n"):
        lc = line.strip()
        if not lc:
            pdf.ln(3)
            continue
        pdf.set_x(pdf.l_margin)
        if lc.startswith("###"):
            pdf.ln(4)
            pdf.set_font("Helvetica", "B", 14)
            pdf.set_text_color(2, 132, 199)
            header = lc.replace("###", "").replace(":", "").strip().upper()
            pdf.cell(ew, 10, sanitize_for_pdf(header), new_x="LMARGIN", new_y="NEXT")
            pdf.line(pdf.l_margin, pdf.get_y(), pdf.l_margin + 40, pdf.get_y())
            pdf.ln(2)
            pdf.set_text_color(15, 23, 42)
        elif lc.startswith("**") and lc.endswith("**"):
            pdf.set_font("Helvetica", "B", 11)
            pdf.cell(ew, 7, sanitize_for_pdf(lc.replace("**", "").strip()),
                     new_x="LMARGIN", new_y="NEXT")
        else:
            pdf.set_font("Helvetica", size=10)
            pdf.multi_cell(ew, 6, sanitize_for_pdf(lc.replace("**", "").replace("*", "-")))
    return bytes(pdf.output())


# =====================================================================
# PAGE CONFIG  — must be the very first Streamlit call
# =====================================================================
st.set_page_config(
    page_title="Salience OS",
    page_icon="⬡",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# =====================================================================
# SESSION STATE — safe defaults, never KeyError
# =====================================================================
_DEFAULTS: dict = {
    "transcript": "",
    "classification": {},
    "salience_map": [],
    "soap_note": "",
    "flags": [],
    "next_steps": [],
    "pipeline_execution_time": 0.0,
    "chart_locked": False,
    # Control center values — stored as plain strings, never None
    "sc_specialty": "Cardiology",
    "sc_language": "Mixed",
    "sc_theme": "Dark",
    "_groq_override": "",
    "_gemini_override": "",
}
for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v


# =====================================================================
# SECRETS — guarded access, never raises
# =====================================================================
try:
    _has_vault_groq   = "groq_api_key"   in st.secrets
    _has_vault_gemini = "gemini_api_key" in st.secrets
    _vault_groq   = st.secrets.get("groq_api_key",   "") if _has_vault_groq   else ""
    _vault_gemini = st.secrets.get("gemini_api_key", "") if _has_vault_gemini else ""
except Exception:
    _has_vault_groq   = False
    _has_vault_gemini = False
    _vault_groq       = ""
    _vault_gemini     = ""


# =====================================================================
# CSS — ambient lighting removed from body::before (iframe-unsafe).
# Replaced with a static gradient on .stApp which Streamlit does render.
# All pointer-event-blocking constructs removed.
# =====================================================================
st.markdown("""
<style>
:root {
  --bg-base:        #080B10;
  --bg-surface:     #0E1117;
  --bg-elevated:    #161B26;
  --bg-hover:       rgba(255,255,255,0.035);
  --border-subtle:  rgba(255,255,255,0.06);
  --border-default: rgba(255,255,255,0.10);
  --border-strong:  rgba(255,255,255,0.17);
  --text-primary:   #EDF0F4;
  --text-secondary: #7E8A9A;
  --text-muted:     #4A5262;
  --accent-blue:    #3B82F6;
  --accent-blue-dim:#2563EB;
  --accent-emerald: #10B981;
  --accent-amber:   #F59E0B;
  --accent-red:     #EF4444;
  --accent-violet:  #8B5CF6;
  --accent-cyan:    #06B6D4;
  --tier-critical:  #EF4444;
  --tier-high:      #F59E0B;
  --tier-medium:    #3B82F6;
  --tier-low:       #10B981;
  --radius-sm: 5px;
  --radius-md: 9px;
  --radius-lg: 14px;
  --font-mono: 'JetBrains Mono','Fira Code','SF Mono',ui-monospace,monospace;
  --transition: 150ms cubic-bezier(0.4,0,0.2,1);
  --soap-font-size: 14px;
  --soap-line-height: 1.9;
}

/* Ambient glow on .stApp — safe inside Streamlit's iframe */
.stApp {
  background:
    radial-gradient(circle at 88% 12%, rgba(59,130,246,0.09) 0%, transparent 38%),
    radial-gradient(circle at 8%  52%, rgba(6,182,212,0.06)  0%, transparent 30%),
    radial-gradient(circle at 72% 92%, rgba(139,92,246,0.05) 0%, transparent 28%),
    #080B10 !important;
}

html, body, [class*="css"] {
  font-family: -apple-system,'SF Pro Text','Helvetica Neue',system-ui,sans-serif;
  color: var(--text-primary) !important;
  -webkit-font-smoothing: antialiased;
}

#MainMenu, footer, header { visibility: hidden !important; }
.stDeployButton { display: none !important; }

.block-container {
  padding-top: 12px !important;
  padding-left: 16px !important;
  padding-right: 16px !important;
  padding-bottom: 40px !important;
  max-width: 100% !important;
}

::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border-default); border-radius: 99px; }

/* ── Header ── */
.os-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 0 14px; border-bottom: 1px solid var(--border-subtle);
  margin-bottom: 20px;
}
.os-wordmark {
  font-size: 15px; font-weight: 700; letter-spacing: 0.3px;
  color: var(--text-primary);
}
.os-wordmark span { color: var(--accent-blue); }
.os-header-meta { display: flex; align-items: center; gap: 12px; }

.os-status-pill {
  display: inline-flex; align-items: center; gap: 5px;
  font-size: 11px; font-weight: 500; padding: 3px 10px;
  border-radius: 99px; letter-spacing: 0.2px;
}
.os-status-pill.ready  { background:rgba(16,185,129,0.10); color:var(--accent-emerald); border:1px solid rgba(16,185,129,0.18); }
.os-status-pill.active { background:rgba(59,130,246,0.10); color:var(--accent-blue);    border:1px solid rgba(59,130,246,0.18); }
.os-status-pill.locked { background:rgba(139,92,246,0.10); color:var(--accent-violet);  border:1px solid rgba(139,92,246,0.18); }
.os-dot { width:5px; height:5px; border-radius:50%; background:currentColor; }
.os-dot.pulse { animation: pulse-dot 2s ease-in-out infinite; }
@keyframes pulse-dot { 0%,100%{opacity:1;transform:scale(1)} 50%{opacity:.4;transform:scale(.75)} }
.os-time { font-size:11px; font-family:var(--font-mono); color:var(--text-muted); font-variant-numeric:tabular-nums; }

/* ── Section Labels ── */
.section-label {
  font-size:10px; font-weight:700; letter-spacing:1px;
  text-transform:uppercase; color:var(--text-muted);
  margin:0 0 12px; display:flex; align-items:center; gap:10px;
}
.section-label::after { content:''; flex:1; height:1px; background:var(--border-subtle); }

/* ── Urgency Banner ── */
.urgency-bar {
  display:flex; align-items:center; gap:12px;
  padding:13px 18px; border-radius:var(--radius-md);
  margin-bottom:20px; border-left:3px solid;
}
.urgency-bar.CRITICAL { background:rgba(239,68,68,0.07);  border-color:var(--tier-critical); }
.urgency-bar.HIGH     { background:rgba(245,158,11,0.07); border-color:var(--tier-high); }
.urgency-bar.MEDIUM   { background:rgba(59,130,246,0.07); border-color:var(--tier-medium); }
.urgency-bar.LOW      { background:rgba(16,185,129,0.07); border-color:var(--tier-low); }
.urgency-label { font-size:9.5px; font-weight:700; letter-spacing:1.1px; text-transform:uppercase; opacity:.65; }
.urgency-text  { font-size:13px; font-weight:500; line-height:1.45; margin-top:2px; }
.urgency-bar.CRITICAL .urgency-label,.urgency-bar.CRITICAL .urgency-text { color:var(--tier-critical); }
.urgency-bar.HIGH     .urgency-label,.urgency-bar.HIGH     .urgency-text { color:var(--tier-high); }
.urgency-bar.MEDIUM   .urgency-label,.urgency-bar.MEDIUM   .urgency-text { color:var(--tier-medium); }
.urgency-bar.LOW      .urgency-label,.urgency-bar.LOW      .urgency-text { color:var(--tier-low); }
.urgency-metrics { margin-left:auto; display:flex; gap:8px; flex-shrink:0; }
.metric-chip {
  display:inline-flex; align-items:center; gap:4px;
  padding:3px 9px; background:var(--bg-elevated);
  border:1px solid var(--border-subtle); border-radius:99px;
  font-size:11px; color:var(--text-secondary); font-family:var(--font-mono);
}
.metric-chip .chip-label { font-family:-apple-system,sans-serif; font-size:10.5px; color:var(--text-muted); }

/* ── Signal Rows ── */
.signal-row {
  display:flex; align-items:flex-start; gap:12px;
  padding:10px 6px; border-bottom:1px solid var(--border-subtle);
  transition:background var(--transition); border-radius:var(--radius-sm);
}
.signal-row:last-child { border-bottom:none; }
.signal-row:hover { background:var(--bg-hover); }
.signal-score-ring {
  flex-shrink:0; width:38px; height:38px; border-radius:50%;
  display:flex; align-items:center; justify-content:center;
  font-size:10.5px; font-weight:700; font-family:var(--font-mono); border:2px solid;
}
.score-critical { background:rgba(239,68,68,0.09);  border-color:var(--tier-critical); color:var(--tier-critical); }
.score-high     { background:rgba(245,158,11,0.09); border-color:var(--tier-high);     color:var(--tier-high); }
.score-medium   { background:rgba(59,130,246,0.09); border-color:var(--tier-medium);   color:var(--tier-medium); }
.score-low      { background:rgba(16,185,129,0.09); border-color:var(--tier-low);      color:var(--tier-low); }
.signal-body { flex:1; min-width:0; }
.signal-entity { font-size:13px; font-weight:600; color:var(--text-primary); }
.signal-category-chip {
  display:inline-block; font-size:9.5px; font-weight:600; letter-spacing:.4px;
  padding:1px 6px; border-radius:99px; background:var(--bg-elevated);
  border:1px solid var(--border-default); color:var(--text-secondary);
  margin:3px 0 4px; text-transform:uppercase;
}
.signal-reasoning { font-size:12px; color:var(--text-secondary); line-height:1.55; }
.signal-bar-track { width:100%; height:2px; background:var(--bg-elevated); border-radius:99px; margin-top:7px; overflow:hidden; }
.signal-bar-fill  { height:100%; border-radius:99px; }

/* ── Flag & Step Items ── */
.flag-item {
  display:flex; align-items:flex-start; gap:10px; padding:11px 14px;
  background:rgba(239,68,68,0.06); border:1px solid rgba(239,68,68,0.15);
  border-left:3px solid var(--tier-critical); border-radius:var(--radius-md);
  margin-bottom:8px; font-size:13px; color:#FCA5A5; line-height:1.55;
}
.flag-icon { flex-shrink:0; color:var(--tier-critical); font-size:13px; margin-top:1px; }
.step-item {
  display:flex; align-items:flex-start; gap:10px; padding:9px 14px;
  background:rgba(59,130,246,0.055); border:1px solid rgba(59,130,246,0.12);
  border-radius:var(--radius-md); margin-bottom:7px;
  font-size:13px; color:#93C5FD; line-height:1.55;
}
.step-num {
  flex-shrink:0; width:19px; height:19px; border-radius:50%;
  background:rgba(59,130,246,0.18); color:var(--accent-blue);
  font-size:9.5px; font-weight:700; display:flex; align-items:center;
  justify-content:center; margin-top:1px;
}

/* ── SOAP ── */
.soap-outer  { max-width:1100px; margin:0 auto; }
.soap-viewer {
  background:var(--bg-surface); border:1px solid var(--border-default);
  border-radius:var(--radius-lg); padding:32px 36px;
  font-size:var(--soap-font-size); line-height:var(--soap-line-height);
  color:var(--text-primary);
}
.soap-section-header {
  font-size:10px; font-weight:700; letter-spacing:1.1px;
  text-transform:uppercase; color:var(--accent-blue);
  margin-top:24px; margin-bottom:10px;
  padding-bottom:7px; border-bottom:1px solid var(--border-subtle);
}
.soap-section-header:first-child { margin-top:0; }
.soap-body-p { margin:0 0 2px; color:var(--text-secondary); }
.soap-bold   { color:var(--text-primary); font-weight:600; }
.soap-meta-row {
  display:flex; align-items:center; gap:16px;
  padding:12px 0; margin-bottom:8px;
  border-bottom:1px solid var(--border-subtle); flex-wrap:wrap;
}
.soap-meta-item { display:flex; flex-direction:column; gap:2px; }
.soap-meta-label { font-size:9.5px; font-weight:700; letter-spacing:.8px; text-transform:uppercase; color:var(--text-muted); }
.soap-meta-value { font-size:12.5px; font-weight:500; color:var(--text-secondary); font-family:var(--font-mono); }

/* ── Empty State ── */
.empty-state {
  display:flex; flex-direction:column; align-items:center; justify-content:center;
  padding:44px 24px; text-align:center; gap:10px;
}
.empty-state-icon  { font-size:24px; opacity:.25; }
.empty-state-title { font-size:13.5px; font-weight:600; color:var(--text-secondary); }
.empty-state-body  { font-size:12px; color:var(--text-muted); line-height:1.6; max-width:260px; }

/* ── Control center label ── */
.ctrl-label {
  font-size:9.5px; font-weight:700; letter-spacing:1px;
  text-transform:uppercase; color:var(--text-muted);
  display:block; margin-bottom:8px; margin-top:16px;
}
.ctrl-label:first-child { margin-top:0; }

/* ── Sidebar ── */
section[data-testid="stSidebar"] {
  background:var(--bg-surface) !important;
  border-right:1px solid var(--border-subtle) !important;
}

/* ── Inputs ── */
.stTextInput > div > div > input,
.stTextArea  > div > div > textarea {
  background:var(--bg-elevated) !important;
  border:1px solid var(--border-default) !important;
  border-radius:var(--radius-md) !important;
  color:var(--text-primary) !important;
  font-size:13px !important;
}
.stTextInput > div > div > input:focus,
.stTextArea  > div > div > textarea:focus {
  border-color:var(--accent-blue) !important;
  box-shadow:0 0 0 3px rgba(59,130,246,0.12) !important;
  outline:none !important;
}
.stSelectbox > div > div > div {
  background:var(--bg-elevated) !important;
  border:1px solid var(--border-default) !important;
  border-radius:var(--radius-md) !important;
  color:var(--text-primary) !important;
  font-size:13px !important;
}

/* ── Buttons ── */
.stButton > button[kind="primary"] {
  background:var(--accent-blue) !important;
  color:#fff !important; border:none !important;
  border-radius:var(--radius-md) !important;
  font-weight:600 !important; font-size:13px !important;
  height:40px !important; letter-spacing:.2px !important;
  transition:background var(--transition),box-shadow var(--transition) !important;
}
.stButton > button[kind="primary"]:hover {
  background:var(--accent-blue-dim) !important;
  box-shadow:0 0 0 3px rgba(59,130,246,0.22) !important;
}
.stButton > button[kind="secondary"],
.stButton > button:not([kind]) {
  background:var(--bg-elevated) !important;
  color:var(--text-primary) !important;
  border:1px solid var(--border-default) !important;
  border-radius:var(--radius-md) !important;
  font-weight:500 !important; font-size:13px !important;
  height:40px !important;
}
.stButton > button:disabled {
  background:var(--bg-elevated) !important;
  color:var(--text-muted) !important;
  border-color:var(--border-subtle) !important;
}
.stDownloadButton > button {
  background:var(--bg-elevated) !important;
  color:var(--text-primary) !important;
  border:1px solid var(--border-default) !important;
  border-radius:var(--radius-md) !important;
  font-weight:500 !important; font-size:13px !important; height:40px !important;
}
.stDownloadButton > button:hover { border-color:var(--accent-blue) !important; color:var(--accent-blue) !important; }

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {
  background:transparent !important;
  border-bottom:1px solid var(--border-subtle) !important;
  gap:0 !important; padding:0 !important;
}
.stTabs [data-baseweb="tab"] {
  background:transparent !important; color:var(--text-muted) !important;
  font-size:12.5px !important; font-weight:500 !important;
  padding:9px 16px !important; border-bottom:2px solid transparent !important;
  border-radius:0 !important;
}
.stTabs [aria-selected="true"] { color:var(--text-primary) !important; border-bottom:2px solid var(--accent-blue) !important; }
.stTabs [data-baseweb="tab-panel"] { padding:18px 0 0 !important; }

/* ── segmented_control ── */
[data-testid="stSegmentedControl"] > div {
  background:var(--bg-elevated) !important;
  border:1px solid var(--border-default) !important;
  border-radius:var(--radius-md) !important;
  padding:3px !important; gap:2px !important;
}
[data-testid="stSegmentedControl"] button {
  background:transparent !important; color:var(--text-secondary) !important;
  border-radius:var(--radius-sm) !important; font-size:12.5px !important;
  font-weight:500 !important; border:none !important;
}
[data-testid="stSegmentedControl"] button[aria-checked="true"] {
  background:var(--accent-blue) !important; color:#fff !important;
  box-shadow:0 1px 4px rgba(0,0,0,.4) !important;
}

/* ── pills ── */
[data-testid="stPills"] button {
  background:var(--bg-elevated) !important; color:var(--text-secondary) !important;
  border:1px solid var(--border-default) !important; border-radius:99px !important;
  font-size:12px !important; font-weight:500 !important;
}
[data-testid="stPills"] button[aria-pressed="true"] {
  background:rgba(59,130,246,0.15) !important;
  color:var(--accent-blue) !important; border-color:rgba(59,130,246,.3) !important;
}

/* ── Misc ── */
.stRadio > label { color:var(--text-secondary) !important; font-size:12.5px !important; }
.stRadio > div > label { color:var(--text-secondary) !important; font-size:13px !important; }
[data-testid="stAudioInput"]   { background:var(--bg-elevated) !important; border:1px solid var(--border-default) !important; border-radius:var(--radius-md) !important; }
[data-testid="stFileUploader"] { background:var(--bg-elevated) !important; border:1px dashed var(--border-default) !important; border-radius:var(--radius-md) !important; }
.stNumberInput > div > div > input { background:var(--bg-elevated) !important; border:1px solid var(--border-default) !important; border-radius:var(--radius-md) !important; color:var(--text-primary) !important; }
[data-baseweb="notification"] { border-radius:var(--radius-md) !important; font-size:13px !important; }
hr { border-color:var(--border-subtle) !important; margin:20px 0 !important; }
[data-testid="stStatusWidget"] { background:var(--bg-elevated) !important; border:1px solid var(--border-default) !important; border-radius:var(--radius-md) !important; }
label[data-testid="stWidgetLabel"] { color:var(--text-secondary) !important; font-size:12px !important; }
.stCaption { color:var(--text-muted) !important; font-size:11.5px !important; }
p { color:var(--text-secondary) !important; }
[data-testid="stPopover"] > div {
  background:var(--bg-elevated) !important; border:1px solid var(--border-default) !important;
  border-radius:var(--radius-lg) !important; box-shadow:0 16px 48px rgba(0,0,0,.7) !important;
}
</style>
""", unsafe_allow_html=True)


# =====================================================================
# CONTROL CENTER  — renders inside st.popover
# Uses separate session_state keys (sc_specialty / sc_language / sc_theme)
# so that segmented_control never returns None in a way that corrupts
# the specialty_profile / target_language strings used in prompts.
# =====================================================================
def render_control_center() -> None:
    st.markdown('<span class="ctrl-label">Specialty Profile</span>', unsafe_allow_html=True)
    chosen_spec = st.segmented_control(
        "Specialty",
        options=SPECIALTY_OPTIONS,
        default=st.session_state.sc_specialty,
        key="sc_specialty_widget",
        label_visibility="collapsed",
    )
    # Only update if widget returned a non-None value
    if chosen_spec is not None:
        st.session_state.sc_specialty = chosen_spec

    st.markdown('<span class="ctrl-label">Language Matrix</span>', unsafe_allow_html=True)
    chosen_lang = st.segmented_control(
        "Language",
        options=LANGUAGE_OPTIONS,
        default=st.session_state.sc_language,
        key="sc_language_widget",
        label_visibility="collapsed",
    )
    if chosen_lang is not None:
        st.session_state.sc_language = chosen_lang

    st.markdown('<span class="ctrl-label">Theme</span>', unsafe_allow_html=True)
    chosen_theme = st.pills(
        "Theme",
        options=["Dark", "System", "Light"],
        default=st.session_state.sc_theme,
        key="sc_theme_widget",
        label_visibility="collapsed",
    )
    if chosen_theme is not None:
        st.session_state.sc_theme = chosen_theme

    st.markdown('<span class="ctrl-label">API Credentials</span>', unsafe_allow_html=True)
    if _has_vault_groq and _has_vault_gemini:
        st.caption("✓  Vault active — keys pre-loaded")
    else:
        st.text_input(
            "Groq API Key",
            type="password",
            placeholder="sk-..." if not _has_vault_groq else "🔒 Vault loaded",
            key="_groq_override",
        )
        st.text_input(
            "Gemini API Key",
            type="password",
            placeholder="AI..." if not _has_vault_gemini else "🔒 Vault loaded",
            key="_gemini_override",
        )


# ── Resolve effective values (always strings, never None) ────────────
_raw_spec = st.session_state.sc_specialty or "Cardiology"
_raw_lang = st.session_state.sc_language  or "Mixed"
specialty_profile: str = SPECIALTY_MAP.get(_raw_spec, "Cardiology Clinic")
target_language:   str = LANGUAGE_MAP.get(_raw_lang, "Mixed (Multi-lingual Code-Switching)")
groq_api_key:   str = (st.session_state.get("_groq_override")   or "").strip() or _vault_groq
gemini_api_key: str = (st.session_state.get("_gemini_override") or "").strip() or _vault_gemini


# =====================================================================
# HEADER
# =====================================================================
has_results  = bool(st.session_state.transcript)
chart_locked = st.session_state.chart_locked

if chart_locked:
    status_cls  = "locked"
    status_txt  = "Signed"
    dot_cls     = "os-dot"
elif has_results:
    status_cls  = "active"
    status_txt  = "Review"
    dot_cls     = "os-dot pulse"
else:
    status_cls  = "ready"
    status_txt  = "Ready"
    dot_cls     = "os-dot pulse"

hcol1, hcol2 = st.columns([5, 1])
with hcol1:
    st.markdown(f"""
    <div class="os-header">
      <div class="os-wordmark">SALIENCE<span> OS</span></div>
      <div class="os-header-meta">
        <div class="os-status-pill {status_cls}">
          <div class="{dot_cls}"></div>{status_txt}
        </div>
        <div class="os-time">{datetime.now().strftime('%H:%M')}</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

with hcol2:
    with st.popover("⚙ Settings", use_container_width=True):
        render_control_center()

# ── Theme token injection ─────────────────────────────────────────────
_active_theme = st.session_state.get("sc_theme", "Dark")

_LIGHT_TOKENS = """
<style>
.stApp {
  background:
    radial-gradient(circle at 88% 12%, rgba(59,130,246,0.06) 0%, transparent 38%),
    radial-gradient(circle at 8%  52%, rgba(6,182,212,0.04)  0%, transparent 30%),
    radial-gradient(circle at 72% 92%, rgba(139,92,246,0.03) 0%, transparent 28%),
    #F0F4F8 !important;
}
:root {
  --bg-base:        #F0F4F8;
  --bg-surface:     #FFFFFF;
  --bg-elevated:    #F7F9FC;
  --bg-hover:       rgba(0,0,0,0.04);
  --border-subtle:  rgba(0,0,0,0.07);
  --border-default: rgba(0,0,0,0.12);
  --border-strong:  rgba(0,0,0,0.20);
  --text-primary:   #0D1117;
  --text-secondary: #3D4A5C;
  --text-muted:     #7A8799;
  --accent-blue:    #1D6FE8;
  --accent-blue-dim:#1558C0;
  --accent-emerald: #0D9065;
  --accent-amber:   #C07800;
  --accent-red:     #C8282B;
  --accent-violet:  #6B3FD4;
  --accent-cyan:    #0592A8;
  --tier-critical:  #C8282B;
  --tier-high:      #C07800;
  --tier-medium:    #1D6FE8;
  --tier-low:       #0D9065;
}
html, body, [class*="css"] { color: var(--text-primary) !important; }
.stApp, .block-container { background-color: var(--bg-base) !important; }
p { color: var(--text-secondary) !important; }
.soap-viewer {
  background: #FFFFFF !important;
  border-color: rgba(0,0,0,0.10) !important;
  color: var(--text-primary) !important;
}
.soap-body-p { color: var(--text-secondary) !important; }
.stTextInput > div > div > input,
.stTextArea  > div > div > textarea {
  background: #FFFFFF !important;
  border-color: rgba(0,0,0,0.15) !important;
  color: var(--text-primary) !important;
}
.stButton > button[kind="secondary"],
.stButton > button:not([kind]) {
  background: #FFFFFF !important;
  color: var(--text-primary) !important;
  border-color: rgba(0,0,0,0.15) !important;
}
.stDownloadButton > button {
  background: #FFFFFF !important;
  color: var(--text-primary) !important;
  border-color: rgba(0,0,0,0.15) !important;
}
[data-testid="stSegmentedControl"] > div {
  background: #FFFFFF !important;
  border-color: rgba(0,0,0,0.12) !important;
}
[data-testid="stSegmentedControl"] button { color: var(--text-secondary) !important; }
[data-testid="stPills"] button { background: #FFFFFF !important; border-color: rgba(0,0,0,0.12) !important; color: var(--text-secondary) !important; }
[data-testid="stPopover"] > div { background: #FFFFFF !important; border-color: rgba(0,0,0,0.10) !important; box-shadow: 0 16px 48px rgba(0,0,0,0.12) !important; }
section[data-testid="stSidebar"] { background: #FFFFFF !important; }
.stTabs [data-baseweb="tab-list"] { border-bottom-color: rgba(0,0,0,0.10) !important; }
.stTabs [data-baseweb="tab"] { color: var(--text-muted) !important; }
.stTabs [aria-selected="true"] { color: var(--text-primary) !important; }
.flag-item { color: #9B1C1C !important; background: rgba(200,40,43,0.06) !important; }
.step-item { color: #1E429F !important; background: rgba(29,111,232,0.06) !important; }
.signal-reasoning { color: var(--text-secondary) !important; }
.urgency-bar.CRITICAL { background: rgba(200,40,43,0.06) !important; }
.urgency-bar.HIGH     { background: rgba(192,120,0,0.06) !important; }
.urgency-bar.MEDIUM   { background: rgba(29,111,232,0.06) !important; }
.urgency-bar.LOW      { background: rgba(13,144,101,0.06) !important; }
.os-header { border-bottom-color: rgba(0,0,0,0.08) !important; }
.section-label::after { background: rgba(0,0,0,0.08) !important; }
.signal-row { border-bottom-color: rgba(0,0,0,0.07) !important; }
.signal-bar-track { background: rgba(0,0,0,0.07) !important; }
</style>
"""

_SYSTEM_CHECK = """
<style>
@media (prefers-color-scheme: light) {
  .stApp {
    background:
      radial-gradient(circle at 88% 12%, rgba(59,130,246,0.06) 0%, transparent 38%),
      radial-gradient(circle at 8%  52%, rgba(6,182,212,0.04)  0%, transparent 30%),
      #F0F4F8 !important;
  }
  :root {
    --bg-base: #F0F4F8; --bg-surface: #FFFFFF; --bg-elevated: #F7F9FC;
    --bg-hover: rgba(0,0,0,0.04); --border-subtle: rgba(0,0,0,0.07);
    --border-default: rgba(0,0,0,0.12); --border-strong: rgba(0,0,0,0.20);
    --text-primary: #0D1117; --text-secondary: #3D4A5C; --text-muted: #7A8799;
    --accent-blue: #1D6FE8; --accent-blue-dim: #1558C0;
    --tier-critical: #C8282B; --tier-high: #C07800;
    --tier-medium: #1D6FE8; --tier-low: #0D9065;
  }
  html, body, [class*="css"] { color: #0D1117 !important; }
  p { color: #3D4A5C !important; }
}
</style>
"""

if _active_theme == "Light":
    st.markdown(_LIGHT_TOKENS, unsafe_allow_html=True)
elif _active_theme == "System":
    st.markdown(_SYSTEM_CHECK, unsafe_allow_html=True)
# Dark is the default — no injection needed
# =====================================================================
# INPUT WORKSPACE
# =====================================================================
st.markdown('<div class="section-label">Consultation Input</div>', unsafe_allow_html=True)
col_input, col_exam = st.columns([1.25, 1], gap="large")

with col_input:
    input_vector: str = st.radio(
        "Input mode",
        ["Text / Paste Transcript", "Live Audio (Microphone)", "File Upload (.wav / .mp3 / .json)"],
        horizontal=False,
        label_visibility="collapsed",
    )

    has_valid_audio_payload: bool = False
    bypass_audio_stt:        bool = False
    injected_text_payload:   str  = ""

    if "Text" in input_vector:
        injected_text_payload = st.text_area(
            "Transcript",
            placeholder="Paste consultation transcript, patient notes, or test data…",
            height=200,
            label_visibility="collapsed",
        )
        if injected_text_payload.strip():
            has_valid_audio_payload = True
            bypass_audio_stt = True

    elif "Live Audio" in input_vector:
        if not PYDUB_AVAILABLE:
            st.warning("Audio processing unavailable. Use Text input instead.")
        else:
            st.caption("Position microphone toward conversation, then tap record.")
            audio_file = st.audio_input("Record audio")
            if audio_file is not None:
                try:
                    with open(TEMP_AUDIO, "wb") as fh:
                        fh.write(audio_file.read())
                    has_valid_audio_payload = True
                except OSError as e:
                    st.error(f"Could not save audio: {e}")

    else:  # File upload
        uploaded_file = st.file_uploader(
            "Upload audio or dataset",
            type=["wav", "mp3", "m4a", "json"],
            label_visibility="collapsed",
        )
        if uploaded_file is not None:
            if uploaded_file.name.endswith(".json"):
                try:
                    json_data = json.load(uploaded_file)
                    if isinstance(json_data, list):
                        st.caption(f"Dataset loaded — {len(json_data)} cases")
                        case_idx = int(st.number_input(
                            "Case index", min_value=0,
                            max_value=max(len(json_data) - 1, 0), value=0,
                        ))
                        node = json_data[case_idx]
                        injected_text_payload = node.get("input", node.get("instruction", ""))
                        if injected_text_payload:
                            st.info(injected_text_payload[:240] +
                                    ("…" if len(injected_text_payload) > 240 else ""))
                        if injected_text_payload.strip():
                            has_valid_audio_payload = True
                            bypass_audio_stt = True
                    else:
                        st.error("JSON must be a list of case objects.")
                except json.JSONDecodeError as e:
                    st.error(f"JSON parse error: {e}")
                except Exception as e:
                    st.error(f"File error: {e}")
            else:
                if not PYDUB_AVAILABLE:
                    st.warning("Audio processing unavailable. Use Text input instead.")
                else:
                    try:
                        with open(TEMP_AUDIO, "wb") as fh:
                            fh.write(uploaded_file.getbuffer())
                        st.audio(TEMP_AUDIO)
                        has_valid_audio_payload = True
                    except OSError as e:
                        st.error(f"Could not save file: {e}")

with col_exam:
    st.markdown('<div class="section-label">Physical Examination</div>', unsafe_allow_html=True)
    st.caption("Findings are merged with transcript during analysis.")
    exam_tabs = st.tabs(["Thoracic", "GI / Abdomen", "Neuro / Reflex", "Musculoskeletal"])
    with exam_tabs[0]:
        notes_thoracic: str = st.text_area(
            "Thoracic",
            value="Cardiovascular: Tachycardic, rhythm regular. S1 and S2 distinct, no audible murmurs, rubs, or gallops. Significant chest wall diaphoresis noted; patient actively clutching retrosternal area. Respiratory: Tachypneic, shallow respirations. Lungs clear to auscultation bilaterally (CTAB).",
            height=140, label_visibility="collapsed",
        )
    with exam_tabs[1]:
        notes_abdominal: str = st.text_area(
            "GI",
            value="Abdomen soft, symmetric, and non-distended. Bowel sounds active in all 4 quadrants. No localized tenderness, guarding, or rebound. No hepatosplenomegaly. Epigastric region non-tender.",
            height=140, label_visibility="collapsed",
        )
    with exam_tabs[2]:
        notes_neuro: str = st.text_area(
            "Neuro",
            value="Patient alert and oriented to person, place, and time (A&Ox3). Pupils equal, round, and reactive to light (PEERRLA). Observable orthostatic lightheadedness upon sitting up. Gross motor and sensory function intact.",
            height=140, label_visibility="collapsed",
        )
    with exam_tabs[3]:
        notes_ortho: str = st.text_area(
            "MSK",
            value="Mild focal tenderness over lumbar paraspinal muscles. Left shoulder and left mandibular jaw display full passive range of motion with zero localized joint or bone tenderness.",
            height=140, label_visibility="collapsed",
        )

compiled_exam: str = (
    f"- Thoracic: {notes_thoracic or 'Deferred/Normal'}\n"
    f"- GI/Abdomen: {notes_abdominal or 'Deferred/Normal'}\n"
    f"- Neuro/Reflex: {notes_neuro or 'Deferred/Normal'}\n"
    f"- Musculoskeletal: {notes_ortho or 'Deferred/Normal'}"
)


# =====================================================================
# ANALYSIS TRIGGER
# =====================================================================
st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

run_pipeline: bool = False
if has_valid_audio_payload:
    trigger_col, _ = st.columns([1, 2])
    with trigger_col:
        run_pipeline = st.button(
            "⬡  Analyse Consultation",
            type="primary",
            use_container_width=True,
        )
else:
    st.markdown("""
    <div class="empty-state">
      <div class="empty-state-icon">⬡</div>
      <div class="empty-state-title">Awaiting input</div>
      <div class="empty-state-body">Paste a transcript, record audio, or upload a file to begin clinical analysis.</div>
    </div>
    """, unsafe_allow_html=True)


# =====================================================================
# PIPELINE EXECUTION
# =====================================================================
if has_valid_audio_payload and run_pipeline:
    if not GROQ_AVAILABLE and not bypass_audio_stt:
        st.error("Groq SDK is not installed. Cannot process audio.")
    elif not GENAI_AVAILABLE:
        st.error("google-generativeai SDK is not installed.")
    elif not groq_api_key and not bypass_audio_stt:
        st.error("Groq API key missing. Open ⚙ Settings to add it.")
    elif not gemini_api_key:
        st.error("Gemini API key missing. Open ⚙ Settings to add it.")
    else:
        t0 = time.time()
        with st.status("Running clinical intelligence pipeline…", expanded=True) as status_widget:
            try:
                # Stage 1 — Transcription
                extracted_raw_text: str = ""
                if bypass_audio_stt:
                    st.write("✓  Text input detected — bypassing STT")
                    extracted_raw_text = injected_text_payload
                else:
                    if not PYDUB_AVAILABLE:
                        raise RuntimeError("pydub is not available. Use Text input mode.")
                    if not os.path.exists(TEMP_AUDIO):
                        raise FileNotFoundError(f"Audio file missing at {TEMP_AUDIO!r}. Re-upload.")
                    st.write("⬡  Compressing audio…")
                    raw_audio = AudioSegment.from_file(TEMP_AUDIO)
                    processed = raw_audio.set_channels(1).set_frame_rate(16000)
                    processed.export(COMP_AUDIO, format="mp3", bitrate="64k")
                    st.write("⬡  Transcribing via Whisper large-v3…")
                    gc = Groq(api_key=groq_api_key, timeout=60.0)
                    with open(COMP_AUDIO, "rb") as ab:
                        extracted_raw_text = gc.audio.transcriptions.create(
                            file=(COMP_AUDIO, ab.read()),
                            model="whisper-large-v3",
                            response_format="text",
                        )
                    for p in (TEMP_AUDIO, COMP_AUDIO):
                        try:
                            if os.path.exists(p):
                                os.remove(p)
                        except OSError:
                            pass
                    st.write("✓  Transcription complete")

                if not (extracted_raw_text or "").strip():
                    raise ValueError("Transcription returned empty text. Check audio quality or API key.")

                # Stage 2 — Gemini
                st.write("⬡  Running salience analysis via Gemini 2.5 Flash…")
                genai.configure(api_key=gemini_api_key)
                engine = genai.GenerativeModel("gemini-2.5-flash")

                prompt = f"""
You are the core analytical pipeline of Salience OS, configured for the specialty: {specialty_profile}.
The incoming data stream was ingested with an expected localization matrix profile of: {target_language}.

RAW INPUT DATA TRANSCRIPT:
\"\"\"{extracted_raw_text}\"\"\"

DOCTOR PHYSICAL EXAMINATION DATA OVERLAYS:
\"\"\"{compiled_exam}\"\"\"

Generate a valid JSON payload object matching exactly this structure (no markdown blocks, no prefix text):
{{
    "cleaned_transcript": "string containing clean, error-corrected text stream",
    "classification": {{"urgency_tier": "CRITICAL or HIGH or MEDIUM or LOW", "primary_clinical_trigger": "Brief sentence"}},
    "salience_weight_map": [
        {{"entity": "Entity Name", "category": "Symptom or Medication or Medical History or Duration or Noise", "salience_score": 0.95, "reasoning_context": "Why this priority?"}}
    ],
    "clinical_safety_red_flags": ["Specific warnings"],
    "suggested_next_steps": ["Lab tracking, imaging profiles"],
    "structured_soap_chart": "Detailed markdown formatted text strictly outputting Subjective, Objective, Assessment, and Plan entries. Base Subjective data ONLY on elements where salience_score >= 0.5."
}}
"""
                resp = engine.generate_content(
                    prompt,
                    generation_config={"response_mime_type": "application/json"},
                )
                raw_json: str = resp.text or ""
                if not raw_json.strip():
                    raise ValueError("Gemini returned empty response. Check API key and quota.")

                try:
                    parsed: dict = json.loads(raw_json, strict=False)
                except json.JSONDecodeError as je:
                    raise ValueError(
                        f"Gemini response was not valid JSON: {je}. "
                        f"First 300 chars: {raw_json[:300]}"
                    ) from je

                st.session_state.transcript              = str(parsed.get("cleaned_transcript", ""))
                st.session_state.classification          = dict(parsed.get("classification", {}))
                st.session_state.salience_map            = list(parsed.get("salience_weight_map", []))
                st.session_state.soap_note               = str(parsed.get("structured_soap_chart", ""))
                st.session_state.flags                   = list(parsed.get("clinical_safety_red_flags", []))
                st.session_state.next_steps              = list(parsed.get("suggested_next_steps", []))
                st.session_state.pipeline_execution_time = round(time.time() - t0, 2)
                st.session_state.chart_locked            = False

                st.write("✓  Pipeline complete")
                status_widget.update(
                    label=f"Analysis complete — {st.session_state.pipeline_execution_time}s",
                    state="complete", expanded=False,
                )
                st.rerun()

            except Exception as err:
                status_widget.update(label="Pipeline error", state="error", expanded=True)
                st.error(f"**Pipeline failed:** {err}")


# =====================================================================
# RESULTS WORKSPACE
# =====================================================================
if st.session_state.transcript:
    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
    st.markdown('<div class="section-label">Clinical Intelligence Output</div>', unsafe_allow_html=True)

    classification = st.session_state.classification
    urgency   = str(classification.get("urgency_tier", "MEDIUM")).upper()
    trigger   = str(classification.get("primary_clinical_trigger", ""))
    n_signals = len(st.session_state.salience_map)
    n_flags   = len(st.session_state.flags)
    elapsed   = st.session_state.pipeline_execution_time
    if urgency not in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
        urgency = "MEDIUM"

    st.markdown(f"""
    <div class="urgency-bar {urgency}">
      <div>
        <div class="urgency-label">{urgency} Priority</div>
        <div class="urgency-text">{trigger}</div>
      </div>
      <div class="urgency-metrics">
        <span class="metric-chip"><span class="chip-label">Signals</span>{n_signals}</span>
        <span class="metric-chip"><span class="chip-label">Flags</span>{n_flags}</span>
        <span class="metric-chip"><span class="chip-label">Time</span>{elapsed}s</span>
      </div>
    </div>
    """, unsafe_allow_html=True)

    output_tabs = st.tabs([
        "Clinical Signals", "Safety Flags", "Next Steps", "SOAP Note", "Explainability",
    ])

    # Tab 1 — Clinical Signals
with output_tabs[0]:
    if st.session_state.salience_map:
        for item in sorted(st.session_state.salience_map,
                           key=lambda x: x.get("salience_score", 0), reverse=True):
            score    = float(item.get("salience_score", 0.0))
            entity   = str(item.get("entity", ""))
            category = str(item.get("category", ""))
            pct      = int(score * 100)
            if score >= 0.85:   ring_cls, bc = "score-critical", "var(--tier-critical)"
            elif score >= 0.70: ring_cls, bc = "score-high",     "var(--tier-high)"
            elif score >= 0.50: ring_cls, bc = "score-medium",   "var(--tier-medium)"
            else:               ring_cls, bc = "score-low",      "var(--tier-low)"
            st.markdown(f"""
            <div class="signal-row">
              <div class="signal-score-ring {ring_cls}">{pct}</div>
              <div class="signal-body">
                <div class="signal-entity">{entity}</div>
                <span class="signal-category-chip">{category}</span>
                <div class="signal-bar-track" style="margin-top:8px">
                  <div class="signal-bar-fill" style="width:{pct}%;background:{bc}"></div>
                </div>
              </div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.markdown('<div class="empty-state"><div class="empty-state-icon">◎</div><div class="empty-state-title">No signals extracted</div></div>', unsafe_allow_html=True)    # Tab 2 — Safety Flags
    with output_tabs[1]:
        if st.session_state.flags:
            for alert in st.session_state.flags:
                st.markdown(f'<div class="flag-item"><div class="flag-icon">⚑</div><div>{alert}</div></div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="empty-state"><div class="empty-state-icon">✓</div><div class="empty-state-title">No safety flags raised</div><div class="empty-state-body">All clinical safety parameters cleared.</div></div>', unsafe_allow_html=True)

    # Tab 3 — Next Steps
    with output_tabs[2]:
        if st.session_state.next_steps:
            for idx, step in enumerate(st.session_state.next_steps, 1):
                st.markdown(f'<div class="step-item"><div class="step-num">{idx}</div><div>{step}</div></div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="empty-state"><div class="empty-state-title">No next steps generated</div></div>', unsafe_allow_html=True)

    # Tab 4 — SOAP Note
with output_tabs[3]:

    # Tab 5 — Explainability
    with output_tabs[4]:
        if st.session_state.salience_map:
            for idx, item in enumerate(sorted(st.session_state.salience_map,
                                              key=lambda x: x.get("salience_score", 0), reverse=True), 1):
                score    = float(item.get("salience_score", 0.0))
                entity   = str(item.get("entity", ""))
                reason   = str(item.get("reasoning_context", ""))
                category = str(item.get("category", ""))
                pct      = int(score * 100)
                sc = ("var(--tier-critical)" if score >= 0.85
                      else "var(--tier-high)"   if score >= 0.70
                      else "var(--tier-medium)"  if score >= 0.50
                      else "var(--tier-low)")
                st.markdown(f"""
                <div class="signal-row" style="padding:11px 6px">
                  <div style="flex-shrink:0;width:26px;font-size:10.5px;font-family:var(--font-mono);color:var(--text-muted);text-align:right;padding-top:2px">{idx:02d}</div>
                  <div class="signal-body">
                    <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">
                      <span class="signal-entity">{entity}</span>
                      <span class="signal-category-chip">{category}</span>
                      <span style="margin-left:auto;font-size:11.5px;font-weight:700;font-family:var(--font-mono);color:{sc}">{pct}%</span>
                    </div>
                    <div class="signal-reasoning">{reason}</div>
                    <div class="signal-bar-track" style="margin-top:8px">
                      <div class="signal-bar-fill" style="width:{pct}%;background:{sc}"></div>
                    </div>
                  </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.markdown('<div class="empty-state"><div class="empty-state-title">No reasoning data available</div></div>', unsafe_allow_html=True)
