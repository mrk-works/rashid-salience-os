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
# 0. SAFETY LAYER: UNICODE TO LATIN-1 CHAR SANITIZATION FOR FPDF
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
# 1. PAGE CONFIG & SESSION STATE
# =====================================================================
st.set_page_config(
    page_title="Salience OS",
    page_icon="⬡",
    layout="wide",
    initial_sidebar_state="collapsed"
)

if "transcript" not in st.session_state:
    st.session_state.transcript = ""
    st.session_state.classification = {}
    st.session_state.salience_map = []
    st.session_state.soap_note = ""
    st.session_state.flags = []
    st.session_state.next_steps = []
    st.session_state.pipeline_execution_time = 0.0
    st.session_state.chart_locked = False


# =====================================================================
# 2. CSS DESIGN SYSTEM
# =====================================================================
st.markdown("""
<style>
/* ── Design Tokens ───────────────────────────────────────────────── */
:root {
  --bg-base:        #0A0C0F;
  --bg-surface:     #111318;
  --bg-elevated:    #181C24;
  --bg-glass:       rgba(24, 28, 36, 0.72);
  --bg-hover:       rgba(255,255,255,0.04);

  --border-subtle:  rgba(255,255,255,0.07);
  --border-default: rgba(255,255,255,0.11);
  --border-strong:  rgba(255,255,255,0.18);

  --text-primary:   #F0F2F5;
  --text-secondary: #8A92A0;
  --text-muted:     #545C6B;
  --text-inverse:   #0A0C0F;

  --accent-blue:    #3B82F6;
  --accent-blue-dim:#1D4ED8;
  --accent-emerald: #10B981;
  --accent-amber:   #F59E0B;
  --accent-red:     #EF4444;
  --accent-violet:  #8B5CF6;

  --tier-critical:  #EF4444;
  --tier-high:      #F59E0B;
  --tier-medium:    #3B82F6;
  --tier-low:       #10B981;

  --radius-sm:  6px;
  --radius-md:  10px;
  --radius-lg:  16px;
  --radius-xl:  24px;

  --shadow-sm:  0 1px 3px rgba(0,0,0,0.4);
  --shadow-md:  0 4px 16px rgba(0,0,0,0.5);
  --shadow-lg:  0 12px 40px rgba(0,0,0,0.6);

  --font-mono:  'JetBrains Mono', 'Fira Code', 'SF Mono', monospace;
  --transition: 160ms cubic-bezier(0.4,0,0.2,1);
}

/* ── Base Reset ──────────────────────────────────────────────────── */
html, body, [class*="css"] {
  font-family: -apple-system, 'SF Pro Display', 'Helvetica Neue', system-ui, sans-serif;
  background-color: var(--bg-base) !important;
  color: var(--text-primary) !important;
  -webkit-font-smoothing: antialiased;
}

/* Hide Streamlit chrome */
#MainMenu, footer, header { visibility: hidden; }
.stDeployButton { display: none; }
.block-container {
  padding: 0 !important;
  max-width: 100% !important;
}

/* ── Scrollbar ───────────────────────────────────────────────────── */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border-default); border-radius: 99px; }

/* ── Global wrapper ──────────────────────────────────────────────── */
.os-shell {
  min-height: 100vh;
  background: var(--bg-base);
  padding: 0;
}

/* ── TOP HEADER BAR ──────────────────────────────────────────────── */
.os-header {
  position: sticky;
  top: 0;
  z-index: 100;
  background: rgba(10, 12, 15, 0.88);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border-bottom: 1px solid var(--border-subtle);
  padding: 0 32px;
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
}

.os-header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.os-wordmark {
  font-size: 15px;
  font-weight: 700;
  letter-spacing: -0.3px;
  color: var(--text-primary);
}

.os-wordmark span {
  color: var(--accent-blue);
}

.os-divider-vert {
  width: 1px;
  height: 20px;
  background: var(--border-default);
}

.os-specialty-badge {
  font-size: 11.5px;
  font-weight: 500;
  color: var(--text-secondary);
  letter-spacing: 0.3px;
  padding: 3px 10px;
  background: var(--bg-elevated);
  border: 1px solid var(--border-subtle);
  border-radius: 99px;
}

.os-header-right {
  display: flex;
  align-items: center;
  gap: 10px;
}

.os-status-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 11.5px;
  font-weight: 500;
  padding: 4px 12px;
  border-radius: 99px;
  letter-spacing: 0.2px;
}

.os-status-pill.ready {
  background: rgba(16,185,129,0.12);
  color: var(--accent-emerald);
  border: 1px solid rgba(16,185,129,0.2);
}

.os-status-pill.active {
  background: rgba(59,130,246,0.12);
  color: var(--accent-blue);
  border: 1px solid rgba(59,130,246,0.2);
}

.os-status-pill.locked {
  background: rgba(139,92,246,0.12);
  color: var(--accent-violet);
  border: 1px solid rgba(139,92,246,0.2);
}

.os-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
}

.os-dot.pulse {
  animation: pulse-dot 2s ease-in-out infinite;
}

@keyframes pulse-dot {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.5; transform: scale(0.8); }
}

.os-timestamp {
  font-size: 11px;
  color: var(--text-muted);
  font-variant-numeric: tabular-nums;
  font-family: var(--font-mono);
}

/* ── MAIN LAYOUT ─────────────────────────────────────────────────── */
.os-content {
  padding: 24px 32px 40px;
  display: grid;
  gap: 20px;
}

/* ── SECTION LABEL ───────────────────────────────────────────────── */
.section-label {
  font-size: 10.5px;
  font-weight: 600;
  letter-spacing: 0.9px;
  text-transform: uppercase;
  color: var(--text-muted);
  margin-bottom: 10px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.section-label::after {
  content: '';
  flex: 1;
  height: 1px;
  background: var(--border-subtle);
}

/* ── PANELS ──────────────────────────────────────────────────────── */
.os-panel {
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg);
  padding: 20px;
  transition: border-color var(--transition);
}

.os-panel:hover {
  border-color: var(--border-default);
}

.os-panel-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 4px;
  letter-spacing: -0.2px;
}

.os-panel-sub {
  font-size: 11.5px;
  color: var(--text-muted);
  margin-bottom: 16px;
  line-height: 1.5;
}

/* ── URGENCY INDICATOR BAR ───────────────────────────────────────── */
.urgency-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 18px;
  border-radius: var(--radius-md);
  margin-bottom: 16px;
  border-left: 3px solid;
}

.urgency-bar.CRITICAL {
  background: rgba(239,68,68,0.08);
  border-color: var(--tier-critical);
}
.urgency-bar.HIGH {
  background: rgba(245,158,11,0.08);
  border-color: var(--tier-high);
}
.urgency-bar.MEDIUM {
  background: rgba(59,130,246,0.08);
  border-color: var(--tier-medium);
}
.urgency-bar.LOW {
  background: rgba(16,185,129,0.08);
  border-color: var(--tier-low);
}

.urgency-label {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 1px;
  text-transform: uppercase;
  opacity: 0.7;
}

.urgency-text {
  font-size: 13.5px;
  font-weight: 500;
  line-height: 1.4;
}

.urgency-bar.CRITICAL .urgency-label,
.urgency-bar.CRITICAL .urgency-text { color: var(--tier-critical); }
.urgency-bar.HIGH .urgency-label,
.urgency-bar.HIGH .urgency-text { color: var(--tier-high); }
.urgency-bar.MEDIUM .urgency-label,
.urgency-bar.MEDIUM .urgency-text { color: var(--tier-medium); }
.urgency-bar.LOW .urgency-label,
.urgency-bar.LOW .urgency-text { color: var(--tier-low); }

/* ── SALIENCE SIGNAL ROW ─────────────────────────────────────────── */
.signal-row {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 10px 0;
  border-bottom: 1px solid var(--border-subtle);
  transition: background var(--transition);
}

.signal-row:last-child { border-bottom: none; }

.signal-row:hover {
  background: var(--bg-hover);
  border-radius: var(--radius-sm);
  padding-left: 6px;
  padding-right: 6px;
}

.signal-score-ring {
  flex-shrink: 0;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 700;
  font-family: var(--font-mono);
  border: 2px solid;
}

.signal-score-ring.score-critical {
  background: rgba(239,68,68,0.1);
  border-color: var(--tier-critical);
  color: var(--tier-critical);
}
.signal-score-ring.score-high {
  background: rgba(245,158,11,0.1);
  border-color: var(--tier-high);
  color: var(--tier-high);
}
.signal-score-ring.score-medium {
  background: rgba(59,130,246,0.1);
  border-color: var(--tier-medium);
  color: var(--tier-blue, var(--tier-medium));
}
.signal-score-ring.score-low {
  background: rgba(16,185,129,0.1);
  border-color: var(--tier-low);
  color: var(--tier-low);
}

.signal-body {
  flex: 1;
  min-width: 0;
}

.signal-entity {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  line-height: 1.3;
}

.signal-category-chip {
  display: inline-block;
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.4px;
  padding: 1px 7px;
  border-radius: 99px;
  background: var(--bg-elevated);
  border: 1px solid var(--border-default);
  color: var(--text-secondary);
  margin: 3px 0 4px;
  text-transform: uppercase;
}

.signal-reasoning {
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.5;
}

.signal-bar-track {
  width: 100%;
  height: 3px;
  background: var(--bg-elevated);
  border-radius: 99px;
  margin-top: 6px;
  overflow: hidden;
}

.signal-bar-fill {
  height: 100%;
  border-radius: 99px;
  transition: width 0.6s cubic-bezier(0.4,0,0.2,1);
}

/* ── FLAG ITEM ───────────────────────────────────────────────────── */
.flag-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 11px 14px;
  background: rgba(239,68,68,0.07);
  border: 1px solid rgba(239,68,68,0.18);
  border-left: 3px solid var(--tier-critical);
  border-radius: var(--radius-md);
  margin-bottom: 8px;
  font-size: 13px;
  color: #FCA5A5;
  line-height: 1.5;
}

.flag-icon {
  flex-shrink: 0;
  margin-top: 1px;
  color: var(--tier-critical);
  font-size: 14px;
}

/* ── NEXT STEP ITEM ──────────────────────────────────────────────── */
.step-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 9px 14px;
  background: rgba(59,130,246,0.06);
  border: 1px solid rgba(59,130,246,0.14);
  border-radius: var(--radius-md);
  margin-bottom: 7px;
  font-size: 13px;
  color: #93C5FD;
  line-height: 1.5;
}

.step-num {
  flex-shrink: 0;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: rgba(59,130,246,0.2);
  color: var(--accent-blue);
  font-size: 10px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-top: 1px;
}

/* ── SOAP NOTE VIEWER ────────────────────────────────────────────── */
.soap-viewer {
  background: var(--bg-base);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  padding: 28px 32px;
  font-size: 13.5px;
  line-height: 1.8;
  color: var(--text-primary);
  min-height: 300px;
}

.soap-section-header {
  font-size: 10.5px;
  font-weight: 700;
  letter-spacing: 1px;
  text-transform: uppercase;
  color: var(--accent-blue);
  margin-top: 22px;
  margin-bottom: 8px;
  padding-bottom: 6px;
  border-bottom: 1px solid var(--border-subtle);
}

.soap-section-header:first-child { margin-top: 0; }

/* ── EHR SIGN-OFF CARD ───────────────────────────────────────────── */
.signoff-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 14px 20px;
  background: var(--bg-elevated);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  margin-top: 16px;
}

.signoff-meta {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.signoff-meta-label {
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.6px;
  text-transform: uppercase;
  color: var(--text-muted);
}

.signoff-meta-value {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary);
  font-family: var(--font-mono);
}

/* ── SIDEBAR OVERRIDES ───────────────────────────────────────────── */
section[data-testid="stSidebar"] {
  background: var(--bg-surface) !important;
  border-right: 1px solid var(--border-subtle) !important;
}

section[data-testid="stSidebar"] .sidebar-label {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.8px;
  text-transform: uppercase;
  color: var(--text-muted);
  margin-bottom: 12px;
  display: block;
}

/* ── INPUT OVERRIDES ─────────────────────────────────────────────── */
.stTextInput > div > div > input,
.stTextArea > div > div > textarea,
.stSelectbox > div > div > div {
  background: var(--bg-elevated) !important;
  border: 1px solid var(--border-default) !important;
  border-radius: var(--radius-md) !important;
  color: var(--text-primary) !important;
  font-size: 13px !important;
}

.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {
  border-color: var(--accent-blue) !important;
  box-shadow: 0 0 0 3px rgba(59,130,246,0.15) !important;
}

/* ── BUTTON OVERRIDES ────────────────────────────────────────────── */
.stButton > button[kind="primary"] {
  background: var(--accent-blue) !important;
  color: #fff !important;
  border: none !important;
  border-radius: var(--radius-md) !important;
  font-weight: 600 !important;
  font-size: 13.5px !important;
  height: 42px !important;
  transition: all var(--transition) !important;
  box-shadow: 0 0 0 0 rgba(59,130,246,0.4) !important;
}

.stButton > button[kind="primary"]:hover {
  background: var(--accent-blue-dim) !important;
  box-shadow: 0 0 0 4px rgba(59,130,246,0.2) !important;
  transform: translateY(-1px) !important;
}

.stButton > button[kind="secondary"] {
  background: var(--bg-elevated) !important;
  color: var(--text-primary) !important;
  border: 1px solid var(--border-default) !important;
  border-radius: var(--radius-md) !important;
  font-weight: 500 !important;
  font-size: 13px !important;
  height: 42px !important;
}

.stButton > button[kind="secondary"]:hover {
  border-color: var(--border-strong) !important;
  background: var(--bg-hover) !important;
}

.stButton > button:disabled {
  background: var(--bg-elevated) !important;
  color: var(--text-muted) !important;
  border-color: var(--border-subtle) !important;
  cursor: not-allowed !important;
}

/* ── TAB OVERRIDES ───────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
  background: transparent !important;
  border-bottom: 1px solid var(--border-subtle) !important;
  gap: 0 !important;
  padding: 0 !important;
}

.stTabs [data-baseweb="tab"] {
  background: transparent !important;
  color: var(--text-muted) !important;
  font-size: 13px !important;
  font-weight: 500 !important;
  padding: 10px 18px !important;
  border-bottom: 2px solid transparent !important;
  border-radius: 0 !important;
  transition: all var(--transition) !important;
}

.stTabs [data-baseweb="tab"]:hover {
  color: var(--text-secondary) !important;
  background: var(--bg-hover) !important;
}

.stTabs [aria-selected="true"] {
  color: var(--text-primary) !important;
  border-bottom: 2px solid var(--accent-blue) !important;
}

.stTabs [data-baseweb="tab-panel"] {
  padding: 20px 0 0 !important;
}

/* ── RADIO / TOGGLE ──────────────────────────────────────────────── */
.stRadio > label {
  color: var(--text-secondary) !important;
  font-size: 13px !important;
}

/* ── INFO / ERROR / SUCCESS ──────────────────────────────────────── */
.stAlert {
  border-radius: var(--radius-md) !important;
  font-size: 13px !important;
}

.element-container .stAlert[data-baseweb="notification"] {
  background: var(--bg-elevated) !important;
}

/* ── SPINNER ─────────────────────────────────────────────────────── */
.stSpinner > div {
  border-color: var(--accent-blue) transparent transparent transparent !important;
}

/* ── DIVIDER ─────────────────────────────────────────────────────── */
hr {
  border-color: var(--border-subtle) !important;
  margin: 20px 0 !important;
}

/* ── DOWNLOAD BUTTON ─────────────────────────────────────────────── */
.stDownloadButton > button {
  background: var(--bg-elevated) !important;
  color: var(--text-primary) !important;
  border: 1px solid var(--border-default) !important;
  border-radius: var(--radius-md) !important;
  font-weight: 500 !important;
  font-size: 13px !important;
  height: 42px !important;
}

.stDownloadButton > button:hover {
  border-color: var(--accent-blue) !important;
  color: var(--accent-blue) !important;
}

/* ── EXAM TAB PANELS ─────────────────────────────────────────────── */
.exam-tab-label {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.5px;
  text-transform: uppercase;
  color: var(--text-muted);
  margin-bottom: 8px;
  display: block;
}

/* ── PROCESSING PIPELINE INDICATOR ──────────────────────────────── */
.pipeline-stage {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 0;
  font-size: 12px;
  color: var(--text-muted);
}

.pipeline-stage .stage-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--border-default);
  flex-shrink: 0;
}

.pipeline-stage.active .stage-dot {
  background: var(--accent-blue);
  box-shadow: 0 0 8px rgba(59,130,246,0.5);
  animation: pulse-dot 1.2s ease-in-out infinite;
}

.pipeline-stage.done .stage-dot {
  background: var(--accent-emerald);
}

.pipeline-stage.active {
  color: var(--text-secondary);
}

.pipeline-connector {
  width: 1px;
  height: 12px;
  background: var(--border-subtle);
  margin-left: 3.5px;
}

/* ── METRIC CHIP ─────────────────────────────────────────────────── */
.metric-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 4px 10px;
  background: var(--bg-elevated);
  border: 1px solid var(--border-subtle);
  border-radius: 99px;
  font-size: 11.5px;
  color: var(--text-secondary);
  font-family: var(--font-mono);
}

.metric-chip .chip-label {
  color: var(--text-muted);
  font-family: -apple-system, sans-serif;
  font-size: 11px;
}

/* ── EMPTY STATE ─────────────────────────────────────────────────── */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px 24px;
  text-align: center;
  gap: 12px;
}

.empty-state-icon {
  font-size: 28px;
  opacity: 0.3;
}

.empty-state-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-secondary);
}

.empty-state-body {
  font-size: 12.5px;
  color: var(--text-muted);
  line-height: 1.6;
  max-width: 280px;
}

/* ── CLEAR ALL ───────────────────────────────────────────────────── */
.stCaption { color: var(--text-muted) !important; font-size: 11.5px !important; }
label[data-testid="stWidgetLabel"] { color: var(--text-secondary) !important; font-size: 12.5px !important; }
p { color: var(--text-secondary) !important; }
</style>
""", unsafe_allow_html=True)


# =====================================================================
# 3. SIDEBAR — CONFIGURATION (COLLAPSED BY DEFAULT)
# =====================================================================
with st.sidebar:
    st.markdown('<span class="sidebar-label">API Credentials</span>', unsafe_allow_html=True)

    has_cloud_groq = "groq_api_key" in st.secrets
    has_cloud_gemini = "gemini_api_key" in st.secrets

    groq_input = st.text_input(
        "Groq API Key",
        type="password",
        placeholder="🔒 Loaded from vault" if has_cloud_groq else "sk-...",
        label_visibility="visible"
    )
    gemini_input = st.text_input(
        "Gemini API Key",
        type="password",
        placeholder="🔒 Loaded from vault" if has_cloud_gemini else "AI...",
        label_visibility="visible"
    )

    groq_api_key = groq_input if groq_input.strip() else st.secrets.get("groq_api_key", "")
    gemini_api_key = gemini_input if gemini_input.strip() else st.secrets.get("gemini_api_key", "")

    if (has_cloud_groq or has_cloud_gemini) and not (groq_input or gemini_input):
        st.caption("✓ Vault credentials active — ready to run.")

    st.divider()
    st.markdown('<span class="sidebar-label">Clinical Context</span>', unsafe_allow_html=True)

    specialty_profile = st.selectbox(
        "Specialty",
        [
            "Cardiology Clinic",
            "General Internal Medicine",
            "Emergency Trauma",
            "Neurology",
            "Pediatrics",
            "Orthopedic Surgery",
            "Psychiatry & Behavioral Health",
            "Oncology"
        ],
        label_visibility="collapsed"
    )
    target_language = st.selectbox(
        "Input Language",
        ["Mixed (Multi-lingual Code-Switching)", "English (US/UK)", "Arabic (Khaleeji/MSA)"],
        label_visibility="collapsed"
    )

    st.divider()
    st.markdown('<span class="sidebar-label">Pipeline</span>', unsafe_allow_html=True)
    st.markdown("""
    <div class="pipeline-stage done"><div class="stage-dot"></div> STT Ingestion</div>
    <div class="pipeline-connector"></div>
    <div class="pipeline-stage done"><div class="stage-dot"></div> Entity Extraction</div>
    <div class="pipeline-connector"></div>
    <div class="pipeline-stage done"><div class="stage-dot"></div> Salience Weighting</div>
    <div class="pipeline-connector"></div>
    <div class="pipeline-stage done"><div class="stage-dot"></div> Safety Filtering</div>
    <div class="pipeline-connector"></div>
    <div class="pipeline-stage done"><div class="stage-dot"></div> SOAP Compilation</div>
    """, unsafe_allow_html=True)


# =====================================================================
# 4. HEADER BAR
# =====================================================================
urgency_tier = st.session_state.classification.get("urgency_tier", "")
has_results = bool(st.session_state.transcript)

if st.session_state.chart_locked:
    status_html = '<div class="os-status-pill locked"><div class="os-dot"></div>Chart Signed</div>'
elif has_results:
    status_html = '<div class="os-status-pill active"><div class="os-dot pulse"></div>Review Pending</div>'
else:
    status_html = '<div class="os-status-pill ready"><div class="os-dot pulse"></div>Ready</div>'

st.markdown(f"""
<div class="os-header">
  <div class="os-header-left">
    <div class="os-wordmark">SALIENCE<span> OS</span></div>
    <div class="os-divider-vert"></div>
    <div class="os-specialty-badge">{specialty_profile}</div>
    {('<div class="os-divider-vert"></div><div class="os-specialty-badge" style="color:var(--tier-' + urgency_tier.lower() + ');border-color:rgba(255,255,255,0.1)">' + urgency_tier + '</div>') if urgency_tier else ''}
  </div>
  <div class="os-header-right">
    {status_html}
    <div class="os-timestamp">{datetime.now().strftime('%H:%M')}</div>
  </div>
</div>
""", unsafe_allow_html=True)

# Spacer below fixed header
st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)


# =====================================================================
# 5. INPUT WORKSPACE
# =====================================================================
with st.container():
    col_input, col_exam = st.columns([1, 1], gap="large")

    # ── Left: Data Capture ──────────────────────────────────────────
    with col_input:
        st.markdown('<div class="section-label">Consultation Input</div>', unsafe_allow_html=True)

        input_vector = st.radio(
            "Input mode",
            [
                "Text / Paste Transcript",
                "Live Audio (Microphone)",
                "File Upload (.wav / .mp3 / .json)"
            ],
            horizontal=False,
            label_visibility="collapsed"
        )

        temp_audio_filename = "active_stream_input.wav"
        has_valid_audio_payload = False
        bypass_audio_stt = False
        injected_text_payload = ""

        if "Text" in input_vector:
            injected_text_payload = st.text_area(
                "Paste transcript or clinical notes:",
                placeholder="Paste consultation transcript, patient notes, or test data here…",
                height=180,
                label_visibility="collapsed"
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
                label_visibility="collapsed"
            )
            if uploaded_file is not None:
                if uploaded_file.name.endswith('.json'):
                    try:
                        json_data = json.load(uploaded_file)
                        if isinstance(json_data, list):
                            st.caption(f"Dataset loaded — {len(json_data)} cases")
                            case_idx = st.number_input("Case index", min_value=0, max_value=len(json_data)-1, value=0)
                            selected_node = json_data[case_idx]
                            injected_text_payload = selected_node.get("input", selected_node.get("instruction", ""))
                            if injected_text_payload:
                                st.info(injected_text_payload[:220] + ("…" if len(injected_text_payload) > 220 else ""))
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

    # ── Right: Physical Exam ────────────────────────────────────────
    with col_exam:
        st.markdown('<div class="section-label">Physical Examination</div>', unsafe_allow_html=True)
        st.caption("Add examination findings per system — merged with transcript during analysis.")

        organ_system_tabs = st.tabs(["Thoracic", "GI / Abdomen", "Neuro / Reflex", "Musculoskeletal"])
        with organ_system_tabs[0]:
            notes_thoracic = st.text_area(
                "Thoracic",
                value="Cardiovascular: Tachycardic, rhythm regular. S1 and S2 distinct, no audible murmurs, rubs, or gallops. Significant chest wall diaphoresis noted; patient actively clutching retrosternal area. Respiratory: Tachypneic, shallow respirations. Lungs clear to auscultation bilaterally (CTAB) with no wheezing, rales, or rhonchi.",
                height=130,
                label_visibility="collapsed"
            )
        with organ_system_tabs[1]:
            notes_abdominal = st.text_area(
                "GI",
                value="Abdomen soft, symmetric, and non-distended. Bowel sounds active in all 4 quadrants. No localized tenderness, guarding, or rebound to light/deep palpation. No hepatosplenomegaly. Epigastric region non-tender.",
                height=130,
                label_visibility="collapsed"
            )
        with organ_system_tabs[2]:
            notes_neuro = st.text_area(
                "Neuro",
                value="Patient alert and oriented to person, place, and time (A&Ox3). Pupils equal, round, and reactive to light (PEERRLA). Observable orthostatic lightheadedness and profound dizziness upon lifting head off the examination bed. Gross motor and sensory function intact.",
                height=130,
                label_visibility="collapsed"
            )
        with organ_system_tabs[3]:
            notes_ortho = st.text_area(
                "MSK",
                value="Mild focal tenderness noted over the lumbar paraspinal muscles. Left shoulder and left mandibular jaw display full passive range of motion with zero localized joint or bone tenderness.",
                height=130,
                label_visibility="collapsed"
            )

compiled_examination_overlay = f"""
- Thoracic Tracking Overlay: {notes_thoracic if notes_thoracic else 'Deferred/Normal checks confirmed'}
- GI/Abdominal Tracking Overlay: {notes_abdominal if notes_abdominal else 'Deferred/Normal checks confirmed'}
- Reflex/Neuro Tracking Overlay: {notes_neuro if notes_neuro else 'Deferred/Normal checks confirmed'}
- Musculoskeletal Tracking Overlay: {notes_ortho if notes_ortho else 'Deferred/Normal checks confirmed'}
"""


# =====================================================================
# 6. ANALYSIS TRIGGER
# =====================================================================
st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

if has_valid_audio_payload:
    run_col, _ = st.columns([1, 2])
    with run_col:
        run_pipeline = st.button(
            "⬡  Analyse Consultation",
            type="primary",
            use_container_width=True
        )
else:
    st.markdown("""
    <div class="empty-state">
      <div class="empty-state-icon">⬡</div>
      <div class="empty-state-title">No input provided</div>
      <div class="empty-state-body">Paste a transcript, record audio, or upload a file to begin clinical analysis.</div>
    </div>
    """, unsafe_allow_html=True)
    run_pipeline = False


# =====================================================================
# 7. PIPELINE EXECUTION
# =====================================================================
if has_valid_audio_payload and run_pipeline:
    if not groq_api_key or not gemini_api_key:
        st.error("API credentials required. Open the sidebar (⚙) to configure.")
    else:
        pipeline_start_checkpoint = time.time()
        with st.spinner("Running clinical intelligence pipeline…"):
            try:
                # STAGE 1: Transcription
                if bypass_audio_stt:
                    extracted_raw_text = injected_text_payload
                else:
                    raw_audio = AudioSegment.from_file(temp_audio_filename)
                    processed_audio = raw_audio.set_channels(1).set_frame_rate(16000)
                    compressed_filename = "optimized_api_payload.mp3"
                    processed_audio.export(compressed_filename, format="mp3", bitrate="64k")
                    groq_client = Groq(api_key=groq_api_key, timeout=60.0)
                    with open(compressed_filename, "rb") as audio_binary:
                        extracted_raw_text = groq_client.audio.transcriptions.create(
                            file=(compressed_filename, audio_binary.read()),
                            model="whisper-large-v3",
                            response_format="text"
                        )
                    if os.path.exists(temp_audio_filename): os.remove(temp_audio_filename)
                    if os.path.exists(compressed_filename): os.remove(compressed_filename)

                # STAGE 2: Gemini Intelligence
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
                    generation_config={"response_mime_type": "application/json"}
                )

                parsed_payload = json.loads(response_package.text, strict=False)

                st.session_state.transcript = parsed_payload.get("cleaned_transcript", "")
                st.session_state.classification = parsed_payload.get("classification", {})
                st.session_state.salience_map = parsed_payload.get("salience_weight_map", [])
                st.session_state.soap_note = parsed_payload.get("structured_soap_chart", "")
                st.session_state.flags = parsed_payload.get("clinical_safety_red_flags", [])
                st.session_state.next_steps = parsed_payload.get("suggested_next_steps", [])
                st.session_state.pipeline_execution_time = round(time.time() - pipeline_start_checkpoint, 2)
                st.session_state.chart_locked = False
                st.rerun()

            except Exception as e:
                st.error(f"Pipeline error: {e}")


# =====================================================================
# 8. RESULTS WORKSPACE
# =====================================================================
if st.session_state.transcript:
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    st.markdown('<div class="section-label">Clinical Intelligence Output</div>', unsafe_allow_html=True)

    # ── Urgency Banner ──────────────────────────────────────────────
    classification = st.session_state.classification
    urgency = classification.get("urgency_tier", "MEDIUM")
    trigger = classification.get("primary_clinical_trigger", "")

    st.markdown(f"""
    <div class="urgency-bar {urgency}">
      <div>
        <div class="urgency-label">{urgency} Priority</div>
        <div class="urgency-text">{trigger}</div>
      </div>
      <div style="margin-left:auto;display:flex;gap:10px;flex-shrink:0">
        <span class="metric-chip"><span class="chip-label">Signals</span>{len(st.session_state.salience_map)}</span>
        <span class="metric-chip"><span class="chip-label">Flags</span>{len(st.session_state.flags)}</span>
        <span class="metric-chip"><span class="chip-label">Time</span>{st.session_state.pipeline_execution_time}s</span>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Output Tabs ─────────────────────────────────────────────────
    output_tabs = st.tabs([
        "Clinical Signals",
        "Safety Flags",
        "Next Steps",
        "SOAP Note",
        "Explainability"
    ])

    # ── Tab 1: Salience Map ─────────────────────────────────────────
    with output_tabs[0]:
        if st.session_state.salience_map:
            # Sort by salience score descending
            sorted_signals = sorted(
                st.session_state.salience_map,
                key=lambda x: x.get("salience_score", 0),
                reverse=True
            )
            for item in sorted_signals:
                score = item.get("salience_score", 0.0)
                entity = item.get("entity", "")
                category = item.get("category", "")
                reasoning = item.get("reasoning_context", "")

                if score >= 0.85:
                    ring_class = "score-critical"
                    bar_color = "var(--tier-critical)"
                elif score >= 0.70:
                    ring_class = "score-high"
                    bar_color = "var(--tier-high)"
                elif score >= 0.50:
                    ring_class = "score-medium"
                    bar_color = "var(--tier-medium)"
                else:
                    ring_class = "score-low"
                    bar_color = "var(--tier-low)"

                bar_pct = int(score * 100)

                st.markdown(f"""
                <div class="signal-row">
                  <div class="signal-score-ring {ring_class}">{bar_pct}</div>
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
        # Render SOAP with section headers highlighted
        soap_raw = st.session_state.soap_note
        soap_lines = soap_raw.split("\n")
        rendered_lines = []
        for line in soap_lines:
            stripped = line.strip()
            if stripped.startswith("###"):
                header = stripped.replace("###", "").strip().rstrip(":")
                rendered_lines.append(f'<div class="soap-section-header">{header}</div>')
            elif stripped.startswith("**") and stripped.endswith("**"):
                bold_text = stripped.replace("**", "").strip()
                rendered_lines.append(f'<strong style="color:var(--text-primary);font-size:13.5px">{bold_text}</strong><br>')
            elif stripped:
                rendered_lines.append(f'<p style="margin:2px 0;color:var(--text-secondary);font-size:13.5px;line-height:1.8">{stripped}</p>')
            else:
                rendered_lines.append('<div style="height:8px"></div>')

        soap_html = "".join(rendered_lines)
        st.markdown(f'<div class="soap-viewer">{soap_html}</div>', unsafe_allow_html=True)

        # Sign-off bar
        st.markdown(f"""
        <div class="signoff-bar">
          <div class="signoff-meta">
            <span class="signoff-meta-label">Generated</span>
            <span class="signoff-meta-value">{datetime.now().strftime('%Y-%m-%d %H:%M')}</span>
          </div>
          <div class="signoff-meta">
            <span class="signoff-meta-label">Specialty</span>
            <span class="signoff-meta-value">{specialty_profile}</span>
          </div>
          <div class="signoff-meta">
            <span class="signoff-meta-label">Status</span>
            <span class="signoff-meta-value" style="color:{'var(--accent-violet)' if st.session_state.chart_locked else 'var(--accent-amber)'}">
              {'Signed & Locked' if st.session_state.chart_locked else 'Pending Review'}
            </span>
          </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

        action_col1, action_col2 = st.columns(2)
        with action_col1:
            try:
                pdf_binary = generate_clinical_pdf(st.session_state.soap_note, specialty_profile)
                st.download_button(
                    label="↓  Export Clinical PDF",
                    data=pdf_binary,
                    file_name=f"SalienceOS_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
            except Exception as pdf_err:
                st.error(f"PDF error: {pdf_err}")

        with action_col2:
            if st.session_state.chart_locked:
                st.button("✓  Synced to FHIR Network", disabled=True, use_container_width=True)
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
                reverse=True
            )
            for idx, item in enumerate(sorted_exp, 1):
                entity = item.get("entity", "")
                score = item.get("salience_score", 0.0)
                reasoning = item.get("reasoning_context", "")
                category = item.get("category", "")

                score_pct = int(score * 100)
                if score >= 0.85:
                    score_color = "var(--tier-critical)"
                elif score >= 0.70:
                    score_color = "var(--tier-high)"
                elif score >= 0.50:
                    score_color = "var(--tier-medium)"
                else:
                    score_color = "var(--tier-low)"

                st.markdown(f"""
                <div class="signal-row" style="padding:12px 6px">
                  <div style="flex-shrink:0;width:28px;font-size:11px;font-family:var(--font-mono);color:var(--text-muted);text-align:right;padding-top:2px">
                    {idx:02d}
                  </div>
                  <div class="signal-body">
                    <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">
                      <span class="signal-entity">{entity}</span>
                      <span class="signal-category-chip">{category}</span>
                      <span style="margin-left:auto;font-size:12px;font-weight:700;font-family:var(--font-mono);color:{score_color}">{score_pct}%</span>
                    </div>
                    <div class="signal-reasoning">{reasoning}</div>
                    <div class="signal-bar-track" style="margin-top:8px">
                      <div class="signal-bar-fill" style="width:{score_pct}%;background:{score_color}"></div>
                    </div>
                  </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.markdown('<div class="empty-state"><div class="empty-state-title">No reasoning data available</div></div>', unsafe_allow_html=True)
