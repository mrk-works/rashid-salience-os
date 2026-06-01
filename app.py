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
import pandas as pd
from pydub import AudioSegment
from fpdf import FPDF


# =====================================================================
# 0. PDF UTILITIES (unchanged logic)
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
# 1. PAGE CONFIG & CSS
# =====================================================================
st.set_page_config(page_title="Salience OS", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
/* ── Reset & base ── */
[data-testid="stAppViewContainer"] {
    background: var(--background-color);
}
[data-testid="stSidebar"] {
    background: rgba(0,0,0,0.02) !important;
    border-right: 1px solid rgba(0,0,0,0.07) !important;
}
[data-testid="stSidebar"] > div:first-child {
    padding-top: 1.25rem;
}

/* ── Sidebar logo ── */
.sb-logo {
    font-size: 15px;
    font-weight: 600;
    letter-spacing: 0.3px;
    padding: 0 1rem 1rem;
    border-bottom: 1px solid rgba(0,0,0,0.07);
    margin-bottom: 1rem;
    color: inherit;
}
.sb-logo span {
    opacity: 0.45;
    font-weight: 400;
}

/* ── Section label ── */
.sb-section-label {
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.8px;
    text-transform: uppercase;
    opacity: 0.4;
    margin-bottom: 0.35rem;
    padding: 0 0.1rem;
}

/* ── Status pills ── */
.status-pill {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    font-size: 11px;
    padding: 3px 9px;
    border-radius: 20px;
    font-weight: 500;
    margin-bottom: 0.75rem;
}
.status-ready {
    background: rgba(100,153,34,0.12);
    color: #3B6D11;
}
.status-processing {
    background: rgba(239,159,39,0.15);
    color: #854F0B;
}
.status-done {
    background: rgba(29,158,117,0.12);
    color: #0F6E56;
}

/* ── Urgency banner ── */
.urgency-critical {
    background: rgba(226,75,74,0.08);
    border: 1px solid rgba(226,75,74,0.25);
    border-radius: 10px;
    padding: 10px 14px;
    margin-bottom: 1rem;
}
.urgency-high {
    background: rgba(239,159,39,0.08);
    border: 1px solid rgba(239,159,39,0.25);
    border-radius: 10px;
    padding: 10px 14px;
    margin-bottom: 1rem;
}
.urgency-label {
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.8px;
    text-transform: uppercase;
}
.urgency-critical .urgency-label { color: #A32D2D; }
.urgency-high .urgency-label { color: #854F0B; }
.urgency-critical .urgency-desc { color: #791F1F; font-size: 13px; margin-top: 3px; }
.urgency-high .urgency-desc { color: #633806; font-size: 13px; margin-top: 3px; }

/* ── Signal rows ── */
.signal-row {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 0;
    border-bottom: 1px solid rgba(0,0,0,0.05);
}
.signal-row:last-child { border-bottom: none; }
.signal-name { font-size: 13px; font-weight: 500; flex: 1; }
.signal-cat { font-size: 10px; opacity: 0.45; }
.signal-score { font-size: 11px; opacity: 0.55; font-variant-numeric: tabular-nums; width: 28px; text-align: right; }

/* ── Flag items ── */
.flag-item {
    background: rgba(226,75,74,0.07);
    border: 1px solid rgba(226,75,74,0.2);
    border-radius: 8px;
    padding: 9px 12px;
    font-size: 12px;
    color: #791F1F;
    margin-bottom: 6px;
    line-height: 1.5;
}

/* ── Explain cards ── */
.explain-card {
    border: 1px solid rgba(0,0,0,0.07);
    border-radius: 9px;
    padding: 10px 13px;
    margin-bottom: 8px;
}
.explain-head {
    font-size: 12px;
    font-weight: 600;
    margin-bottom: 4px;
    display: flex;
    align-items: center;
    gap: 7px;
}
.explain-body {
    font-size: 11px;
    opacity: 0.6;
    line-height: 1.6;
}
.conf-hi { color: #A32D2D; }
.conf-med { color: #854F0B; }
.conf-lo { color: #3B6D11; }

/* ── SOAP review ── */
.soap-section-label {
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.8px;
    text-transform: uppercase;
    opacity: 0.4;
    margin-bottom: 4px;
    margin-top: 12px;
}
.soap-content {
    font-size: 13px;
    line-height: 1.8;
    opacity: 0.85;
}

/* ── Step list ── */
.step-item {
    font-size: 12px;
    padding: 6px 0;
    border-bottom: 1px solid rgba(0,0,0,0.05);
    opacity: 0.75;
    display: flex;
    gap: 8px;
    align-items: flex-start;
}
.step-item:last-child { border-bottom: none; }

/* ── Panel header ── */
.panel-header {
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.8px;
    text-transform: uppercase;
    opacity: 0.4;
    margin-bottom: 0.75rem;
    margin-top: 0;
}

/* ── Hide default streamlit chrome ── */
#MainMenu, footer, header { visibility: hidden; }
[data-testid="stDecoration"] { display: none; }
div[data-testid="stToolbar"] { display: none; }

/* ── Compact stMetric ── */
[data-testid="metric-container"] {
    background: rgba(0,0,0,0.03);
    border-radius: 10px;
    padding: 10px 14px;
    border: 1px solid rgba(0,0,0,0.06);
}
</style>
""", unsafe_allow_html=True)


# =====================================================================
# 2. SESSION STATE
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
# 3. SIDEBAR — configuration (collapsed by default when output exists)
# =====================================================================
with st.sidebar:
    st.markdown('<div class="sb-logo">Salience <span>OS</span></div>', unsafe_allow_html=True)

    if st.session_state.transcript:
        st.markdown('<div class="status-pill status-done">● Analysis complete</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="status-pill status-ready">● Ready</div>', unsafe_allow_html=True)

    st.markdown('<div class="sb-section-label">Clinical context</div>', unsafe_allow_html=True)
    specialty_profile = st.selectbox(
        "Specialty",
        ["Cardiology Clinic", "General Internal Medicine", "Emergency Trauma",
         "Neurology", "Pediatrics", "Orthopedic Surgery",
         "Psychiatry & Behavioral Health", "Oncology"],
        label_visibility="collapsed"
    )
    target_language = st.selectbox(
        "Language matrix",
        ["Mixed (Multi-lingual Code-Switching)", "English (US/UK)", "Arabic (Khaleeji/MSA)"],
        label_visibility="collapsed"
    )

    st.divider()
    st.markdown('<div class="sb-section-label">API credentials</div>', unsafe_allow_html=True)

    has_cloud_groq = "groq_api_key" in st.secrets
    has_cloud_gemini = "gemini_api_key" in st.secrets

    groq_input = st.text_input(
        "Groq (Whisper v3)",
        type="password",
        placeholder="Active via vault" if has_cloud_groq else "sk-...",
    )
    gemini_input = st.text_input(
        "Gemini (Flash 2.5)",
        type="password",
        placeholder="Active via vault" if has_cloud_gemini else "AI...",
    )

    groq_api_key = groq_input if groq_input.strip() else st.secrets.get("groq_api_key", "")
    gemini_api_key = gemini_input if gemini_input.strip() else st.secrets.get("gemini_api_key", "")

    if (has_cloud_groq or has_cloud_gemini) and not (groq_input or gemini_input):
        st.caption("Vault credentials active — fields optional.")

    if st.session_state.transcript:
        st.divider()
        st.caption(f"Last run: {st.session_state.pipeline_execution_time}s · {specialty_profile}")


# =====================================================================
# 4. MAIN HEADER
# =====================================================================
header_col, meta_col = st.columns([3, 1])
with header_col:
    st.markdown("## Clinical intelligence workspace")
    st.caption(f"{specialty_profile} · {target_language}")
with meta_col:
    if st.session_state.transcript:
        urgency = st.session_state.classification.get("urgency_tier", "—")
        color = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢"}.get(urgency, "⚪")
        st.metric("Urgency", f"{color} {urgency}")

st.divider()


# =====================================================================
# 5. INPUT CAPTURE AREA
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

        temp_audio_filename = "active_stream_input.wav"
        has_valid_audio_payload = False
        bypass_audio_stt = False
        injected_text_payload = ""

        if "Text" in input_vector:
            injected_text_payload = st.text_area(
                "Transcript",
                placeholder="Paste or type the consultation transcript here…",
                height=180,
                label_visibility="collapsed"
            )
            if injected_text_payload.strip():
                has_valid_audio_payload = True
                bypass_audio_stt = True

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
                            case_idx = st.number_input("Case index", min_value=0, max_value=len(json_data)-1, value=0)
                            selected_node = json_data[case_idx]
                            injected_text_payload = selected_node.get("input", selected_node.get("instruction", ""))
                            if injected_text_payload:
                                st.caption(injected_text_payload[:200] + "…")
                                has_valid_audio_payload = True
                                bypass_audio_stt = True
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

    # ── RUN BUTTON ──
    run_disabled = not has_valid_audio_payload
    if st.button(
        "Run salience analysis",
        type="primary",
        use_container_width=True,
        disabled=run_disabled
    ):
        if not groq_api_key or not gemini_api_key:
            st.error("API credentials missing. Add keys in the sidebar or configure vault secrets.")
        else:
            pipeline_start = time.time()
            with st.status("Running analysis pipeline…", expanded=True) as status:
                try:
                    # STAGE 1: STT
                    if bypass_audio_stt:
                        extracted_raw_text = injected_text_payload
                        st.write("✓ Text input ingested")
                    else:
                        st.write("Compressing audio…")
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
                        st.write("✓ Transcription complete")

                    # STAGE 2: Gemini
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

                    st.session_state.transcript = parsed_payload.get("cleaned_transcript", "")
                    st.session_state.classification = parsed_payload.get("classification", {})
                    st.session_state.salience_map = parsed_payload.get("salience_weight_map", [])
                    st.session_state.soap_note = parsed_payload.get("structured_soap_chart", "")
                    st.session_state.flags = parsed_payload.get("clinical_safety_red_flags", [])
                    st.session_state.next_steps = parsed_payload.get("suggested_next_steps", [])
                    st.session_state.pipeline_execution_time = round(time.time() - pipeline_start, 2)
                    st.session_state.chart_locked = False

                    status.update(label="Analysis complete", state="complete", expanded=False)
                    st.rerun()

                except Exception as e:
                    status.update(label="Pipeline error", state="error")
                    st.error(f"Error: {e}")

    if run_disabled:
        st.caption("Add a transcript or audio recording above to enable analysis.")


# =====================================================================
# 6. OUTPUT WORKSPACE
# =====================================================================
if st.session_state.transcript:

    urgency = st.session_state.classification.get("urgency_tier", "")
    trigger = st.session_state.classification.get("primary_clinical_trigger", "")

    # ── Urgency banner ──
    if urgency == "CRITICAL":
        st.markdown(f"""
        <div class="urgency-critical">
            <div class="urgency-label">⬤ Critical</div>
            <div class="urgency-desc">{trigger}</div>
        </div>
        """, unsafe_allow_html=True)
    elif urgency == "HIGH":
        st.markdown(f"""
        <div class="urgency-high">
            <div class="urgency-label">⬤ High priority</div>
            <div class="urgency-desc">{trigger}</div>
        </div>
        """, unsafe_allow_html=True)

    # ── Output tabs ──
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
                        bar_color = "#E24B4A"
                    elif score >= 0.65:
                        bar_color = "#EF9F27"
                    else:
                        bar_color = "#639922"

                    bar_width = int(score * 60)
                    st.markdown(f"""
                    <div class="signal-row">
                        <div style="width:{bar_width}px;height:3px;border-radius:2px;background:{bar_color};flex-shrink:0;min-width:4px"></div>
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
                    st.markdown(f'<div class="flag-item">⚠ {flag}</div>', unsafe_allow_html=True)
            else:
                st.success("No safety flags identified.")

        with step_col:
            st.markdown('<p class="panel-header">Suggested next steps</p>', unsafe_allow_html=True)
            if st.session_state.next_steps:
                for i, step in enumerate(st.session_state.next_steps, 1):
                    st.markdown(f"""
                    <div class="step-item">
                        <span style="opacity:0.35;font-size:11px;min-width:16px">{i}</span>
                        <span>{step}</span>
                    </div>
                    """, unsafe_allow_html=True)

    # ── TAB 3: SOAP review ──
    with out_tabs[2]:
        soap_col, action_col = st.columns([1.6, 1], gap="large")

        with soap_col:
            st.markdown('<p class="panel-header">Clinical note — pending review</p>', unsafe_allow_html=True)

            # Parse SOAP sections for display
            soap_raw = st.session_state.soap_note
            # Render the raw markdown for editing
            edited_soap = st.text_area(
                "SOAP note",
                value=soap_raw,
                height=420,
                label_visibility="collapsed"
            )

        with action_col:
            st.markdown('<p class="panel-header">Review & sign-off</p>', unsafe_allow_html=True)

            st.caption(
                f"Processed {st.session_state.pipeline_execution_time}s ago · "
                f"{specialty_profile}"
            )
            st.divider()

            # PDF download
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

            # EHR sign-off
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
        st.markdown('<p class="panel-header">Model reasoning — why these signals were prioritised</p>', unsafe_allow_html=True)
        if st.session_state.salience_map:
            for item in sorted(
                st.session_state.salience_map,
                key=lambda x: x.get("salience_score", 0),
                reverse=True
            ):
                score = item.get("salience_score", 0)
                if score >= 0.85:
                    conf_class = "conf-hi"
                    conf_label = "High"
                elif score >= 0.65:
                    conf_class = "conf-med"
                    conf_label = "Medium"
                else:
                    conf_class = "conf-lo"
                    conf_label = "Low"

                st.markdown(f"""
                <div class="explain-card">
                    <div class="explain-head">
                        <span class="{conf_class}">●</span>
                        {item.get('entity','')}
                        <span style="margin-left:auto;font-size:10px;opacity:0.4">{conf_label} · {score:.2f}</span>
                    </div>
                    <div class="explain-body">{item.get('reasoning_context','')}</div>
                </div>
                """, unsafe_allow_html=True)
