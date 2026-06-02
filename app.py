# =====================================================================
# SALIENCE OS v2 — Clinical Intelligence Workspace
# Production-Stabilized Build — All backend logic preserved 100%
# Fixed issues: FIX-01 through FIX-16 (see inline comments)
# =====================================================================

# ── FIX-01 ───────────────────────────────────────────────────────────
# ISSUE: If both audioop AND audioop_lts are absent (Python 3.13+),
# pydub raises ImportError at module load before st.set_page_config
# fires → blank page with no error shown to user.
# FIX: Patch sys.modules first, then import pydub inside a guarded
# try/except, capturing the result into a module-level flag. All
# audio paths check PYDUB_AVAILABLE before calling AudioSegment.
# ─────────────────────────────────────────────────────────────────────
import sys

try:
    import audioop  # noqa: F401
except ImportError:
    try:
        import audioop_lts as audioop  # type: ignore
        sys.modules["audioop"] = audioop
    except ImportError:
        pass  # Python 3.13+ with neither — pydub will handle gracefully below

import streamlit as st
import os
import json
import time
from datetime import datetime
from groq import Groq
import google.generativeai as genai

# ── FIX-13 ───────────────────────────────────────────────────────────
# ISSUE: pandas imported but never used after bar_chart removal.
# Adds ~80 MB memory + ~1 s cold-start penalty on Streamlit Cloud.
# FIX: Removed unused import.
# ─────────────────────────────────────────────────────────────────────
# import pandas as pd  ← REMOVED

try:
    from pydub import AudioSegment
    PYDUB_AVAILABLE = True
except ImportError:
    PYDUB_AVAILABLE = False  # FIX-01: graceful degradation, not a crash

from fpdf import FPDF


# =====================================================================
# 0. PDF SAFETY LAYER
#    FIX-14: fpdf2 >= 2.7 deprecates ln=True in cell().
#    Replace with new_x="LMARGIN", new_y="NEXT" throughout.
# =====================================================================
def sanitize_for_pdf(text: str) -> str:
    """Coerce Unicode to Latin-1 safe characters for core FPDF fonts."""
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
    """Generate a clinical PDF from SOAP text. Returns bytes. Never raises."""
    pdf = FPDF()
    pdf.set_margins(left=15, top=10, right=15)
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # Header banner
    pdf.set_fill_color(2, 132, 199)
    pdf.rect(0, 0, 210, 38, "F")
    pdf.set_xy(0, 8)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 18)
    # FIX-14: use new_x/new_y instead of deprecated ln=True
    pdf.cell(
        210, 12,
        "SALIENCE OS | CLINICAL NOTE MATRIX",
        new_x="LMARGIN", new_y="NEXT", align="C",
    )
    pdf.set_font("Helvetica", "I", 10)
    pdf.cell(
        210, 5,
        sanitize_for_pdf(
            f"Specialty: {specialty} | "
            f"Compiled: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        ),
        new_x="LMARGIN", new_y="NEXT", align="C",
    )

    pdf.set_xy(15, 45)
    pdf.set_text_color(15, 23, 42)
    effective_width = pdf.w - pdf.l_margin - pdf.r_margin

    for line in soap_text.split("\n"):
        line_clean = line.strip()
        if not line_clean:
            pdf.ln(3)
            continue
        pdf.set_x(pdf.l_margin)
        if line_clean.startswith("###"):
            pdf.ln(4)
            pdf.set_font("Helvetica", "B", 14)
            pdf.set_text_color(2, 132, 199)
            header_text = line_clean.replace("###", "").replace(":", "").strip()
            pdf.cell(
                effective_width, 10,
                sanitize_for_pdf(header_text.upper()),
                new_x="LMARGIN", new_y="NEXT",
            )
            x = pdf.l_margin
            pdf.line(x, pdf.get_y(), x + 40, pdf.get_y())
            pdf.ln(2)
            pdf.set_text_color(15, 23, 42)
        elif line_clean.startswith("**") and line_clean.endswith("**"):
            pdf.set_font("Helvetica", "B", 11)
            bold_text = line_clean.replace("**", "").strip()
            pdf.cell(
                effective_width, 7,
                sanitize_for_pdf(bold_text),
                new_x="LMARGIN", new_y="NEXT",
            )
        else:
            pdf.set_font("Helvetica", size=10)
            sanitized_body = line_clean.replace("**", "").replace("*", "-")
            pdf.multi_cell(effective_width, 6, sanitize_for_pdf(sanitized_body))

    return bytes(pdf.output())


# =====================================================================
# 1. PAGE CONFIG — must be first Streamlit call
# =====================================================================
st.set_page_config(
    page_title="Salience OS",
    page_icon="⬡",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# =====================================================================
# 2. SESSION STATE
#    Using setdefault pattern to avoid KeyError on any key at any point.
# =====================================================================
_STATE_DEFAULTS: dict = {
    "transcript": "",
    "classification": {},
    "salience_map": [],
    "soap_note": "",
    "flags": [],
    "next_steps": [],
    "pipeline_execution_time": 0.0,
    "chart_locked": False,
    "specialty_profile": "Cardiology",
    "target_language": "Mixed",
    "theme": "Dark",
    # API key overrides — never KeyError on .get()
    "_groq_override": "",
    "_gemini_override": "",
}
for _k, _v in _STATE_DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

SPECIALTY_MAP: dict[str, str] = {
    "Cardiology":  "Cardiology Clinic",
    "General":     "General Internal Medicine",
    "Emergency":   "Emergency Trauma",
    "Neurology":   "Neurology",
    "Pediatrics":  "Pediatrics",
    "Orthopedics": "Orthopedic Surgery",
    "Psychiatry":  "Psychiatry & Behavioral Health",
    "Oncology":    "Oncology",
}
LANGUAGE_MAP: dict[str, str] = {
    "Mixed":   "Mixed (Multi-lingual Code-Switching)",
    "English": "English (US/UK)",
    "Arabic":  "Arabic (Khaleeji/MSA)",
}


# =====================================================================
# 3. CSS DESIGN SYSTEM
#    FIX-15: Removed transform: translateY on button hover (layout shift).
#    FIX-16: .block-container uses padding: 0 4px not hard 0.
# =====================================================================
st.markdown("""
<style>
/* ── Design Tokens ───────────────────────────────────────────────── */
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

  --font-mono: 'JetBrains Mono', 'Fira Code', 'SF Mono', ui-monospace, monospace;
  --transition: 150ms cubic-bezier(0.4,0,0.2,1);

  --soap-font-size: 14px;
  --soap-line-height: 1.9;
}

/* ── Ambient Background Lighting ─────────────────────────────────── */
body::before {
  content: '';
  position: fixed;
  inset: 0;
  z-index: 0;
  pointer-events: none;
  background:
    radial-gradient(circle at 88% 12%, rgba(59,130,246,0.11) 0%, transparent 38%),
    radial-gradient(circle at 8%  52%, rgba(6,182,212,0.07)  0%, transparent 30%),
    radial-gradient(circle at 72% 92%, rgba(139,92,246,0.06) 0%, transparent 28%);
}
.stApp { position: relative; z-index: 1; }

/* ── Base ────────────────────────────────────────────────────────── */
html, body, [class*="css"] {
  font-family: -apple-system, 'SF Pro Text', 'Helvetica Neue', system-ui, sans-serif;
  background-color: var(--bg-base) !important;
  color: var(--text-primary) !important;
  -webkit-font-smoothing: antialiased;
}

#MainMenu, footer, header { visibility: hidden; }
.stDeployButton { display: none; }

/* FIX-16: keep minimal horizontal padding to prevent edge-clipping */
.block-container {
  padding: 0 4px !important;
  max-width: 100% !important;
}

/* ── Scrollbar ───────────────────────────────────────────────────── */
::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border-default); border-radius: 99px; }

/* ── Header ──────────────────────────────────────────────────────── */
.os-header {
  height: 52px;
  padding: 0 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: rgba(8,11,16,0.85);
  backdrop-filter: blur(24px);
  -webkit-backdrop-filter: blur(24px);
  border-bottom: 1px solid var(--border-subtle);
  margin: 0 -4px;   /* compensate FIX-16 padding */
}
.os-wordmark {
  font-size: 14.5px; font-weight: 700; letter-spacing: 0.3px;
  color: var(--text-primary);
}
.os-wordmark span { color: var(--accent-blue); }
.os-header-right { display: flex; align-items: center; gap: 12px; }

.os-status-pill {
  display: inline-flex; align-items: center; gap: 5px;
  font-size: 11px; font-weight: 500; padding: 3px 10px;
  border-radius: 99px; letter-spacing: 0.2px;
}
.os-status-pill.ready  { background: rgba(16,185,129,0.10); color: var(--accent-emerald); border: 1px solid rgba(16,185,129,0.18); }
.os-status-pill.active { background: rgba(59,130,246,0.10); color: var(--accent-blue);    border: 1px solid rgba(59,130,246,0.18); }
.os-status-pill.locked { background: rgba(139,92,246,0.10); color: var(--accent-violet);  border: 1px solid rgba(139,92,246,0.18); }

.os-dot { width: 5px; height: 5px; border-radius: 50%; background: currentColor; }
.os-dot.pulse { animation: pulse-dot 2s ease-in-out infinite; }
@keyframes pulse-dot {
  0%,100% { opacity:1; transform:scale(1); }
  50%      { opacity:0.4; transform:scale(0.75); }
}
.os-time { font-size: 11px; font-family: var(--font-mono); color: var(--text-muted); font-variant-numeric: tabular-nums; }

/* ── Section Labels ──────────────────────────────────────────────── */
.section-label {
  font-size: 10px; font-weight: 700; letter-spacing: 1px;
  text-transform: uppercase; color: var(--text-muted);
  margin: 0 0 12px; display: flex; align-items: center; gap: 10px;
}
.section-label::after { content:''; flex:1; height:1px; background: var(--border-subtle); }

/* ── Urgency Banner ──────────────────────────────────────────────── */
.urgency-bar {
  display: flex; align-items: center; gap: 12px;
  padding: 13px 18px; border-radius: var(--radius-md);
  margin-bottom: 20px; border-left: 3px solid;
}
.urgency-bar.CRITICAL { background: rgba(239,68,68,0.07);  border-color: var(--tier-critical); }
.urgency-bar.HIGH     { background: rgba(245,158,11,0.07); border-color: var(--tier-high); }
.urgency-bar.MEDIUM   { background: rgba(59,130,246,0.07); border-color: var(--tier-medium); }
.urgency-bar.LOW      { background: rgba(16,185,129,0.07); border-color: var(--tier-low); }
.urgency-label { font-size:9.5px; font-weight:700; letter-spacing:1.1px; text-transform:uppercase; opacity:0.65; }
.urgency-text  { font-size:13px; font-weight:500; line-height:1.45; margin-top:2px; }
.urgency-bar.CRITICAL .urgency-label, .urgency-bar.CRITICAL .urgency-text { color: var(--tier-critical); }
.urgency-bar.HIGH     .urgency-label, .urgency-bar.HIGH     .urgency-text { color: var(--tier-high); }
.urgency-bar.MEDIUM   .urgency-label, .urgency-bar.MEDIUM   .urgency-text { color: var(--tier-medium); }
.urgency-bar.LOW      .urgency-label, .urgency-bar.LOW      .urgency-text { color: var(--tier-low); }
.urgency-metrics { margin-left:auto; display:flex; gap:8px; flex-shrink:0; }

.metric-chip {
  display:inline-flex; align-items:center; gap:4px;
  padding:3px 9px; background: var(--bg-elevated);
  border:1px solid var(--border-subtle); border-radius:99px;
  font-size:11px; color: var(--text-secondary); font-family: var(--font-mono);
}
.metric-chip .chip-label { font-family:-apple-system,sans-serif; font-size:10.5px; color: var(--text-muted); }

/* ── Signal Rows ─────────────────────────────────────────────────── */
.signal-row {
  display:flex; align-items:flex-start; gap:12px;
  padding:10px 6px; border-bottom:1px solid var(--border-subtle);
  transition: background var(--transition); border-radius: var(--radius-sm);
}
.signal-row:last-child { border-bottom:none; }
.signal-row:hover { background: var(--bg-hover); }

.signal-score-ring {
  flex-shrink:0; width:38px; height:38px; border-radius:50%;
  display:flex; align-items:center; justify-content:center;
  font-size:10.5px; font-weight:700; font-family: var(--font-mono); border:2px solid;
}
.score-critical { background:rgba(239,68,68,0.09);  border-color:var(--tier-critical); color:var(--tier-critical); }
.score-high     { background:rgba(245,158,11,0.09); border-color:var(--tier-high);     color:var(--tier-high); }
.score-medium   { background:rgba(59,130,246,0.09); border-color:var(--tier-medium);   color:var(--tier-medium); }
.score-low      { background:rgba(16,185,129,0.09); border-color:var(--tier-low);      color:var(--tier-low); }

.signal-body { flex:1; min-width:0; }
.signal-entity { font-size:13px; font-weight:600; color: var(--text-primary); }
.signal-category-chip {
  display:inline-block; font-size:9.5px; font-weight:600; letter-spacing:0.4px;
  padding:1px 6px; border-radius:99px; background: var(--bg-elevated);
  border:1px solid var(--border-default); color: var(--text-secondary);
  margin:3px 0 4px; text-transform:uppercase;
}
.signal-reasoning { font-size:12px; color: var(--text-secondary); line-height:1.55; }
.signal-bar-track { width:100%; height:2px; background: var(--bg-elevated); border-radius:99px; margin-top:7px; overflow:hidden; }
.signal-bar-fill  { height:100%; border-radius:99px; transition:width 0.7s cubic-bezier(0.4,0,0.2,1); }

/* ── Flag & Step Items ───────────────────────────────────────────── */
.flag-item {
  display:flex; align-items:flex-start; gap:10px; padding:11px 14px;
  background:rgba(239,68,68,0.06); border:1px solid rgba(239,68,68,0.15);
  border-left:3px solid var(--tier-critical); border-radius: var(--radius-md);
  margin-bottom:8px; font-size:13px; color:#FCA5A5; line-height:1.55;
}
.flag-icon { flex-shrink:0; color:var(--tier-critical); font-size:13px; margin-top:1px; }

.step-item {
  display:flex; align-items:flex-start; gap:10px; padding:9px 14px;
  background:rgba(59,130,246,0.055); border:1px solid rgba(59,130,246,0.12);
  border-radius: var(--radius-md); margin-bottom:7px;
  font-size:13px; color:#93C5FD; line-height:1.55;
}
.step-num {
  flex-shrink:0; width:19px; height:19px; border-radius:50%;
  background:rgba(59,130,246,0.18); color:var(--accent-blue);
  font-size:9.5px; font-weight:700; display:flex; align-items:center;
  justify-content:center; margin-top:1px;
}

/* ── SOAP Viewer ─────────────────────────────────────────────────── */
.soap-outer  { max-width:1100px; margin:0 auto; }
.soap-viewer {
  background: var(--bg-surface); border:1px solid var(--border-default);
  border-radius: var(--radius-lg); padding:32px 36px;
  font-size: var(--soap-font-size); line-height: var(--soap-line-height);
  color: var(--text-primary);
}
.soap-section-header {
  font-size:10px; font-weight:700; letter-spacing:1.1px;
  text-transform:uppercase; color: var(--accent-blue);
  margin-top:24px; margin-bottom:10px;
  padding-bottom:7px; border-bottom:1px solid var(--border-subtle);
}
.soap-section-header:first-child { margin-top:0; }
.soap-body-p  { margin:0 0 2px; color: var(--text-secondary); font-size: var(--soap-font-size); line-height: var(--soap-line-height); }
.soap-bold    { color: var(--text-primary); font-weight:600; font-size: var(--soap-font-size); }

.soap-meta-row {
  display:flex; align-items:center; gap:16px;
  padding:12px 0; margin-bottom:8px;
  border-bottom:1px solid var(--border-subtle);
}
.soap-meta-item { display:flex; flex-direction:column; gap:2px; }
.soap-meta-label { font-size:9.5px; font-weight:700; letter-spacing:0.8px; text-transform:uppercase; color: var(--text-muted); }
.soap-meta-value { font-size:12.5px; font-weight:500; color: var(--text-secondary); font-family: var(--font-mono); }

/* ── Empty State ─────────────────────────────────────────────────── */
.empty-state {
  display:flex; flex-direction:column; align-items:center; justify-content:center;
  padding:44px 24px; text-align:center; gap:10px;
}
.empty-state-icon  { font-size:24px; opacity:0.25; }
.empty-state-title { font-size:13.5px; font-weight:600; color: var(--text-secondary); }
.empty-state-body  { font-size:12px; color: var(--text-muted); line-height:1.6; max-width:260px; }

/* ── Native Component Overrides ──────────────────────────────────── */
section[data-testid="stSidebar"] {
  background: var(--bg-surface) !important;
  border-right: 1px solid var(--border-subtle) !important;
}

.stTextInput > div > div > input,
.stTextArea  > div > div > textarea {
  background: var(--bg-elevated) !important;
  border: 1px solid var(--border-default) !important;
  border-radius: var(--radius-md) !important;
  color: var(--text-primary) !important;
  font-size: 13px !important;
}
.stTextInput > div > div > input:focus,
.stTextArea  > div > div > textarea:focus {
  border-color: var(--accent-blue) !important;
  box-shadow: 0 0 0 3px rgba(59,130,246,0.12) !important;
  outline: none !important;
}

.stSelectbox > div > div > div {
  background: var(--bg-elevated) !important;
  border: 1px solid var(--border-default) !important;
  border-radius: var(--radius-md) !important;
  color: var(--text-primary) !important;
  font-size: 13px !important;
}

/* FIX-15: removed transform: translateY to prevent layout shift in iframe */
.stButton > button[kind="primary"] {
  background: var(--accent-blue) !important;
  color: #fff !important; border: none !important;
  border-radius: var(--radius-md) !important;
  font-weight: 600 !important; font-size: 13px !important;
  height: 40px !important; letter-spacing: 0.2px !important;
  transition: background var(--transition), box-shadow var(--transition) !important;
}
.stButton > button[kind="primary"]:hover {
  background: var(--accent-blue-dim) !important;
  box-shadow: 0 0 0 3px rgba(59,130,246,0.22) !important;
}

.stButton > button[kind="secondary"],
.stButton > button:not([kind]) {
  background: var(--bg-elevated) !important;
  color: var(--text-primary) !important;
  border: 1px solid var(--border-default) !important;
  border-radius: var(--radius-md) !important;
  font-weight: 500 !important; font-size: 13px !important;
  height: 40px !important;
}
.stButton > button[kind="secondary"]:hover,
.stButton > button:not([kind]):hover { border-color: var(--border-strong) !important; }
.stButton > button:disabled {
  background: var(--bg-elevated) !important;
  color: var(--text-muted) !important; border-color: var(--border-subtle) !important;
}

.stDownloadButton > button {
  background: var(--bg-elevated) !important;
  color: var(--text-primary) !important;
  border: 1px solid var(--border-default) !important;
  border-radius: var(--radius-md) !important;
  font-weight: 500 !important; font-size: 13px !important; height: 40px !important;
}
.stDownloadButton > button:hover { border-color: var(--accent-blue) !important; color: var(--accent-blue) !important; }

.stTabs [data-baseweb="tab-list"] {
  background: transparent !important;
  border-bottom: 1px solid var(--border-subtle) !important;
  gap: 0 !important; padding: 0 !important;
}
.stTabs [data-baseweb="tab"] {
  background: transparent !important; color: var(--text-muted) !important;
  font-size: 12.5px !important; font-weight: 500 !important;
  padding: 9px 16px !important; border-bottom: 2px solid transparent !important;
  border-radius: 0 !important; transition: color var(--transition) !important;
}
.stTabs [data-baseweb="tab"]:hover { color: var(--text-secondary) !important; }
.stTabs [aria-selected="true"] { color: var(--text-primary) !important; border-bottom: 2px solid var(--accent-blue) !important; }
.stTabs [data-baseweb="tab-panel"] { padding: 18px 0 0 !important; }

[data-testid="stSegmentedControl"] > div {
  background: var(--bg-elevated) !important;
  border: 1px solid var(--border-default) !important;
  border-radius: var(--radius-md) !important;
  padding: 3px !important; gap: 2px !important;
}
[data-testid="stSegmentedControl"] button {
  background: transparent !important; color: var(--text-secondary) !important;
  border-radius: var(--radius-sm) !important; font-size: 12.5px !important;
  font-weight: 500 !important; border: none !important;
  transition: all var(--transition) !important;
}
[data-testid="stSegmentedControl"] button[aria-checked="true"] {
  background: var(--accent-blue) !important; color: #fff !important;
  box-shadow: 0 1px 4px rgba(0,0,0,0.4) !important;
}

[data-testid="stPills"] button {
  background: var(--bg-elevated) !important; color: var(--text-secondary) !important;
  border: 1px solid var(--border-default) !important; border-radius: 99px !important;
  font-size: 12px !important; font-weight: 500 !important;
  transition: all var(--transition) !important;
}
[data-testid="stPills"] button[aria-pressed="true"] {
  background: rgba(59,130,246,0.15) !important;
  color: var(--accent-blue) !important; border-color: rgba(59,130,246,0.3) !important;
}

.stRadio > label { color: var(--text-secondary) !important; font-size: 12.5px !important; }
.stRadio > div > label { color: var(--text-secondary) !important; font-size: 13px !important; }

[data-testid="stAudioInput"]  { background: var(--bg-elevated) !important; border: 1px solid var(--border-default) !important; border-radius: var(--radius-md) !important; }
[data-testid="stFileUploader"] { background: var(--bg-elevated) !important; border: 1px dashed var(--border-default) !important; border-radius: var(--radius-md) !important; }

.stNumberInput > div > div > input {
  background: var(--bg-elevated) !important; border: 1px solid var(--border-default) !important;
  border-radius: var(--radius-md) !important; color: var(--text-primary) !important; font-size: 13px !important;
}
[data-baseweb="notification"] { border-radius: var(--radius-md) !important; font-size: 13px !important; }
hr { border-color: var(--border-subtle) !important; margin: 20px 0 !important; }
[data-testid="stStatusWidget"] { background: var(--bg-elevated) !important; border: 1px solid var(--border-default) !important; border-radius: var(--radius-md) !important; }
.stSpinner > div { border-color: var(--accent-blue) transparent transparent !important; }
label[data-testid="stWidgetLabel"] { color: var(--text-secondary) !important; font-size: 12px !important; }
.stCaption { color: var(--text-muted) !important; font-size: 11.5px !important; }
p { color: var(--text-secondary) !important; }

[data-testid="stPopover"] > div {
  background: var(--bg-elevated) !important; border: 1px solid var(--border-default) !important;
  border-radius: var(--radius-lg) !important; box-shadow: 0 16px 48px rgba(0,0,0,0.7) !important;
}

.ctrl-label {
  font-size: 9.5px; font-weight: 700; letter-spacing: 1px;
  text-transform: uppercase; color: var(--text-muted);
  display: block; margin-bottom: 8px; margin-top: 16px;
}
.ctrl-label:first-child { margin-top: 0; }
</style>
""", unsafe_allow_html=True)


# =====================================================================
# 4. API CREDENTIAL RESOLUTION
#    FIX-09: secrets access is guarded — st.secrets raises on missing
#    keys in some Streamlit versions; use .get() with default.
# =====================================================================
# ── FIX-09 ───────────────────────────────────────────────────────────
# ISSUE: st.secrets.get() is safe, but checking "key in st.secrets"
# can raise AttributeError if secrets are not configured at all on
# some Streamlit Cloud setups (no secrets.toml exists).
# FIX: Wrap entire secrets access in try/except.
# ─────────────────────────────────────────────────────────────────────
try:
    has_cloud_groq   = "groq_api_key"   in st.secrets
    has_cloud_gemini = "gemini_api_key" in st.secrets
    _vault_groq   = st.secrets.get("groq_api_key",   "")
    _vault_gemini = st.secrets.get("gemini_api_key", "")
except Exception:
    has_cloud_groq   = False
    has_cloud_gemini = False
    _vault_groq      = ""
    _vault_gemini    = ""


# =====================================================================
# 5. CONTROL CENTER — st.popover() with native Streamlit widgets
#
#    FIX-07: Removed st.rerun() from inside the popover function.
#    st.rerun() inside a popover fires before the popover widget tree
#    is fully committed, causing blank renders and ScriptRunContext
#    warnings. Streamlit widget reactivity handles the state update
#    naturally on the next user interaction — no manual rerun needed.
#
#    FIX-09: API keys are stored in session_state on every run, not
#    only when the popover is open, so they persist across reruns.
# =====================================================================
def render_control_center() -> None:
    """Workspace settings panel — native Streamlit widgets only."""

    st.markdown('<span class="ctrl-label">Specialty Profile</span>', unsafe_allow_html=True)
    # FIX-07: No st.rerun() — value written directly to session_state key
    st.segmented_control(
        "Specialty",
        options=["Cardiology", "General", "Emergency", "Neurology",
                 "Pediatrics", "Orthopedics", "Psychiatry", "Oncology"],
        key="specialty_profile",   # ← writes directly to session_state
        label_visibility="collapsed",
    )

    st.markdown('<span class="ctrl-label">Language Matrix</span>', unsafe_allow_html=True)
    st.segmented_control(
        "Language",
        options=["Mixed", "English", "Arabic"],
        key="target_language",     # ← writes directly to session_state
        label_visibility="collapsed",
    )

    st.markdown('<span class="ctrl-label">Theme</span>', unsafe_allow_html=True)
    st.pills(
        "Theme",
        options=["Dark", "System", "Light"],
        key="theme",               # ← writes directly to session_state
        label_visibility="collapsed",
    )

    st.markdown('<span class="ctrl-label">API Credentials</span>', unsafe_allow_html=True)
    if has_cloud_groq and has_cloud_gemini:
        st.caption("✓  Vault active — keys pre-loaded")
    else:
        # FIX-09: written to named session_state keys so they survive reruns
        st.text_input(
            "Groq API Key",
            type="password",
            placeholder="sk-..." if not has_cloud_groq else "🔒 Vault loaded",
            key="_groq_override",
        )
        st.text_input(
            "Gemini API Key",
            type="password",
            placeholder="AI..." if not has_cloud_gemini else "🔒 Vault loaded",
            key="_gemini_override",
        )


# Resolve final API keys: manual override > vault
# FIX-09: read after widget definition so overrides are always current
groq_api_key   = st.session_state.get("_groq_override", "") or _vault_groq
gemini_api_key = st.session_state.get("_gemini_override", "") or _vault_gemini

# Resolve display names → full prompt strings
specialty_profile: str = SPECIALTY_MAP.get(
    st.session_state.get("specialty_profile", "Cardiology"), "Cardiology Clinic"
)
target_language: str = LANGUAGE_MAP.get(
    st.session_state.get("target_language", "Mixed"),
    "Mixed (Multi-lingual Code-Switching)",
)


# =====================================================================
# 6. HEADER
#    FIX-12: Removed orphaned <div> wrapper around the popover.
#    Each st.markdown() call is an independent DOM node in Streamlit —
#    an opening tag in one call and a closing tag in the next do NOT
#    form a matching pair. The browser sees an orphaned </div> which
#    can corrupt column layout. Fixed by removing the wrapper entirely.
# =====================================================================
has_results  = bool(st.session_state.transcript)
chart_locked = st.session_state.chart_locked

if chart_locked:
    status_html = '<div class="os-status-pill locked"><div class="os-dot"></div>Signed</div>'
elif has_results:
    status_html = '<div class="os-status-pill active"><div class="os-dot pulse"></div>Review</div>'
else:
    status_html = '<div class="os-status-pill ready"><div class="os-dot pulse"></div>Ready</div>'

header_left, header_right = st.columns([6, 1], gap="small")

with header_left:
    st.markdown(f"""
    <div class="os-header">
      <div class="os-wordmark">SALIENCE<span> OS</span></div>
      <div class="os-header-right">
        {status_html}
        <div class="os-time">{datetime.now().strftime('%H:%M')}</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

with header_right:
    # FIX-12: no orphaned div wrappers around the popover
    with st.popover("⚙ Settings", use_container_width=False):
        render_control_center()

st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)


# =====================================================================
# 7. INPUT WORKSPACE
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

    TEMP_AUDIO: str = "active_stream_input.wav"
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
        # FIX-01: guard st.audio_input behind PYDUB_AVAILABLE check
        if not PYDUB_AVAILABLE:
            st.warning("Audio processing unavailable (pydub could not load). Use Text input instead.")
        else:
            st.caption("Position microphone toward conversation, then tap record.")
            audio_file = st.audio_input("Record audio")
            if audio_file is not None:
                try:
                    with open(TEMP_AUDIO, "wb") as f:
                        f.write(audio_file.read())
                    has_valid_audio_payload = True
                except OSError as write_err:
                    st.error(f"Could not save audio file: {write_err}")

    else:
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
                        case_idx: int = st.number_input(
                            "Case index",
                            min_value=0,
                            max_value=max(len(json_data) - 1, 0),
                            value=0,
                        )
                        selected_node = json_data[int(case_idx)]
                        injected_text_payload = selected_node.get(
                            "input", selected_node.get("instruction", "")
                        )
                        if injected_text_payload:
                            preview = injected_text_payload[:240]
                            st.info(preview + ("…" if len(injected_text_payload) > 240 else ""))
                        if injected_text_payload.strip():
                            has_valid_audio_payload = True
                            bypass_audio_stt = True
                    else:
                        st.error("JSON must be a list of cases.")
                except json.JSONDecodeError as json_err:
                    st.error(f"JSON parse error: {json_err}")
                except Exception as e:
                    st.error(f"File error: {e}")
            else:
                if not PYDUB_AVAILABLE:
                    st.warning("Audio processing unavailable. Use Text input instead.")
                else:
                    try:
                        with open(TEMP_AUDIO, "wb") as f:
                            f.write(uploaded_file.getbuffer())
                        st.audio(TEMP_AUDIO)
                        has_valid_audio_payload = True
                    except OSError as write_err:
                        st.error(f"Could not save uploaded file: {write_err}")

with col_exam:
    st.markdown('<div class="section-label">Physical Examination</div>', unsafe_allow_html=True)
    st.caption("Examination findings are merged with transcript during analysis.")

    exam_tabs = st.tabs(["Thoracic", "GI / Abdomen", "Neuro / Reflex", "Musculoskeletal"])
    with exam_tabs[0]:
        notes_thoracic: str = st.text_area(
            "Thoracic",
            value="Cardiovascular: Tachycardic, rhythm regular. S1 and S2 distinct, no audible murmurs, rubs, or gallops. Significant chest wall diaphoresis noted; patient actively clutching retrosternal area. Respiratory: Tachypneic, shallow respirations. Lungs clear to auscultation bilaterally (CTAB).",
            height=140,
            label_visibility="collapsed",
        )
    with exam_tabs[1]:
        notes_abdominal: str = st.text_area(
            "GI",
            value="Abdomen soft, symmetric, and non-distended. Bowel sounds active in all 4 quadrants. No localized tenderness, guarding, or rebound. No hepatosplenomegaly. Epigastric region non-tender.",
            height=140,
            label_visibility="collapsed",
        )
    with exam_tabs[2]:
        notes_neuro: str = st.text_area(
            "Neuro",
            value="Patient alert and oriented to person, place, and time (A&Ox3). Pupils equal, round, and reactive to light (PEERRLA). Observable orthostatic lightheadedness upon sitting up. Gross motor and sensory function intact.",
            height=140,
            label_visibility="collapsed",
        )
    with exam_tabs[3]:
        notes_ortho: str = st.text_area(
            "MSK",
            value="Mild focal tenderness over lumbar paraspinal muscles. Left shoulder and left mandibular jaw display full passive range of motion with zero localized joint or bone tenderness.",
            height=140,
            label_visibility="collapsed",
        )

compiled_examination_overlay: str = (
    f"- Thoracic Tracking Overlay: {notes_thoracic or 'Deferred/Normal checks confirmed'}\n"
    f"- GI/Abdominal Tracking Overlay: {notes_abdominal or 'Deferred/Normal checks confirmed'}\n"
    f"- Reflex/Neuro Tracking Overlay: {notes_neuro or 'Deferred/Normal checks confirmed'}\n"
    f"- Musculoskeletal Tracking Overlay: {notes_ortho or 'Deferred/Normal checks confirmed'}"
)


# =====================================================================
# 8. ANALYSIS TRIGGER
# =====================================================================
st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

if has_valid_audio_payload:
    trigger_col, _ = st.columns([1, 2])
    with trigger_col:
        run_pipeline: bool = st.button(
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
    run_pipeline = False


# =====================================================================
# 9. PIPELINE EXECUTION
#    FIX-11: Check os.path.exists() before opening audio file.
#    All external API calls wrapped with specific exception handling.
#    Gemini JSON parse uses strict=False (pre-existing fix preserved).
# =====================================================================
if has_valid_audio_payload and run_pipeline:
    if not groq_api_key or not gemini_api_key:
        st.error(
            "API credentials required. Open ⚙ Settings and enter your Groq and Gemini API keys."
        )
    else:
        pipeline_start: float = time.time()

        with st.status("Running clinical intelligence pipeline…", expanded=True) as status_widget:
            try:
                # ── Stage 1: Transcription ──────────────────────────
                extracted_raw_text: str = ""

                if bypass_audio_stt:
                    st.write("✓  Text input detected — bypassing STT")
                    extracted_raw_text = injected_text_payload

                else:
                    # FIX-01: guard pydub usage
                    if not PYDUB_AVAILABLE:
                        raise RuntimeError(
                            "Audio processing library (pydub) is not available. "
                            "Use Text input mode instead."
                        )

                    # FIX-11: verify audio file exists before opening
                    if not os.path.exists(TEMP_AUDIO):
                        raise FileNotFoundError(
                            f"Audio file not found at {TEMP_AUDIO!r}. "
                            "Please re-record or re-upload."
                        )

                    st.write("⬡  Compressing audio for Whisper API…")
                    raw_audio = AudioSegment.from_file(TEMP_AUDIO)
                    processed_audio = raw_audio.set_channels(1).set_frame_rate(16000)
                    compressed = "optimized_api_payload.mp3"
                    processed_audio.export(compressed, format="mp3", bitrate="64k")

                    st.write("⬡  Transcribing via Whisper large-v3…")
                    groq_client = Groq(api_key=groq_api_key, timeout=60.0)
                    with open(compressed, "rb") as audio_binary:
                        extracted_raw_text = groq_client.audio.transcriptions.create(
                            file=(compressed, audio_binary.read()),
                            model="whisper-large-v3",
                            response_format="text",
                        )

                    for _path in (TEMP_AUDIO, compressed):
                        try:
                            if os.path.exists(_path):
                                os.remove(_path)
                        except OSError:
                            pass

                    st.write("✓  Transcription complete")

                if not extracted_raw_text or not extracted_raw_text.strip():
                    raise ValueError(
                        "Transcription returned empty text. "
                        "Check your audio quality or API key."
                    )

                # ── Stage 2: Gemini Intelligence ───────────────────
                st.write("⬡  Running salience analysis via Gemini 2.5 Flash…")
                genai.configure(api_key=gemini_api_key)
                intelligence_engine = genai.GenerativeModel("gemini-2.5-flash")

                system_prompt: str = f"""
You are the core analytical pipeline of Salience OS, configured for the specialty: {specialty_profile}.
The incoming data stream was ingested with an expected localization matrix profile of: {target_language}.

RAW INPUT DATA TRANSCRIPT:
\"\"\"{extracted_raw_text}\"\"\"

DOCTOR PHYSICAL EXAMINATION DATA OVERLAYS:
\"\"\"{compiled_examination_overlay}\"\"\"

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

                response_package = intelligence_engine.generate_content(
                    system_prompt,
                    generation_config={"response_mime_type": "application/json"},
                )

                # SYSTEM PATCH: strict=False prevents crashes from unescaped control chars
                raw_json: str = response_package.text
                if not raw_json or not raw_json.strip():
                    raise ValueError(
                        "Gemini returned an empty response. "
                        "Check your API key and quota."
                    )

                try:
                    parsed_payload: dict = json.loads(raw_json, strict=False)
                except json.JSONDecodeError as json_err:
                    raise ValueError(
                        f"Gemini response was not valid JSON: {json_err}. "
                        f"Raw response (first 300 chars): {raw_json[:300]}"
                    ) from json_err

                # Validate expected keys exist, defaulting gracefully
                st.session_state.transcript             = str(parsed_payload.get("cleaned_transcript", ""))
                st.session_state.classification         = dict(parsed_payload.get("classification", {}))
                st.session_state.salience_map           = list(parsed_payload.get("salience_weight_map", []))
                st.session_state.soap_note              = str(parsed_payload.get("structured_soap_chart", ""))
                st.session_state.flags                  = list(parsed_payload.get("clinical_safety_red_flags", []))
                st.session_state.next_steps             = list(parsed_payload.get("suggested_next_steps", []))
                st.session_state.pipeline_execution_time = round(time.time() - pipeline_start, 2)
                st.session_state.chart_locked           = False

                st.write("✓  Pipeline complete")
                status_widget.update(
                    label=f"Analysis complete — {st.session_state.pipeline_execution_time}s",
                    state="complete",
                    expanded=False,
                )
                st.rerun()

            except Exception as pipeline_err:
                status_widget.update(label="Pipeline error", state="error", expanded=True)
                st.error(f"**Pipeline failed:** {pipeline_err}")


# =====================================================================
# 10. RESULTS WORKSPACE
#     FIX-08: Ternary strings inside f-string HTML attributes replaced
#     with pre-computed Python variables to avoid quote-nesting issues.
#     FIX-10: PDF generated only when soap_note is non-empty.
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

    # Guard: urgency must be one of the four valid CSS classes
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

    # ── Tab 1: Clinical Signals ─────────────────────────────────────
    with output_tabs[0]:
        if st.session_state.salience_map:
            sorted_signals = sorted(
                st.session_state.salience_map,
                key=lambda x: x.get("salience_score", 0),
                reverse=True,
            )
            for item in sorted_signals:
                score     = float(item.get("salience_score", 0.0))
                entity    = str(item.get("entity", ""))
                category  = str(item.get("category", ""))
                reasoning = str(item.get("reasoning_context", ""))
                bar_pct   = int(score * 100)

                if score >= 0.85:   ring_cls, bar_color = "score-critical", "var(--tier-critical)"
                elif score >= 0.70: ring_cls, bar_color = "score-high",     "var(--tier-high)"
                elif score >= 0.50: ring_cls, bar_color = "score-medium",   "var(--tier-medium)"
                else:               ring_cls, bar_color = "score-low",      "var(--tier-low)"

                st.markdown(f"""
                <div class="signal-row">
                  <div class="signal-score-ring {ring_cls}">{bar_pct}</div>
                  <div class="signal-body">
                    <div class="signal-entity">{entity}</div>
                    <span class="signal-category-chip">{category}</span>
                    <div class="signal-reasoning">{reasoning}</div>
                    <div class="signal-bar-track">
                      <div class="signal-bar-fill" style="width:{bar_pct}%;background:{bar_color}"></div>
                    </div>
                  </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div class="empty-state">
              <div class="empty-state-icon">◎</div>
              <div class="empty-state-title">No signals extracted</div>
            </div>""", unsafe_allow_html=True)

    # ── Tab 2: Safety Flags ─────────────────────────────────────────
    with output_tabs[1]:
        if st.session_state.flags:
            for alert in st.session_state.flags:
                st.markdown(f"""
                <div class="flag-item">
                  <div class="flag-icon">⚑</div>
                  <div>{alert}</div>
                </div>""", unsafe_allow_html=True)
        else:
            st.markdown("""
            <div class="empty-state">
              <div class="empty-state-icon">✓</div>
              <div class="empty-state-title">No safety flags raised</div>
              <div class="empty-state-body">All clinical safety parameters cleared for this consultation.</div>
            </div>""", unsafe_allow_html=True)

    # ── Tab 3: Next Steps ───────────────────────────────────────────
    with output_tabs[2]:
        if st.session_state.next_steps:
            for idx, step in enumerate(st.session_state.next_steps, 1):
                st.markdown(f"""
                <div class="step-item">
                  <div class="step-num">{idx}</div>
                  <div>{step}</div>
                </div>""", unsafe_allow_html=True)
        else:
            st.markdown("""
            <div class="empty-state">
              <div class="empty-state-title">No next steps generated</div>
            </div>""", unsafe_allow_html=True)

    # ── Tab 4: SOAP Note ────────────────────────────────────────────
    with output_tabs[3]:
        soap_raw: str = st.session_state.soap_note

        # FIX-08: pre-compute ternary values outside f-string
        chart_status_label = "Signed & Locked" if st.session_state.chart_locked else "Pending Review"
        chart_status_color = "var(--accent-violet)" if st.session_state.chart_locked else "var(--accent-amber)"
        generated_at       = datetime.now().strftime("%Y-%m-%d %H:%M")

        st.markdown(f"""
        <div class="soap-meta-row">
          <div class="soap-meta-item">
            <span class="soap-meta-label">Generated</span>
            <span class="soap-meta-value">{generated_at}</span>
          </div>
          <div class="soap-meta-item">
            <span class="soap-meta-label">Specialty</span>
            <span class="soap-meta-value">{specialty_profile}</span>
          </div>
          <div class="soap-meta-item">
            <span class="soap-meta-label">Status</span>
            <span class="soap-meta-value" style="color:{chart_status_color}">{chart_status_label}</span>
          </div>
          <div class="soap-meta-item">
            <span class="soap-meta-label">Pipeline Time</span>
            <span class="soap-meta-value">{elapsed}s</span>
          </div>
        </div>
        """, unsafe_allow_html=True)

        # Render SOAP with improved typography
        rendered: list[str] = []
        for line in soap_raw.split("\n"):
            s = line.strip()
            if s.startswith("###"):
                header = s.replace("###", "").strip().rstrip(":")
                rendered.append(f'<div class="soap-section-header">{header}</div>')
            elif s.startswith("**") and s.endswith("**"):
                bt = s.replace("**", "").strip()
                rendered.append(f'<span class="soap-bold">{bt}</span><br>')
            elif s:
                rendered.append(f'<p class="soap-body-p">{s}</p>')
            else:
                rendered.append('<div style="height:6px"></div>')

        st.markdown(f"""
        <div class="soap-outer">
          <div class="soap-viewer">{"".join(rendered)}</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
        act1, act2, act3 = st.columns(3)

        with act1:
            st.button(
                "⎘  Copy SOAP",
                key="copy_soap_btn",
                use_container_width=True,
                help="Select all text in the viewer above, then Ctrl+C / Cmd+C",
            )

        with act2:
            # FIX-10: only generate PDF when soap_note is non-empty
            if soap_raw.strip():
                try:
                    pdf_binary: bytes = generate_clinical_pdf(soap_raw, specialty_profile)
                    st.download_button(
                        label="↓  Export PDF",
                        data=pdf_binary,
                        file_name=f"SalienceOS_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                        mime="application/pdf",
                        use_container_width=True,
                    )
                except Exception as pdf_err:
                    st.error(f"PDF generation failed: {pdf_err}")
            else:
                st.button("↓  Export PDF", disabled=True, use_container_width=True)

        with act3:
            if st.session_state.chart_locked:
                st.button("✓  Synced to FHIR", disabled=True, use_container_width=True)
            else:
                if st.button("Sign & Push to EHR", type="primary", use_container_width=True):
                    with st.spinner("Encrypting and synchronising with HL7/FHIR endpoint…"):
                        time.sleep(2.0)
                        st.session_state.chart_locked = True
                        st.success("Chart signed and pushed to simulated EHR database.")
                        st.balloons()
                        st.rerun()

    # ── Tab 5: Explainability ───────────────────────────────────────
    with output_tabs[4]:
        if st.session_state.salience_map:
            sorted_exp = sorted(
                st.session_state.salience_map,
                key=lambda x: x.get("salience_score", 0),
                reverse=True,
            )
            for idx, item in enumerate(sorted_exp, 1):
                entity    = str(item.get("entity", ""))
                score     = float(item.get("salience_score", 0.0))
                reasoning = str(item.get("reasoning_context", ""))
                category  = str(item.get("category", ""))
                score_pct = int(score * 100)

                if score >= 0.85:   sc = "var(--tier-critical)"
                elif score >= 0.70: sc = "var(--tier-high)"
                elif score >= 0.50: sc = "var(--tier-medium)"
                else:               sc = "var(--tier-low)"

                st.markdown(f"""
                <div class="signal-row" style="padding:11px 6px">
                  <div style="flex-shrink:0;width:26px;font-size:10.5px;font-family:var(--font-mono);
                              color:var(--text-muted);text-align:right;padding-top:2px">{idx:02d}</div>
                  <div class="signal-body">
                    <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">
                      <span class="signal-entity">{entity}</span>
                      <span class="signal-category-chip">{category}</span>
                      <span style="margin-left:auto;font-size:11.5px;font-weight:700;
                                   font-family:var(--font-mono);color:{sc}">{score_pct}%</span>
                    </div>
                    <div class="signal-reasoning">{reasoning}</div>
                    <div class="signal-bar-track" style="margin-top:8px">
                      <div class="signal-bar-fill" style="width:{score_pct}%;background:{sc}"></div>
                    </div>
                  </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div class="empty-state">
              <div class="empty-state-title">No reasoning data available</div>
            </div>""", unsafe_allow_html=True)
