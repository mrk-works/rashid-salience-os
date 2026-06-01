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
from pydub import AudioSegment
from fpdf import FPDF


# =====================================================================
# 0. PDF UTILITIES (unchanged)
# =====================================================================
def sanitize_for_pdf(text):
    if not text:
        return ""
    char_map = {
        "•": "-", "—": "-", "–": "-", "\u201c": '"', "\u201d": '"',
        "\u2018": "'", "\u2019": "'", "™": "TM", "©": "(c)", "®": "(r)"
    }
    for u, s in char_map.items():
        text = text.replace(u, s)
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
            pdf.line(pdf.l_margin, pdf.get_y(), pdf.l_margin + 40, pdf.get_y())
            pdf.ln(2)
            pdf.set_text_color(15, 23, 42)
        elif line_clean.startswith("**") and line_clean.endswith("**"):
            pdf.set_font("Helvetica", "B", 11)
            pdf.cell(effective_width, 7, sanitize_for_pdf(line_clean.replace("**", "").strip()), ln=True)
        else:
            pdf.set_font("Helvetica", size=10)
            pdf.multi_cell(effective_width, 6, sanitize_for_pdf(
                line_clean.replace("**", "").replace("*", "-")
            ))
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
    "specialty": "",
    "language": "Mixed (Multi-lingual Code-Switching)",
    "show_drawer": False,
    "focus_mode": False,
    "groq_key_override": "",
    "gemini_key_override": "",
    "setup_done": False,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


# =====================================================================
# 3. THEME ENGINE
# =====================================================================
def inject_theme_engine():
    components.html("""
    <script>
    (function() {
        const KEY = 'SALIENCE_THEME';
        function apply(mode) {
            const root = window.parent.document.documentElement;
            if (mode === 'system') {
                root.setAttribute('data-salience-theme',
                    window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
            } else {
                root.setAttribute('data-salience-theme', mode);
            }
        }
        window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
            if ((localStorage.getItem(KEY) || 'system') === 'system') apply('system');
        });
        apply(localStorage.getItem(KEY) || 'system');
    })();
    </script>
    """, height=0, scrolling=False)

inject_theme_engine()


# =====================================================================
# 4. DESIGN SYSTEM CSS
# =====================================================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap');

/* ── Token layer: Light ── */
:root, html[data-salience-theme="light"] {
    --s-bg-base:         #F7F8FA;
    --s-bg-surface:      #FFFFFF;
    --s-bg-subtle:       #F0F2F5;
    --s-bg-hover:        rgba(0,0,0,0.04);
    --s-border:          rgba(0,0,0,0.08);
    --s-border-strong:   rgba(0,0,0,0.14);
    --s-border-focus:    #3B82F6;
    --s-text-primary:    #0D1117;
    --s-text-secondary:  #4B5563;
    --s-text-tertiary:   #9CA3AF;
    --s-text-inverse:    #FFFFFF;
    --s-critical-bg:     #FEF2F2;
    --s-critical-border: #FECACA;
    --s-critical-rail:   #DC2626;
    --s-critical-text:   #7F1D1D;
    --s-critical-label:  #991B1B;
    --s-critical-glow:   rgba(220,38,38,0.18);
    --s-critical-pulse:  rgba(220,38,38,0.08);
    --s-high-bg:         #FFFBEB;
    --s-high-border:     #FDE68A;
    --s-high-rail:       #D97706;
    --s-high-text:       #78350F;
    --s-high-label:      #92400E;
    --s-medium-bg:       #EFF6FF;
    --s-medium-border:   #BFDBFE;
    --s-medium-rail:     #2563EB;
    --s-medium-text:     #1E3A5F;
    --s-medium-label:    #1D4ED8;
    --s-info-bg:         #F0FDF4;
    --s-info-border:     #BBF7D0;
    --s-info-rail:       #16A34A;
    --s-info-text:       #14532D;
    --s-info-label:      #15803D;
    --s-bar-critical:    #DC2626;
    --s-bar-high:        #D97706;
    --s-bar-low:         #16A34A;
    --s-overlay-bg:      rgba(0,0,0,0.3);
    --s-drawer-bg:       #FFFFFF;
    --s-transition:      background 0.2s ease, color 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
    --s-font-ui:         'IBM Plex Sans', system-ui, sans-serif;
    --s-font-mono:       'IBM Plex Mono', monospace;
}

/* ── Token layer: Dark ── */
html[data-salience-theme="dark"] {
    --s-bg-base:         #0A0C10;
    --s-bg-surface:      #111318;
    --s-bg-subtle:       #1F222A;
    --s-bg-hover:        rgba(255,255,255,0.05);
    --s-border:          rgba(255,255,255,0.08);
    --s-border-strong:   rgba(255,255,255,0.14);
    --s-border-focus:    #60A5FA;
    --s-text-primary:    #F1F5F9;
    --s-text-secondary:  #94A3B8;
    --s-text-tertiary:   #475569;
    --s-text-inverse:    #0D1117;
    --s-critical-bg:     rgba(220,38,38,0.12);
    --s-critical-border: rgba(220,38,38,0.35);
    --s-critical-rail:   #EF4444;
    --s-critical-text:   #FCA5A5;
    --s-critical-label:  #F87171;
    --s-critical-glow:   rgba(239,68,68,0.25);
    --s-critical-pulse:  rgba(239,68,68,0.10);
    --s-high-bg:         rgba(217,119,6,0.10);
    --s-high-border:     rgba(217,119,6,0.35);
    --s-high-rail:       #F59E0B;
    --s-high-text:       #FCD34D;
    --s-high-label:      #FBBF24;
    --s-medium-bg:       rgba(37,99,235,0.12);
    --s-medium-border:   rgba(37,99,235,0.35);
    --s-medium-rail:     #60A5FA;
    --s-medium-text:     #BFDBFE;
    --s-medium-label:    #93C5FD;
    --s-info-bg:         rgba(22,163,74,0.10);
    --s-info-border:     rgba(22,163,74,0.30);
    --s-info-rail:       #34D399;
    --s-info-text:       #A7F3D0;
    --s-info-label:      #6EE7B7;
    --s-bar-critical:    #EF4444;
    --s-bar-high:        #F59E0B;
    --s-bar-low:         #34D399;
    --s-overlay-bg:      rgba(0,0,0,0.6);
    --s-drawer-bg:       #111318;
}

/* ── Global base ── */
html, body,
[data-testid="stAppViewContainer"],
[data-testid="stMain"], .main, .block-container {
    font-family: var(--s-font-ui) !important;
    background: var(--s-bg-base) !important;
    color: var(--s-text-primary) !important;
    transition: var(--s-transition);
}
h1,h2,h3,h4 { font-family: var(--s-font-ui) !important; font-weight: 600 !important; color: var(--s-text-primary) !important; }
p,span,div,label { font-family: var(--s-font-ui) !important; }
#MainMenu, footer, [data-testid="stDecoration"],
div[data-testid="stToolbar"], header { visibility: hidden !important; display: none !important; }
.block-container { padding: 0 !important; max-width: 100% !important; }

/* ── Top bar ── */
.s-topbar {
    position: sticky;
    top: 0;
    z-index: 100;
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 0 24px;
    height: 52px;
    background: var(--s-bg-surface);
    border-bottom: 0.5px solid var(--s-border);
    transition: var(--s-transition);
}
.s-logo {
    font-size: 15px;
    font-weight: 600;
    letter-spacing: 0.2px;
    color: var(--s-text-primary);
    margin-right: 4px;
}
.s-logo span { opacity: 0.35; font-weight: 400; }
.s-spec-badge {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    font-size: 11px;
    font-weight: 500;
    padding: 4px 10px;
    border-radius: 20px;
    background: var(--s-bg-subtle);
    border: 0.5px solid var(--s-border);
    color: var(--s-text-secondary);
    cursor: pointer;
    transition: all 0.15s ease;
}
.s-spec-badge:hover { border-color: var(--s-border-strong); color: var(--s-text-primary); }
.s-topbar-spacer { flex: 1; }
.s-topbar-actions { display: flex; align-items: center; gap: 6px; }
.s-icon-btn {
    width: 32px; height: 32px;
    border-radius: 8px;
    border: 0.5px solid var(--s-border);
    background: transparent;
    display: flex; align-items: center; justify-content: center;
    font-size: 15px;
    color: var(--s-text-secondary);
    cursor: pointer;
    transition: all 0.15s ease;
    text-decoration: none;
}
.s-icon-btn:hover { background: var(--s-bg-subtle); border-color: var(--s-border-strong); color: var(--s-text-primary); }
.s-settings-btn {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 6px 12px;
    border-radius: 8px;
    border: 0.5px solid var(--s-border);
    background: transparent;
    font-size: 12px; font-weight: 500;
    color: var(--s-text-secondary);
    cursor: pointer;
    transition: all 0.15s ease;
}
.s-settings-btn:hover { background: var(--s-bg-subtle); color: var(--s-text-primary); }
.s-focus-active {
    background: rgba(37,99,235,0.08) !important;
    border-color: rgba(37,99,235,0.3) !important;
    color: #1D4ED8 !important;
}
html[data-salience-theme="dark"] .s-focus-active { color: #60A5FA !important; }

/* ── Main content wrapper ── */
.s-content { padding: 20px 24px 40px; }

/* ── Setup card ── */
.s-setup-wrap {
    min-height: 70vh;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 40px 24px;
}
.s-setup-card {
    background: var(--s-bg-surface);
    border: 0.5px solid var(--s-border);
    border-radius: 16px;
    padding: 36px 40px;
    width: 100%;
    max-width: 440px;
    text-align: center;
}
.s-setup-title { font-size: 22px; font-weight: 600; margin-bottom: 6px; }
.s-setup-sub { font-size: 13px; color: var(--s-text-secondary); margin-bottom: 28px; line-height: 1.6; }
.s-setup-label { font-size: 10px; font-weight: 600; letter-spacing: 0.8px; text-transform: uppercase; color: var(--s-text-tertiary); margin-bottom: 8px; text-align: left; }

/* ── Alert shells ── */
.alert-shell {
    display: flex; border-radius: 10px; overflow: hidden;
    margin-bottom: 16px; border: 1px solid; transition: var(--s-transition);
}
.alert-rail { width: 4px; flex-shrink: 0; }
.alert-body { flex: 1; padding: 12px 14px; }
.alert-tier {
    font-size: 10px; font-weight: 600; letter-spacing: 0.9px;
    text-transform: uppercase; margin-bottom: 4px;
}
.alert-desc { font-size: 13px; line-height: 1.55; }
.alert-critical {
    background: var(--s-critical-bg); border-color: var(--s-critical-border);
    box-shadow: 0 0 0 1px var(--s-critical-border), 0 4px 16px var(--s-critical-glow);
    animation: critPulse 2.4s ease-in-out infinite;
}
.alert-critical .alert-rail { background: var(--s-critical-rail); }
.alert-critical .alert-tier { color: var(--s-critical-label); }
.alert-critical .alert-desc { color: var(--s-critical-text); }
@keyframes critPulse {
    0%,100% { box-shadow: 0 0 0 1px var(--s-critical-border), 0 4px 16px var(--s-critical-glow); }
    50%      { box-shadow: 0 0 0 1px var(--s-critical-border), 0 4px 28px var(--s-critical-glow), 0 0 0 4px var(--s-critical-pulse); }
}
.alert-high { background: var(--s-high-bg); border-color: var(--s-high-border); }
.alert-high .alert-rail { background: var(--s-high-rail); }
.alert-high .alert-tier { color: var(--s-high-label); }
.alert-high .alert-desc { color: var(--s-high-text); }
.alert-medium { background: var(--s-medium-bg); border-color: var(--s-medium-border); }
.alert-medium .alert-rail { background: var(--s-medium-rail); }
.alert-medium .alert-tier { color: var(--s-medium-label); }
.alert-medium .alert-desc { color: var(--s-medium-text); }
.alert-info { background: var(--s-info-bg); border-color: var(--s-info-border); }
.alert-info .alert-rail { background: var(--s-info-rail); }
.alert-info .alert-tier { color: var(--s-info-label); }
.alert-info .alert-desc { color: var(--s-info-text); }
@media (prefers-reduced-motion: reduce) {
    .alert-critical { animation: none !important; }
    * { transition-duration: 0ms !important; }
}

/* ── Panel headers ── */
.panel-header {
    font-size: 10px; font-weight: 600; letter-spacing: 0.9px;
    text-transform: uppercase; color: var(--s-text-tertiary) !important;
    margin-bottom: 0.65rem;
    font-family: var(--s-font-ui) !important;
}

/* ── Signal rows ── */
.signal-row {
    display: flex; align-items: center; gap: 10px;
    padding: 9px 6px; border-bottom: 0.5px solid var(--s-border);
    border-radius: 6px; transition: background 0.15s ease;
}
.signal-row:last-child { border-bottom: none; }
.signal-row:hover { background: var(--s-bg-hover); }
.signal-name { font-size: 13px; font-weight: 500; color: var(--s-text-primary); flex: 1; }
.signal-cat { font-size: 10px; color: var(--s-text-tertiary); }
.signal-score { font-family: var(--s-font-mono); font-size: 11px; color: var(--s-text-secondary); width: 32px; text-align: right; }

/* ── Flag items ── */
.flag-item {
    display: flex; align-items: flex-start; gap: 10px;
    background: var(--s-critical-bg);
    border: 1px solid var(--s-critical-border);
    border-left: 4px solid var(--s-critical-rail);
    border-radius: 0 8px 8px 0;
    padding: 10px 13px; font-size: 12px;
    color: var(--s-critical-text); margin-bottom: 7px; line-height: 1.55;
    transition: var(--s-transition);
}
.flag-item::before { content: "⚠"; font-size: 13px; flex-shrink: 0; margin-top: 1px; }

/* ── Step items ── */
.step-item {
    font-size: 12px; padding: 7px 0;
    border-bottom: 0.5px solid var(--s-border);
    color: var(--s-text-secondary);
    display: flex; gap: 10px; align-items: flex-start;
    line-height: 1.5; transition: color 0.15s ease;
}
.step-item:hover { color: var(--s-text-primary); }
.step-item:last-child { border-bottom: none; }

/* ── Explain cards ── */
.explain-card {
    border: 0.5px solid var(--s-border); border-radius: 9px;
    padding: 11px 14px; margin-bottom: 8px;
    background: var(--s-bg-surface); transition: var(--s-transition);
}
.explain-card:hover { border-color: var(--s-border-strong); box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
.explain-head { font-size: 12px; font-weight: 600; margin-bottom: 5px; display: flex; align-items: center; gap: 7px; color: var(--s-text-primary); }
.explain-body { font-size: 11px; color: var(--s-text-secondary); line-height: 1.65; }
.conf-hi  { color: var(--s-critical-rail); }
.conf-med { color: var(--s-high-rail); }
.conf-lo  { color: var(--s-info-rail); }

/* ── Buttons ── */
[data-testid="stButton"] button {
    font-family: var(--s-font-ui) !important; font-size: 13px !important;
    font-weight: 500 !important; border-radius: 8px !important;
    border: 0.5px solid var(--s-border-strong) !important;
    background: var(--s-bg-surface) !important;
    color: var(--s-text-primary) !important;
    transition: all 0.15s ease !important; padding: 0.45rem 1rem !important;
}
[data-testid="stButton"] button:hover {
    background: var(--s-bg-subtle) !important;
    transform: translateY(-1px);
    box-shadow: 0 2px 8px rgba(0,0,0,0.08) !important;
}
[data-testid="stButton"] button:active { transform: translateY(0) scale(0.98) !important; }
[data-testid="stButton"] button[kind="primary"] {
    background: var(--s-text-primary) !important;
    color: var(--s-text-inverse) !important;
    border-color: transparent !important;
}
[data-testid="stButton"] button[kind="primary"]:hover { opacity: 0.88 !important; }
[data-testid="stButton"] button:disabled { opacity: 0.38 !important; cursor: not-allowed !important; transform: none !important; }
[data-testid="stButton"] button:focus-visible { outline: 2px solid var(--s-border-focus) !important; outline-offset: 2px !important; }

/* ── Form elements ── */
[data-baseweb="select"] > div,
[data-baseweb="input"] > div {
    background: var(--s-bg-surface) !important; border-color: var(--s-border) !important;
    border-radius: 8px !important; color: var(--s-text-primary) !important;
    font-family: var(--s-font-ui) !important; font-size: 13px !important;
    transition: var(--s-transition) !important;
}
[data-baseweb="select"] > div:focus-within,
[data-baseweb="input"] > div:focus-within {
    border-color: var(--s-border-focus) !important;
    box-shadow: 0 0 0 3px rgba(59,130,246,0.15) !important;
}
textarea {
    background: var(--s-bg-surface) !important; color: var(--s-text-primary) !important;
    font-family: var(--s-font-mono) !important; font-size: 12px !important;
    line-height: 1.75 !important; border-radius: 8px !important;
    border-color: var(--s-border) !important; transition: var(--s-transition) !important;
}

/* ── Tabs ── */
[data-testid="stTabs"] [data-baseweb="tab-list"] {
    background: var(--s-bg-subtle) !important; border-radius: 10px !important;
    padding: 3px !important; gap: 2px !important;
    border: 0.5px solid var(--s-border) !important; transition: var(--s-transition);
}
[data-testid="stTabs"] [data-baseweb="tab"] {
    background: transparent !important; border-radius: 8px !important;
    font-family: var(--s-font-ui) !important; font-size: 12px !important;
    font-weight: 500 !important; color: var(--s-text-secondary) !important;
    padding: 5px 14px !important; transition: all 0.15s ease !important; border: none !important;
}
[data-testid="stTabs"] [aria-selected="true"] {
    background: var(--s-bg-surface) !important; color: var(--s-text-primary) !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08) !important;
}
[data-testid="stTabs"] [data-baseweb="tab-highlight"],
[data-testid="stTabs"] [data-baseweb="tab-border"] { display: none !important; }

/* ── Metrics ── */
[data-testid="metric-container"] {
    background: var(--s-bg-surface) !important; border-radius: 10px !important;
    padding: 12px 16px !important; border: 0.5px solid var(--s-border) !important;
    transition: var(--s-transition);
}
[data-testid="metric-container"] label {
    font-size: 10px !important; font-weight: 600 !important;
    letter-spacing: 0.7px !important; text-transform: uppercase !important;
    color: var(--s-text-tertiary) !important;
}
[data-testid="metric-container"] [data-testid="stMetricValue"] {
    font-family: var(--s-font-mono) !important; font-size: 18px !important;
    font-weight: 600 !important; color: var(--s-text-primary) !important;
}

/* ── Misc native elements ── */
hr { border-color: var(--s-border) !important; }
[data-testid="stStatus"] {
    background: var(--s-bg-surface) !important; border: 0.5px solid var(--s-border) !important;
    border-radius: 10px !important; font-family: var(--s-font-ui) !important;
    transition: var(--s-transition);
}
[data-testid="stCaptionContainer"] p, .stCaption {
    font-size: 11px !important; color: var(--s-text-tertiary) !important;
    font-family: var(--s-font-ui) !important;
}
[data-testid="stAlert"] { border-radius: 9px !important; font-family: var(--s-font-ui) !important; font-size: 13px !important; }
[data-testid="stFileUploader"] {
    border: 0.5px dashed var(--s-border-strong) !important;
    border-radius: 10px !important; background: var(--s-bg-subtle) !important;
    transition: var(--s-transition);
}
[data-testid="stDownloadButton"] button {
    font-family: var(--s-font-ui) !important; font-size: 13px !important;
    font-weight: 500 !important; background: var(--s-bg-surface) !important;
    border: 0.5px solid var(--s-border-strong) !important;
    color: var(--s-text-primary) !important; border-radius: 8px !important;
    transition: all 0.15s ease !important;
}
[data-testid="stDownloadButton"] button:hover { background: var(--s-bg-subtle) !important; transform: translateY(-1px); }
[data-testid="stRadio"] label { font-family: var(--s-font-ui) !important; font-size: 13px !important; color: var(--s-text-secondary) !important; }
[data-testid="stRadio"] label:hover { color: var(--s-text-primary) !important; }
*:focus-visible { outline: 2px solid var(--s-border-focus) !important; outline-offset: 2px !important; }

/* ── Drawer overlay ── */
.s-drawer-overlay {
    position: fixed; inset: 0; z-index: 999;
    background: var(--s-overlay-bg);
    backdrop-filter: blur(2px);
    transition: opacity 0.2s ease;
}
.s-drawer {
    position: fixed; top: 0; right: 0; bottom: 0;
    width: 340px; z-index: 1000;
    background: var(--s-drawer-bg);
    border-left: 0.5px solid var(--s-border);
    display: flex; flex-direction: column;
    box-shadow: -8px 0 32px rgba(0,0,0,0.12);
    animation: slideIn 0.22s ease;
}
@keyframes slideIn {
    from { transform: translateX(100%); opacity: 0; }
    to   { transform: translateX(0);   opacity: 1; }
}
.s-drawer-head {
    padding: 18px 20px 16px;
    border-bottom: 0.5px solid var(--s-border);
    display: flex; align-items: center; justify-content: space-between;
}
.s-drawer-title { font-size: 13px; font-weight: 600; color: var(--s-text-primary); }
.s-drawer-close {
    width: 28px; height: 28px; border-radius: 7px;
    border: 0.5px solid var(--s-border);
    background: var(--s-bg-subtle);
    display: flex; align-items: center; justify-content: center;
    cursor: pointer; font-size: 14px; color: var(--s-text-secondary);
    transition: all 0.15s ease;
}
.s-drawer-close:hover { background: var(--s-bg-hover); color: var(--s-text-primary); }
.s-drawer-body { flex: 1; padding: 20px; overflow-y: auto; }
.s-drawer-section { margin-bottom: 24px; }
.s-drawer-label {
    font-size: 10px; font-weight: 600; letter-spacing: 0.8px;
    text-transform: uppercase; color: var(--s-text-tertiary);
    margin-bottom: 8px;
}
.s-seg {
    display: flex; border: 0.5px solid var(--s-border);
    border-radius: 9px; overflow: hidden; background: var(--s-bg-subtle);
    padding: 3px; gap: 2px;
}
.s-seg-btn {
    flex: 1; padding: 6px 4px; font-size: 11px; font-weight: 500;
    text-align: center; border: none; border-radius: 6px;
    cursor: pointer; background: transparent;
    color: var(--s-text-secondary);
    font-family: var(--s-font-ui);
    transition: all 0.15s ease;
}
.s-seg-btn:hover { color: var(--s-text-primary); background: var(--s-bg-hover); }
.s-seg-btn.active {
    background: var(--s-bg-surface);
    color: var(--s-text-primary);
    box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}
.s-theme-row { display: flex; gap: 6px; }
.s-theme-dot {
    flex: 1; padding: 8px 0; font-size: 11px; font-weight: 500;
    text-align: center; border: 0.5px solid var(--s-border);
    border-radius: 8px; cursor: pointer;
    background: var(--s-bg-subtle); color: var(--s-text-secondary);
    font-family: var(--s-font-ui);
    transition: all 0.15s ease;
}
.s-theme-dot:hover { border-color: var(--s-border-strong); color: var(--s-text-primary); }
.s-theme-dot.active {
    background: var(--s-bg-surface);
    border-color: var(--s-border-focus);
    color: var(--s-text-primary);
    box-shadow: 0 0 0 3px rgba(59,130,246,0.12);
}
.s-vault-chip {
    display: flex; align-items: center; gap: 6px;
    padding: 8px 10px; border-radius: 8px;
    background: var(--s-info-bg); border: 0.5px solid var(--s-info-border);
    font-size: 11px; color: var(--s-info-text);
}
.s-drawer-footer {
    padding: 16px 20px;
    border-top: 0.5px solid var(--s-border);
}

/* ── Focus mode banner ── */
.s-focus-banner {
    display: flex; align-items: center; gap: 8px;
    padding: 6px 24px;
    background: rgba(37,99,235,0.06);
    border-bottom: 0.5px solid rgba(37,99,235,0.15);
    font-size: 11px; font-weight: 500;
    color: #1D4ED8;
}
html[data-salience-theme="dark"] .s-focus-banner { color: #60A5FA; background: rgba(60,165,250,0.06); border-color: rgba(60,165,250,0.15); }

/* ── Sidebar hide ── */
[data-testid="stSidebar"] { display: none !important; }
section[data-testid="stSidebarContent"] { display: none !important; }
</style>
""", unsafe_allow_html=True)


# =====================================================================
# 5. HELPERS
# =====================================================================
SPECIALTIES = [
    "Cardiology", "General Internal Medicine", "Emergency Medicine",
    "Neurology", "Pediatrics", "Orthopedic Surgery",
    "Psychiatry & Behavioral Health", "Oncology"
]
LANGUAGES = [
    "Mixed (Multi-lingual Code-Switching)",
    "English (US/UK)",
    "Arabic (Khaleeji/MSA)"
]

def get_api_keys():
    has_groq   = "groq_api_key"   in st.secrets
    has_gemini = "gemini_api_key" in st.secrets
    groq_key   = st.session_state.groq_key_override   or st.secrets.get("groq_api_key",   "")
    gemini_key = st.session_state.gemini_key_override or st.secrets.get("gemini_api_key", "")
    return groq_key, gemini_key, has_groq, has_gemini

def render_urgency_banner(urgency, trigger):
    tier_map = {
        "CRITICAL": ("alert-critical", "⬤ Critical — immediate action required"),
        "HIGH":     ("alert-high",     "⬤ High priority"),
        "MEDIUM":   ("alert-medium",   "⬤ Medium priority"),
        "LOW":      ("alert-info",     "⬤ Low urgency"),
    }
    if urgency in tier_map:
        css, label = tier_map[urgency]
        st.markdown(f"""
        <div class="alert-shell {css}" role="alert" aria-live="assertive">
            <div class="alert-rail"></div>
            <div class="alert-body">
                <div class="alert-tier">{label}</div>
                <div class="alert-desc">{trigger}</div>
            </div>
        </div>""", unsafe_allow_html=True)


# =====================================================================
# 6. SETTINGS DRAWER (rendered via components.html)
# =====================================================================
def render_drawer():
    _, _, has_groq, has_gemini = get_api_keys()
    vault_active = has_groq and has_gemini
    spec_opts    = "\n".join(
        f'<button class="s-seg-btn{" active" if s == st.session_state.specialty else ""}" '
        f'onclick="pick(\'spec\',\'{s}\')">{s}</button>'
        for s in SPECIALTIES
    )
    lang_opts = "\n".join(
        f'<button class="s-seg-btn{" active" if l == st.session_state.language else ""}" '
        f'onclick="pick(\'lang\',\'{l}\')">{l.split("(")[0].strip()}</button>'
        for l in LANGUAGES
    )
    vault_html = (
        '<div class="s-vault-chip">'
        '<i class="ti ti-lock" style="font-size:13px" aria-hidden="true"></i>'
        'Vault credentials active</div>'
        if vault_active else
        '<input class="s-key-input" id="groq-key" type="password" placeholder="Groq API key (sk-...)" '
        'style="width:100%;padding:8px 10px;border:0.5px solid var(--s-border);border-radius:8px;'
        'background:var(--s-bg-surface);color:var(--s-text-primary);font-family:var(--s-font-ui);'
        'font-size:12px;margin-bottom:6px;box-sizing:border-box">'
        '<input class="s-key-input" id="gem-key" type="password" placeholder="Gemini API key (AI...)" '
        'style="width:100%;padding:8px 10px;border:0.5px solid var(--s-border);border-radius:8px;'
        'background:var(--s-bg-surface);color:var(--s-text-primary);font-family:var(--s-font-ui);'
        'font-size:12px;box-sizing:border-box">'
    )

    components.html(f"""
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@2.44.0/tabler-icons.min.css">
    <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{font-family:'IBM Plex Sans',system-ui,sans-serif;background:transparent}}
    .ov{{position:fixed;inset:0;background:rgba(0,0,0,0.35);backdrop-filter:blur(2px);z-index:999;cursor:pointer}}
    .dr{{position:fixed;top:0;right:0;bottom:0;width:320px;z-index:1000;
         background:var(--s-drawer-bg,#fff);border-left:0.5px solid rgba(0,0,0,.08);
         display:flex;flex-direction:column;box-shadow:-8px 0 32px rgba(0,0,0,.1);
         animation:si .2s ease}}
    @keyframes si{{from{{transform:translateX(100%);opacity:0}}to{{transform:translateX(0);opacity:1}}}}
    .dh{{padding:16px 18px 14px;border-bottom:0.5px solid rgba(0,0,0,.08);display:flex;align-items:center;justify-content:space-between}}
    .dt{{font-size:13px;font-weight:600;color:#0D1117}}
    .dc{{width:28px;height:28px;border-radius:7px;border:0.5px solid rgba(0,0,0,.1);
         background:rgba(0,0,0,.04);display:flex;align-items:center;justify-content:center;
         cursor:pointer;font-size:16px;color:#6B7280;transition:all .15s}}
    .dc:hover{{background:rgba(0,0,0,.08);color:#111}}
    .db{{flex:1;padding:18px;overflow-y:auto}}
    .ds{{margin-bottom:20px}}
    .dl{{font-size:10px;font-weight:600;letter-spacing:.8px;text-transform:uppercase;
         color:#9CA3AF;margin-bottom:8px}}
    .sg{{display:flex;border:0.5px solid rgba(0,0,0,.08);border-radius:9px;overflow:hidden;
         background:rgba(0,0,0,.03);padding:3px;gap:2px;flex-wrap:wrap}}
    .sb{{flex:1;min-width:80px;padding:6px 4px;font-size:11px;font-weight:500;text-align:center;
         border:none;border-radius:6px;cursor:pointer;background:transparent;
         color:#6B7280;font-family:inherit;transition:all .15s}}
    .sb:hover{{color:#111;background:rgba(0,0,0,.04)}}
    .sb.active{{background:#fff;color:#0D1117;box-shadow:0 1px 3px rgba(0,0,0,.1)}}
    .tr{{display:flex;gap:6px}}
    .td{{flex:1;padding:8px 0;font-size:11px;font-weight:500;text-align:center;
         border:0.5px solid rgba(0,0,0,.08);border-radius:8px;cursor:pointer;
         background:rgba(0,0,0,.03);color:#6B7280;font-family:inherit;transition:all .15s}}
    .td:hover{{border-color:rgba(0,0,0,.14);color:#111}}
    .td.active{{background:#fff;border-color:#3B82F6;color:#0D1117;
                box-shadow:0 0 0 3px rgba(59,130,246,.1)}}
    .df{{padding:14px 18px;border-top:0.5px solid rgba(0,0,0,.08)}}
    .nb{{width:100%;padding:10px;background:#0D1117;color:#fff;border:none;border-radius:8px;
         font-size:13px;font-weight:500;cursor:pointer;font-family:inherit;transition:opacity .15s}}
    .nb:hover{{opacity:.88}}
    </style>
    <div class="ov" onclick="close_drawer()"></div>
    <div class="dr" role="dialog" aria-label="Workspace settings">
      <div class="dh">
        <span class="dt">Workspace settings</span>
        <div class="dc" onclick="close_drawer()" aria-label="Close settings">
          <i class="ti ti-x" aria-hidden="true"></i>
        </div>
      </div>
      <div class="db">
        <div class="ds">
          <div class="dl">Specialty profile</div>
          <div class="sg" id="spec-grp">
            {''.join(f'<button class="sb{" active" if s == st.session_state.specialty else ""}" onclick="pick(\'spec\',this,\'{s}\')">{s.split(" ")[0]}</button>' for s in SPECIALTIES)}
          </div>
        </div>
        <div class="ds">
          <div class="dl">Language matrix</div>
          <div class="sg" id="lang-grp">
            {''.join(f'<button class="sb{" active" if l == st.session_state.language else ""}" onclick="pick(\'lang\',this,\'{l}\')">{l.split("(")[0].strip()}</button>' for l in LANGUAGES)}
          </div>
        </div>
        <div class="ds">
          <div class="dl">Theme</div>
          <div class="tr" id="theme-grp">
            <button class="td" id="t-light" onclick="setTheme('light')">☀ Light</button>
            <button class="td" id="t-system" onclick="setTheme('system')">◑ System</button>
            <button class="td" id="t-dark"   onclick="setTheme('dark')">☽ Dark</button>
          </div>
        </div>
        <div class="ds">
          <div class="dl">API credentials</div>
          {vault_html}
        </div>
      </div>
      <div class="df">
        <button class="nb" onclick="save()">Apply &amp; close</button>
      </div>
    </div>
    <script>
    const KEY = 'SALIENCE_THEME';
    function close_drawer() {{
      window.parent.postMessage({{type:'salience',action:'close_drawer'}}, '*');
    }}
    function pick(group, btn, val) {{
      const grp = document.getElementById(group === 'spec' ? 'spec-grp' : 'lang-grp');
      grp.querySelectorAll('.sb').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      btn.dataset.val = val;
    }}
    function setTheme(mode) {{
      localStorage.setItem(KEY, mode);
      const root = window.parent.document.documentElement;
      if (mode === 'system') {{
        root.setAttribute('data-salience-theme', window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
      }} else {{
        root.setAttribute('data-salience-theme', mode);
      }}
      document.querySelectorAll('.td').forEach(b => b.classList.remove('active'));
      document.getElementById('t-' + mode).classList.add('active');
    }}
    function save() {{
      const spec = document.querySelector('#spec-grp .sb.active');
      const lang = document.querySelector('#lang-grp .sb.active');
      const msg  = {{type:'salience', action:'save_settings',
                     spec: spec ? spec.dataset.val || spec.textContent.trim() : null,
                     lang: lang ? lang.dataset.val || lang.textContent.trim() : null}};
      window.parent.postMessage(msg, '*');
    }}
    (function initTheme() {{
      const stored = localStorage.getItem(KEY) || 'system';
      const btn = document.getElementById('t-' + stored);
      if (btn) btn.classList.add('active');
    }})();
    </script>
    """, height=600, scrolling=False)


# =====================================================================
# 7. TOP BAR
# =====================================================================
def render_topbar():
    focus = st.session_state.focus_mode
    spec  = st.session_state.specialty or "No specialty"

    col_logo, col_spec, col_spacer, col_actions = st.columns([1, 2, 4, 3])

    with col_logo:
        st.markdown(
            '<div style="padding:12px 0 12px 0;font-size:15px;font-weight:600;'
            'color:var(--s-text-primary);font-family:var(--s-font-ui)">'
            'Salience <span style="opacity:.35;font-weight:400">OS</span></div>',
            unsafe_allow_html=True
        )

    with col_spec:
        if st.session_state.setup_done:
            st.markdown(
                f'<div style="padding:12px 0">'
                f'<span style="display:inline-flex;align-items:center;gap:5px;font-size:11px;'
                f'font-weight:500;padding:4px 10px;border-radius:20px;'
                f'background:var(--s-bg-subtle);border:0.5px solid var(--s-border);'
                f'color:var(--s-text-secondary);font-family:var(--s-font-ui)">'
                f'<i class="ti ti-stethoscope" style="font-size:12px" aria-hidden="true"></i>'
                f'{spec}</span></div>',
                unsafe_allow_html=True
            )

    with col_actions:
        a1, a2, a3, a4 = st.columns(4)

        with a1:
            if st.button(
                "⊙" if not focus else "◎",
                key="focus_toggle",
                help="Toggle focus mode"
            ):
                st.session_state.focus_mode = not st.session_state.focus_mode
                st.rerun()

        with a2:
            if st.button("⚙", key="open_drawer", help="Workspace settings"):
                st.session_state.show_drawer = True
                st.rerun()

        with a3:
            if st.button("◑", key="theme_quick", help="Cycle theme"):
                components.html("""
                <script>
                const KEY='SALIENCE_THEME';
                const cur = localStorage.getItem(KEY)||'system';
                const nxt = cur==='light'?'dark':cur==='dark'?'system':'light';
                localStorage.setItem(KEY, nxt);
                const root = window.parent.document.documentElement;
                if(nxt==='system'){
                  root.setAttribute('data-salience-theme',
                    window.matchMedia('(prefers-color-scheme:dark)').matches?'dark':'light');
                }else{ root.setAttribute('data-salience-theme', nxt); }
                </script>""", height=0)

        with a4:
            if st.session_state.transcript:
                if st.button("+ New", key="new_consult", help="New consultation"):
                    for k in ["transcript","classification","salience_map","soap_note",
                               "flags","next_steps","pipeline_execution_time","chart_locked"]:
                        st.session_state[k] = defaults[k]
                    st.rerun()

    st.markdown('<hr style="margin:0;border-color:var(--s-border)">', unsafe_allow_html=True)


# =====================================================================
# 8. SETUP CARD (first load)
# =====================================================================
def render_setup():
    st.markdown('<div class="s-setup-wrap">', unsafe_allow_html=True)

    with st.container():
        _, card_col, _ = st.columns([1, 2, 1])
        with card_col:
            st.markdown("""
            <div style="text-align:center;padding:20px 0 8px">
                <div style="font-size:22px;font-weight:600;margin-bottom:6px">
                    Clinical intelligence workspace
                </div>
                <div style="font-size:13px;color:var(--s-text-secondary);line-height:1.6;margin-bottom:24px">
                    Select your specialty profile to begin.<br>All other settings are available in workspace preferences.
                </div>
            </div>""", unsafe_allow_html=True)

            st.markdown('<p class="panel-header">Specialty profile</p>', unsafe_allow_html=True)
            chosen = st.selectbox(
                "Specialty",
                SPECIALTIES,
                index=0,
                label_visibility="collapsed"
            )

            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Open workspace", type="primary", use_container_width=True):
                st.session_state.specialty  = chosen
                st.session_state.setup_done = True
                st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)


# =====================================================================
# 9. INPUT CAPTURE
# =====================================================================
def render_input():
    cap_col, exam_col = st.columns([1.1, 1], gap="large")

    with cap_col:
        st.markdown('<p class="panel-header">Input capture</p>', unsafe_allow_html=True)
        input_vector = st.radio(
            "Input mode",
            ["Text (paste/type)", "Microphone (live)", "File upload (.wav / .json)"],
            label_visibility="collapsed"
        )

        temp_audio = "active_stream_input.wav"
        has_payload = False
        bypass_stt  = False
        injected    = ""

        if "Text" in input_vector:
            injected = st.text_area(
                "Transcript",
                placeholder="Paste or type the consultation transcript here…",
                height=200, label_visibility="collapsed"
            )
            if injected.strip():
                has_payload = True
                bypass_stt  = True

        elif "Microphone" in input_vector:
            af = st.audio_input("Record")
            if af:
                with open(temp_audio, "wb") as f:
                    f.write(af.read())
                has_payload = True

        else:
            uf = st.file_uploader("Upload", type=["wav","mp3","m4a","json"], label_visibility="collapsed")
            if uf:
                if uf.name.endswith(".json"):
                    try:
                        jd = json.load(uf)
                        if isinstance(jd, list):
                            st.success(f"{len(jd)} cases loaded")
                            idx  = st.number_input("Case index", min_value=0, max_value=len(jd)-1, value=0)
                            node = jd[idx]
                            injected = node.get("input", node.get("instruction", ""))
                            if injected:
                                st.caption(injected[:200] + "…")
                                has_payload = True
                                bypass_stt  = True
                        else:
                            st.error("JSON must be a list.")
                    except Exception as e:
                        st.error(f"JSON error: {e}")
                else:
                    with open(temp_audio, "wb") as f:
                        f.write(uf.getbuffer())
                    st.audio(temp_audio)
                    has_payload = True

    with exam_col:
        st.markdown('<p class="panel-header">Physical examination</p>', unsafe_allow_html=True)
        etabs = st.tabs(["Thoracic", "GI / Abdomen", "Neuro", "MSK"])
        with etabs[0]:
            notes_t = st.text_area("Thoracic", height=100, label_visibility="collapsed",
                value="Cardiovascular: Tachycardic, rhythm regular. S1/S2 distinct. Diaphoresis. Respiratory: Tachypneic, CTAB.")
        with etabs[1]:
            notes_g = st.text_area("GI", height=100, label_visibility="collapsed",
                value="Abdomen soft, non-distended. Bowel sounds active. No tenderness, guarding, or rebound.")
        with etabs[2]:
            notes_n = st.text_area("Neuro", height=100, label_visibility="collapsed",
                value="A&Ox3. PERRLA. Orthostatic lightheadedness. Gross motor and sensory intact.")
        with etabs[3]:
            notes_m = st.text_area("MSK", height=100, label_visibility="collapsed",
                value="Mild lumbar paraspinal tenderness. Left shoulder — full passive ROM, no joint tenderness.")

    exam_overlay = f"""
    - Thoracic: {notes_t}
    - GI/Abdomen: {notes_g}
    - Neuro: {notes_n}
    - MSK: {notes_m}
    """
    return has_payload, bypass_stt, injected, temp_audio, exam_overlay


# =====================================================================
# 10. PIPELINE EXECUTION
# =====================================================================
def run_pipeline(bypass_stt, injected, temp_audio, exam_overlay):
    groq_key, gemini_key, _, _ = get_api_keys()
    if not groq_key or not gemini_key:
        st.error("API credentials missing. Add keys via workspace settings.")
        return

    t0 = time.time()
    with st.status("Running analysis pipeline…", expanded=True) as status:
        try:
            if bypass_stt:
                raw_text = injected
                st.write("✓ Text ingested")
            else:
                st.write("Compressing audio…")
                audio = AudioSegment.from_file(temp_audio)
                audio = audio.set_channels(1).set_frame_rate(16000)
                comp  = "optimized_payload.mp3"
                audio.export(comp, format="mp3", bitrate="64k")
                client = Groq(api_key=groq_key, timeout=60.0)
                with open(comp, "rb") as ab:
                    raw_text = client.audio.transcriptions.create(
                        file=(comp, ab.read()),
                        model="whisper-large-v3",
                        response_format="text"
                    )
                for f in [temp_audio, comp]:
                    if os.path.exists(f): os.remove(f)
                st.write("✓ Transcription complete")

            st.write("Running salience engine…")
            genai.configure(api_key=gemini_key)
            model = genai.GenerativeModel('gemini-2.5-flash')

            prompt = f"""
            You are the core analytical pipeline of Salience OS, configured for: {st.session_state.specialty}.
            Language matrix: {st.session_state.language}.

            RAW TRANSCRIPT:
            \"\"\"{raw_text}\"\"\"

            PHYSICAL EXAMINATION:
            \"\"\"{exam_overlay}\"\"\"

            Return valid JSON only — no markdown, no prefix:
            {{
                "cleaned_transcript": "corrected text",
                "classification": {{"urgency_tier": "CRITICAL|HIGH|MEDIUM|LOW", "primary_clinical_trigger": "brief sentence"}},
                "salience_weight_map": [
                    {{"entity": "name", "category": "Symptom|Medication|Medical History|Duration|Noise",
                      "salience_score": 0.95, "reasoning_context": "why"}}
                ],
                "clinical_safety_red_flags": ["warning"],
                "suggested_next_steps": ["action"],
                "structured_soap_chart": "markdown SOAP note. Subjective based only on salience_score >= 0.5."
            }}
            """

            resp   = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
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


# =====================================================================
# 11. OUTPUT — FULL MODE
# =====================================================================
def render_output_full():
    urgency = st.session_state.classification.get("urgency_tier", "")
    trigger = st.session_state.classification.get("primary_clinical_trigger", "")
    render_urgency_banner(urgency, trigger)

    out_tabs = st.tabs(["Key findings", "Red flags & next steps", "SOAP review", "Explainability"])

    # ── Key findings ──
    with out_tabs[0]:
        sig_col, trans_col = st.columns([1, 1], gap="large")
        with sig_col:
            st.markdown('<p class="panel-header">Clinical signals — by salience weight</p>', unsafe_allow_html=True)
            if st.session_state.salience_map:
                for item in sorted(st.session_state.salience_map, key=lambda x: x.get("salience_score",0), reverse=True):
                    score = item.get("salience_score", 0)
                    color = "var(--s-bar-critical)" if score >= 0.85 else "var(--s-bar-high)" if score >= 0.65 else "var(--s-bar-low)"
                    width = max(4, int(score * 60))
                    st.markdown(f"""
                    <div class="signal-row">
                        <div style="width:{width}px;height:3px;border-radius:2px;background:{color};flex-shrink:0"></div>
                        <span class="signal-name">{item.get('entity','')}</span>
                        <span class="signal-cat">{item.get('category','')}</span>
                        <span class="signal-score">{score:.2f}</span>
                    </div>""", unsafe_allow_html=True)
        with trans_col:
            st.markdown('<p class="panel-header">Cleaned transcript</p>', unsafe_allow_html=True)
            st.text_area("Transcript", value=st.session_state.transcript,
                         height=320, disabled=True, label_visibility="collapsed")

    # ── Red flags & next steps ──
    with out_tabs[1]:
        fc, sc = st.columns([1,1], gap="large")
        with fc:
            st.markdown('<p class="panel-header">Safety flags</p>', unsafe_allow_html=True)
            if st.session_state.flags:
                for f in st.session_state.flags:
                    st.markdown(f'<div class="flag-item" role="alert">{f}</div>', unsafe_allow_html=True)
            else:
                st.success("No safety flags identified.")
        with sc:
            st.markdown('<p class="panel-header">Suggested next steps</p>', unsafe_allow_html=True)
            for i, step in enumerate(st.session_state.next_steps, 1):
                st.markdown(f"""
                <div class="step-item">
                    <span style="opacity:.35;font-size:11px;min-width:16px;font-family:var(--s-font-mono)">{i}</span>
                    <span>{step}</span>
                </div>""", unsafe_allow_html=True)

    # ── SOAP review ──
    with out_tabs[2]:
        soap_col, action_col = st.columns([1.6, 1], gap="large")
        with soap_col:
            st.markdown('<p class="panel-header">Clinical note — pending review</p>', unsafe_allow_html=True)
            edited_soap = st.text_area("SOAP", value=st.session_state.soap_note,
                                       height=420, label_visibility="collapsed")
        with action_col:
            st.markdown('<p class="panel-header">Review & sign-off</p>', unsafe_allow_html=True)
            st.caption(f"Processed {st.session_state.pipeline_execution_time}s · {st.session_state.specialty}")
            st.divider()
            try:
                pdf = generate_clinical_pdf(edited_soap, st.session_state.specialty)
                st.download_button("Download PDF", data=pdf,
                    file_name=f"Salience_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                    mime="application/pdf", use_container_width=True)
            except Exception as e:
                st.error(f"PDF error: {e}")
            st.divider()
            if st.session_state.chart_locked:
                st.success("Signed and pushed to EHR.")
                st.button("Chart locked", disabled=True, use_container_width=True)
            else:
                st.warning("Note unsigned. Review before sign-off.")
                if st.button("Sign & push to EHR", type="primary", use_container_width=True):
                    with st.spinner("Pushing to EHR…"):
                        time.sleep(2.0)
                    st.session_state.chart_locked = True
                    st.rerun()

    # ── Explainability ──
    with out_tabs[3]:
        st.markdown('<p class="panel-header">Model reasoning</p>', unsafe_allow_html=True)
        for item in sorted(st.session_state.salience_map, key=lambda x: x.get("salience_score",0), reverse=True):
            score = item.get("salience_score", 0)
            cls   = "conf-hi" if score >= 0.85 else "conf-med" if score >= 0.65 else "conf-lo"
            lbl   = "High" if score >= 0.85 else "Medium" if score >= 0.65 else "Low"
            st.markdown(f"""
            <div class="explain-card">
                <div class="explain-head">
                    <span class="{cls}">●</span>{item.get('entity','')}
                    <span style="margin-left:auto;font-size:10px;color:var(--s-text-tertiary);
                                 font-family:var(--s-font-mono)">{lbl} · {score:.2f}</span>
                </div>
                <div class="explain-body">{item.get('reasoning_context','')}</div>
            </div>""", unsafe_allow_html=True)


# =====================================================================
# 12. OUTPUT — FOCUS MODE
# =====================================================================
def render_output_focus():
    st.markdown("""
    <div class="s-focus-banner" role="status">
        <i class="ti ti-focus-2" style="font-size:13px" aria-hidden="true"></i>
        Focus mode — settings and secondary panels hidden
    </div>""", unsafe_allow_html=True)

    urgency = st.session_state.classification.get("urgency_tier", "")
    trigger = st.session_state.classification.get("primary_clinical_trigger", "")
    render_urgency_banner(urgency, trigger)

    sig_col, right_col = st.columns([1, 1], gap="large")

    with sig_col:
        st.markdown('<p class="panel-header">Clinical signals</p>', unsafe_allow_html=True)
        for item in sorted(st.session_state.salience_map, key=lambda x: x.get("salience_score",0), reverse=True):
            score = item.get("salience_score", 0)
            color = "var(--s-bar-critical)" if score >= 0.85 else "var(--s-bar-high)" if score >= 0.65 else "var(--s-bar-low)"
            width = max(4, int(score * 60))
            st.markdown(f"""
            <div class="signal-row">
                <div style="width:{width}px;height:3px;border-radius:2px;background:{color};flex-shrink:0"></div>
                <span class="signal-name">{item.get('entity','')}</span>
                <span class="signal-score">{score:.2f}</span>
            </div>""", unsafe_allow_html=True)

        if st.session_state.flags:
            st.markdown('<br><p class="panel-header">Safety flags</p>', unsafe_allow_html=True)
            for f in st.session_state.flags:
                st.markdown(f'<div class="flag-item" role="alert">{f}</div>', unsafe_allow_html=True)

    with right_col:
        st.markdown('<p class="panel-header">SOAP draft</p>', unsafe_allow_html=True)
        edited_soap = st.text_area("SOAP", value=st.session_state.soap_note,
                                   height=340, label_visibility="collapsed")
        st.markdown("<br>", unsafe_allow_html=True)

        try:
            pdf = generate_clinical_pdf(edited_soap, st.session_state.specialty)
            st.download_button("Download PDF", data=pdf,
                file_name=f"Salience_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                mime="application/pdf", use_container_width=True)
        except Exception as e:
            st.error(f"PDF error: {e}")

        st.markdown("<br>", unsafe_allow_html=True)
        if st.session_state.chart_locked:
            st.success("Signed and pushed to EHR.")
            st.button("Chart locked", disabled=True, use_container_width=True)
        else:
            if st.button("Sign & push to EHR", type="primary", use_container_width=True):
                with st.spinner("Pushing to EHR…"):
                    time.sleep(2.0)
                st.session_state.chart_locked = True
                st.rerun()


# =====================================================================
# 13. MAIN RENDER LOOP
# =====================================================================

# Top bar (always rendered after setup)
if st.session_state.setup_done:
    render_topbar()

# Settings drawer overlay
if st.session_state.show_drawer:
    render_drawer()
    # Listen for postMessage close via a hidden component
    components.html("""
    <script>
    window.addEventListener('message', function(e) {
        if (e.data && e.data.type === 'salience') {
            if (e.data.action === 'close_drawer' || e.data.action === 'save_settings') {
                // Trigger rerun via Streamlit's internal mechanism
                window.parent.postMessage({type:'streamlit:setComponentValue', value: e.data}, '*');
            }
        }
    });
    </script>""", height=0)

    col_close = st.columns([3, 1])[1]
    with col_close:
        if st.button("Close settings", key="close_drawer_btn"):
            st.session_state.show_drawer = False
            st.rerun()

# ── SETUP CARD ──
if not st.session_state.setup_done:
    render_setup()

# ── MAIN WORKSPACE ──
else:
    st.markdown('<div class="s-content">', unsafe_allow_html=True)

    # Input phase
    if not st.session_state.transcript:
        has_payload, bypass_stt, injected, temp_audio, exam_overlay = render_input()
        st.divider()

        if st.button("Run salience analysis", type="primary",
                     use_container_width=True, disabled=not has_payload):
            run_pipeline(bypass_stt, injected, temp_audio, exam_overlay)

        if not has_payload:
            st.caption("Add a transcript or audio recording above to enable analysis.")

    # Output phase
    else:
        if st.session_state.focus_mode:
            render_output_focus()
        else:
            render_output_full()

    st.markdown('</div>', unsafe_allow_html=True)
