# SYSTEM HOTFIX: Bridge Python 3.13+ audioop removal for pydub stability
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
import streamlit.components.v1 as components
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
# 0. PDF UTILITIES
# =====================================================================
def sanitize_for_pdf(text):
    if not text:
        return ""
    char_map = {
        "•": "-", "—": "-", "–": "-", "\u201c": '"', "\u201d": '"',
        "\u2018": "'", "\u2019": "'", "™": "TM", "©": "(c)", "®": "(r)"
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
    pdf.cell(210, 12, "SALIENCE OS | CLINICAL NOTE", ln=True, align="C")
    pdf.set_font("Helvetica", "I", 10)
    pdf.cell(210, 5, sanitize_for_pdf(
        f"Specialty: {specialty} | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
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
            sanitized = line_clean.replace("**", "").replace("*", "-")
            pdf.multi_cell(effective_width, 6, sanitize_for_pdf(sanitized))
    return bytes(pdf.output())


# =====================================================================
# 1. PAGE CONFIG
# =====================================================================
st.set_page_config(
    page_title="Salience OS",
    layout="wide",
    initial_sidebar_state="collapsed"
)


# =====================================================================
# 2. SESSION STATE
# =====================================================================
defaults = {
    "transcript": "",
    "classification": {},
    "salience_map": [],
    "soap_note": "",
    "flags": [],
    "next_steps": [],
    "pipeline_execution_time": 0.0,
    "chart_locked": False,
    "show_settings": False,
    "focus_mode": False,
    "specialty": "Cardiology Clinic",
    "language": "Mixed (Multi-lingual Code-Switching)",
    "theme": "system",
    "setup_done": False,
    "groq_key_override": "",
    "gemini_key_override": "",
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


# =====================================================================
# 3. THEME ENGINE
# =====================================================================
components.html(f"""
<script>
(function(){{
  const stored = '{st.session_state.theme}';
  const root = window.parent.document.documentElement;
  if (stored === 'system') {{
    root.setAttribute('data-salience-theme',
      window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
  }} else {{
    root.setAttribute('data-salience-theme', stored);
  }}
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', e => {{
    if ('{st.session_state.theme}' === 'system')
      root.setAttribute('data-salience-theme', e.matches ? 'dark' : 'light');
  }});
}})();
</script>
""", height=0, scrolling=False)


# =====================================================================
# 4. DESIGN SYSTEM CSS
# =====================================================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap');

:root,
html[data-salience-theme="light"] {
    --s-bg-base:          #F7F8FA;
    --s-bg-surface:       #FFFFFF;
    --s-bg-subtle:        #F0F2F5;
    --s-bg-hover:         rgba(0,0,0,0.04);
    --s-border:           rgba(0,0,0,0.08);
    --s-border-strong:    rgba(0,0,0,0.14);
    --s-border-focus:     #3B82F6;
    --s-text-primary:     #0D1117;
    --s-text-secondary:   #4B5563;
    --s-text-tertiary:    #9CA3AF;
    --s-text-inverse:     #FFFFFF;
    --s-critical-bg:      #FEF2F2;
    --s-critical-border:  #FECACA;
    --s-critical-rail:    #DC2626;
    --s-critical-text:    #7F1D1D;
    --s-critical-label:   #991B1B;
    --s-critical-glow:    rgba(220,38,38,0.18);
    --s-critical-pulse:   rgba(220,38,38,0.08);
    --s-high-bg:          #FFFBEB;
    --s-high-border:      #FDE68A;
    --s-high-rail:        #D97706;
    --s-high-text:        #78350F;
    --s-high-label:       #92400E;
    --s-medium-bg:        #EFF6FF;
    --s-medium-border:    #BFDBFE;
    --s-medium-rail:      #2563EB;
    --s-medium-text:      #1E3A5F;
    --s-medium-label:     #1D4ED8;
    --s-info-bg:          #F0FDF4;
    --s-info-border:      #BBF7D0;
    --s-info-rail:        #16A34A;
    --s-info-text:        #14532D;
    --s-info-label:       #15803D;
    --s-bar-critical:     #DC2626;
    --s-bar-high:         #D97706;
    --s-bar-low:          #16A34A;
    --s-transition:       background 0.2s ease, color 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
    --s-font-ui:          'IBM Plex Sans', system-ui, sans-serif;
    --s-font-mono:        'IBM Plex Mono', 'SF Mono', monospace;
}

html[data-salience-theme="dark"] {
    --s-bg-base:          #0A0C10;
    --s-bg-surface:       #111318;
    --s-bg-subtle:        #1F222A;
    --s-bg-hover:         rgba(255,255,255,0.05);
    --s-border:           rgba(255,255,255,0.08);
    --s-border-strong:    rgba(255,255,255,0.14);
    --s-border-focus:     #60A5FA;
    --s-text-primary:     #F1F5F9;
    --s-text-secondary:   #94A3B8;
    --s-text-tertiary:    #475569;
    --s-text-inverse:     #0D1117;
    --s-critical-bg:      rgba(220,38,38,0.12);
    --s-critical-border:  rgba(220,38,38,0.35);
    --s-critical-rail:    #EF4444;
    --s-critical-text:    #FCA5A5;
    --s-critical-label:   #F87171;
    --s-critical-glow:    rgba(239,68,68,0.25);
    --s-critical-pulse:   rgba(239,68,68,0.10);
    --s-high-bg:          rgba(217,119,6,0.10);
    --s-high-border:      rgba(217,119,6,0.35);
    --s-high-rail:        #F59E0B;
    --s-high-text:        #FCD34D;
    --s-high-label:       #FBBF24;
    --s-medium-bg:        rgba(37,99,235,0.12);
    --s-medium-border:    rgba(37,99,235,0.35);
    --s-medium-rail:      #60A5FA;
    --s-medium-text:      #BFDBFE;
    --s-medium-label:     #93C5FD;
    --s-info-bg:          rgba(22,163,74,0.10);
    --s-info-border:      rgba(22,163,74,0.30);
    --s-info-rail:        #34D399;
    --s-info-text:        #A7F3D0;
    --s-info-label:       #6EE7B7;
    --s-bar-critical:     #EF4444;
    --s-bar-high:         #F59E0B;
    --s-bar-low:          #34D399;
}

html, body,
[data-testid="stAppViewContainer"],
[data-testid="stMain"],
.main, .block-container {
    font-family: var(--s-font-ui) !important;
    background: var(--s-bg-base) !important;
    color: var(--s-text-primary) !important;
    transition: var(--s-transition);
}

/* Hide ALL Streamlit chrome including sidebar toggle */
#MainMenu, footer, header,
[data-testid="stDecoration"],
[data-testid="stToolbar"],
[data-testid="collapsedControl"],
section[data-testid="stSidebar"] {
    display: none !important;
    visibility: hidden !important;
}

.block-container {
    padding: 0 !important;
    max-width: 100% !important;
}

/* Top bar */
.s-topbar {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 0 24px;
    height: 52px;
    background: var(--s-bg-surface);
    border-bottom: 1px solid var(--s-border);
    position: sticky;
    top: 0;
    z-index: 100;
    transition: var(--s-transition);
}
.s-logo {
    font-family: var(--s-font-ui);
    font-size: 14px;
    font-weight: 600;
    color: var(--s-text-primary);
    letter-spacing: 0.2px;
    flex-shrink: 0;
}
.s-logo span { opacity: 0.35; font-weight: 400; }
.s-spacer { flex: 1; }
.s-spec-badge {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    font-size: 11px;
    font-weight: 500;
    color: var(--s-text-secondary);
    background: var(--s-bg-subtle);
    border: 1px solid var(--s-border);
    padding: 4px 10px;
    border-radius: 20px;
    white-space: nowrap;
}
.s-topbar-actions {
    display: flex;
    align-items: center;
    gap: 4px;
}
.s-icon-btn {
    width: 32px;
    height: 32px;
    border-radius: 8px;
    border: 1px solid var(--s-border);
    background: transparent;
    color: var(--s-text-secondary);
    display: inline-flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    font-size: 14px;
    transition: all 0.15s ease;
}
.s-icon-btn:hover {
    background: var(--s-bg-subtle);
    border-color: var(--s-border-strong);
    color: var(--s-text-primary);
}
.s-icon-btn:focus-visible {
    outline: 2px solid var(--s-border-focus);
    outline-offset: 2px;
}
.s-icon-btn.active {
    background: var(--s-text-primary);
    color: var(--s-text-inverse);
    border-color: transparent;
}
.s-settings-btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    height: 32px;
    padding: 0 12px;
    border-radius: 8px;
    border: 1px solid var(--s-border);
    background: transparent;
    color: var(--s-text-secondary);
    font-size: 12px;
    font-weight: 500;
    font-family: var(--s-font-ui);
    cursor: pointer;
    transition: all 0.15s ease;
    white-space: nowrap;
}
.s-settings-btn:hover {
    background: var(--s-bg-subtle);
    border-color: var(--s-border-strong);
    color: var(--s-text-primary);
}

/* Main content area */
.s-content {
    padding: 20px 24px 48px;
    max-width: 1200px;
    margin: 0 auto;
    transition: var(--s-transition);
}

/* Setup card */
.s-setup-wrap {
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 60vh;
    padding: 40px 24px;
}
.s-setup-card {
    background: var(--s-bg-surface);
    border: 1px solid var(--s-border);
    border-radius: 16px;
    padding: 32px 36px;
    width: 100%;
    max-width: 480px;
    text-align: center;
}
.s-setup-title {
    font-size: 18px;
    font-weight: 600;
    color: var(--s-text-primary);
    margin-bottom: 6px;
}
.s-setup-sub {
    font-size: 13px;
    color: var(--s-text-secondary);
    margin-bottom: 24px;
    line-height: 1.6;
}

/* Settings drawer overlay */
.s-drawer-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0,0,0,0.25);
    z-index: 200;
    display: flex;
    justify-content: flex-end;
}
.s-drawer {
    width: 340px;
    height: 100%;
    background: var(--s-bg-surface);
    border-left: 1px solid var(--s-border);
    display: flex;
    flex-direction: column;
    overflow-y: auto;
}
.s-drawer-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 20px;
    border-bottom: 1px solid var(--s-border);
    flex-shrink: 0;
}
.s-drawer-title {
    font-size: 13px;
    font-weight: 600;
    color: var(--s-text-primary);
}
.s-drawer-body { padding: 20px; flex: 1; }
.s-drawer-section { margin-bottom: 22px; }
.s-drawer-label {
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.8px;
    text-transform: uppercase;
    color: var(--s-text-tertiary);
    margin-bottom: 8px;
    display: block;
}
.s-theme-row {
    display: flex;
    gap: 6px;
}
.s-theme-opt {
    flex: 1;
    padding: 8px 0;
    border-radius: 8px;
    border: 1px solid var(--s-border);
    background: var(--s-bg-subtle);
    color: var(--s-text-secondary);
    font-size: 12px;
    font-weight: 500;
    font-family: var(--s-font-ui);
    cursor: pointer;
    text-align: center;
    transition: all 0.15s ease;
}
.s-theme-opt:hover { border-color: var(--s-border-strong); color: var(--s-text-primary); }
.s-theme-opt.active {
    background: var(--s-text-primary);
    color: var(--s-text-inverse);
    border-color: transparent;
}
.s-vault-note {
    background: var(--s-info-bg);
    border: 1px solid var(--s-info-border);
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 11px;
    color: var(--s-info-text);
    line-height: 1.5;
}

/* Urgency banners */
.alert-shell {
    display: flex;
    border-radius: 10px;
    overflow: hidden;
    margin-bottom: 16px;
    border: 1px solid;
    transition: var(--s-transition);
}
.alert-rail { width: 4px; flex-shrink: 0; }
.alert-body { flex: 1; padding: 12px 14px; }
.alert-tier {
    font-family: var(--s-font-ui);
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.9px;
    text-transform: uppercase;
    margin-bottom: 3px;
}
.alert-desc { font-size: 13px; line-height: 1.55; }
.alert-critical {
    background: var(--s-critical-bg);
    border-color: var(--s-critical-border);
    animation: criticalPulse 2.4s ease-in-out infinite;
}
.alert-critical .alert-rail  { background: var(--s-critical-rail); }
.alert-critical .alert-tier  { color: var(--s-critical-label); }
.alert-critical .alert-desc  { color: var(--s-critical-text); }
@keyframes criticalPulse {
    0%,100% { box-shadow: 0 0 0 1px var(--s-critical-border), 0 4px 16px var(--s-critical-glow); }
    50%      { box-shadow: 0 0 0 1px var(--s-critical-border), 0 4px 28px var(--s-critical-glow), 0 0 0 4px var(--s-critical-pulse); }
}
.alert-high { background: var(--s-high-bg); border-color: var(--s-high-border); }
.alert-high .alert-rail  { background: var(--s-high-rail); }
.alert-high .alert-tier  { color: var(--s-high-label); }
.alert-high .alert-desc  { color: var(--s-high-text); }
.alert-medium { background: var(--s-medium-bg); border-color: var(--s-medium-border); }
.alert-medium .alert-rail  { background: var(--s-medium-rail); }
.alert-medium .alert-tier  { color: var(--s-medium-label); }
.alert-medium .alert-desc  { color: var(--s-medium-text); }
.alert-info { background: var(--s-info-bg); border-color: var(--s-info-border); }
.alert-info .alert-rail  { background: var(--s-info-rail); }
.alert-info .alert-tier  { color: var(--s-info-label); }
.alert-info .alert-desc  { color: var(--s-info-text); }

/* Panel header */
.panel-header {
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.9px;
    text-transform: uppercase;
    color: var(--s-text-tertiary);
    margin: 0 0 12px;
}

/* Signal rows */
.signal-row {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 6px;
    border-bottom: 1px solid var(--s-border);
    border-radius: 6px;
    transition: background 0.15s ease;
}
.signal-row:last-child { border-bottom: none; }
.signal-row:hover { background: var(--s-bg-hover); }
.signal-name { font-size: 13px; font-weight: 500; color: var(--s-text-primary); flex: 1; }
.signal-cat  { font-size: 10px; color: var(--s-text-tertiary); }
.signal-score {
    font-family: var(--s-font-mono);
    font-size: 11px;
    color: var(--s-text-secondary);
    width: 30px;
    text-align: right;
}

/* Flag items */
.flag-item {
    display: flex;
    align-items: flex-start;
    gap: 8px;
    background: var(--s-critical-bg);
    border: 1px solid var(--s-critical-border);
    border-left: 4px solid var(--s-critical-rail);
    border-radius: 0 8px 8px 0;
    padding: 9px 12px;
    font-size: 12px;
    color: var(--s-critical-text);
    margin-bottom: 6px;
    line-height: 1.5;
    transition: var(--s-transition);
}
.flag-item::before { content: "⚠"; font-size: 12px; flex-shrink: 0; margin-top: 1px; }

/* Step items */
.step-item {
    font-size: 12px;
    padding: 7px 0;
    border-bottom: 1px solid var(--s-border);
    color: var(--s-text-secondary);
    display: flex;
    gap: 10px;
    align-items: flex-start;
    line-height: 1.5;
    transition: color 0.15s ease;
}
.step-item:hover { color: var(--s-text-primary); }
.step-item:last-child { border-bottom: none; }

/* Explain cards */
.explain-card {
    border: 1px solid var(--s-border);
    border-radius: 9px;
    padding: 11px 14px;
    margin-bottom: 8px;
    background: var(--s-bg-surface);
    transition: var(--s-transition);
}
.explain-card:hover { border-color: var(--s-border-strong); }
.explain-head {
    font-size: 12px;
    font-weight: 600;
    margin-bottom: 4px;
    display: flex;
    align-items: center;
    gap: 7px;
    color: var(--s-text-primary);
}
.explain-body { font-size: 11px; color: var(--s-text-secondary); line-height: 1.65; }
.conf-hi  { color: var(--s-critical-rail); }
.conf-med { color: var(--s-high-rail); }
.conf-lo  { color: var(--s-info-rail); }

/* Focus mode badge */
.focus-badge {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    font-size: 11px;
    font-weight: 500;
    color: var(--s-medium-label);
    background: var(--s-medium-bg);
    border: 1px solid var(--s-medium-border);
    padding: 3px 10px;
    border-radius: 20px;
}

/* Buttons */
[data-testid="stButton"] button {
    font-family: var(--s-font-ui) !important;
    font-size: 13px !important;
    font-weight: 500 !important;
    border-radius: 8px !important;
    border: 1px solid var(--s-border-strong) !important;
    background: var(--s-bg-surface) !important;
    color: var(--s-text-primary) !important;
    transition: all 0.15s ease !important;
}
[data-testid="stButton"] button:hover {
    background: var(--s-bg-subtle) !important;
    transform: translateY(-1px);
    box-shadow: 0 2px 8px rgba(0,0,0,0.07) !important;
}
[data-testid="stButton"] button:active { transform: scale(0.98) !important; }
[data-testid="stButton"] button[kind="primary"] {
    background: var(--s-text-primary) !important;
    color: var(--s-text-inverse) !important;
    border-color: transparent !important;
}
[data-testid="stButton"] button[kind="primary"]:hover { opacity: 0.88 !important; }
[data-testid="stButton"] button:disabled {
    opacity: 0.35 !important;
    cursor: not-allowed !important;
    transform: none !important;
}
[data-testid="stButton"] button:focus-visible {
    outline: 2px solid var(--s-border-focus) !important;
    outline-offset: 2px !important;
}

/* Form elements */
[data-baseweb="select"] > div,
[data-baseweb="input"] > div {
    background: var(--s-bg-surface) !important;
    border-color: var(--s-border) !important;
    border-radius: 8px !important;
    color: var(--s-text-primary) !important;
    font-family: var(--s-font-ui) !important;
    font-size: 13px !important;
    transition: var(--s-transition) !important;
}
[data-baseweb="select"] > div:focus-within,
[data-baseweb="input"] > div:focus-within {
    border-color: var(--s-border-focus) !important;
    box-shadow: 0 0 0 3px rgba(59,130,246,0.15) !important;
}
textarea {
    background: var(--s-bg-surface) !important;
    color: var(--s-text-primary) !important;
    font-family: var(--s-font-mono) !important;
    font-size: 12px !important;
    line-height: 1.75 !important;
    border-radius: 8px !important;
    border-color: var(--s-border) !important;
    transition: var(--s-transition) !important;
}

/* Tabs */
[data-testid="stTabs"] [data-baseweb="tab-list"] {
    background: var(--s-bg-subtle) !important;
    border-radius: 10px !important;
    padding: 3px !important;
    gap: 2px !important;
    border: 1px solid var(--s-border) !important;
}
[data-testid="stTabs"] [data-baseweb="tab"] {
    background: transparent !important;
    border-radius: 8px !important;
    font-family: var(--s-font-ui) !important;
    font-size: 12px !important;
    font-weight: 500 !important;
    color: var(--s-text-secondary) !important;
    padding: 5px 14px !important;
    transition: all 0.15s ease !important;
    border: none !important;
}
[data-testid="stTabs"] [aria-selected="true"] {
    background: var(--s-bg-surface) !important;
    color: var(--s-text-primary) !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08) !important;
}
[data-testid="stTabs"] [data-baseweb="tab-highlight"],
[data-testid="stTabs"] [data-baseweb="tab-border"] { display: none !important; }

/* Metrics */
[data-testid="metric-container"] {
    background: var(--s-bg-surface) !important;
    border-radius: 10px !important;
    padding: 12px 16px !important;
    border: 1px solid var(--s-border) !important;
    transition: var(--s-transition);
}

/* Misc */
hr { border-color: var(--s-border) !important; }
[data-testid="stStatus"] {
    background: var(--s-bg-surface) !important;
    border: 1px solid var(--s-border) !important;
    border-radius: 10px !important;
    font-family: var(--s-font-ui) !important;
}
[data-testid="stCaptionContainer"] p {
    font-size: 11px !important;
    color: var(--s-text-tertiary) !important;
    font-family: var(--s-font-ui) !important;
}
[data-testid="stAlert"] {
    border-radius: 9px !important;
    font-family: var(--s-font-ui) !important;
    font-size: 13px !important;
    border-left-width: 4px !important;
}
[data-testid="stDownloadButton"] button {
    font-family: var(--s-font-ui) !important;
    font-size: 13px !important;
    font-weight: 500 !important;
    background: var(--s-bg-surface) !important;
    border: 1px solid var(--s-border-strong) !important;
    color: var(--s-text-primary) !important;
    border-radius: 8px !important;
    transition: all 0.15s ease !important;
}
[data-testid="stDownloadButton"] button:hover {
    background: var(--s-bg-subtle) !important;
    transform: translateY(-1px);
}
[data-testid="stRadio"] label {
    font-family: var(--s-font-ui) !important;
    font-size: 13px !important;
    color: var(--s-text-secondary) !important;
}
[data-testid="stFileUploader"] {
    border: 1px dashed var(--s-border-strong) !important;
    border-radius: 10px !important;
    background: var(--s-bg-subtle) !important;
}
*:focus-visible {
    outline: 2px solid var(--s-border-focus) !important;
    outline-offset: 2px !important;
}
@media (prefers-reduced-motion: reduce) {
    .alert-critical { animation: none !important; }
    * { transition-duration: 0ms !important; }
}
</style>
""", unsafe_allow_html=True)


# =====================================================================
# 5. HELPERS
# =====================================================================
has_cloud_groq   = "groq_api_key"   in st.secrets
has_cloud_gemini = "gemini_api_key" in st.secrets

def get_groq_key():
    return st.session_state.groq_key_override or st.secrets.get("groq_api_key", "")

def get_gemini_key():
    return st.session_state.gemini_key_override or st.secrets.get("gemini_api_key", "")

SPECIALTIES = [
    "Cardiology Clinic", "General Internal Medicine", "Emergency Trauma",
    "Neurology", "Pediatrics", "Orthopedic Surgery",
    "Psychiatry & Behavioral Health", "Oncology"
]
LANGUAGES = [
    "Mixed (Multi-lingual Code-Switching)",
    "English (US/UK)",
    "Arabic (Khaleeji/MSA)"
]
SPECIALTY_SHORT = {
    "Cardiology Clinic": "Cardiology",
    "General Internal Medicine": "General Medicine",
    "Emergency Trauma": "Emergency",
    "Neurology": "Neurology",
    "Pediatrics": "Pediatrics",
    "Orthopedic Surgery": "Orthopaedics",
    "Psychiatry & Behavioral Health": "Psychiatry",
    "Oncology": "Oncology",
}
THEME_ICONS = {"light": "☀", "dark": "☽", "system": "◑"}


# =====================================================================
# 6. TOP BAR
# =====================================================================
focus = st.session_state.focus_mode
spec_short = SPECIALTY_SHORT.get(st.session_state.specialty, st.session_state.specialty)
theme_icon = THEME_ICONS.get(st.session_state.theme, "◑")

topbar_html = f"""
<div class="s-topbar" role="banner">
  <div class="s-logo">Salience <span>OS</span></div>
  <div class="s-spec-badge">{spec_short}</div>
  <div class="s-spacer"></div>
  <div class="s-topbar-actions">
"""
if not focus:
    topbar_html += f"""
    <button class="s-settings-btn" onclick="window.parent.document.querySelector('[data-testid=\\"stMain\\"]').dispatchEvent(new CustomEvent('salience:settings'))"
      aria-label="Open workspace settings" title="Workspace settings">
      ⚙ Settings
    </button>
    <button class="s-icon-btn" title="Theme: {st.session_state.theme}"
      onclick="window.parent.document.querySelector('[data-testid=\\"stMain\\"]').dispatchEvent(new CustomEvent('salience:theme'))"
      aria-label="Toggle theme">
      {theme_icon}
    </button>
"""
topbar_html += f"""
    <button class="s-icon-btn {'active' if focus else ''}" title="{'Exit focus mode' if focus else 'Focus mode'}"
      onclick="window.parent.document.querySelector('[data-testid=\\"stMain\\"]').dispatchEvent(new CustomEvent('salience:focus'))"
      aria-label="{'Exit focus mode' if focus else 'Enable focus mode'}">
      {'✕' if focus else '⊡'}
    </button>
  </div>
</div>
"""
st.markdown(topbar_html, unsafe_allow_html=True)

# Button actions via hidden Streamlit buttons (the JS dispatches events,
# but we use native st.button for actual state changes below the fold)
tb_col1, tb_col2, tb_col3 = st.columns([1, 1, 1])
with tb_col1:
    if st.button("__settings__", key="tb_settings", label_visibility="collapsed"):
        st.session_state.show_settings = not st.session_state.show_settings
        st.rerun()
with tb_col2:
    if st.button("__theme__", key="tb_theme", label_visibility="collapsed"):
        cycle = {"light": "dark", "dark": "system", "system": "light"}
        st.session_state.theme = cycle.get(st.session_state.theme, "system")
        st.rerun()
with tb_col3:
    if st.button("__focus__", key="tb_focus", label_visibility="collapsed"):
        st.session_state.focus_mode = not st.session_state.focus_mode
        st.rerun()

# Wire top bar buttons to the hidden Streamlit buttons
components.html("""
<script>
(function(){
  function wire(event, btnText) {
    const parent = window.parent.document;
    parent.addEventListener(event, () => {
      const btns = parent.querySelectorAll('[data-testid="stButton"] button');
      for (const b of btns) {
        if (b.textContent.trim() === btnText) { b.click(); break; }
      }
    });
  }
  wire('salience:settings', '__settings__');
  wire('salience:theme',    '__theme__');
  wire('salience:focus',    '__focus__');
})();
</script>
""", height=0, scrolling=False)


# =====================================================================
# 7. SETTINGS DRAWER
# =====================================================================
if st.session_state.show_settings and not focus:
    st.markdown("""
    <div class="s-drawer-overlay" id="drawer-overlay">
      <div class="s-drawer" role="dialog" aria-label="Workspace settings">
        <div class="s-drawer-head">
          <span class="s-drawer-title">Workspace settings</span>
        </div>
        <div class="s-drawer-body">
    """, unsafe_allow_html=True)

    with st.container():
        st.markdown('<span class="s-drawer-label">Specialty profile</span>', unsafe_allow_html=True)
        new_spec = st.selectbox(
            "Specialty",
            SPECIALTIES,
            index=SPECIALTIES.index(st.session_state.specialty),
            label_visibility="collapsed",
            key="drawer_specialty"
        )
        if new_spec != st.session_state.specialty:
            st.session_state.specialty = new_spec
            st.rerun()

        st.markdown('<span class="s-drawer-label" style="margin-top:16px;display:block">Language matrix</span>', unsafe_allow_html=True)
        new_lang = st.selectbox(
            "Language",
            LANGUAGES,
            index=LANGUAGES.index(st.session_state.language),
            label_visibility="collapsed",
            key="drawer_language"
        )
        if new_lang != st.session_state.language:
            st.session_state.language = new_lang
            st.rerun()

        st.markdown('<span class="s-drawer-label" style="margin-top:16px;display:block">Theme</span>', unsafe_allow_html=True)
        theme_cols = st.columns(3)
        theme_opts = [("☀ Light", "light"), ("☽ Dark", "dark"), ("◑ System", "system")]
        for col, (label, val) in zip(theme_cols, theme_opts):
            with col:
                if st.button(
                    label,
                    key=f"theme_{val}",
                    type="primary" if st.session_state.theme == val else "secondary",
                    use_container_width=True
                ):
                    st.session_state.theme = val
                    st.rerun()

        st.markdown('<span class="s-drawer-label" style="margin-top:16px;display:block">API credentials</span>', unsafe_allow_html=True)
        if has_cloud_groq and has_cloud_gemini:
            st.markdown('<div class="s-vault-note">Vault credentials active — both API keys pre-loaded. Override below only if needed.</div>', unsafe_allow_html=True)

        groq_override = st.text_input(
            "Groq — Whisper v3",
            type="password",
            value=st.session_state.groq_key_override,
            placeholder="Vault active" if has_cloud_groq else "sk-...",
            key="drawer_groq"
        )
        st.session_state.groq_key_override = groq_override

        gemini_override = st.text_input(
            "Gemini — Flash 2.5",
            type="password",
            value=st.session_state.gemini_key_override,
            placeholder="Vault active" if has_cloud_gemini else "AI...",
            key="drawer_gemini"
        )
        st.session_state.gemini_key_override = gemini_override

        st.divider()
        if st.button("Close settings", use_container_width=True, key="close_drawer"):
            st.session_state.show_settings = False
            st.rerun()

        if st.session_state.transcript:
            if st.button("New consultation", use_container_width=True, key="new_consult_drawer"):
                for key in ["transcript", "classification", "salience_map",
                            "soap_note", "flags", "next_steps",
                            "pipeline_execution_time", "chart_locked"]:
                    st.session_state[key] = defaults[key]
                st.session_state.show_settings = False
                st.rerun()

    st.markdown("</div></div></div>", unsafe_allow_html=True)


# =====================================================================
# 8. SETUP SCREEN (first load, no specialty confirmed)
# =====================================================================
if not st.session_state.setup_done:
    st.markdown('<div class="s-setup-wrap">', unsafe_allow_html=True)
    st.markdown(f"""
    <div class="s-setup-card">
      <div class="s-setup-title">Select your specialty profile</div>
      <div class="s-setup-sub">Salience OS will calibrate its clinical intelligence engine to your specialty context.</div>
    </div>
    """, unsafe_allow_html=True)

    with st.container():
        setup_spec = st.selectbox(
            "Specialty",
            SPECIALTIES,
            index=SPECIALTIES.index(st.session_state.specialty),
            label_visibility="collapsed",
            key="setup_spec"
        )
        if st.button("Begin consultation", type="primary", use_container_width=True, key="setup_begin"):
            st.session_state.specialty = setup_spec
            st.session_state.setup_done = True
            st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)
    st.stop()


# =====================================================================
# 9. MAIN CONTENT
# =====================================================================
st.markdown('<div class="s-content">', unsafe_allow_html=True)

# Focus mode banner
if focus:
    st.markdown('<div class="focus-badge">⊡ Focus mode — all configuration hidden</div>', unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)


# ─── INPUT AREA (pre-analysis) ───────────────────────────────────────
if not st.session_state.transcript:
    cap_col, exam_col = st.columns([1.1, 1], gap="large")

    with cap_col:
        st.markdown('<p class="panel-header">Input capture</p>', unsafe_allow_html=True)

        input_vector = st.radio(
            "Input mode",
            ["Text (paste/type)", "Microphone (live)", "File upload (.wav / .json)"],
            label_visibility="collapsed"
        )

        temp_audio_filename   = "active_stream_input.wav"
        has_valid_audio       = False
        bypass_stt            = False
        injected_text         = ""

        if "Text" in input_vector:
            injected_text = st.text_area(
                "Transcript",
                placeholder="Paste or type the consultation transcript here…",
                height=180,
                label_visibility="collapsed"
            )
            if injected_text.strip():
                has_valid_audio = True
                bypass_stt      = True

        elif "Microphone" in input_vector:
            audio_file = st.audio_input("Record")
            if audio_file is not None:
                with open(temp_audio_filename, "wb") as f:
                    f.write(audio_file.read())
                has_valid_audio = True

        else:
            uploaded_file = st.file_uploader(
                "Upload file",
                type=["wav", "mp3", "m4a", "json"],
                label_visibility="collapsed"
            )
            if uploaded_file is not None:
                if uploaded_file.name.endswith('.json'):
                    try:
                        json_data = json.load(uploaded_file)
                        if isinstance(json_data, list):
                            st.success(f"{len(json_data)} cases loaded")
                            case_idx      = st.number_input("Case index", min_value=0, max_value=len(json_data)-1, value=0)
                            selected_node = json_data[case_idx]
                            injected_text = selected_node.get("input", selected_node.get("instruction", ""))
                            if injected_text:
                                st.caption(injected_text[:200] + "…")
                                has_valid_audio = True
                                bypass_stt      = True
                        else:
                            st.error("JSON must be a list of case objects.")
                    except Exception as e:
                        st.error(f"JSON parse error: {e}")
                else:
                    with open(temp_audio_filename, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    st.audio(temp_audio_filename)
                    has_valid_audio = True

    with exam_col:
        st.markdown('<p class="panel-header">Physical examination</p>', unsafe_allow_html=True)
        exam_tabs = st.tabs(["Thoracic", "GI / Abdomen", "Neuro", "MSK"])
        with exam_tabs[0]:
            notes_thoracic = st.text_area(
                "Thoracic", height=100, label_visibility="collapsed",
                value="Cardiovascular: Tachycardic, rhythm regular. S1 and S2 distinct, no audible murmurs. Diaphoresis noted. Respiratory: Tachypneic, shallow. CTAB bilaterally."
            )
        with exam_tabs[1]:
            notes_abdominal = st.text_area(
                "GI", height=100, label_visibility="collapsed",
                value="Abdomen soft, non-distended. Bowel sounds active. No tenderness, guarding, or rebound. No hepatosplenomegaly. Epigastric non-tender."
            )
        with exam_tabs[2]:
            notes_neuro = st.text_area(
                "Neuro", height=100, label_visibility="collapsed",
                value="A&Ox3. PERRLA. Orthostatic lightheadedness on sitting up. Gross motor and sensory intact."
            )
        with exam_tabs[3]:
            notes_ortho = st.text_area(
                "MSK", height=100, label_visibility="collapsed",
                value="Mild lumbar paraspinal tenderness. Left shoulder and mandible — full passive ROM, no joint tenderness."
            )

    compiled_exam = f"""
    - Thoracic: {notes_thoracic}
    - GI/Abdomen: {notes_abdominal}
    - Neuro/Reflex: {notes_neuro}
    - Musculoskeletal: {notes_ortho}
    """

    st.divider()
    if st.button(
        "Run salience analysis",
        type="primary",
        use_container_width=True,
        disabled=not has_valid_audio,
        key="run_pipeline"
    ):
        groq_key   = get_groq_key()
        gemini_key = get_gemini_key()
        if not groq_key or not gemini_key:
            st.error("API credentials missing. Open Settings to add your keys.")
        else:
            t0 = time.time()
            with st.status("Running analysis pipeline…", expanded=True) as status:
                try:
                    if bypass_stt:
                        raw_text = injected_text
                        st.write("✓ Text input ingested")
                    else:
                        st.write("Compressing audio…")
                        raw_audio = AudioSegment.from_file(temp_audio_filename)
                        processed = raw_audio.set_channels(1).set_frame_rate(16000)
                        comp_file = "optimized_api_payload.mp3"
                        processed.export(comp_file, format="mp3", bitrate="64k")
                        groq_client = Groq(api_key=groq_key, timeout=60.0)
                        with open(comp_file, "rb") as ab:
                            raw_text = groq_client.audio.transcriptions.create(
                                file=(comp_file, ab.read()),
                                model="whisper-large-v3",
                                response_format="text"
                            )
                        for f in [temp_audio_filename, comp_file]:
                            if os.path.exists(f): os.remove(f)
                        st.write("✓ Transcription complete")

                    st.write("Running clinical salience engine…")
                    genai.configure(api_key=gemini_key)
                    model = genai.GenerativeModel('gemini-2.5-flash')

                    prompt = f"""
                    You are the core analytical pipeline of Salience OS, configured for the specialty: {st.session_state.specialty}.
                    The incoming data stream was ingested with an expected localization matrix profile of: {st.session_state.language}.

                    RAW INPUT DATA TRANSCRIPT:
                    \"\"\"{raw_text}\"\"\"

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

                    resp = model.generate_content(
                        prompt,
                        generation_config={"response_mime_type": "application/json"}
                    )
                    parsed = json.loads(resp.text, strict=False)

                    st.session_state.transcript              = parsed.get("cleaned_transcript", "")
                    st.session_state.classification          = parsed.get("classification", {})
                    st.session_state.salience_map            = parsed.get("salience_weight_map", [])
                    st.session_state.soap_note               = parsed.get("structured_soap_chart", "")
                    st.session_state.flags                   = parsed.get("clinical_safety_red_flags", [])
                    st.session_state.next_steps              = parsed.get("suggested_next_steps", [])
                    st.session_state.pipeline_execution_time = round(time.time() - t0, 2)
                    st.session_state.chart_locked            = False

                    status.update(label="Analysis complete", state="complete", expanded=False)
                    st.rerun()

                except Exception as e:
                    status.update(label="Pipeline error", state="error")
                    st.error(f"Error: {e}")

    if not has_valid_audio:
        st.caption("Add a transcript or audio recording above to enable analysis.")


# ─── OUTPUT WORKSPACE (post-analysis) ────────────────────────────────
if st.session_state.transcript:

    urgency = st.session_state.classification.get("urgency_tier", "")
    trigger = st.session_state.classification.get("primary_clinical_trigger", "")

    # Urgency banner
    _tiers = {
        "CRITICAL": ("alert-critical", "⬤ Critical — immediate action required"),
        "HIGH":     ("alert-high",     "⬤ High priority"),
        "MEDIUM":   ("alert-medium",   "⬤ Medium priority"),
        "LOW":      ("alert-info",     "⬤ Low urgency"),
    }
    if urgency in _tiers:
        css_cls, label_txt = _tiers[urgency]
        st.markdown(f"""
        <div class="alert-shell {css_cls}" role="alert" aria-live="assertive">
            <div class="alert-rail"></div>
            <div class="alert-body">
                <div class="alert-tier">{label_txt}</div>
                <div class="alert-desc">{trigger}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # ── FOCUS MODE — single-scroll layout ──────────────────────────
    if focus:
        f_col1, f_col2 = st.columns([1, 1], gap="large")

        with f_col1:
            st.markdown('<p class="panel-header">Clinical signals</p>', unsafe_allow_html=True)
            if st.session_state.salience_map:
                for item in sorted(st.session_state.salience_map,
                                   key=lambda x: x.get("salience_score", 0), reverse=True):
                    score = item.get("salience_score", 0)
                    bc = "var(--s-bar-critical)" if score >= 0.85 else (
                         "var(--s-bar-high)"     if score >= 0.65 else "var(--s-bar-low)")
                    bw = max(4, int(score * 56))
                    st.markdown(f"""
                    <div class="signal-row">
                      <div style="width:{bw}px;height:3px;border-radius:2px;background:{bc};flex-shrink:0"></div>
                      <span class="signal-name">{item.get('entity','')}</span>
                      <span class="signal-cat">{item.get('category','')}</span>
                      <span class="signal-score">{score:.2f}</span>
                    </div>""", unsafe_allow_html=True)

            st.markdown('<p class="panel-header" style="margin-top:20px">Safety flags</p>', unsafe_allow_html=True)
            if st.session_state.flags:
                for flag in st.session_state.flags:
                    st.markdown(f'<div class="flag-item" role="alert">{flag}</div>', unsafe_allow_html=True)
            else:
                st.success("No safety flags identified.")

        with f_col2:
            st.markdown('<p class="panel-header">SOAP draft — pending review</p>', unsafe_allow_html=True)
            edited_soap = st.text_area(
                "SOAP", value=st.session_state.soap_note,
                height=360, label_visibility="collapsed", key="focus_soap"
            )

        st.divider()
        sign_col1, sign_col2, sign_col3 = st.columns([1, 1, 1])
        with sign_col1:
            try:
                pdf_bytes = generate_clinical_pdf(edited_soap, st.session_state.specialty)
                st.download_button(
                    "Download PDF", data=pdf_bytes,
                    file_name=f"Salience_OS_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                    mime="application/pdf", use_container_width=True, key="focus_pdf"
                )
            except Exception as e:
                st.error(f"PDF error: {e}")
        with sign_col2:
            if st.session_state.chart_locked:
                st.button("Chart locked", disabled=True, use_container_width=True, key="focus_locked")
            else:
                if st.button("Sign & push to EHR", type="primary", use_container_width=True, key="focus_sign"):
                    with st.spinner("Pushing to EHR…"):
                        time.sleep(2.0)
                        st.session_state.chart_locked = True
                        st.rerun()
        with sign_col3:
            if st.button("New consultation", use_container_width=True, key="focus_new"):
                for key in ["transcript", "classification", "salience_map",
                            "soap_note", "flags", "next_steps",
                            "pipeline_execution_time", "chart_locked"]:
                    st.session_state[key] = defaults[key]
                st.rerun()

    # ── FULL MODE — tabbed layout ───────────────────────────────────
    else:
        out_tabs = st.tabs(["Key findings", "Red flags & next steps", "SOAP review", "Explainability"])

        # Tab 1 — Key findings
        with out_tabs[0]:
            sig_col, trans_col = st.columns([1, 1], gap="large")
            with sig_col:
                st.markdown('<p class="panel-header">Clinical signals — by salience weight</p>', unsafe_allow_html=True)
                if st.session_state.salience_map:
                    for item in sorted(st.session_state.salience_map,
                                       key=lambda x: x.get("salience_score", 0), reverse=True):
                        score = item.get("salience_score", 0)
                        bc = "var(--s-bar-critical)" if score >= 0.85 else (
                             "var(--s-bar-high)"     if score >= 0.65 else "var(--s-bar-low)")
                        bw = max(4, int(score * 56))
                        st.markdown(f"""
                        <div class="signal-row">
                          <div style="width:{bw}px;height:3px;border-radius:2px;background:{bc};flex-shrink:0"></div>
                          <span class="signal-name">{item.get('entity','')}</span>
                          <span class="signal-cat">{item.get('category','')}</span>
                          <span class="signal-score">{score:.2f}</span>
                        </div>""", unsafe_allow_html=True)
            with trans_col:
                st.markdown('<p class="panel-header">Cleaned transcript</p>', unsafe_allow_html=True)
                st.text_area(
                    "Transcript", value=st.session_state.transcript,
                    height=320, disabled=True, label_visibility="collapsed", key="trans_out"
                )

        # Tab 2 — Red flags & next steps
        with out_tabs[1]:
            flag_col, step_col = st.columns([1, 1], gap="large")
            with flag_col:
                st.markdown('<p class="panel-header">Safety flags</p>', unsafe_allow_html=True)
                if st.session_state.flags:
                    for flag in st.session_state.flags:
                        st.markdown(f'<div class="flag-item" role="alert">{flag}</div>', unsafe_allow_html=True)
                else:
                    st.success("No safety flags identified.")
            with step_col:
                st.markdown('<p class="panel-header">Suggested next steps</p>', unsafe_allow_html=True)
                for i, step in enumerate(st.session_state.next_steps, 1):
                    st.markdown(f"""
                    <div class="step-item">
                      <span style="opacity:.3;font-size:11px;min-width:16px;font-family:var(--s-font-mono)">{i}</span>
                      <span>{step}</span>
                    </div>""", unsafe_allow_html=True)

        # Tab 3 — SOAP review
        with out_tabs[2]:
            soap_col, action_col = st.columns([1.6, 1], gap="large")
            with soap_col:
                st.markdown('<p class="panel-header">Clinical note — pending review</p>', unsafe_allow_html=True)
                edited_soap = st.text_area(
                    "SOAP note", value=st.session_state.soap_note,
                    height=420, label_visibility="collapsed", key="soap_edit"
                )
            with action_col:
                st.markdown('<p class="panel-header">Review & sign-off</p>', unsafe_allow_html=True)
                st.caption(f"Processed {st.session_state.pipeline_execution_time}s ago · {st.session_state.specialty}")
                st.divider()
                try:
                    pdf_bytes = generate_clinical_pdf(edited_soap, st.session_state.specialty)
                    st.download_button(
                        "Download PDF", data=pdf_bytes,
                        file_name=f"Salience_OS_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                        mime="application/pdf", use_container_width=True, key="full_pdf"
                    )
                except Exception as e:
                    st.error(f"PDF error: {e}")
                st.divider()
                if st.session_state.chart_locked:
                    st.success("Signed and pushed to EHR.")
                    st.button("Chart locked", disabled=True, use_container_width=True, key="full_locked")
                else:
                    st.warning("Note is unsigned. Review before sign-off.")
                    if st.button("Sign & push to EHR", type="primary", use_container_width=True, key="full_sign"):
                        with st.spinner("Pushing to EHR…"):
                            time.sleep(2.0)
                            st.session_state.chart_locked = True
                            st.rerun()
                st.divider()
                if st.button("New consultation", use_container_width=True, key="full_new"):
                    for key in ["transcript", "classification", "salience_map",
                                "soap_note", "flags", "next_steps",
                                "pipeline_execution_time", "chart_locked"]:
                        st.session_state[key] = defaults[key]
                    st.rerun()

        # Tab 4 — Explainability
        with out_tabs[3]:
            st.markdown('<p class="panel-header">Model reasoning — why these signals were prioritised</p>', unsafe_allow_html=True)
            for item in sorted(st.session_state.salience_map,
                               key=lambda x: x.get("salience_score", 0), reverse=True):
                score = item.get("salience_score", 0)
                if score >= 0.85:   cc, cl = "conf-hi",  "High"
                elif score >= 0.65: cc, cl = "conf-med", "Medium"
                else:               cc, cl = "conf-lo",  "Low"
                st.markdown(f"""
                <div class="explain-card">
                  <div class="explain-head">
                    <span class="{cc}">●</span>
                    {item.get('entity','')}
                    <span style="margin-left:auto;font-size:10px;color:var(--s-text-tertiary);font-family:var(--s-font-mono)">{cl} · {score:.2f}</span>
                  </div>
                  <div class="explain-body">{item.get('reasoning_context','')}</div>
                </div>""", unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)
