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
# 0. PDF UTILITIES (unchanged)
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
            pdf.line(pdf.l_margin, pdf.get_y(), pdf.l_margin + 40, pdf.get_y())
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
# 2. THEME ENGINE INJECTOR
# =====================================================================
def inject_theme_engine():
    components.html("""
    <script>
    (function() {
        const THEME_KEY = 'SALIENCE_THEME_KEY';
        function applyTheme(mode) {
            const root = window.parent.document.documentElement;
            if (mode === 'system') {
                const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
                root.setAttribute('data-salience-theme', prefersDark ? 'dark' : 'light');
            } else {
                root.setAttribute('data-salience-theme', mode);
            }
        }
        window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
            const stored = localStorage.getItem('SALIENCE_THEME_KEY') || 'system';
            if (stored === 'system') applyTheme('system');
        });
        const stored = localStorage.getItem(THEME_KEY) || 'system';
        applyTheme(stored);
    })();
    </script>
    """, height=0, scrolling=False)

inject_theme_engine()


# =====================================================================
# 3. DESIGN SYSTEM CSS
# =====================================================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap');

/* ══ TOKEN LAYER — Light ══ */
:root,
html[data-salience-theme="light"] {
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
    --s-critical-icon:   #DC2626;
    --s-critical-glow:   rgba(220,38,38,0.18);
    --s-critical-pulse:  rgba(220,38,38,0.08);
    --s-high-bg:         #FFFBEB;
    --s-high-border:     #FDE68A;
    --s-high-rail:       #D97706;
    --s-high-text:       #78350F;
    --s-high-label:      #92400E;
    --s-high-icon:       #D97706;
    --s-medium-bg:       #EFF6FF;
    --s-medium-border:   #BFDBFE;
    --s-medium-rail:     #2563EB;
    --s-medium-text:     #1E3A5F;
    --s-medium-label:    #1D4ED8;
    --s-medium-icon:     #2563EB;
    --s-info-bg:         #F0FDF4;
    --s-info-border:     #BBF7D0;
    --s-info-rail:       #16A34A;
    --s-info-text:       #14532D;
    --s-info-label:      #15803D;
    --s-info-icon:       #16A34A;
    --s-bar-critical:    #DC2626;
    --s-bar-high:        #D97706;
    --s-bar-low:         #16A34A;
    --s-transition:      background 0.2s ease, color 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
    --s-font-ui:         'IBM Plex Sans', system-ui, sans-serif;
    --s-font-mono:       'IBM Plex Mono', 'SF Mono', monospace;
    --s-weight-normal:   400;
    --s-weight-medium:   500;
    --s-weight-semibold: 600;
}

/* ══ TOKEN LAYER — Dark ══ */
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
    --s-critical-icon:   #EF4444;
    --s-critical-glow:   rgba(239,68,68,0.25);
    --s-critical-pulse:  rgba(239,68,68,0.10);
    --s-high-bg:         rgba(217,119,6,0.10);
    --s-high-border:     rgba(217,119,6,0.35);
    --s-high-rail:       #F59E0B;
    --s-high-text:       #FCD34D;
    --s-high-label:      #FBBF24;
    --s-high-icon:       #F59E0B;
    --s-medium-bg:       rgba(37,99,235,0.12);
    --s-medium-border:   rgba(37,99,235,0.35);
    --s-medium-rail:     #60A5FA;
    --s-medium-text:     #BFDBFE;
    --s-medium-label:    #93C5FD;
    --s-medium-icon:     #60A5FA;
    --s-info-bg:         rgba(22,163,74,0.10);
    --s-info-border:     rgba(22,163,74,0.30);
    --s-info-rail:       #34D399;
    --s-info-text:       #A7F3D0;
    --s-info-label:      #6EE7B7;
    --s-info-icon:       #34D399;
    --s-bar-critical:    #EF4444;
    --s-bar-high:        #F59E0B;
    --s-bar-low:         #34D399;
}

/* ══ GLOBAL BASE ══ */
html, body,
[data-testid="stAppViewContainer"],
[data-testid="stMain"],
.main, .block-container {
    font-family: var(--s-font-ui) !important;
    background: var(--s-bg-base) !important;
    color: var(--s-text-primary) !important;
    transition: var(--s-transition);
}
h1, h2, h3, h4 {
    font-family: var(--s-font-ui) !important;
    font-weight: var(--s-weight-semibold) !important;
    color: var(--s-text-primary) !important;
}
p, span, div, label { font-family: var(--s-font-ui) !important; }

/* Hide Streamlit chrome & sidebar */
#MainMenu, footer,
[data-testid="stDecoration"],
[data-testid="stToolbar"],
[data-testid="collapsedControl"],
[data-testid="stSidebarCollapsedControl"],
section[data-testid="stSidebar"] {
    display: none !important;
    visibility: hidden !important;
}

.block-container { padding: 0 !important; max-width: 100% !important; }

/* ══ TOP BAR ══ */
.s-topbar {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 11px 24px;
    background: var(--s-bg-surface);
    border-bottom: 1px solid var(--s-border);
    transition: var(--s-transition);
}
.s-logo {
    font-size: 14px;
    font-weight: var(--s-weight-semibold);
    color: var(--s-text-primary);
    letter-spacing: 0.2px;
    flex-shrink: 0;
}
.s-logo span { opacity: 0.35; font-weight: var(--s-weight-normal); }
.s-spec-badge {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    font-size: 11px;
    font-weight: var(--s-weight-medium);
    color: var(--s-text-secondary);
    background: var(--s-bg-subtle);
    border: 1px solid var(--s-border);
    padding: 4px 10px;
    border-radius: 20px;
    flex-shrink: 0;
}
.s-topbar-spacer { flex: 1; }
.s-topbar-actions { display: flex; align-items: center; gap: 6px; }
.s-theme-row { display: flex; gap: 4px; }
.s-theme-btn {
    padding: 5px 10px;
    font-size: 11px;
    font-weight: var(--s-weight-medium);
    font-family: var(--s-font-ui);
    border: 1px solid var(--s-border);
    border-radius: 7px;
    background: var(--s-bg-surface);
    color: var(--s-text-secondary);
    cursor: pointer;
    transition: all 0.15s ease;
}
.s-theme-btn:hover { background: var(--s-bg-subtle); color: var(--s-text-primary); }
.s-theme-btn.active {
    background: var(--s-text-primary);
    color: var(--s-text-inverse);
    border-color: transparent;
}

/* ══ DRAWER ══ */
.s-drawer-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(0,0,0,0.2);
    z-index: 200;
    animation: fadeIn 0.15s ease;
}
.s-drawer {
    position: fixed;
    top: 0; right: 0; bottom: 0;
    width: 340px;
    background: var(--s-bg-surface);
    border-left: 1px solid var(--s-border);
    z-index: 201;
    display: flex;
    flex-direction: column;
    animation: slideIn 0.2s ease;
    box-shadow: -8px 0 32px rgba(0,0,0,0.08);
    overflow-y: auto;
    padding: 20px;
    transition: var(--s-transition);
}
@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
@keyframes slideIn { from { transform: translateX(100%); } to { transform: translateX(0); } }
.s-drawer-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 20px;
    padding-bottom: 16px;
    border-bottom: 1px solid var(--s-border);
}
.s-drawer-title {
    font-size: 13px;
    font-weight: var(--s-weight-semibold);
    color: var(--s-text-primary);
}
.s-drawer-label {
    display: block;
    font-size: 10px;
    font-weight: var(--s-weight-semibold);
    letter-spacing: 0.9px;
    text-transform: uppercase;
    color: var(--s-text-tertiary);
    margin-bottom: 8px;
    margin-top: 18px;
}
.s-drawer-label:first-child { margin-top: 0; }
.s-vault-status {
    display: flex;
    align-items: center;
    gap: 7px;
    padding: 9px 12px;
    background: var(--s-info-bg);
    border: 1px solid var(--s-info-border);
    border-radius: 8px;
    font-size: 11px;
    color: var(--s-info-text);
}

/* ══ CONTENT WRAPPER ══ */
.s-content { padding: 24px 32px; max-width: 1280px; margin: 0 auto; }

/* ══ PANEL HEADER ══ */
.panel-header {
    font-family: var(--s-font-ui) !important;
    font-size: 10px;
    font-weight: var(--s-weight-semibold);
    letter-spacing: 0.9px;
    text-transform: uppercase;
    color: var(--s-text-tertiary) !important;
    margin-bottom: 0.6rem;
}

/* ══ SEVERITY ALERTS ══ */
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
    font-weight: var(--s-weight-semibold);
    letter-spacing: 0.9px;
    text-transform: uppercase;
    margin-bottom: 4px;
}
.alert-desc { font-size: 13px; line-height: 1.55; }
.alert-critical {
    background: var(--s-critical-bg);
    border-color: var(--s-critical-border);
    box-shadow: 0 0 0 1px var(--s-critical-border), 0 4px 16px var(--s-critical-glow);
    animation: criticalPulse 2.4s ease-in-out infinite;
}
.alert-critical .alert-rail { background: var(--s-critical-rail); }
.alert-critical .alert-tier { color: var(--s-critical-label); }
.alert-critical .alert-desc { color: var(--s-critical-text); }
@keyframes criticalPulse {
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

/* ══ FLAG ITEMS ══ */
.flag-item {
    display: flex;
    align-items: flex-start;
    gap: 10px;
    background: var(--s-critical-bg);
    border: 1px solid var(--s-critical-border);
    border-left: 4px solid var(--s-critical-rail);
    border-radius: 0 8px 8px 0;
    padding: 10px 13px;
    font-size: 12px;
    color: var(--s-critical-text);
    margin-bottom: 7px;
    line-height: 1.55;
    transition: var(--s-transition);
}
.flag-item::before { content: "⚠"; font-size: 13px; flex-shrink: 0; margin-top: 1px; }

/* ══ SIGNAL ROWS ══ */
.signal-row {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 9px 6px;
    border-bottom: 1px solid var(--s-border);
    border-radius: 6px;
    transition: background 0.15s ease;
}
.signal-row:last-child { border-bottom: none; }
.signal-row:hover { background: var(--s-bg-hover); }
.signal-name { font-size: 13px; font-weight: var(--s-weight-medium); color: var(--s-text-primary); flex: 1; }
.signal-cat  { font-size: 10px; color: var(--s-text-tertiary); }
.signal-score {
    font-family: var(--s-font-mono);
    font-size: 11px;
    color: var(--s-text-secondary);
    width: 32px;
    text-align: right;
}

/* ══ EXPLAIN CARDS ══ */
.explain-card {
    border: 1px solid var(--s-border);
    border-radius: 9px;
    padding: 11px 14px;
    margin-bottom: 8px;
    background: var(--s-bg-surface);
    transition: var(--s-transition);
}
.explain-card:hover { border-color: var(--s-border-strong); box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
.explain-head {
    font-size: 12px;
    font-weight: var(--s-weight-semibold);
    margin-bottom: 5px;
    display: flex;
    align-items: center;
    gap: 7px;
    color: var(--s-text-primary);
}
.explain-body { font-size: 11px; color: var(--s-text-secondary); line-height: 1.65; }
.conf-hi  { color: var(--s-critical-icon); }
.conf-med { color: var(--s-high-icon); }
.conf-lo  { color: var(--s-info-icon); }

/* ══ STEP LIST ══ */
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

/* ══ BUTTONS ══ */
[data-testid="stButton"] button {
    font-family: var(--s-font-ui) !important;
    font-size: 13px !important;
    font-weight: var(--s-weight-medium) !important;
    border-radius: 8px !important;
    border: 1px solid var(--s-border-strong) !important;
    background: var(--s-bg-surface) !important;
    color: var(--s-text-primary) !important;
    transition: all 0.15s ease !important;
    padding: 0.45rem 1rem !important;
}
[data-testid="stButton"] button:hover {
    background: var(--s-bg-subtle) !important;
    transform: translateY(-1px);
    box-shadow: 0 2px 8px rgba(0,0,0,0.08) !important;
}
[data-testid="stButton"] button:active { transform: translateY(0) scale(0.98) !important; }
[data-testid="stButton"] button:focus-visible {
    outline: 2px solid var(--s-border-focus) !important;
    outline-offset: 2px !important;
}
[data-testid="stButton"] button[kind="primary"] {
    background: var(--s-text-primary) !important;
    color: var(--s-text-inverse) !important;
    border-color: transparent !important;
}
[data-testid="stButton"] button[kind="primary"]:hover { opacity: 0.88 !important; }
[data-testid="stButton"] button:disabled {
    opacity: 0.38 !important;
    cursor: not-allowed !important;
    transform: none !important;
    box-shadow: none !important;
}

/* ══ FORM ELEMENTS ══ */
[data-baseweb="select"] > div,
[data-baseweb="input"] > div,
[data-baseweb="textarea"] {
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

/* ══ TABS ══ */
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
    font-weight: var(--s-weight-medium) !important;
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

/* ══ METRICS ══ */
[data-testid="metric-container"] {
    background: var(--s-bg-surface) !important;
    border-radius: 10px !important;
    padding: 12px 16px !important;
    border: 1px solid var(--s-border) !important;
    transition: var(--s-transition);
}
[data-testid="metric-container"] label {
    font-size: 10px !important;
    font-weight: var(--s-weight-semibold) !important;
    letter-spacing: 0.7px !important;
    text-transform: uppercase !important;
    color: var(--s-text-tertiary) !important;
}
[data-testid="metric-container"] [data-testid="stMetricValue"] {
    font-family: var(--s-font-mono) !important;
    font-size: 18px !important;
    font-weight: var(--s-weight-semibold) !important;
    color: var(--s-text-primary) !important;
}

/* ══ MISC ══ */
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
[data-testid="stRadio"] label {
    font-family: var(--s-font-ui) !important;
    font-size: 13px !important;
    color: var(--s-text-secondary) !important;
}
[data-testid="stDownloadButton"] button {
    font-family: var(--s-font-ui) !important;
    font-size: 13px !important;
    font-weight: var(--s-weight-medium) !important;
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
*:focus-visible {
    outline: 2px solid var(--s-border-focus) !important;
    outline-offset: 2px !important;
}
</style>
""", unsafe_allow_html=True)


# =====================================================================
# 4. SESSION STATE
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
    "show_drawer": False,
    "focus_mode": False,
    "specialty_profile": "Cardiology Clinic",
    "target_language": "Mixed (Multi-lingual Code-Switching)",
    "groq_key_override": "",
    "gemini_key_override": "",
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

specialty_options = [
    "Cardiology Clinic", "General Internal Medicine", "Emergency Trauma",
    "Neurology", "Pediatrics", "Orthopedic Surgery",
    "Psychiatry & Behavioral Health", "Oncology",
]
language_options = [
    "Mixed (Multi-lingual Code-Switching)",
    "English (US/UK)",
    "Arabic (Khaleeji/MSA)",
]
specialty_short = {
    "Cardiology Clinic":            "Cardiology",
    "General Internal Medicine":    "Gen. Medicine",
    "Emergency Trauma":             "Emergency",
    "Neurology":                    "Neurology",
    "Pediatrics":                   "Pediatrics",
    "Orthopedic Surgery":           "Orthopaedics",
    "Psychiatry & Behavioral Health": "Psychiatry",
    "Oncology":                     "Oncology",
}


# =====================================================================
# 5. TOP BAR  (pure HTML + inline JS for theme; Streamlit buttons for drawer/focus)
# =====================================================================
spec_label = specialty_short.get(st.session_state.specialty_profile,
                                  st.session_state.specialty_profile)

st.markdown(f"""
<div class="s-topbar">
    <div class="s-logo">Salience <span>OS</span></div>
    <div class="s-spec-badge">⊕ {spec_label}</div>
    <div class="s-topbar-spacer"></div>
    <div class="s-topbar-actions">
        <div class="s-theme-row">
            <button class="s-theme-btn" id="tbtn-light"  onclick="setTheme('light')"  title="Light">☀ Light</button>
            <button class="s-theme-btn" id="tbtn-system" onclick="setTheme('system')" title="System">◑ System</button>
            <button class="s-theme-btn" id="tbtn-dark"   onclick="setTheme('dark')"   title="Dark">☽ Dark</button>
        </div>
    </div>
</div>
<script>
(function(){{
    const KEY = 'SALIENCE_THEME_KEY';
    window.setTheme = function(mode) {{
        localStorage.setItem(KEY, mode);
        const root = window.parent.document.documentElement;
        if (mode === 'system') {{
            const dark = window.matchMedia('(prefers-color-scheme: dark)').matches;
            root.setAttribute('data-salience-theme', dark ? 'dark' : 'light');
        }} else {{
            root.setAttribute('data-salience-theme', mode);
        }}
        document.querySelectorAll('.s-theme-btn').forEach(b => b.classList.remove('active'));
        const el = document.getElementById('tbtn-' + mode);
        if (el) el.classList.add('active');
    }};
    const stored = localStorage.getItem(KEY) || 'system';
    const el = document.getElementById('tbtn-' + stored);
    if (el) el.classList.add('active');
}})();
</script>
""", unsafe_allow_html=True)


# =====================================================================
# 6. TOP BAR ACTION BUTTONS  (Streamlit buttons styled to match the bar)
# =====================================================================
btn_col1, btn_col2, btn_col3 = st.columns([1, 1, 8])

with btn_col1:
    settings_label = "⚙ Settings"
    if st.button(settings_label, key="topbar_settings"):
        st.session_state.show_drawer = not st.session_state.show_drawer
        st.rerun()

with btn_col2:
    focus_label = "◎ Focus" if not st.session_state.focus_mode else "⊙ Exit focus"
    if st.button(focus_label, key="topbar_focus"):
        st.session_state.focus_mode = not st.session_state.focus_mode
        st.rerun()

# Style these two buttons to look like top-bar icon buttons, not page content
st.markdown("""
<style>
/* Target only the first two button columns in the top action row */
div[data-testid="stHorizontalBlock"]:first-of-type [data-testid="stButton"] button {
    font-size: 11px !important;
    padding: 0.3rem 0.75rem !important;
    border-radius: 7px !important;
    height: 32px !important;
    white-space: nowrap !important;
}
</style>
""", unsafe_allow_html=True)


# =====================================================================
# 7. SETTINGS DRAWER
# =====================================================================
has_cloud_groq   = "groq_api_key"   in st.secrets
has_cloud_gemini = "gemini_api_key" in st.secrets

if st.session_state.show_drawer:
    # Backdrop — clicking it closes the drawer via a button below
    st.markdown("""
    <div class="s-drawer-backdrop" id="drawer-backdrop"></div>
    <div class="s-drawer" role="dialog" aria-modal="true" aria-label="Workspace settings">
        <div class="s-drawer-head">
            <span class="s-drawer-title">Workspace settings</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # All interactive drawer content rendered as normal Streamlit widgets
    # in a visually contained block
    with st.container():
        st.markdown("""
        <style>
        /* Push this container to overlap the drawer area visually */
        div[data-testid="stVerticalBlockBorderWrapper"]:has(#drawer-inner) {
            position: fixed;
            top: 0; right: 0; bottom: 0;
            width: 340px;
            background: var(--s-bg-surface);
            border-left: 1px solid var(--s-border);
            z-index: 202;
            overflow-y: auto;
            padding: 20px;
            box-shadow: -8px 0 32px rgba(0,0,0,0.08);
        }
        </style>
        <div id="drawer-inner"></div>
        """, unsafe_allow_html=True)

        st.markdown("### Workspace settings")
        st.divider()

        # Specialty
        st.markdown('<span class="s-drawer-label">Specialty profile</span>', unsafe_allow_html=True)
        new_specialty = st.selectbox(
            "Specialty profile",
            specialty_options,
            index=specialty_options.index(st.session_state.specialty_profile),
            key="drawer_specialty",
            label_visibility="collapsed",
        )
        if new_specialty != st.session_state.specialty_profile:
            st.session_state.specialty_profile = new_specialty

        # Language
        st.markdown('<span class="s-drawer-label">Language matrix</span>', unsafe_allow_html=True)
        new_language = st.selectbox(
            "Language matrix",
            language_options,
            index=language_options.index(st.session_state.target_language),
            key="drawer_language",
            label_visibility="collapsed",
        )
        if new_language != st.session_state.target_language:
            st.session_state.target_language = new_language

        # API credentials
        st.markdown('<span class="s-drawer-label">API credentials</span>', unsafe_allow_html=True)
        if has_cloud_groq and has_cloud_gemini:
            st.markdown(
                '<div class="s-vault-status">🔒 Vault active — credentials pre-loaded</div>',
                unsafe_allow_html=True
            )
        else:
            new_groq = st.text_input(
                "Groq — Whisper v3",
                type="password",
                value=st.session_state.groq_key_override,
                placeholder="Active via vault" if has_cloud_groq else "sk-...",
                key="drawer_groq",
            )
            new_gemini = st.text_input(
                "Gemini — Flash 2.5",
                type="password",
                value=st.session_state.gemini_key_override,
                placeholder="Active via vault" if has_cloud_gemini else "AI...",
                key="drawer_gemini",
            )
            st.session_state.groq_key_override   = new_groq
            st.session_state.gemini_key_override = new_gemini

        # Focus mode toggle inside drawer
        st.markdown('<span class="s-drawer-label">Focus mode</span>', unsafe_allow_html=True)
        focus_btn_label = "Exit focus mode" if st.session_state.focus_mode else "Enable focus mode"
        if st.button(focus_btn_label, key="drawer_focus", use_container_width=True):
            st.session_state.focus_mode  = not st.session_state.focus_mode
            st.session_state.show_drawer = False
            st.rerun()

        st.divider()

        # New consultation (only when output exists)
        if st.session_state.transcript:
            if st.button("New consultation", key="drawer_new", use_container_width=True):
                for key in ["transcript", "classification", "salience_map",
                            "soap_note", "flags", "next_steps",
                            "pipeline_execution_time", "chart_locked"]:
                    st.session_state[key] = defaults[key]
                st.session_state.show_drawer = False
                st.rerun()

        # Close button at the bottom
        if st.button("✕ Close", key="drawer_close", use_container_width=True):
            st.session_state.show_drawer = False
            st.rerun()


# =====================================================================
# 8. RESOLVE KEYS
# =====================================================================
groq_api_key = (
    st.session_state.groq_key_override.strip()
    or st.secrets.get("groq_api_key", "")
)
gemini_api_key = (
    st.session_state.gemini_key_override.strip()
    or st.secrets.get("gemini_api_key", "")
)
specialty_profile = st.session_state.specialty_profile
target_language   = st.session_state.target_language


# =====================================================================
# 9. MAIN CONTENT
# =====================================================================
st.markdown('<div class="s-content">', unsafe_allow_html=True)


# =====================================================================
# 10. INPUT AREA
# =====================================================================
if not st.session_state.transcript:
    cap_col, exam_col = st.columns([1.1, 1], gap="large")

    with cap_col:
        st.markdown('<p class="panel-header">Input capture</p>', unsafe_allow_html=True)
        input_vector = st.radio(
            "Input mode",
            ["Text (paste/type)", "Microphone (live)", "File upload (.wav / .json)"],
            label_visibility="collapsed",
        )

        temp_audio_filename     = "active_stream_input.wav"
        has_valid_audio_payload = False
        bypass_audio_stt        = False
        injected_text_payload   = ""

        if "Text" in input_vector:
            injected_text_payload = st.text_area(
                "Transcript",
                placeholder="Paste or type the consultation transcript here…",
                height=180,
                label_visibility="collapsed",
            )
            if injected_text_payload.strip():
                has_valid_audio_payload = True
                bypass_audio_stt        = True

        elif "Microphone" in input_vector:
            audio_file = st.audio_input("Record")
            if audio_file is not None:
                with open(temp_audio_filename, "wb") as f:
                    f.write(audio_file.read())
                has_valid_audio_payload = True

        else:
            uploaded_file = st.file_uploader(
                "Upload file",
                type=["wav", "mp3", "m4a", "json"],
                label_visibility="collapsed",
            )
            if uploaded_file is not None:
                if uploaded_file.name.endswith('.json'):
                    try:
                        json_data = json.load(uploaded_file)
                        if isinstance(json_data, list):
                            st.success(f"{len(json_data)} cases loaded")
                            case_idx      = st.number_input("Case index", min_value=0,
                                                            max_value=len(json_data) - 1, value=0)
                            selected_node = json_data[case_idx]
                            injected_text_payload = selected_node.get(
                                "input", selected_node.get("instruction", ""))
                            if injected_text_payload:
                                st.caption(injected_text_payload[:200] + "…")
                                has_valid_audio_payload = True
                                bypass_audio_stt        = True
                        else:
                            st.error("JSON must be a list of case objects.")
                    except Exception as json_err:
                        st.error(f"JSON parse error: {json_err}")
                else:
                    with open(temp_audio_filename, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    st.audio(temp_audio_filename)
                    has_valid_audio_payload = True

    with exam_col:
        st.markdown('<p class="panel-header">Physical examination</p>', unsafe_allow_html=True)
        organ_tabs = st.tabs(["Thoracic", "GI / Abdomen", "Neuro", "MSK"])
        with organ_tabs[0]:
            notes_thoracic = st.text_area(
                "Thoracic",
                value="Cardiovascular: Tachycardic, rhythm regular. S1 and S2 distinct, no audible murmurs. "
                      "Diaphoresis noted. Respiratory: Tachypneic, shallow. CTAB bilaterally.",
                height=100, label_visibility="collapsed",
            )
        with organ_tabs[1]:
            notes_abdominal = st.text_area(
                "GI",
                value="Abdomen soft, non-distended. Bowel sounds active. No tenderness, guarding, or rebound. "
                      "No hepatosplenomegaly. Epigastric non-tender.",
                height=100, label_visibility="collapsed",
            )
        with organ_tabs[2]:
            notes_neuro = st.text_area(
                "Neuro",
                value="A&Ox3. PERRLA. Orthostatic lightheadedness on sitting up. Gross motor and sensory intact.",
                height=100, label_visibility="collapsed",
            )
        with organ_tabs[3]:
            notes_ortho = st.text_area(
                "MSK",
                value="Mild lumbar paraspinal tenderness. Left shoulder and mandible — full passive ROM, "
                      "no joint tenderness.",
                height=100, label_visibility="collapsed",
            )

    compiled_examination_overlay = (
        f"- Thoracic: {notes_thoracic}\n"
        f"- GI/Abdomen: {notes_abdominal}\n"
        f"- Neuro/Reflex: {notes_neuro}\n"
        f"- Musculoskeletal: {notes_ortho}"
    )

    st.divider()

    if st.button(
        "Run salience analysis",
        type="primary",
        use_container_width=True,
        disabled=not has_valid_audio_payload,
        key="run_pipeline",
    ):
        if not groq_api_key or not gemini_api_key:
            st.error("API credentials missing. Open ⚙ Settings (top left) to add keys.")
        else:
            pipeline_start = time.time()
            with st.status("Running analysis pipeline…", expanded=True) as status:
                try:
                    # STAGE 1 — STT
                    if bypass_audio_stt:
                        extracted_raw_text = injected_text_payload
                        st.write("✓ Text input ingested")
                    else:
                        st.write("Compressing audio…")
                        raw_audio       = AudioSegment.from_file(temp_audio_filename)
                        processed_audio = raw_audio.set_channels(1).set_frame_rate(16000)
                        compressed      = "optimized_api_payload.mp3"
                        processed_audio.export(compressed, format="mp3", bitrate="64k")
                        groq_client = Groq(api_key=groq_api_key, timeout=60.0)
                        with open(compressed, "rb") as ab:
                            extracted_raw_text = groq_client.audio.transcriptions.create(
                                file=(compressed, ab.read()),
                                model="whisper-large-v3",
                                response_format="text",
                            )
                        for f in [temp_audio_filename, compressed]:
                            if os.path.exists(f):
                                os.remove(f)
                        st.write("✓ Transcription complete")

                    # STAGE 2 — Gemini
                    st.write("Running clinical salience engine…")
                    genai.configure(api_key=gemini_api_key)
                    engine = genai.GenerativeModel('gemini-2.5-flash')

                    prompt = f"""
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
                    response = engine.generate_content(
                        prompt,
                        generation_config={"response_mime_type": "application/json"},
                    )
                    parsed = json.loads(response.text, strict=False)

                    st.session_state.transcript              = parsed.get("cleaned_transcript", "")
                    st.session_state.classification          = parsed.get("classification", {})
                    st.session_state.salience_map            = parsed.get("salience_weight_map", [])
                    st.session_state.soap_note               = parsed.get("structured_soap_chart", "")
                    st.session_state.flags                   = parsed.get("clinical_safety_red_flags", [])
                    st.session_state.next_steps              = parsed.get("suggested_next_steps", [])
                    st.session_state.pipeline_execution_time = round(time.time() - pipeline_start, 2)
                    st.session_state.chart_locked            = False

                    status.update(label="Analysis complete", state="complete", expanded=False)
                    st.rerun()

                except Exception as e:
                    status.update(label="Pipeline error", state="error")
                    st.error(f"Error: {e}")

    if not has_valid_audio_payload:
        st.caption("Add a transcript or recording above to enable analysis.")


# =====================================================================
# 11. OUTPUT WORKSPACE
# =====================================================================
if st.session_state.transcript:

    urgency = st.session_state.classification.get("urgency_tier", "")
    trigger = st.session_state.classification.get("primary_clinical_trigger", "")

    _tier_map = {
        "CRITICAL": ("alert-critical", "⬤ Critical — immediate action required"),
        "HIGH":     ("alert-high",     "⬤ High priority"),
        "MEDIUM":   ("alert-medium",   "⬤ Medium priority"),
        "LOW":      ("alert-info",     "⬤ Low urgency"),
    }
    if urgency in _tier_map:
        css_class, label_text = _tier_map[urgency]
        st.markdown(f"""
        <div class="alert-shell {css_class}" role="alert" aria-live="assertive">
            <div class="alert-rail"></div>
            <div class="alert-body">
                <div class="alert-tier">{label_text}</div>
                <div class="alert-desc">{trigger}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # ── FOCUS MODE ──
    if st.session_state.focus_mode:
        fc1, fc2 = st.columns([1, 1], gap="large")

        with fc1:
            st.markdown('<p class="panel-header">Clinical signals</p>', unsafe_allow_html=True)
            for item in sorted(st.session_state.salience_map,
                               key=lambda x: x.get("salience_score", 0), reverse=True):
                score     = item.get("salience_score", 0)
                bar_color = (
                    "var(--s-bar-critical)" if score >= 0.85
                    else "var(--s-bar-high)" if score >= 0.65
                    else "var(--s-bar-low)"
                )
                bar_width = max(4, int(score * 60))
                st.markdown(f"""
                <div class="signal-row">
                    <div style="width:{bar_width}px;height:3px;border-radius:2px;
                                background:{bar_color};flex-shrink:0"></div>
                    <span class="signal-name">{item.get('entity','')}</span>
                    <span class="signal-cat">{item.get('category','')}</span>
                    <span class="signal-score">{score:.2f}</span>
                </div>
                """, unsafe_allow_html=True)

            st.markdown('<p class="panel-header" style="margin-top:20px">Safety flags</p>',
                        unsafe_allow_html=True)
            if st.session_state.flags:
                for flag in st.session_state.flags:
                    st.markdown(f'<div class="flag-item" role="alert">{flag}</div>',
                                unsafe_allow_html=True)
            else:
                st.success("No safety flags identified.")

        with fc2:
            st.markdown('<p class="panel-header">SOAP note</p>', unsafe_allow_html=True)
            edited_soap = st.text_area(
                "SOAP", value=st.session_state.soap_note,
                height=320, label_visibility="collapsed", key="focus_soap",
            )
            try:
                pdf_bin = generate_clinical_pdf(edited_soap, specialty_profile)
                st.download_button(
                    "Download PDF", data=pdf_bin,
                    file_name=f"Salience_OS_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                    mime="application/pdf", use_container_width=True,
                )
            except Exception as pdf_err:
                st.error(f"PDF error: {pdf_err}")

            if st.session_state.chart_locked:
                st.success("Signed and pushed to EHR.")
                st.button("Chart locked", disabled=True, use_container_width=True, key="focus_locked")
            else:
                st.warning("Note unsigned. Review before sign-off.")
                if st.button("Sign & push to EHR", type="primary",
                             use_container_width=True, key="focus_sign"):
                    with st.spinner("Pushing to EHR…"):
                        time.sleep(2.0)
                        st.session_state.chart_locked = True
                        st.rerun()

    # ── FULL MODE ──
    else:
        out_tabs = st.tabs([
            "Key findings",
            "Red flags & next steps",
            "SOAP review",
            "Explainability",
        ])

        # Tab 1 — Key findings
        with out_tabs[0]:
            sig_col, trans_col = st.columns([1, 1], gap="large")
            with sig_col:
                st.markdown('<p class="panel-header">Clinical signals — by salience weight</p>',
                            unsafe_allow_html=True)
                for item in sorted(st.session_state.salience_map,
                                   key=lambda x: x.get("salience_score", 0), reverse=True):
                    score     = item.get("salience_score", 0)
                    bar_color = (
                        "var(--s-bar-critical)" if score >= 0.85
                        else "var(--s-bar-high)" if score >= 0.65
                        else "var(--s-bar-low)"
                    )
                    bar_width = max(4, int(score * 60))
                    st.markdown(f"""
                    <div class="signal-row">
                        <div style="width:{bar_width}px;height:3px;border-radius:2px;
                                    background:{bar_color};flex-shrink:0"></div>
                        <span class="signal-name">{item.get('entity','')}</span>
                        <span class="signal-cat">{item.get('category','')}</span>
                        <span class="signal-score">{score:.2f}</span>
                    </div>
                    """, unsafe_allow_html=True)
            with trans_col:
                st.markdown('<p class="panel-header">Cleaned transcript</p>', unsafe_allow_html=True)
                st.text_area(
                    "Transcript", value=st.session_state.transcript,
                    height=320, disabled=True, label_visibility="collapsed", key="full_transcript",
                )

        # Tab 2 — Red flags & next steps
        with out_tabs[1]:
            flag_col, step_col = st.columns([1, 1], gap="large")
            with flag_col:
                st.markdown('<p class="panel-header">Safety flags</p>', unsafe_allow_html=True)
                if st.session_state.flags:
                    for flag in st.session_state.flags:
                        st.markdown(f'<div class="flag-item" role="alert">{flag}</div>',
                                    unsafe_allow_html=True)
                else:
                    st.success("No safety flags identified.")
            with step_col:
                st.markdown('<p class="panel-header">Suggested next steps</p>', unsafe_allow_html=True)
                for i, step in enumerate(st.session_state.next_steps, 1):
                    st.markdown(f"""
                    <div class="step-item">
                        <span style="opacity:0.35;font-size:11px;min-width:16px;
                                     font-family:var(--s-font-mono)">{i}</span>
                        <span>{step}</span>
                    </div>
                    """, unsafe_allow_html=True)

        # Tab 3 — SOAP review
        with out_tabs[2]:
            soap_col, action_col = st.columns([1.6, 1], gap="large")
            with soap_col:
                st.markdown('<p class="panel-header">Clinical note — pending review</p>',
                            unsafe_allow_html=True)
                edited_soap = st.text_area(
                    "SOAP note", value=st.session_state.soap_note,
                    height=420, label_visibility="collapsed", key="full_soap",
                )
            with action_col:
                st.markdown('<p class="panel-header">Review & sign-off</p>', unsafe_allow_html=True)
                st.caption(
                    f"Processed {st.session_state.pipeline_execution_time}s ago · {specialty_profile}"
                )
                st.divider()
                try:
                    pdf_bin = generate_clinical_pdf(edited_soap, specialty_profile)
                    st.download_button(
                        "Download PDF", data=pdf_bin,
                        file_name=f"Salience_OS_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                        mime="application/pdf", use_container_width=True,
                    )
                except Exception as pdf_err:
                    st.error(f"PDF error: {pdf_err}")
                st.divider()
                if st.session_state.chart_locked:
                    st.success("Signed and pushed to EHR.")
                    st.button("Chart locked", disabled=True,
                              use_container_width=True, key="full_locked")
                else:
                    st.warning("Note is unsigned. Review before sign-off.")
                    if st.button("Sign & push to EHR", type="primary",
                                 use_container_width=True, key="full_sign"):
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
            st.markdown(
                '<p class="panel-header">Model reasoning — why these signals were prioritised</p>',
                unsafe_allow_html=True,
            )
            for item in sorted(st.session_state.salience_map,
                               key=lambda x: x.get("salience_score", 0), reverse=True):
                score = item.get("salience_score", 0)
                conf_class, conf_label = (
                    ("conf-hi",  "High")   if score >= 0.85 else
                    ("conf-med", "Medium") if score >= 0.65 else
                    ("conf-lo",  "Low")
                )
                st.markdown(f"""
                <div class="explain-card">
                    <div class="explain-head">
                        <span class="{conf_class}">●</span>
                        {item.get('entity','')}
                        <span style="margin-left:auto;font-size:10px;
                                     color:var(--s-text-tertiary);
                                     font-family:var(--s-font-mono)">
                            {conf_label} · {score:.2f}
                        </span>
                    </div>
                    <div class="explain-body">{item.get('reasoning_context','')}</div>
                </div>
                """, unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)
