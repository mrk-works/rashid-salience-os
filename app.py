# =====================================================================
# SALIENCE OS v2 — Clinical Intelligence Workspace
# Streamlit-Native Redesign: Priority 1–7 compliance pass
# All backend logic preserved 100%.
# =====================================================================

# SYSTEM HOTFIX: Bridge Python 3.13+ audioop removal for pydub
import sys
try:
    import audioop
except ImportError:
    try:
        import audioop_lts as audioop
        sys.modules['audioop'] = audioop
    except ImportError:
        pass

import streamlit as st
import os
import json
import time
from datetime import datetime
from groq import Groq
import google.generativeai as genai
import pandas as pd
from pydub import AudioSegment
from fpdf import FPDF

# =====================================================================
# 0. PDF SAFETY LAYER — preserved exactly
# =====================================================================
def sanitize_for_pdf(text):
    if not text:
        return ""
    char_map = {
        "•": "-", "—": "-", "–": "-",
        "\u201c": '"', "\u201d": '"',
        "\u2018": "'", "\u2019": "'",
        "™": "TM", "©": "(c)", "®": "(r)"
    }
    for unicode_char, safe_char in char_map.items():
        text = text.replace(unicode_char, safe_char)
    return text.encode('latin-1', errors='replace').decode('latin-1')


def generate_clinical_pdf(soap_text, specialty):
    pdf = FPDF()
    pdf.set_margins(left=15, top=10, right=15)
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_fill_color(2, 132, 199)
    pdf.rect(0, 0, 210, 38, 'F')
    pdf.set_xy(0, 8)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(210, 12, "SALIENCE OS | CLINICAL NOTE MATRIX", ln=True, align="C")
    pdf.set_font("Helvetica", "I", 10)
    pdf.cell(210, 5, sanitize_for_pdf(
        f"Specialty: {specialty} | Compiled: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    ), ln=True, align="C")
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
            pdf.cell(effective_width, 10, sanitize_for_pdf(header_text.upper()), ln=True)
            x = pdf.l_margin
            pdf.line(x, pdf.get_y(), x + 40, pdf.get_y())
            pdf.ln(2)
            pdf.set_text_color(15, 23, 42)
        elif line_clean.startswith("**") and line_clean.endswith("**"):
            pdf.set_font("Helvetica", "B", 11)
            bold_text = line_clean.replace("**", "").strip()
            pdf.cell(effective_width, 7, sanitize_for_pdf(bold_text), ln=True)
        else:
            pdf.set_font("Helvetica", size=10)
            sanitized_body_line = line_clean.replace("**", "").replace("*", "-")
            pdf.multi_cell(effective_width, 6, sanitize_for_pdf(sanitized_body_line))
    return bytes(pdf.output())


# =====================================================================
# 1. PAGE CONFIG
# =====================================================================
st.set_page_config(
    page_title="Salience OS",
    page_icon="⬡",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# =====================================================================
# 2. SESSION STATE — clinical + settings
# =====================================================================
_defaults = {
    "transcript": "",
    "classification": {},
    "salience_map": [],
    "soap_note": "",
    "flags": [],
    "next_steps": [],
    "pipeline_execution_time": 0.0,
    "chart_locked": False,
    # Workspace settings (persist across reruns)
    "specialty_profile": "Cardiology",
    "target_language": "Mixed",
    "theme": "Dark",
}
for k, v in _defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# Map display names → full strings used in prompt
SPECIALTY_MAP = {
    "Cardiology":   "Cardiology Clinic",
    "General":      "General Internal Medicine",
    "Emergency":    "Emergency Trauma",
    "Neurology":    "Neurology",
    "Pediatrics":   "Pediatrics",
    "Orthopedics":  "Orthopedic Surgery",
    "Psychiatry":   "Psychiatry & Behavioral Health",
    "Oncology":     "Oncology",
}
LANGUAGE_MAP = {
    "Mixed":   "Mixed (Multi-lingual Code-Switching)",
    "English": "English (US/UK)",
    "Arabic":  "Arabic (Khaleeji/MSA)",
}

specialty_profile = SPECIALTY_MAP.get(st.session_state.specialty_profile, "Cardiology Clinic")
target_language   = LANGUAGE_MAP.get(st.session_state.target_language, "Mixed (Multi-lingual Code-Switching)")


# =====================================================================
# 3. CSS — Full Design System
#    Priority 2: Ambient background lighting via body::before layers
#    Priority 3: Lean header (wordmark + status + time only)
#    Priority 4: Layout rhythm & consistent spacing
#    Priority 6: SOAP readability tokens
#    Priority 7: Override Streamlit natives to match design system
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
  --text-inverse:   #080B10;

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

  --radius-sm:  5px;
  --radius-md:  9px;
  --radius-lg:  14px;
  --radius-xl:  20px;

  --font-mono: 'JetBrains Mono', 'Fira Code', 'SF Mono', ui-monospace, monospace;
  --transition: 150ms cubic-bezier(0.4,0,0.2,1);

  /* SOAP readability */
  --soap-font-size: 14px;
  --soap-line-height: 1.9;
}

/* ── Priority 2: Ambient Background Lighting ─────────────────────── */
/* Three-layer radial glow: blue (top-right), cyan (center-left),    */
/* violet (bottom-right). Subconscious, not decorative.              */
body::before {
  content: '';
  position: fixed;
  inset: 0;
  z-index: 0;
  pointer-events: none;
  background:
    radial-gradient(
      circle at 88% 12%,
      rgba(59, 130, 246, 0.11) 0%,
      transparent 38%
    ),
    radial-gradient(
      circle at 8% 52%,
      rgba(6, 182, 212, 0.07) 0%,
      transparent 30%
    ),
    radial-gradient(
      circle at 72% 92%,
      rgba(139, 92, 246, 0.06) 0%,
      transparent 28%
    );
}

/* Ensure Streamlit app sits above ::before */
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
.block-container {
  padding: 0 !important;
  max-width: 100% !important;
}

/* ── Scrollbar ───────────────────────────────────────────────────── */
::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border-default); border-radius: 99px; }

/* ── Priority 3: Lean Header ─────────────────────────────────────── */
.os-header {
  position: sticky;
  top: 0;
  z-index: 200;
  height: 52px;
  padding: 0 28px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: rgba(8, 11, 16, 0.85);
  backdrop-filter: blur(24px);
  -webkit-backdrop-filter: blur(24px);
  border-bottom: 1px solid var(--border-subtle);
}

.os-wordmark {
  font-size: 14.5px;
  font-weight: 700;
  letter-spacing: 0.3px;
  color: var(--text-primary);
}
.os-wordmark span { color: var(--accent-blue); }

.os-header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.os-status-pill {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 11px;
  font-weight: 500;
  padding: 3px 10px;
  border-radius: 99px;
  letter-spacing: 0.2px;
}
.os-status-pill.ready {
  background: rgba(16,185,129,0.10);
  color: var(--accent-emerald);
  border: 1px solid rgba(16,185,129,0.18);
}
.os-status-pill.active {
  background: rgba(59,130,246,0.10);
  color: var(--accent-blue);
  border: 1px solid rgba(59,130,246,0.18);
}
.os-status-pill.locked {
  background: rgba(139,92,246,0.10);
  color: var(--accent-violet);
  border: 1px solid rgba(139,92,246,0.18);
}
.os-dot {
  width: 5px; height: 5px;
  border-radius: 50%;
  background: currentColor;
}
.os-dot.pulse { animation: pulse-dot 2s ease-in-out infinite; }
@keyframes pulse-dot {
  0%,100% { opacity:1; transform:scale(1); }
  50% { opacity:0.4; transform:scale(0.75); }
}
.os-time {
  font-size: 11px;
  font-family: var(--font-mono);
  color: var(--text-muted);
  font-variant-numeric: tabular-nums;
}

/* ── Content Wrapper ─────────────────────────────────────────────── */
.os-content {
  padding: 24px 28px 48px;
}

/* ── Section Labels ──────────────────────────────────────────────── */
.section-label {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 1px;
  text-transform: uppercase;
  color: var(--text-muted);
  margin: 0 0 12px;
  display: flex;
  align-items: center;
  gap: 10px;
}
.section-label::after {
  content: '';
  flex: 1;
  height: 1px;
  background: var(--border-subtle);
}

/* ── Urgency Banner ──────────────────────────────────────────────── */
.urgency-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 13px 18px;
  border-radius: var(--radius-md);
  margin-bottom: 20px;
  border-left: 3px solid;
}
.urgency-bar.CRITICAL { background: rgba(239,68,68,0.07);  border-color: var(--tier-critical); }
.urgency-bar.HIGH     { background: rgba(245,158,11,0.07); border-color: var(--tier-high); }
.urgency-bar.MEDIUM   { background: rgba(59,130,246,0.07); border-color: var(--tier-medium); }
.urgency-bar.LOW      { background: rgba(16,185,129,0.07); border-color: var(--tier-low); }
.urgency-label {
  font-size: 9.5px; font-weight: 700;
  letter-spacing: 1.1px; text-transform: uppercase; opacity: 0.65;
}
.urgency-text { font-size: 13px; font-weight: 500; line-height: 1.45; margin-top: 2px; }
.urgency-bar.CRITICAL .urgency-label,
.urgency-bar.CRITICAL .urgency-text { color: var(--tier-critical); }
.urgency-bar.HIGH .urgency-label,
.urgency-bar.HIGH .urgency-text { color: var(--tier-high); }
.urgency-bar.MEDIUM .urgency-label,
.urgency-bar.MEDIUM .urgency-text { color: var(--tier-medium); }
.urgency-bar.LOW .urgency-label,
.urgency-bar.LOW .urgency-text { color: var(--tier-low); }

.urgency-metrics {
  margin-left: auto;
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}
.metric-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 9px;
  background: var(--bg-elevated);
  border: 1px solid var(--border-subtle);
  border-radius: 99px;
  font-size: 11px;
  color: var(--text-secondary);
  font-family: var(--font-mono);
}
.metric-chip .chip-label {
  font-family: -apple-system, sans-serif;
  font-size: 10.5px;
  color: var(--text-muted);
}

/* ── Signal Rows ─────────────────────────────────────────────────── */
.signal-row {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 10px 6px;
  border-bottom: 1px solid var(--border-subtle);
  transition: background var(--transition), padding-left var(--transition);
  border-radius: var(--radius-sm);
}
.signal-row:last-child { border-bottom: none; }
.signal-row:hover { background: var(--bg-hover); padding-left: 10px; }

.signal-score-ring {
  flex-shrink: 0;
  width: 38px; height: 38px;
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 10.5px; font-weight: 700;
  font-family: var(--font-mono);
  border: 2px solid;
}
.signal-score-ring.score-critical { background:rgba(239,68,68,0.09);  border-color:var(--tier-critical); color:var(--tier-critical); }
.signal-score-ring.score-high     { background:rgba(245,158,11,0.09); border-color:var(--tier-high);     color:var(--tier-high); }
.signal-score-ring.score-medium   { background:rgba(59,130,246,0.09); border-color:var(--tier-medium);   color:var(--tier-medium); }
.signal-score-ring.score-low      { background:rgba(16,185,129,0.09); border-color:var(--tier-low);      color:var(--tier-low); }

.signal-body { flex: 1; min-width: 0; }
.signal-entity { font-size: 13px; font-weight: 600; color: var(--text-primary); }
.signal-category-chip {
  display: inline-block;
  font-size: 9.5px; font-weight: 600; letter-spacing: 0.4px;
  padding: 1px 6px; border-radius: 99px;
  background: var(--bg-elevated);
  border: 1px solid var(--border-default);
  color: var(--text-secondary);
  margin: 3px 0 4px; text-transform: uppercase;
}
.signal-reasoning { font-size: 12px; color: var(--text-secondary); line-height: 1.55; }
.signal-bar-track {
  width: 100%; height: 2px;
  background: var(--bg-elevated); border-radius: 99px;
  margin-top: 7px; overflow: hidden;
}
.signal-bar-fill {
  height: 100%; border-radius: 99px;
  transition: width 0.7s cubic-bezier(0.4,0,0.2,1);
}

/* ── Flag & Step Items ───────────────────────────────────────────── */
.flag-item {
  display: flex; align-items: flex-start; gap: 10px;
  padding: 11px 14px;
  background: rgba(239,68,68,0.06);
  border: 1px solid rgba(239,68,68,0.15);
  border-left: 3px solid var(--tier-critical);
  border-radius: var(--radius-md); margin-bottom: 8px;
  font-size: 13px; color: #FCA5A5; line-height: 1.55;
}
.flag-icon { flex-shrink:0; color:var(--tier-critical); font-size:13px; margin-top:1px; }

.step-item {
  display: flex; align-items: flex-start; gap: 10px;
  padding: 9px 14px;
  background: rgba(59,130,246,0.055);
  border: 1px solid rgba(59,130,246,0.12);
  border-radius: var(--radius-md); margin-bottom: 7px;
  font-size: 13px; color: #93C5FD; line-height: 1.55;
}
.step-num {
  flex-shrink:0; width:19px; height:19px; border-radius:50%;
  background:rgba(59,130,246,0.18); color:var(--accent-blue);
  font-size:9.5px; font-weight:700;
  display:flex; align-items:center; justify-content:center; margin-top:1px;
}

/* ── Priority 6: SOAP Viewer ─────────────────────────────────────── */
.soap-outer {
  max-width: 1100px;
  margin: 0 auto;
}
.soap-viewer {
  background: var(--bg-surface);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  padding: 32px 36px;
  font-size: var(--soap-font-size);
  line-height: var(--soap-line-height);
  color: var(--text-primary);
}
.soap-section-header {
  font-size: 10px; font-weight: 700; letter-spacing: 1.1px;
  text-transform: uppercase; color: var(--accent-blue);
  margin-top: 24px; margin-bottom: 10px;
  padding-bottom: 7px; border-bottom: 1px solid var(--border-subtle);
}
.soap-section-header:first-child { margin-top: 0; }
.soap-body-p {
  margin: 0 0 2px;
  color: var(--text-secondary);
  font-size: var(--soap-font-size);
  line-height: var(--soap-line-height);
}
.soap-bold {
  color: var(--text-primary);
  font-weight: 600;
  font-size: var(--soap-font-size);
}

/* Sticky SOAP action bar */
.soap-action-bar {
  position: sticky;
  bottom: 0;
  background: rgba(8,11,16,0.92);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border-top: 1px solid var(--border-subtle);
  padding: 12px 0 14px;
  margin-top: 16px;
  display: flex;
  align-items: center;
  gap: 10px;
}
.soap-meta-row {
  display: flex; align-items: center; gap: 16px;
  padding: 12px 0;
  margin-bottom: 8px;
  border-bottom: 1px solid var(--border-subtle);
}
.soap-meta-item { display:flex; flex-direction:column; gap:2px; }
.soap-meta-label {
  font-size:9.5px; font-weight:700; letter-spacing:0.8px;
  text-transform:uppercase; color:var(--text-muted);
}
.soap-meta-value {
  font-size:12.5px; font-weight:500; color:var(--text-secondary);
  font-family: var(--font-mono);
}

/* ── Empty State ─────────────────────────────────────────────────── */
.empty-state {
  display:flex; flex-direction:column; align-items:center; justify-content:center;
  padding:44px 24px; text-align:center; gap:10px;
}
.empty-state-icon  { font-size:24px; opacity:0.25; }
.empty-state-title { font-size:13.5px; font-weight:600; color:var(--text-secondary); }
.empty-state-body  { font-size:12px; color:var(--text-muted); line-height:1.6; max-width:260px; }

/* ── Streamlit Native Component Overrides ────────────────────────── */

/* Sidebar */
section[data-testid="stSidebar"] {
  background: var(--bg-surface) !important;
  border-right: 1px solid var(--border-subtle) !important;
}

/* Inputs */
.stTextInput > div > div > input,
.stTextArea > div > div > textarea {
  background: var(--bg-elevated) !important;
  border: 1px solid var(--border-default) !important;
  border-radius: var(--radius-md) !important;
  color: var(--text-primary) !important;
  font-size: 13px !important;
}
.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {
  border-color: var(--accent-blue) !important;
  box-shadow: 0 0 0 3px rgba(59,130,246,0.12) !important;
  outline: none !important;
}
.stTextInput label, .stTextArea label {
  font-size: 11px !important; font-weight: 600 !important;
  letter-spacing: 0.5px !important; text-transform: uppercase !important;
  color: var(--text-muted) !important;
}

/* Selectbox */
.stSelectbox > div > div > div {
  background: var(--bg-elevated) !important;
  border: 1px solid var(--border-default) !important;
  border-radius: var(--radius-md) !important;
  color: var(--text-primary) !important;
  font-size: 13px !important;
}

/* Primary button */
.stButton > button[kind="primary"] {
  background: var(--accent-blue) !important;
  color: #fff !important; border: none !important;
  border-radius: var(--radius-md) !important;
  font-weight: 600 !important; font-size: 13px !important;
  height: 40px !important; letter-spacing: 0.2px !important;
  transition: all var(--transition) !important;
}
.stButton > button[kind="primary"]:hover {
  background: var(--accent-blue-dim) !important;
  box-shadow: 0 0 0 3px rgba(59,130,246,0.22) !important;
  transform: translateY(-1px) !important;
}
/* Secondary button */
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
.stButton > button:not([kind]):hover {
  border-color: var(--border-strong) !important;
}
.stButton > button:disabled {
  background: var(--bg-elevated) !important;
  color: var(--text-muted) !important;
  border-color: var(--border-subtle) !important;
}

/* Download button */
.stDownloadButton > button {
  background: var(--bg-elevated) !important;
  color: var(--text-primary) !important;
  border: 1px solid var(--border-default) !important;
  border-radius: var(--radius-md) !important;
  font-weight: 500 !important; font-size: 13px !important;
  height: 40px !important;
}
.stDownloadButton > button:hover {
  border-color: var(--accent-blue) !important;
  color: var(--accent-blue) !important;
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
  background: transparent !important;
  border-bottom: 1px solid var(--border-subtle) !important;
  gap: 0 !important; padding: 0 !important;
}
.stTabs [data-baseweb="tab"] {
  background: transparent !important;
  color: var(--text-muted) !important;
  font-size: 12.5px !important; font-weight: 500 !important;
  padding: 9px 16px !important;
  border-bottom: 2px solid transparent !important;
  border-radius: 0 !important;
  transition: all var(--transition) !important;
}
.stTabs [data-baseweb="tab"]:hover { color: var(--text-secondary) !important; }
.stTabs [aria-selected="true"] {
  color: var(--text-primary) !important;
  border-bottom: 2px solid var(--accent-blue) !important;
}
.stTabs [data-baseweb="tab-panel"] { padding: 18px 0 0 !important; }

/* Segmented control (st.segmented_control) */
[data-testid="stSegmentedControl"] > div {
  background: var(--bg-elevated) !important;
  border: 1px solid var(--border-default) !important;
  border-radius: var(--radius-md) !important;
  padding: 3px !important;
  gap: 2px !important;
}
[data-testid="stSegmentedControl"] button {
  background: transparent !important;
  color: var(--text-secondary) !important;
  border-radius: var(--radius-sm) !important;
  font-size: 12.5px !important; font-weight: 500 !important;
  border: none !important;
  transition: all var(--transition) !important;
}
[data-testid="stSegmentedControl"] button[aria-checked="true"] {
  background: var(--accent-blue) !important;
  color: #fff !important;
  box-shadow: 0 1px 4px rgba(0,0,0,0.4) !important;
}

/* Pills (st.pills) */
[data-testid="stPills"] button {
  background: var(--bg-elevated) !important;
  color: var(--text-secondary) !important;
  border: 1px solid var(--border-default) !important;
  border-radius: 99px !important;
  font-size: 12px !important; font-weight: 500 !important;
  transition: all var(--transition) !important;
}
[data-testid="stPills"] button[aria-pressed="true"] {
  background: rgba(59,130,246,0.15) !important;
  color: var(--accent-blue) !important;
  border-color: rgba(59,130,246,0.3) !important;
}

/* Radio */
.stRadio > label { color: var(--text-secondary) !important; font-size: 12.5px !important; }
.stRadio > div > label { color: var(--text-secondary) !important; font-size: 13px !important; }

/* Audio input */
[data-testid="stAudioInput"] {
  background: var(--bg-elevated) !important;
  border: 1px solid var(--border-default) !important;
  border-radius: var(--radius-md) !important;
}

/* File uploader */
[data-testid="stFileUploader"] {
  background: var(--bg-elevated) !important;
  border: 1px dashed var(--border-default) !important;
  border-radius: var(--radius-md) !important;
}

/* Number input */
.stNumberInput > div > div > input {
  background: var(--bg-elevated) !important;
  border: 1px solid var(--border-default) !important;
  border-radius: var(--radius-md) !important;
  color: var(--text-primary) !important;
  font-size: 13px !important;
}

/* Alert/info/error/success */
[data-baseweb="notification"] {
  border-radius: var(--radius-md) !important;
  font-size: 13px !important;
}

/* Divider */
hr { border-color: var(--border-subtle) !important; margin: 20px 0 !important; }

/* st.status */
[data-testid="stStatusWidget"] {
  background: var(--bg-elevated) !important;
  border: 1px solid var(--border-default) !important;
  border-radius: var(--radius-md) !important;
}

/* Spinner */
.stSpinner > div {
  border-color: var(--accent-blue) transparent transparent !important;
}

/* Label typography */
label[data-testid="stWidgetLabel"] {
  color: var(--text-secondary) !important; font-size: 12px !important;
}
.stCaption { color: var(--text-muted) !important; font-size: 11.5px !important; }
p { color: var(--text-secondary) !important; }

/* Popover */
[data-testid="stPopover"] > div {
  background: var(--bg-elevated) !important;
  border: 1px solid var(--border-default) !important;
  border-radius: var(--radius-lg) !important;
  box-shadow: 0 16px 48px rgba(0,0,0,0.7) !important;
}

/* Sidebar control-center section label */
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
# =====================================================================
has_cloud_groq   = "groq_api_key"   in st.secrets
has_cloud_gemini = "gemini_api_key" in st.secrets


# =====================================================================
# 5. PRIORITY 1: Control Center — st.popover() with native components
# =====================================================================
# We'll render the popover inside the header columns below.
# Defined here so settings are resolved before header renders.

def render_control_center():
    """Workspace settings using only native Streamlit components."""
    st.markdown('<span class="ctrl-label">Specialty Profile</span>', unsafe_allow_html=True)
    specialty_choice = st.segmented_control(
        "Specialty",
        options=["Cardiology", "General", "Emergency", "Neurology",
                 "Pediatrics", "Orthopedics", "Psychiatry", "Oncology"],
        default=st.session_state.specialty_profile,
        key="ctrl_specialty",
        label_visibility="collapsed",
    )
    if specialty_choice and specialty_choice != st.session_state.specialty_profile:
        st.session_state.specialty_profile = specialty_choice
        st.rerun()

    st.markdown('<span class="ctrl-label">Language Matrix</span>', unsafe_allow_html=True)
    lang_choice = st.segmented_control(
        "Language",
        options=["Mixed", "English", "Arabic"],
        default=st.session_state.target_language,
        key="ctrl_language",
        label_visibility="collapsed",
    )
    if lang_choice and lang_choice != st.session_state.target_language:
        st.session_state.target_language = lang_choice
        st.rerun()

    st.markdown('<span class="ctrl-label">Theme</span>', unsafe_allow_html=True)
    theme_choice = st.pills(
        "Theme",
        options=["Dark", "System", "Light"],
        default=st.session_state.theme,
        key="ctrl_theme",
        label_visibility="collapsed",
    )
    if theme_choice and theme_choice != st.session_state.theme:
        st.session_state.theme = theme_choice
        st.rerun()

    st.markdown('<span class="ctrl-label">API Credentials</span>', unsafe_allow_html=True)
    if has_cloud_groq and has_cloud_gemini:
        st.caption("✓  Vault active — keys pre-loaded")
    else:
        # Allow override if vault is missing
        groq_override = st.text_input(
            "Groq API Key", type="password",
            placeholder="sk-..." if not has_cloud_groq else "🔒 Vault loaded",
            key="ctrl_groq"
        )
        gemini_override = st.text_input(
            "Gemini API Key", type="password",
            placeholder="AI..." if not has_cloud_gemini else "🔒 Vault loaded",
            key="ctrl_gemini"
        )
        if groq_override:
            st.session_state["_groq_override"] = groq_override
        if gemini_override:
            st.session_state["_gemini_override"] = gemini_override


# Resolve API keys (override > vault)
groq_api_key   = st.session_state.get("_groq_override", "") or st.secrets.get("groq_api_key", "")
gemini_api_key = st.session_state.get("_gemini_override", "") or st.secrets.get("gemini_api_key", "")

# Update resolved specialty/language for prompt use
specialty_profile = SPECIALTY_MAP.get(st.session_state.specialty_profile, "Cardiology Clinic")
target_language   = LANGUAGE_MAP.get(st.session_state.target_language, "Mixed (Multi-lingual Code-Switching)")


# =====================================================================
# 6. PRIORITY 3: Lean Header — wordmark + status + time
# =====================================================================
has_results  = bool(st.session_state.transcript)
chart_locked = st.session_state.chart_locked

if chart_locked:
    status_html = '<div class="os-status-pill locked"><div class="os-dot"></div>Signed</div>'
elif has_results:
    status_html = '<div class="os-status-pill active"><div class="os-dot pulse"></div>Review</div>'
else:
    status_html = '<div class="os-status-pill ready"><div class="os-dot pulse"></div>Ready</div>'

# Header is a sticky HTML bar; the settings popover sits adjacent in Streamlit column
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
    # Align popover button with header visually
    st.markdown("<div style='padding-top:10px'>", unsafe_allow_html=True)
    with st.popover("⚙ Settings", use_container_width=False):
        render_control_center()
    st.markdown("</div>", unsafe_allow_html=True)

st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)


# =====================================================================
# 7. INPUT WORKSPACE
#    Priority 4: col ratio [1.25, 1] for input vs exam
# =====================================================================
st.markdown('<div class="section-label">Consultation Input</div>', unsafe_allow_html=True)

col_input, col_exam = st.columns([1.25, 1], gap="large")

# ── Left: Data Capture ──────────────────────────────────────────────
with col_input:
    input_vector = st.radio(
        "Input mode",
        ["Text / Paste Transcript", "Live Audio (Microphone)", "File Upload (.wav / .mp3 / .json)"],
        horizontal=False,
        label_visibility="collapsed",
    )

    temp_audio_filename = "active_stream_input.wav"
    has_valid_audio_payload = False
    bypass_audio_stt        = False
    injected_text_payload   = ""

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
        st.caption("Position microphone toward conversation, then tap record.")
        audio_file = st.audio_input("Record audio")
        if audio_file is not None:
            with open(temp_audio_filename, "wb") as f:
                f.write(audio_file.read())
            has_valid_audio_payload = True

    else:
        uploaded_file = st.file_uploader(
            "Upload audio or dataset",
            type=["wav", "mp3", "m4a", "json"],
            label_visibility="collapsed",
        )
        if uploaded_file is not None:
            if uploaded_file.name.endswith('.json'):
                try:
                    json_data = json.load(uploaded_file)
                    if isinstance(json_data, list):
                        st.caption(f"Dataset loaded — {len(json_data)} cases")
                        case_idx = st.number_input(
                            "Case index", min_value=0, max_value=len(json_data)-1, value=0
                        )
                        selected_node = json_data[case_idx]
                        injected_text_payload = selected_node.get(
                            "input", selected_node.get("instruction", "")
                        )
                        if injected_text_payload:
                            st.info(injected_text_payload[:240] + ("…" if len(injected_text_payload) > 240 else ""))
                        if injected_text_payload.strip():
                            has_valid_audio_payload = True
                            bypass_audio_stt = True
                    else:
                        st.error("JSON must be a list of cases.")
                except Exception as json_err:
                    st.error(f"JSON parse error: {json_err}")
            else:
                with open(temp_audio_filename, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                st.audio(temp_audio_filename)
                has_valid_audio_payload = True

# ── Right: Physical Exam ────────────────────────────────────────────
with col_exam:
    st.markdown('<div class="section-label">Physical Examination</div>', unsafe_allow_html=True)
    st.caption("Examination findings are merged with transcript during analysis.")

    exam_tabs = st.tabs(["Thoracic", "GI / Abdomen", "Neuro / Reflex", "Musculoskeletal"])
    with exam_tabs[0]:
        notes_thoracic = st.text_area(
            "Thoracic",
            value="Cardiovascular: Tachycardic, rhythm regular. S1 and S2 distinct, no audible murmurs, rubs, or gallops. Significant chest wall diaphoresis noted; patient actively clutching retrosternal area. Respiratory: Tachypneic, shallow respirations. Lungs clear to auscultation bilaterally (CTAB).",
            height=140,
            label_visibility="collapsed",
        )
    with exam_tabs[1]:
        notes_abdominal = st.text_area(
            "GI",
            value="Abdomen soft, symmetric, and non-distended. Bowel sounds active in all 4 quadrants. No localized tenderness, guarding, or rebound. No hepatosplenomegaly. Epigastric region non-tender.",
            height=140,
            label_visibility="collapsed",
        )
    with exam_tabs[2]:
        notes_neuro = st.text_area(
            "Neuro",
            value="Patient alert and oriented to person, place, and time (A&Ox3). Pupils equal, round, and reactive to light (PEERRLA). Observable orthostatic lightheadedness upon sitting up. Gross motor and sensory function intact.",
            height=140,
            label_visibility="collapsed",
        )
    with exam_tabs[3]:
        notes_ortho = st.text_area(
            "MSK",
            value="Mild focal tenderness over lumbar paraspinal muscles. Left shoulder and left mandibular jaw display full passive range of motion with zero localized joint or bone tenderness.",
            height=140,
            label_visibility="collapsed",
        )

compiled_examination_overlay = f"""
- Thoracic Tracking Overlay: {notes_thoracic if notes_thoracic else 'Deferred/Normal checks confirmed'}
- GI/Abdominal Tracking Overlay: {notes_abdominal if notes_abdominal else 'Deferred/Normal checks confirmed'}
- Reflex/Neuro Tracking Overlay: {notes_neuro if notes_neuro else 'Deferred/Normal checks confirmed'}
- Musculoskeletal Tracking Overlay: {notes_ortho if notes_ortho else 'Deferred/Normal checks confirmed'}
"""


# =====================================================================
# 8. ANALYSIS TRIGGER
# =====================================================================
st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

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
    run_pipeline = False


# =====================================================================
# 9. PIPELINE EXECUTION
#    Priority 5: st.status() for live stage feedback; hidden when done
# =====================================================================
if has_valid_audio_payload and run_pipeline:
    if not groq_api_key or not gemini_api_key:
        st.error("API credentials required — open ⚙ Settings to configure.")
    else:
        pipeline_start = time.time()

        with st.status("Running clinical intelligence pipeline…", expanded=True) as status_widget:
            try:
                # ── Stage 1: Transcription ──────────────────────────
                if bypass_audio_stt:
                    st.write("✓  Text input detected — bypassing STT")
                    extracted_raw_text = injected_text_payload
                else:
                    st.write("⬡  Compressing audio for Whisper API…")
                    raw_audio = AudioSegment.from_file(temp_audio_filename)
                    processed_audio = raw_audio.set_channels(1).set_frame_rate(16000)
                    compressed_filename = "optimized_api_payload.mp3"
                    processed_audio.export(compressed_filename, format="mp3", bitrate="64k")

                    st.write("⬡  Transcribing via Whisper large-v3…")
                    groq_client = Groq(api_key=groq_api_key, timeout=60.0)
                    with open(compressed_filename, "rb") as audio_binary:
                        extracted_raw_text = groq_client.audio.transcriptions.create(
                            file=(compressed_filename, audio_binary.read()),
                            model="whisper-large-v3",
                            response_format="text",
                        )
                    if os.path.exists(temp_audio_filename):  os.remove(temp_audio_filename)
                    if os.path.exists(compressed_filename):  os.remove(compressed_filename)
                    st.write("✓  Transcription complete")

                # ── Stage 2: Gemini Intelligence ───────────────────
                st.write("⬡  Running salience analysis via Gemini 2.5 Flash…")
                genai.configure(api_key=gemini_api_key)
                intelligence_engine = genai.GenerativeModel('gemini-2.5-flash')

                system_prompt = f"""
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
                parsed_payload = json.loads(response_package.text, strict=False)

                st.write("✓  Intelligence extraction complete")
                st.write("⬡  Compiling SOAP chart…")

                st.session_state.transcript             = parsed_payload.get("cleaned_transcript", "")
                st.session_state.classification         = parsed_payload.get("classification", {})
                st.session_state.salience_map           = parsed_payload.get("salience_weight_map", [])
                st.session_state.soap_note              = parsed_payload.get("structured_soap_chart", "")
                st.session_state.flags                  = parsed_payload.get("clinical_safety_red_flags", [])
                st.session_state.next_steps             = parsed_payload.get("suggested_next_steps", [])
                st.session_state.pipeline_execution_time = round(time.time() - pipeline_start, 2)
                st.session_state.chart_locked           = False

                st.write("✓  Pipeline complete")
                status_widget.update(
                    label=f"Analysis complete — {st.session_state.pipeline_execution_time}s",
                    state="complete",
                    expanded=False,
                )
                st.rerun()

            except Exception as e:
                status_widget.update(label="Pipeline error", state="error", expanded=True)
                st.error(f"Error: {e}")


# =====================================================================
# 10. RESULTS WORKSPACE
#     Priority 4: Urgency in results area, not header
#     Priority 6: SOAP readability + sticky action bar
# =====================================================================
if st.session_state.transcript:
    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
    st.markdown('<div class="section-label">Clinical Intelligence Output</div>', unsafe_allow_html=True)

    # ── Urgency Banner (lives here, not in header) ──────────────────
    classification = st.session_state.classification
    urgency  = classification.get("urgency_tier", "MEDIUM")
    trigger  = classification.get("primary_clinical_trigger", "")

    n_signals = len(st.session_state.salience_map)
    n_flags   = len(st.session_state.flags)
    elapsed   = st.session_state.pipeline_execution_time

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

    # ── Output Tabs (native st.tabs) ────────────────────────────────
    output_tabs = st.tabs([
        "Clinical Signals",
        "Safety Flags",
        "Next Steps",
        "SOAP Note",
        "Explainability",
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
                score    = item.get("salience_score", 0.0)
                entity   = item.get("entity", "")
                category = item.get("category", "")
                reasoning = item.get("reasoning_context", "")
                bar_pct  = int(score * 100)

                if score >= 0.85:
                    ring_cls = "score-critical"; bar_color = "var(--tier-critical)"
                elif score >= 0.70:
                    ring_cls = "score-high";     bar_color = "var(--tier-high)"
                elif score >= 0.50:
                    ring_cls = "score-medium";   bar_color = "var(--tier-medium)"
                else:
                    ring_cls = "score-low";      bar_color = "var(--tier-low)"

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
            st.markdown('<div class="empty-state"><div class="empty-state-icon">◎</div><div class="empty-state-title">No signals extracted</div></div>', unsafe_allow_html=True)

    # ── Tab 2: Safety Flags ─────────────────────────────────────────
    with output_tabs[1]:
        if st.session_state.flags:
            for alert in st.session_state.flags:
                st.markdown(f"""
                <div class="flag-item">
                  <div class="flag-icon">⚑</div>
                  <div>{alert}</div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div class="empty-state">
              <div class="empty-state-icon">✓</div>
              <div class="empty-state-title">No safety flags raised</div>
              <div class="empty-state-body">All clinical safety parameters cleared for this consultation.</div>
            </div>
            """, unsafe_allow_html=True)

    # ── Tab 3: Next Steps ───────────────────────────────────────────
    with output_tabs[2]:
        if st.session_state.next_steps:
            for idx, step in enumerate(st.session_state.next_steps, 1):
                st.markdown(f"""
                <div class="step-item">
                  <div class="step-num">{idx}</div>
                  <div>{step}</div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.markdown('<div class="empty-state"><div class="empty-state-title">No next steps generated</div></div>', unsafe_allow_html=True)

    # ── Tab 4: SOAP Note ────────────────────────────────────────────
    with output_tabs[3]:
        soap_raw = st.session_state.soap_note

        # Meta row
        st.markdown(f"""
        <div class="soap-meta-row">
          <div class="soap-meta-item">
            <span class="soap-meta-label">Generated</span>
            <span class="soap-meta-value">{datetime.now().strftime('%Y-%m-%d %H:%M')}</span>
          </div>
          <div class="soap-meta-item">
            <span class="soap-meta-label">Specialty</span>
            <span class="soap-meta-value">{specialty_profile}</span>
          </div>
          <div class="soap-meta-item">
            <span class="soap-meta-label">Status</span>
            <span class="soap-meta-value" style="color:{'var(--accent-violet)' if st.session_state.chart_locked else 'var(--accent-amber)'}">
              {'Signed & Locked' if st.session_state.chart_locked else 'Pending Review'}
            </span>
          </div>
          <div class="soap-meta-item">
            <span class="soap-meta-label">Pipeline Time</span>
            <span class="soap-meta-value">{elapsed}s</span>
          </div>
        </div>
        """, unsafe_allow_html=True)

        # Render SOAP with improved typography
        soap_lines = soap_raw.split("\n")
        rendered = []
        for line in soap_lines:
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

        soap_html = "".join(rendered)
        st.markdown(f"""
        <div class="soap-outer">
          <div class="soap-viewer">{soap_html}</div>
        </div>
        """, unsafe_allow_html=True)

        # Action bar — three native buttons in columns
        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
        act1, act2, act3 = st.columns([1, 1, 1])

        with act1:
            st.button(
                "⎘  Copy SOAP",
                key="copy_soap_btn",
                use_container_width=True,
                help="Copy SOAP note to clipboard (use Ctrl+A in viewer above)",
            )

        with act2:
            try:
                pdf_binary = generate_clinical_pdf(st.session_state.soap_note, specialty_profile)
                st.download_button(
                    label="↓  Export PDF",
                    data=pdf_binary,
                    file_name=f"SalienceOS_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )
            except Exception as pdf_err:
                st.error(f"PDF error: {pdf_err}")

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
                entity   = item.get("entity", "")
                score    = item.get("salience_score", 0.0)
                reasoning = item.get("reasoning_context", "")
                category = item.get("category", "")
                score_pct = int(score * 100)

                if score >= 0.85:    sc = "var(--tier-critical)"
                elif score >= 0.70:  sc = "var(--tier-high)"
                elif score >= 0.50:  sc = "var(--tier-medium)"
                else:                sc = "var(--tier-low)"

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
            st.markdown('<div class="empty-state"><div class="empty-state-title">No reasoning data available</div></div>', unsafe_allow_html=True)
