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
    initial_sidebar_state="expanded"
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

/* ══════════════════════════════════════════
   TOKEN LAYER — Light
══════════════════════════════════════════ */
:root,
html[data-salience-theme="light"] {
    --s-bg-base:          #F7F8FA;
    --s-bg-surface:       #FFFFFF;
    --s-bg-raised:        #FFFFFF;
    --s-bg-subtle:        #F0F2F5;
    --s-bg-hover:         rgba(0,0,0,0.04);
    --s-border:           rgba(0,0,0,0.08);
    --s-border-strong:    rgba(0,0,0,0.14);
    --s-border-focus:     #3B82F6;
    --s-text-primary:     #0D1117;
    --s-text-secondary:   #4B5563;
    --s-text-tertiary:    #9CA3AF;
    --s-text-inverse:     #FFFFFF;
    --s-accent:           #1D4ED8;
    --s-accent-hover:     #1E40AF;
    --s-critical-bg:      #FEF2F2;
    --s-critical-border:  #FECACA;
    --s-critical-rail:    #DC2626;
    --s-critical-text:    #7F1D1D;
    --s-critical-label:   #991B1B;
    --s-critical-icon:    #DC2626;
    --s-critical-glow:    rgba(220,38,38,0.18);
    --s-critical-pulse:   rgba(220,38,38,0.08);
    --s-high-bg:          #FFFBEB;
    --s-high-border:      #FDE68A;
    --s-high-rail:        #D97706;
    --s-high-text:        #78350F;
    --s-high-label:       #92400E;
    --s-high-icon:        #D97706;
    --s-medium-bg:        #EFF6FF;
    --s-medium-border:    #BFDBFE;
    --s-medium-rail:      #2563EB;
    --s-medium-text:      #1E3A5F;
    --s-medium-label:     #1D4ED8;
    --s-medium-icon:      #2563EB;
    --s-info-bg:          #F0FDF4;
    --s-info-border:      #BBF7D0;
    --s-info-rail:        #16A34A;
    --s-info-text:        #14532D;
    --s-info-label:       #15803D;
    --s-info-icon:        #16A34A;
    --s-bar-critical:     #DC2626;
    --s-bar-high:         #D97706;
    --s-bar-low:          #16A34A;
    --s-sidebar-bg:       #F3F4F6;
    --s-sidebar-border:   rgba(0,0,0,0.08);
    --s-sidebar-text:     #374151;
    --s-transition:       background 0.2s ease, color 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
    --s-font-ui:          'IBM Plex Sans', system-ui, sans-serif;
    --s-font-mono:        'IBM Plex Mono', 'SF Mono', monospace;
    --s-weight-normal:    400;
    --s-weight-medium:    500;
    --s-weight-semibold:  600;
}

/* ══════════════════════════════════════════
   TOKEN LAYER — Dark
══════════════════════════════════════════ */
html[data-salience-theme="dark"] {
    --s-bg-base:          #0A0C10;
    --s-bg-surface:       #111318;
    --s-bg-raised:        #1A1D24;
    --s-bg-subtle:        #1F222A;
    --s-bg-hover:         rgba(255,255,255,0.05);
    --s-border:           rgba(255,255,255,0.08);
    --s-border-strong:    rgba(255,255,255,0.14);
    --s-border-focus:     #60A5FA;
    --s-text-primary:     #F1F5F9;
    --s-text-secondary:   #94A3B8;
    --s-text-tertiary:    #475569;
    --s-text-inverse:     #0D1117;
    --s-accent:           #60A5FA;
    --s-accent-hover:     #93C5FD;
    --s-critical-bg:      rgba(220,38,38,0.12);
    --s-critical-border:  rgba(220,38,38,0.35);
    --s-critical-rail:    #EF4444;
    --s-critical-text:    #FCA5A5;
    --s-critical-label:   #F87171;
    --s-critical-icon:    #EF4444;
    --s-critical-glow:    rgba(239,68,68,0.25);
    --s-critical-pulse:   rgba(239,68,68,0.10);
    --s-high-bg:          rgba(217,119,6,0.10);
    --s-high-border:      rgba(217,119,6,0.35);
    --s-high-rail:        #F59E0B;
    --s-high-text:        #FCD34D;
    --s-high-label:       #FBBF24;
    --s-high-icon:        #F59E0B;
    --s-medium-bg:        rgba(37,99,235,0.12);
    --s-medium-border:    rgba(37,99,235,0.35);
    --s-medium-rail:      #60A5FA;
    --s-medium-text:      #BFDBFE;
    --s-medium-label:     #93C5FD;
    --s-medium-icon:      #60A5FA;
    --s-info-bg:          rgba(22,163,74,0.10);
    --s-info-border:      rgba(22,163,74,0.30);
    --s-info-rail:        #34D399;
    --s-info-text:        #A7F3D0;
    --s-info-label:       #6EE7B7;
    --s-info-icon:        #34D399;
    --s-bar-critical:     #EF4444;
    --s-bar-high:         #F59E0B;
    --s-bar-low:          #34D399;
    --s-sidebar-bg:       #0E1015;
    --s-sidebar-border:   rgba(255,255,255,0.06);
    --s-sidebar-text:     #94A3B8;
}

/* ══════════════════════════════════════════
   GLOBAL BASE
══════════════════════════════════════════ */
html, body,
[data-testid="stAppViewContainer"],
[data-testid="stMain"],
.main,
.block-container {
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
p, span, div, label {
    font-family: var(--s-font-ui) !important;
}

/* Hide Streamlit chrome — keep header so sidebar toggle works */
#MainMenu, footer,
[data-testid="stDecoration"],
div[data-testid="stToolbar"] {
    visibility: hidden !important;
    display: none !important;
}

.block-container {
    padding: 1.5rem 2rem 3rem !important;
    max-width: 1280px !important;
}

/* ══════════════════════════════════════════
   SIDEBAR
══════════════════════════════════════════ */
[data-testid="stSidebar"] {
    background: var(--s-sidebar-bg) !important;
    border-right: 1px solid var(--s-sidebar-border) !important;
    transition: var(--s-transition);
}

/* Targeted sidebar text — NOT a blanket * override */
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] .stMarkdown {
    color: var(--s-sidebar-text) !important;
    font-family: var(--s-font-ui) !important;
    transition: var(--s-transition);
}
[data-testid="stSidebar"] > div:first-child {
    padding-top: 1.25rem;
}
[data-testid="stSidebar"] [data-baseweb="select"] > div,
[data-testid="stSidebar"] [data-baseweb="input"] > div {
    background: var(--s-bg-surface) !important;
    border-color: var(--s-border) !important;
    border-radius: 7px !important;
    transition: var(--s-transition);
}
[data-testid="stSidebar"] [data-baseweb="select"] > div:hover,
[data-testid="stSidebar"] [data-baseweb="input"] > div:hover {
    border-color: var(--s-border-strong) !important;
    box-shadow: 0 0 0 3px rgba(59,130,246,0.08) !important;
}

/* ══════════════════════════════════════════
   SIDEBAR LOGO & LABELS
══════════════════════════════════════════ */
.sb-logo {
    font-size: 15px;
    font-weight: var(--s-weight-semibold);
    letter-spacing: 0.3px;
    padding: 0 1rem 1rem;
    border-bottom: 1px solid var(--s-border);
    margin-bottom: 1rem;
    color: var(--s-text-primary) !important;
    transition: var(--s-transition);
}
.sb-logo span {
    opacity: 0.35;
    font-weight: var(--s-weight-normal);
}
.sb-section-label,
.panel-header {
    font-family: var(--s-font-ui) !important;
    font-size: 10px;
    font-weight: var(--s-weight-semibold);
    letter-spacing: 0.9px;
    text-transform: uppercase;
    color: var(--s-text-tertiary) !important;
    margin-bottom: 0.6rem;
    transition: color 0.2s ease;
}

/* ══════════════════════════════════════════
   STATUS PILLS
══════════════════════════════════════════ */
.status-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 11px;
    font-weight: var(--s-weight-medium);
    padding: 4px 10px;
    border-radius: 20px;
    margin-bottom: 0.85rem;
    transition: var(--s-transition);
}
.status-ready {
    background: var(--s-info-bg);
    color: var(--s-info-label) !important;
    border: 1px solid var(--s-info-border);
}
.status-done {
    background: var(--s-info-bg);
    color: var(--s-info-label) !important;
    border: 1px solid var(--s-info-border);
}
.status-processing {
    background: var(--s-high-bg);
    color: var(--s-high-label) !important;
    border: 1px solid var(--s-high-border);
}

/* ══════════════════════════════════════════
   SEVERITY ALERT SHELLS
══════════════════════════════════════════ */
.alert-shell {
    display: flex;
    gap: 0;
    border-radius: 10px;
    overflow: hidden;
    margin-bottom: 12px;
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
    display: flex;
    align-items: center;
    gap: 6px;
}
.alert-desc {
    font-size: 13px;
    font-weight: var(--s-weight-normal);
    line-height: 1.55;
}

.alert-critical {
    background: var(--s-critical-bg);
    border-color: var(--s-critical-border);
    box-shadow: 0 0 0 1px var(--s-critical-border), 0 4px 16px var(--s-critical-glow);
    animation: criticalPulse 2.4s ease-in-out infinite;
}
.alert-critical .alert-rail  { background: var(--s-critical-rail); }
.alert-critical .alert-tier  { color: var(--s-critical-label); }
.alert-critical .alert-desc  { color: var(--s-critical-text); }

@keyframes criticalPulse {
    0%, 100% { box-shadow: 0 0 0 1px var(--s-critical-border), 0 4px 16px var(--s-critical-glow); }
    50%       { box-shadow: 0 0 0 1px var(--s-critical-border), 0 4px 28px var(--s-critical-glow), 0 0 0 4px var(--s-critical-pulse); }
}

.alert-high {
    background: var(--s-high-bg);
    border-color: var(--s-high-border);
}
.alert-high .alert-rail  { background: var(--s-high-rail); }
.alert-high .alert-tier  { color: var(--s-high-label); }
.alert-high .alert-desc  { color: var(--s-high-text); }

.alert-medium {
    background: var(--s-medium-bg);
    border-color: var(--s-medium-border);
}
.alert-medium .alert-rail  { background: var(--s-medium-rail); }
.alert-medium .alert-tier  { color: var(--s-medium-label); }
.alert-medium .alert-desc  { color: var(--s-medium-text); }

.alert-info {
    background: var(--s-info-bg);
    border-color: var(--s-info-border);
}
.alert-info .alert-rail  { background: var(--s-info-rail); }
.alert-info .alert-tier  { color: var(--s-info-label); }
.alert-info .alert-desc  { color: var(--s-info-text); }

@media (prefers-reduced-motion: reduce) {
    .alert-critical { animation: none !important; }
    * { transition-duration: 0ms !important; }
}

/* ══════════════════════════════════════════
   FLAG ITEMS
══════════════════════════════════════════ */
.flag-item {
    display: flex;
    align-items: flex-start;
    gap: 10px;
    background: var(--s-critical-bg);
    border: 1px solid var(--s-critical-border);
    border-left: 4px solid var(--s-critical-rail);
    border-radius: 8px;
    padding: 10px 13px;
    font-size: 12px;
    color: var(--s-critical-text);
    margin-bottom: 7px;
    line-height: 1.55;
    transition: var(--s-transition);
}
.flag-item::before {
    content: "⚠";
    font-size: 13px;
    flex-shrink: 0;
    margin-top: 1px;
}

/* ══════════════════════════════════════════
   SIGNAL ROWS
══════════════════════════════════════════ */
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
.signal-name {
    font-size: 13px;
    font-weight: var(--s-weight-medium);
    color: var(--s-text-primary);
    flex: 1;
}
.signal-cat  { font-size: 10px; color: var(--s-text-tertiary); }
.signal-score {
    font-family: var(--s-font-mono);
    font-size: 11px;
    color: var(--s-text-secondary);
    width: 32px;
    text-align: right;
}

/* ══════════════════════════════════════════
   EXPLAINABILITY CARDS
══════════════════════════════════════════ */
.explain-card {
    border: 1px solid var(--s-border);
    border-radius: 9px;
    padding: 11px 14px;
    margin-bottom: 8px;
    background: var(--s-bg-surface);
    transition: var(--s-transition);
}
.explain-card:hover {
    border-color: var(--s-border-strong);
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}
.explain-head {
    font-size: 12px;
    font-weight: var(--s-weight-semibold);
    margin-bottom: 5px;
    display: flex;
    align-items: center;
    gap: 7px;
    color: var(--s-text-primary);
}
.explain-body {
    font-size: 11px;
    color: var(--s-text-secondary);
    line-height: 1.65;
}
.conf-hi  { color: var(--s-critical-icon); }
.conf-med { color: var(--s-high-icon); }
.conf-lo  { color: var(--s-info-icon); }

/* ══════════════════════════════════════════
   STEP LIST
══════════════════════════════════════════ */
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

/* ══════════════════════════════════════════
   BUTTONS
══════════════════════════════════════════ */
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
[data-testid="stButton"] button:active {
    transform: translateY(0) scale(0.98) !important;
}
[data-testid="stButton"] button:focus-visible {
    outline: 2px solid var(--s-border-focus) !important;
    outline-offset: 2px !important;
}
[data-testid="stButton"] button[kind="primary"] {
    background: var(--s-text-primary) !important;
    color: var(--s-text-inverse) !important;
    border-color: transparent !important;
}
[data-testid="stButton"] button[kind="primary"]:hover {
    opacity: 0.88 !important;
}
[data-testid="stButton"] button:disabled {
    opacity: 0.38 !important;
    cursor: not-allowed !important;
    transform: none !important;
    box-shadow: none !important;
}

/* ══════════════════════════════════════════
   FORM ELEMENTS
══════════════════════════════════════════ */
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
[data-baseweb="select"] > div:hover,
[data-baseweb="input"] > div:hover {
    border-color: var(--s-border-strong) !important;
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

/* ══════════════════════════════════════════
   TABS
══════════════════════════════════════════ */
[data-testid="stTabs"] [data-baseweb="tab-list"] {
    background: var(--s-bg-subtle) !important;
    border-radius: 10px !important;
    padding: 3px !important;
    gap: 2px !important;
    border: 1px solid var(--s-border) !important;
    transition: var(--s-transition);
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
[data-testid="stTabs"] [data-baseweb="tab"]:hover {
    color: var(--s-text-primary) !important;
}
[data-testid="stTabs"] [data-baseweb="tab-highlight"],
[data-testid="stTabs"] [data-baseweb="tab-border"] {
    display: none !important;
}

/* ══════════════════════════════════════════
   METRICS
══════════════════════════════════════════ */
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

/* ══════════════════════════════════════════
   MISC
══════════════════════════════════════════ */
hr { border-color: var(--s-border) !important; }

[data-testid="stStatus"] {
    background: var(--s-bg-surface) !important;
    border: 1px solid var(--s-border) !important;
    border-radius: 10px !important;
    font-family: var(--s-font-ui) !important;
    transition: var(--s-transition);
}
[data-testid="stCaptionContainer"] p,
.stCaption {
    font-size: 11px !important;
    color: var(--s-text-tertiary) !important;
    font-family: var(--s-font-ui) !important;
}
[data-testid="stAlert"] {
    border-radius: 9px !important;
    font-family: var(--s-font-ui) !important;
    font-size: 13px !important;
    border-left-width: 4px !important;
    transition: var(--s-transition);
}
[data-testid="stRadio"] label {
    font-family: var(--s-font-ui) !important;
    font-size: 13px !important;
    color: var(--s-text-secondary) !important;
    transition: color 0.15s ease;
}
[data-testid="stRadio"] label:hover {
    color: var(--s-text-primary) !important;
}
[data-testid="stFileUploader"] {
    border: 1px dashed var(--s-border-strong) !important;
    border-radius: 10px !important;
    background: var(--s-bg-subtle) !important;
    transition: var(--s-transition);
}
[data-testid="stFileUploader"]:hover {
    border-color: var(--s-border-focus) !important;
    background: var(--s-bg-hover) !important;
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
    box-shadow: 0 2px 8px rgba(0,0,0,0.07) !important;
}
[data-testid="stSpinner"] {
    color: var(--s-text-secondary) !important;
    font-family: var(--s-font-ui) !important;
    font-size: 13px !important;
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
# 5. SIDEBAR
# =====================================================================
with st.sidebar:
    st.markdown('<div class="sb-logo">Salience <span>OS</span></div>', unsafe_allow_html=True)

    # Theme switcher
    components.html("""
    <style>
      * { box-sizing: border-box; margin: 0; padding: 0; }
      body { background: transparent; }
      .ts { display: flex; gap: 3px; padding: 3px;
            background: rgba(0,0,0,0.06); border-radius: 8px;
            margin: 0 0 10px; border: 1px solid rgba(0,0,0,0.09); }
      .tb { flex: 1; padding: 5px 0; font-size: 11px; font-weight: 500;
            text-align: center; border: none; border-radius: 6px;
            cursor: pointer; background: transparent;
            color: rgba(0,0,0,0.45); font-family: system-ui, sans-serif;
            transition: all 0.15s ease; }
      .tb:hover { color: rgba(0,0,0,0.75); background: rgba(0,0,0,0.05); }
      .tb.active { background: white; color: #0D1117;
                   box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
    </style>
    <div class="ts" role="group" aria-label="Theme selector">
      <button class="tb" id="btn-light"  onclick="setTheme('light')">Light</button>
      <button class="tb" id="btn-system" onclick="setTheme('system')">System</button>
      <button class="tb" id="btn-dark"   onclick="setTheme('dark')">Dark</button>
    </div>
    <script>
      const THEME_KEY = 'SALIENCE_THEME_KEY';
      function setTheme(mode) {
        localStorage.setItem(THEME_KEY, mode);
        const root = window.parent.document.documentElement;
        if (mode === 'system') {
          const dark = window.matchMedia('(prefers-color-scheme: dark)').matches;
          root.setAttribute('data-salience-theme', dark ? 'dark' : 'light');
        } else {
          root.setAttribute('data-salience-theme', mode);
        }
        document.querySelectorAll('.tb').forEach(b => b.classList.remove('active'));
        document.getElementById('btn-' + mode).classList.add('active');
      }
      const stored = localStorage.getItem(THEME_KEY) || 'system';
      document.querySelectorAll('.tb').forEach(b => b.classList.remove('active'));
      document.getElementById('btn-' + stored)?.classList.add('active');
    </script>
    """, height=50, scrolling=False)

    if st.session_state.transcript:
        st.markdown('<div class="status-pill status-done">● Analysis complete</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="status-pill status-ready">● Ready</div>', unsafe_allow_html=True)

    st.markdown('<div class="sb-section-label">Clinical context</div>', unsafe_allow_html=True)
    specialty_profile = st.selectbox(
        "Specialty profile",
        ["Cardiology Clinic", "General Internal Medicine", "Emergency Trauma",
         "Neurology", "Pediatrics", "Orthopedic Surgery",
         "Psychiatry & Behavioral Health", "Oncology"],
    )
    target_language = st.selectbox(
        "Language matrix",
        ["Mixed (Multi-lingual Code-Switching)", "English (US/UK)", "Arabic (Khaleeji/MSA)"],
    )

    st.divider()
    st.markdown('<div class="sb-section-label">API credentials</div>', unsafe_allow_html=True)

    has_cloud_groq   = "groq_api_key"   in st.secrets
    has_cloud_gemini = "gemini_api_key" in st.secrets

    groq_input = st.text_input(
        "Groq — Whisper v3",
        type="password",
        placeholder="Active via vault" if has_cloud_groq else "sk-...",
    )
    gemini_input = st.text_input(
        "Gemini — Flash 2.5",
        type="password",
        placeholder="Active via vault" if has_cloud_gemini else "AI...",
    )

    groq_api_key   = groq_input   if groq_input.strip()   else st.secrets.get("groq_api_key", "")
    gemini_api_key = gemini_input if gemini_input.strip() else st.secrets.get("gemini_api_key", "")

    if (has_cloud_groq or has_cloud_gemini) and not (groq_input or gemini_input):
        st.caption("Vault credentials active — fields optional.")

    if st.session_state.transcript:
        st.divider()
        st.caption(f"Last run: {st.session_state.pipeline_execution_time}s · {specialty_profile}")


# =====================================================================
# 6. MAIN HEADER
# =====================================================================
header_col, meta_col = st.columns([3, 1])
with header_col:
    st.markdown("## Clinical intelligence workspace")
    st.caption(f"{specialty_profile} · {target_language}")
with meta_col:
    if st.session_state.transcript:
        urgency = st.session_state.classification.get("urgency_tier", "—")
        color   = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢"}.get(urgency, "⚪")
        st.metric("Urgency", f"{color} {urgency}")

st.divider()


# =====================================================================
# 7. INPUT AREA
# =====================================================================
if not st.session_state.transcript:
    cap_col, exam_col = st.columns([1.1, 1], gap="large")

    with cap_col:
        st.markdown('<p class="panel-header">Input capture</p>', unsafe_allow_html=True)

        input_vector = st.radio(
            "Input mode",
            ["Text (paste/type)", "Microphone (live)", "File upload (.wav / .json)"],
            horizontal=False,
            label_visibility="collapsed"
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
                label_visibility="collapsed"
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
                            injected_text_payload = selected_node.get("input", selected_node.get("instruction", ""))
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

        organ_system_tabs = st.tabs(["Thoracic", "GI / Abdomen", "Neuro", "MSK"])
        with organ_system_tabs[0]:
            notes_thoracic = st.text_area(
                "Thoracic",
                value="Cardiovascular: Tachycardic, rhythm regular. S1 and S2 distinct, no audible murmurs. Diaphoresis noted. Respiratory: Tachypneic, shallow. CTAB bilaterally.",
                height=100, label_visibility="collapsed"
            )
        with organ_system_tabs[1]:
            notes_abdominal = st.text_area(
                "GI",
                value="Abdomen soft, non-distended. Bowel sounds active. No tenderness, guarding, or rebound. No hepatosplenomegaly. Epigastric non-tender.",
                height=100, label_visibility="collapsed"
            )
        with organ_system_tabs[2]:
            notes_neuro = st.text_area(
                "Neuro",
                value="A&Ox3. PERRLA. Orthostatic lightheadedness on sitting up. Gross motor and sensory intact.",
                height=100, label_visibility="collapsed"
            )
        with organ_system_tabs[3]:
            notes_ortho = st.text_area(
                "MSK",
                value="Mild lumbar paraspinal tenderness. Left shoulder and mandible — full passive ROM, no joint tenderness.",
                height=100, label_visibility="collapsed"
            )

    compiled_examination_overlay = f"""
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
        disabled=not has_valid_audio_payload
    ):
        if not groq_api_key or not gemini_api_key:
            st.error("API credentials missing. Add keys in the sidebar or configure vault secrets.")
        else:
            pipeline_start = time.time()
            with st.status("Running analysis pipeline…", expanded=True) as status:
                try:
                    if bypass_audio_stt:
                        extracted_raw_text = injected_text_payload
                        st.write("✓ Text input ingested")
                    else:
                        st.write("Compressing audio…")
                        raw_audio           = AudioSegment.from_file(temp_audio_filename)
                        processed_audio     = raw_audio.set_channels(1).set_frame_rate(16000)
                        compressed_filename = "optimized_api_payload.mp3"
                        processed_audio.export(compressed_filename, format="mp3", bitrate="64k")
                        groq_client = Groq(api_key=groq_api_key, timeout=60.0)
                        with open(compressed_filename, "rb") as audio_binary:
                            extracted_raw_text = groq_client.audio.transcriptions.create(
                                file=(compressed_filename, audio_binary.read()),
                                model="whisper-large-v3",
                                response_format="text"
                            )
                        if os.path.exists(temp_audio_filename):   os.remove(temp_audio_filename)
                        if os.path.exists(compressed_filename):   os.remove(compressed_filename)
                        st.write("✓ Transcription complete")

                    st.write("Running clinical salience engine…")
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

                    st.session_state.transcript              = parsed_payload.get("cleaned_transcript", "")
                    st.session_state.classification          = parsed_payload.get("classification", {})
                    st.session_state.salience_map            = parsed_payload.get("salience_weight_map", [])
                    st.session_state.soap_note               = parsed_payload.get("structured_soap_chart", "")
                    st.session_state.flags                   = parsed_payload.get("clinical_safety_red_flags", [])
                    st.session_state.next_steps              = parsed_payload.get("suggested_next_steps", [])
                    st.session_state.pipeline_execution_time = round(time.time() - pipeline_start, 2)
                    st.session_state.chart_locked            = False

                    status.update(label="Analysis complete", state="complete", expanded=False)
                    st.rerun()

                except Exception as e:
                    status.update(label="Pipeline error", state="error")
                    st.error(f"Error: {e}")

    if not has_valid_audio_payload:
        st.caption("Add a transcript or audio recording above to enable analysis.")


# =====================================================================
# 8. OUTPUT WORKSPACE
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

    out_tabs = st.tabs([
        "Key findings",
        "Red flags & next steps",
        "SOAP review",
        "Explainability"
    ])

    # ── TAB 1: Key findings ──
    with out_tabs[0]:
        sig_col, trans_col = st.columns([1, 1], gap="large")

        with sig_col:
            st.markdown('<p class="panel-header">Clinical signals — by salience weight</p>', unsafe_allow_html=True)
            if st.session_state.salience_map:
                sorted_signals = sorted(
                    st.session_state.salience_map,
                    key=lambda x: x.get("salience_score", 0),
                    reverse=True
                )
                for item in sorted_signals:
                    score = item.get("salience_score", 0)
                    if score >= 0.85:
                        bar_color = "var(--s-bar-critical)"
                    elif score >= 0.65:
                        bar_color = "var(--s-bar-high)"
                    else:
                        bar_color = "var(--s-bar-low)"
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
                "Transcript",
                value=st.session_state.transcript,
                height=320,
                disabled=True,
                label_visibility="collapsed"
            )

    # ── TAB 2: Red flags & next steps ──
    with out_tabs[1]:
        flag_col, step_col = st.columns([1, 1], gap="large")

        with flag_col:
            st.markdown('<p class="panel-header">Safety flags</p>', unsafe_allow_html=True)
            if st.session_state.flags:
                for flag in st.session_state.flags:
                    st.markdown(
                        f'<div class="flag-item" role="alert">{flag}</div>',
                        unsafe_allow_html=True
                    )
            else:
                st.success("No safety flags identified.")

        with step_col:
            st.markdown('<p class="panel-header">Suggested next steps</p>', unsafe_allow_html=True)
            if st.session_state.next_steps:
                for i, step in enumerate(st.session_state.next_steps, 1):
                    st.markdown(f"""
                    <div class="step-item">
                        <span style="opacity:0.35;font-size:11px;min-width:16px;
                                     font-family:var(--s-font-mono)">{i}</span>
                        <span>{step}</span>
                    </div>
                    """, unsafe_allow_html=True)

    # ── TAB 3: SOAP review ──
    with out_tabs[2]:
        soap_col, action_col = st.columns([1.6, 1], gap="large")

        with soap_col:
            st.markdown('<p class="panel-header">Clinical note — pending review</p>', unsafe_allow_html=True)
            edited_soap = st.text_area(
                "SOAP note",
                value=st.session_state.soap_note,
                height=420,
                label_visibility="collapsed"
            )

        with action_col:
            st.markdown('<p class="panel-header">Review & sign-off</p>', unsafe_allow_html=True)
            st.caption(f"Processed {st.session_state.pipeline_execution_time}s ago · {specialty_profile}")
            st.divider()

            try:
                pdf_binary = generate_clinical_pdf(edited_soap, specialty_profile)
                st.download_button(
                    label="Download PDF",
                    data=pdf_binary,
                    file_name=f"Salience_OS_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
            except Exception as pdf_err:
                st.error(f"PDF error: {pdf_err}")

            st.divider()

            if st.session_state.chart_locked:
                st.success("Signed and pushed to EHR.")
                st.button("Chart locked", disabled=True, use_container_width=True)
            else:
                st.warning("Note is unsigned. Review before sign-off.")
                if st.button("Sign & push to EHR", type="primary", use_container_width=True):
                    with st.spinner("Pushing to EHR…"):
                        time.sleep(2.0)
                        st.session_state.chart_locked = True
                        st.rerun()

            st.divider()
            if st.button("New consultation", use_container_width=True):
                for key in ["transcript", "classification", "salience_map",
                            "soap_note", "flags", "next_steps",
                            "pipeline_execution_time", "chart_locked"]:
                    del st.session_state[key]
                st.rerun()

    # ── TAB 4: Explainability ──
    with out_tabs[3]:
        st.markdown(
            '<p class="panel-header">Model reasoning — why these signals were prioritised</p>',
            unsafe_allow_html=True
        )
        if st.session_state.salience_map:
            for item in sorted(
                st.session_state.salience_map,
                key=lambda x: x.get("salience_score", 0),
                reverse=True
            ):
                score = item.get("salience_score", 0)
                if score >= 0.85:
                    conf_class, conf_label = "conf-hi",  "High"
                elif score >= 0.65:
                    conf_class, conf_label = "conf-med", "Medium"
                else:
                    conf_class, conf_label = "conf-lo",  "Low"

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
```
