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
import os
import json
import time
from datetime import datetime
from groq import Groq
import google.generativeai as genai
from pydub import AudioSegment
from fpdf import FPDF


# ─────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────
SPECIALTY_OPTIONS = [
    "Cardiology Clinic",
    "General Internal Medicine",
    "Emergency Trauma",
    "Neurology",
    "Pediatrics",
    "Orthopedic Surgery",
    "Psychiatry & Behavioral Health",
    "Oncology",
]
LANGUAGE_OPTIONS = [
    "Mixed (Multi-lingual Code-Switching)",
    "English (US/UK)",
    "Arabic (Khaleeji/MSA)",
]
SPECIALTY_SHORT = {
    "Cardiology Clinic": "Cardiology",
    "General Internal Medicine": "Gen. Medicine",
    "Emergency Trauma": "Emergency",
    "Neurology": "Neurology",
    "Pediatrics": "Pediatrics",
    "Orthopedic Surgery": "Orthopaedics",
    "Psychiatry & Behavioral Health": "Psychiatry",
    "Oncology": "Oncology",
}
TEMP_AUDIO = "active_stream_input.wav"
COMP_AUDIO = "optimized_payload.mp3"


# ─────────────────────────────────────────────
# PDF UTILITIES  (unchanged logic)
# ─────────────────────────────────────────────
def sanitize_for_pdf(text: str) -> str:
    if not text:
        return ""
    replacements = {
        "•": "-", "—": "-", "–": "-",
        "\u201c": '"', "\u201d": '"',
        "\u2018": "'", "\u2019": "'",
        "™": "TM", "©": "(c)", "®": "(r)",
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    return text.encode("latin-1", errors="replace").decode("latin-1")


def generate_clinical_pdf(soap_text: str, specialty: str) -> bytes:
    pdf = FPDF()
    pdf.set_margins(left=15, top=10, right=15)
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    pdf.set_fill_color(2, 132, 199)
    pdf.rect(0, 0, 210, 38, "F")
    pdf.set_xy(0, 8)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(210, 12, "SALIENCE OS | CLINICAL NOTE", ln=True, align="C")
    pdf.set_font("Helvetica", "I", 10)
    pdf.cell(
        210, 5,
        sanitize_for_pdf(f"Specialty: {specialty} | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"),
        ln=True, align="C",
    )

    pdf.set_xy(15, 45)
    pdf.set_text_color(15, 23, 42)
    ew = pdf.w - pdf.l_margin - pdf.r_margin

    for raw_line in soap_text.split("\n"):
        line = raw_line.strip()
        if not line:
            pdf.ln(3)
            continue
        pdf.set_x(pdf.l_margin)
        if line.startswith("###"):
            pdf.ln(4)
            pdf.set_font("Helvetica", "B", 14)
            pdf.set_text_color(2, 132, 199)
            header = line.replace("###", "").replace(":", "").strip().upper()
            pdf.cell(ew, 10, sanitize_for_pdf(header), ln=True)
            pdf.line(pdf.l_margin, pdf.get_y(), pdf.l_margin + 40, pdf.get_y())
            pdf.ln(2)
            pdf.set_text_color(15, 23, 42)
        elif line.startswith("**") and line.endswith("**"):
            pdf.set_font("Helvetica", "B", 11)
            pdf.cell(ew, 7, sanitize_for_pdf(line.replace("**", "").strip()), ln=True)
        else:
            pdf.set_font("Helvetica", size=10)
            pdf.multi_cell(ew, 6, sanitize_for_pdf(line.replace("**", "").replace("*", "-")))

    return bytes(pdf.output())


# ─────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Salience OS",
    page_icon="⊕",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ─────────────────────────────────────────────
# SESSION STATE DEFAULTS
# ─────────────────────────────────────────────
_DEFAULTS = {
    "transcript": "",
    "classification": {},
    "salience_map": [],
    "soap_note": "",
    "flags": [],
    "next_steps": [],
    "pipeline_time": 0.0,
    "chart_locked": False,
    "focus_mode": False,
    "specialty": "Cardiology Clinic",
    "language": "Mixed (Multi-lingual Code-Switching)",
    "groq_key": "",
    "gemini_key": "",
    "theme": "System",
}
for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v


# ─────────────────────────────────────────────
# MINIMAL CSS  — only what Streamlit cannot do natively
# ─────────────────────────────────────────────
# Kept to: alert severity colors, signal bar rows, explain cards,
# IBM Plex Sans font load, and a handful of typography tweaks.
# Zero DOM overrides, zero position:fixed, zero parent-document access.
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap');

/* Font application — additive only, no !important resets */
html, body, [class*="css"] {
    font-family: 'IBM Plex Sans', system-ui, sans-serif;
}
code, pre, .monospace {
    font-family: 'IBM Plex Mono', monospace;
}

/* ── Severity alert shells ── */
.sal-alert {
    display: flex;
    border-radius: 10px;
    overflow: hidden;
    margin-bottom: 14px;
    border: 2px solid;
}
.sal-alert-rail { width: 6px; flex-shrink: 0; }
.sal-alert-body { flex: 1; padding: 12px 15px; }
.sal-alert-tier {
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 1px;
    text-transform: uppercase;
    margin-bottom: 4px;
}
.sal-alert-desc { font-size: 13px; line-height: 1.55; font-weight: 400; }

/* CRITICAL — most visually dominant */
.sal-critical {
    background: #FEF2F2;
    border-color: #DC2626;
    animation: sal-pulse 2.5s ease-in-out infinite;
}
.sal-critical .sal-alert-rail { background: #DC2626; }
.sal-critical .sal-alert-tier { color: #7F1D1D; }
.sal-critical .sal-alert-desc { color: #7F1D1D; font-weight: 500; }
@keyframes sal-pulse {
    0%,100% { box-shadow: 0 0 0 0 rgba(220,38,38,0); }
    50%      { box-shadow: 0 0 0 4px rgba(220,38,38,0.15); }
}

/* HIGH */
.sal-high {
    background: #FFFBEB;
    border-color: #D97706;
}
.sal-high .sal-alert-rail { background: #D97706; }
.sal-high .sal-alert-tier { color: #78350F; }
.sal-high .sal-alert-desc { color: #78350F; }

/* MEDIUM */
.sal-medium {
    background: #EFF6FF;
    border-color: #2563EB;
}
.sal-medium .sal-alert-rail { background: #2563EB; }
.sal-medium .sal-alert-tier { color: #1E3A5F; }
.sal-medium .sal-alert-desc { color: #1E3A5F; }

/* LOW / INFO */
.sal-low {
    background: #F0FDF4;
    border-color: #16A34A;
}
.sal-low .sal-alert-rail { background: #16A34A; }
.sal-low .sal-alert-tier { color: #14532D; }
.sal-low .sal-alert-desc { color: #14532D; }

/* Dark theme overrides — applied when body has dark background */
@media (prefers-color-scheme: dark) {
    .sal-critical { background: rgba(220,38,38,0.15); border-color: #EF4444; }
    .sal-critical .sal-alert-tier,
    .sal-critical .sal-alert-desc { color: #FCA5A5; }
    .sal-high     { background: rgba(217,119,6,0.15);  border-color: #F59E0B; }
    .sal-high .sal-alert-tier,
    .sal-high .sal-alert-desc { color: #FCD34D; }
    .sal-medium   { background: rgba(37,99,235,0.15);  border-color: #60A5FA; }
    .sal-medium .sal-alert-tier,
    .sal-medium .sal-alert-desc { color: #BFDBFE; }
    .sal-low      { background: rgba(22,163,74,0.15);  border-color: #34D399; }
    .sal-low .sal-alert-tier,
    .sal-low .sal-alert-desc { color: #A7F3D0; }
}

/* ── Signal rows ── */
.sig-row {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 4px;
    border-bottom: 1px solid rgba(128,128,128,0.15);
    border-radius: 4px;
}
.sig-row:last-child { border-bottom: none; }
.sig-name { font-size: 13px; font-weight: 500; flex: 1; }
.sig-cat  { font-size: 10px; opacity: 0.5; }
.sig-score {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 11px;
    opacity: 0.6;
    width: 32px;
    text-align: right;
}

/* ── Explain cards ── */
.exp-card {
    border: 1px solid rgba(128,128,128,0.2);
    border-radius: 9px;
    padding: 11px 14px;
    margin-bottom: 8px;
}
.exp-head {
    font-size: 12px;
    font-weight: 600;
    margin-bottom: 4px;
    display: flex;
    align-items: center;
    gap: 7px;
}
.exp-body { font-size: 11px; opacity: 0.7; line-height: 1.65; }

/* ── Flag items ── */
.flag-item {
    display: flex;
    gap: 9px;
    background: rgba(220,38,38,0.08);
    border: 1px solid rgba(220,38,38,0.3);
    border-left: 4px solid #DC2626;
    border-radius: 0 8px 8px 0;
    padding: 9px 12px;
    font-size: 12px;
    color: #7F1D1D;
    margin-bottom: 7px;
    line-height: 1.55;
}
@media (prefers-color-scheme: dark) {
    .flag-item { color: #FCA5A5; background: rgba(220,38,38,0.12); border-color: rgba(239,68,68,0.4); }
}
.flag-item::before { content: "⚠"; flex-shrink: 0; margin-top: 1px; }

/* ── Step list ── */
.step-item {
    display: flex;
    gap: 10px;
    font-size: 12px;
    padding: 6px 0;
    border-bottom: 1px solid rgba(128,128,128,0.12);
    line-height: 1.5;
    opacity: 0.8;
}
.step-item:last-child { border-bottom: none; }

/* ── Section label ── */
.sec-label {
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.9px;
    text-transform: uppercase;
    opacity: 0.45;
    margin-bottom: 8px;
    margin-top: 4px;
}

/* ── Focus mode strip ── */
.focus-badge {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    font-size: 11px;
    font-weight: 500;
    padding: 3px 10px;
    border-radius: 20px;
    background: rgba(37,99,235,0.1);
    color: #1D4ED8;
    border: 1px solid rgba(37,99,235,0.25);
    margin-bottom: 12px;
}

@media (prefers-reduced-motion: reduce) {
    .sal-critical { animation: none; }
}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
def render_alert(urgency: str, trigger: str) -> None:
    """Render a severity-coded alert using pure HTML (no JS, no DOM access)."""
    tier_map = {
        "CRITICAL": ("sal-critical", "⬤  Critical — immediate action required"),
        "HIGH":     ("sal-high",     "⬤  High priority"),
        "MEDIUM":   ("sal-medium",   "⬤  Medium priority"),
        "LOW":      ("sal-low",      "⬤  Low urgency"),
    }
    if urgency not in tier_map:
        return
    css, label = tier_map[urgency]
    st.markdown(f"""
    <div class="sal-alert {css}" role="alert" aria-live="assertive">
        <div class="sal-alert-rail"></div>
        <div class="sal-alert-body">
            <div class="sal-alert-tier">{label}</div>
            <div class="sal-alert-desc">{trigger}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_signals(salience_map: list) -> None:
    """Render signal rows sorted by salience score."""
    st.markdown('<div class="sec-label">Clinical signals — by salience weight</div>',
                unsafe_allow_html=True)
    bar_colors = {
        "critical": "#DC2626",
        "high":     "#D97706",
        "low":      "#16A34A",
    }
    for item in sorted(salience_map, key=lambda x: x.get("salience_score", 0), reverse=True):
        score = item.get("salience_score", 0)
        color = (bar_colors["critical"] if score >= 0.85
                 else bar_colors["high"] if score >= 0.65
                 else bar_colors["low"])
        width = max(4, int(score * 56))
        st.markdown(f"""
        <div class="sig-row">
            <div style="width:{width}px;height:3px;border-radius:2px;
                        background:{color};flex-shrink:0"></div>
            <span class="sig-name">{item.get('entity', '')}</span>
            <span class="sig-cat">{item.get('category', '')}</span>
            <span class="sig-score">{score:.2f}</span>
        </div>
        """, unsafe_allow_html=True)


def render_flags(flags: list) -> None:
    if flags:
        for flag in flags:
            st.markdown(f'<div class="flag-item">{flag}</div>', unsafe_allow_html=True)
    else:
        st.success("No safety flags identified.")


def render_steps(steps: list) -> None:
    if steps:
        for i, step in enumerate(steps, 1):
            st.markdown(f"""
            <div class="step-item">
                <span style="opacity:.35;font-family:'IBM Plex Mono',monospace;
                             font-size:11px;min-width:18px">{i}</span>
                <span>{step}</span>
            </div>
            """, unsafe_allow_html=True)


def render_explainability(salience_map: list) -> None:
    st.markdown('<div class="sec-label">Why these signals were prioritised</div>',
                unsafe_allow_html=True)
    for item in sorted(salience_map, key=lambda x: x.get("salience_score", 0), reverse=True):
        score = item.get("salience_score", 0)
        dot_color, conf = (
            ("#DC2626", "High")   if score >= 0.85 else
            ("#D97706", "Medium") if score >= 0.65 else
            ("#16A34A", "Low")
        )
        st.markdown(f"""
        <div class="exp-card">
            <div class="exp-head">
                <span style="color:{dot_color}">●</span>
                {item.get('entity', '')}
                <span style="margin-left:auto;font-size:10px;opacity:.45;
                             font-family:'IBM Plex Mono',monospace">
                    {conf} · {score:.2f}
                </span>
            </div>
            <div class="exp-body">{item.get('reasoning_context', '')}</div>
        </div>
        """, unsafe_allow_html=True)


def reset_analysis() -> None:
    for k in ["transcript", "classification", "salience_map", "soap_note",
              "flags", "next_steps", "pipeline_time", "chart_locked"]:
        st.session_state[k] = _DEFAULTS[k]


# ─────────────────────────────────────────────
# SIDEBAR — settings only, fully native
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⊕ Salience OS")
    st.caption("Clinical intelligence workspace")
    st.divider()

    # ── Theme ──
    st.markdown("**Theme**")
    theme = st.radio(
        "Theme",
        ["System", "Light", "Dark"],
        index=["System", "Light", "Dark"].index(st.session_state.theme),
        horizontal=True,
        label_visibility="collapsed",
        key="theme_radio",
    )
    st.session_state.theme = theme

    st.divider()

    # ── Clinical context ──
    st.markdown("**Clinical context**")
    st.session_state.specialty = st.selectbox(
        "Specialty profile",
        SPECIALTY_OPTIONS,
        index=SPECIALTY_OPTIONS.index(st.session_state.specialty),
        key="sel_specialty",
    )
    st.session_state.language = st.selectbox(
        "Language matrix",
        LANGUAGE_OPTIONS,
        index=LANGUAGE_OPTIONS.index(st.session_state.language),
        key="sel_language",
    )

    st.divider()

    # ── API credentials ──
    has_vault_groq   = "groq_api_key"   in st.secrets
    has_vault_gemini = "gemini_api_key" in st.secrets

    st.markdown("**API credentials**")
    if has_vault_groq and has_vault_gemini:
        st.success("🔒 Vault credentials active")
    else:
        st.session_state.groq_key = st.text_input(
            "Groq API key (Whisper v3)",
            type="password",
            value=st.session_state.groq_key,
            placeholder="Vault active" if has_vault_groq else "sk-...",
        )
        st.session_state.gemini_key = st.text_input(
            "Gemini API key (Flash 2.5)",
            type="password",
            value=st.session_state.gemini_key,
            placeholder="Vault active" if has_vault_gemini else "AI...",
        )

    st.divider()

    # ── Focus mode ──
    focus_label = "⊙ Exit focus mode" if st.session_state.focus_mode else "◎ Enable focus mode"
    if st.button(focus_label, use_container_width=True):
        st.session_state.focus_mode = not st.session_state.focus_mode
        st.rerun()

    # ── New consultation ──
    if st.session_state.transcript:
        st.divider()
        st.caption(f"Last run: {st.session_state.pipeline_time}s · "
                   f"{SPECIALTY_SHORT.get(st.session_state.specialty, '')}")
        if st.button("↩ New consultation", use_container_width=True):
            reset_analysis()
            st.rerun()


# ─────────────────────────────────────────────
# RESOLVE KEYS
# ─────────────────────────────────────────────
groq_api_key = (
    st.session_state.groq_key.strip()
    or st.secrets.get("groq_api_key", "")
)
gemini_api_key = (
    st.session_state.gemini_key.strip()
    or st.secrets.get("gemini_api_key", "")
)
specialty_profile = st.session_state.specialty
target_language   = st.session_state.language


# ─────────────────────────────────────────────
# HEADER
# ─────────────────────────────────────────────
spec_short = SPECIALTY_SHORT.get(specialty_profile, specialty_profile)

if st.session_state.focus_mode:
    st.markdown(
        f'<div class="focus-badge">◎ Focus mode &nbsp;·&nbsp; {spec_short}</div>',
        unsafe_allow_html=True,
    )
else:
    hcol1, hcol2 = st.columns([3, 1])
    with hcol1:
        st.markdown(f"## Clinical workspace")
        st.caption(f"{spec_short} · {target_language}")
    with hcol2:
        if st.session_state.transcript:
            urgency = st.session_state.classification.get("urgency_tier", "—")
            emoji   = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢"}.get(urgency, "⚪")
            st.metric("Urgency", f"{emoji} {urgency}")

st.divider()


# ─────────────────────────────────────────────
# INPUT SECTION  (only shown before first analysis)
# ─────────────────────────────────────────────
if not st.session_state.transcript:

    if not st.session_state.focus_mode:
        inp_col, exam_col = st.columns([1.1, 1], gap="large")
    else:
        inp_col = st.container()

    # ── Input capture ──
    with inp_col:
        st.markdown('<div class="sec-label">Input capture</div>', unsafe_allow_html=True)

        mode = st.radio(
            "Input mode",
            ["Text (paste / type)", "Microphone (live)", "File (.wav / .mp3 / .json)"],
            horizontal=False,
            label_visibility="collapsed",
        )

        has_input      = False
        bypass_stt     = False
        injected_text  = ""

        if "Text" in mode:
            injected_text = st.text_area(
                "Transcript",
                placeholder="Paste or type the consultation transcript here…",
                height=200,
                label_visibility="collapsed",
            )
            if injected_text.strip():
                has_input  = True
                bypass_stt = True

        elif "Microphone" in mode:
            audio_file = st.audio_input("Record consultation audio")
            if audio_file is not None:
                with open(TEMP_AUDIO, "wb") as f:
                    f.write(audio_file.read())
                has_input = True

        else:  # File upload
            uploaded = st.file_uploader(
                "Upload audio or dataset",
                type=["wav", "mp3", "m4a", "json"],
                label_visibility="collapsed",
            )
            if uploaded is not None:
                if uploaded.name.endswith(".json"):
                    try:
                        data = json.load(uploaded)
                        if isinstance(data, list):
                            st.success(f"{len(data)} cases loaded")
                            idx  = st.number_input(
                                "Case index", min_value=0,
                                max_value=len(data) - 1, value=0,
                            )
                            node          = data[idx]
                            injected_text = node.get("input", node.get("instruction", ""))
                            if injected_text:
                                st.caption(injected_text[:240] + "…")
                                has_input  = True
                                bypass_stt = True
                        else:
                            st.error("JSON must be a list of case objects.")
                    except Exception as e:
                        st.error(f"JSON parse error: {e}")
                else:
                    with open(TEMP_AUDIO, "wb") as f:
                        f.write(uploaded.getbuffer())
                    st.audio(TEMP_AUDIO)
                    has_input = True

    # ── Physical examination (hidden in focus mode) ──
    if not st.session_state.focus_mode:
        with exam_col:
            st.markdown('<div class="sec-label">Physical examination</div>',
                        unsafe_allow_html=True)
            etabs = st.tabs(["Thoracic", "GI / Abdomen", "Neuro", "MSK"])
            with etabs[0]:
                notes_thoracic = st.text_area(
                    "Thoracic findings",
                    value="Cardiovascular: Tachycardic, rhythm regular. S1 and S2 distinct, "
                          "no audible murmurs. Diaphoresis noted. "
                          "Respiratory: Tachypneic, shallow. CTAB bilaterally.",
                    height=110, label_visibility="collapsed",
                )
            with etabs[1]:
                notes_gi = st.text_area(
                    "GI findings",
                    value="Abdomen soft, non-distended. Bowel sounds active. "
                          "No tenderness, guarding, or rebound. "
                          "No hepatosplenomegaly. Epigastric non-tender.",
                    height=110, label_visibility="collapsed",
                )
            with etabs[2]:
                notes_neuro = st.text_area(
                    "Neuro findings",
                    value="A&Ox3. PERRLA. Orthostatic lightheadedness on sitting up. "
                          "Gross motor and sensory intact.",
                    height=110, label_visibility="collapsed",
                )
            with etabs[3]:
                notes_msk = st.text_area(
                    "MSK findings",
                    value="Mild lumbar paraspinal tenderness. "
                          "Left shoulder and mandible — full passive ROM, no joint tenderness.",
                    height=110, label_visibility="collapsed",
                )
    else:
        notes_thoracic = "Deferred in focus mode"
        notes_gi       = "Deferred in focus mode"
        notes_neuro    = "Deferred in focus mode"
        notes_msk      = "Deferred in focus mode"

    compiled_exam = (
        f"- Thoracic: {notes_thoracic}\n"
        f"- GI/Abdomen: {notes_gi}\n"
        f"- Neuro/Reflex: {notes_neuro}\n"
        f"- Musculoskeletal: {notes_msk}"
    )

    st.divider()

    # ── Run button ──
    run_disabled = not has_input
    if st.button(
        "Run salience analysis",
        type="primary",
        use_container_width=True,
        disabled=run_disabled,
        key="run_btn",
    ):
        if not groq_api_key or not gemini_api_key:
            st.error("API credentials missing. Add keys in the sidebar.")
            st.stop()

        t0 = time.time()
        with st.status("Running analysis pipeline…", expanded=True) as status:
            try:
                # ── Stage 1: STT ──
                if bypass_stt:
                    raw_text = injected_text
                    st.write("✓ Text input ingested")
                else:
                    st.write("Compressing audio…")
                    audio    = AudioSegment.from_file(TEMP_AUDIO)
                    audio    = audio.set_channels(1).set_frame_rate(16000)
                    audio.export(COMP_AUDIO, format="mp3", bitrate="64k")
                    gc = Groq(api_key=groq_api_key, timeout=60.0)
                    with open(COMP_AUDIO, "rb") as ab:
                        raw_text = gc.audio.transcriptions.create(
                            file=(COMP_AUDIO, ab.read()),
                            model="whisper-large-v3",
                            response_format="text",
                        )
                    for fp in [TEMP_AUDIO, COMP_AUDIO]:
                        if os.path.exists(fp):
                            os.remove(fp)
                    st.write("✓ Transcription complete")

                # ── Stage 2: Gemini salience engine ──
                st.write("Running clinical salience engine…")
                genai.configure(api_key=gemini_api_key)
                engine = genai.GenerativeModel("gemini-2.5-flash")

                prompt = f"""
You are the core analytical pipeline of Salience OS, configured for the specialty: {specialty_profile}.
The incoming data stream was ingested with an expected localization matrix profile of: {target_language}.

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
                resp   = engine.generate_content(
                    prompt,
                    generation_config={"response_mime_type": "application/json"},
                )
                parsed = json.loads(resp.text, strict=False)

                st.session_state.transcript    = parsed.get("cleaned_transcript", "")
                st.session_state.classification = parsed.get("classification", {})
                st.session_state.salience_map  = parsed.get("salience_weight_map", [])
                st.session_state.soap_note     = parsed.get("structured_soap_chart", "")
                st.session_state.flags         = parsed.get("clinical_safety_red_flags", [])
                st.session_state.next_steps    = parsed.get("suggested_next_steps", [])
                st.session_state.pipeline_time = round(time.time() - t0, 2)
                st.session_state.chart_locked  = False

                status.update(label="Analysis complete", state="complete", expanded=False)
                st.rerun()

            except Exception as e:
                status.update(label="Pipeline error", state="error")
                st.error(f"Error: {e}")

    if run_disabled:
        st.caption("Add a transcript or recording above to enable analysis.")


# ─────────────────────────────────────────────
# OUTPUT SECTION
# ─────────────────────────────────────────────
if st.session_state.transcript:

    urgency = st.session_state.classification.get("urgency_tier", "")
    trigger = st.session_state.classification.get("primary_clinical_trigger", "")

    # Always-visible urgency banner
    render_alert(urgency, trigger)

    # ── FOCUS MODE — single-page stripped view ──
    if st.session_state.focus_mode:
        fc1, fc2 = st.columns([1, 1], gap="large")

        with fc1:
            render_signals(st.session_state.salience_map)
            st.divider()
            st.markdown('<div class="sec-label">Safety flags</div>', unsafe_allow_html=True)
            render_flags(st.session_state.flags)

        with fc2:
            st.markdown('<div class="sec-label">SOAP note</div>', unsafe_allow_html=True)
            edited_soap = st.text_area(
                "SOAP note",
                value=st.session_state.soap_note,
                height=340,
                label_visibility="collapsed",
                key="focus_soap",
            )
            try:
                pdf_bytes = generate_clinical_pdf(edited_soap, specialty_profile)
                st.download_button(
                    "⬇ Download PDF",
                    data=pdf_bytes,
                    file_name=f"Salience_OS_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )
            except Exception as e:
                st.error(f"PDF error: {e}")

            st.divider()
            if st.session_state.chart_locked:
                st.success("✓ Signed and pushed to EHR.")
                st.button("Chart locked", disabled=True,
                          use_container_width=True, key="focus_locked")
            else:
                st.warning("Note unsigned — review before sign-off.")
                if st.button("Sign & push to EHR", type="primary",
                             use_container_width=True, key="focus_sign"):
                    with st.spinner("Pushing to EHR…"):
                        time.sleep(2.0)
                    st.session_state.chart_locked = True
                    st.rerun()

    # ── FULL MODE — tabbed workspace ──
    else:
        tab_findings, tab_flags, tab_soap, tab_explain = st.tabs([
            "Key findings",
            "Red flags & next steps",
            "SOAP review",
            "Explainability",
        ])

        # ── Tab 1: Key findings ──
        with tab_findings:
            sig_col, tx_col = st.columns([1, 1], gap="large")

            with sig_col:
                render_signals(st.session_state.salience_map)

            with tx_col:
                st.markdown('<div class="sec-label">Cleaned transcript</div>',
                            unsafe_allow_html=True)
                st.text_area(
                    "Cleaned transcript",
                    value=st.session_state.transcript,
                    height=340,
                    disabled=True,
                    label_visibility="collapsed",
                    key="view_transcript",
                )

        # ── Tab 2: Red flags & next steps ──
        with tab_flags:
            fc, sc = st.columns([1, 1], gap="large")

            with fc:
                st.markdown('<div class="sec-label">Safety flags</div>', unsafe_allow_html=True)
                render_flags(st.session_state.flags)

            with sc:
                st.markdown('<div class="sec-label">Suggested next steps</div>',
                            unsafe_allow_html=True)
                render_steps(st.session_state.next_steps)

        # ── Tab 3: SOAP review ──
        with tab_soap:
            note_col, action_col = st.columns([1.65, 1], gap="large")

            with note_col:
                st.markdown('<div class="sec-label">Clinical note — pending review</div>',
                            unsafe_allow_html=True)
                edited_soap = st.text_area(
                    "SOAP note",
                    value=st.session_state.soap_note,
                    height=440,
                    label_visibility="collapsed",
                    key="edit_soap",
                )

            with action_col:
                st.markdown('<div class="sec-label">Review & sign-off</div>',
                            unsafe_allow_html=True)
                st.caption(
                    f"Processed in {st.session_state.pipeline_time}s · {specialty_profile}"
                )
                st.divider()

                # PDF download
                try:
                    pdf_bytes = generate_clinical_pdf(edited_soap, specialty_profile)
                    st.download_button(
                        "⬇ Download clinical PDF",
                        data=pdf_bytes,
                        file_name=f"Salience_OS_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                        mime="application/pdf",
                        use_container_width=True,
                    )
                except Exception as e:
                    st.error(f"PDF error: {e}")

                st.divider()

                # EHR sign-off
                if st.session_state.chart_locked:
                    st.success("✓ Signed and pushed to EHR.")
                    st.button("Chart locked", disabled=True,
                              use_container_width=True, key="full_locked")
                else:
                    st.warning("Note is unsigned. Review before sign-off.")
                    if st.button("Sign & push to EHR", type="primary",
                                 use_container_width=True, key="full_sign"):
                        with st.spinner("Encrypting and pushing to EHR…"):
                            time.sleep(2.0)
                        st.session_state.chart_locked = True
                        st.rerun()

                st.divider()
                if st.button("↩ New consultation", use_container_width=True, key="new_consult"):
                    reset_analysis()
                    st.rerun()

        # ── Tab 4: Explainability ──
        with tab_explain:
            render_explainability(st.session_state.salience_map)
