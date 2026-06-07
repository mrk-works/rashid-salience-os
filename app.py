# =====================================================================
# SALIENCE OS — Clinical Intelligence Workspace
# Production-Stabilized + UX Onboarding Layer
# =====================================================================

import sys
try:
    import audioop  # noqa: F401
except ImportError:
    try:
        import audioop_lts as audioop  # type: ignore
        sys.modules["audioop"] = audioop
    except ImportError:
        pass

import streamlit as st
import os
import json
import time
from datetime import datetime

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

# Demo patient data — pre-loaded case for exploration
DEMO_TRANSCRIPT = """
Doctor: Good morning. What brings you in today?
Patient: I've had this crushing chest pain for about 45 minutes now. It started suddenly while I was walking to my car. It's radiating down my left arm and I feel really short of breath.
Doctor: On a scale of 1 to 10, how severe is the pain?
Patient: About an 8 or 9. I'm also feeling quite nauseous and I've been sweating a lot.
Doctor: Any history of heart problems? High blood pressure? Diabetes?
Patient: Yes, I have high blood pressure — I take amlodipine 5mg. I'm also on metformin for type 2 diabetes. My father had a heart attack at 58.
Doctor: Any previous chest pain episodes like this?
Patient: I had some milder episodes a few weeks ago but they went away after a few minutes. This one isn't going away.
Doctor: Are you on any blood thinners or statins?
Patient: I take atorvastatin 20mg. No blood thinners.
"""

DEMO_EXAM = {
    "thoracic": "Cardiovascular: Tachycardic at 112 bpm, rhythm regular. S1 and S2 distinct, no murmurs. Diaphoresis noted. BP 158/94 mmHg. Respiratory: RR 22, shallow. Lungs clear to auscultation bilaterally.",
    "gi": "Abdomen soft, non-distended. Bowel sounds present. No epigastric tenderness. No hepatosplenomegaly.",
    "neuro": "Alert and oriented x3. GCS 15. No focal neurological deficits. Mild anxiety observed.",
    "msk": "No peripheral oedema. Peripheral pulses present bilaterally. No calf tenderness.",
}

DEMO_OUTPUT = {
    "transcript": "Patient presents with 45-minute history of crushing chest pain radiating to left arm, associated with diaphoresis, nausea, and dyspnoea. PMH: hypertension (amlodipine 5mg), type 2 diabetes (metformin). FH: paternal MI at 58. Current medications: atorvastatin 20mg. Similar but milder episodes reported in preceding weeks.",
    "classification": {
        "urgency_tier": "CRITICAL",
        "primary_clinical_trigger": "Acute chest pain with radiation, diaphoresis, and dyspnoea — high probability acute coronary syndrome requiring immediate evaluation.",
    },
    "salience_map": [
        {"entity": "Crushing chest pain (45 min)", "category": "Symptom", "salience_score": 0.98, "reasoning_context": "Cardinal presenting symptom. Duration >20 min, quality, and radiation pattern strongly suggest ACS. Highest clinical priority."},
        {"entity": "Left arm radiation", "category": "Symptom", "salience_score": 0.94, "reasoning_context": "Classic referred pain pattern via C8-T1 dermatomes. Increases pre-test probability for myocardial infarction significantly."},
        {"entity": "Diaphoresis", "category": "Symptom", "salience_score": 0.91, "reasoning_context": "Autonomic activation indicating haemodynamic stress. Combined with tachycardia, suggests significant myocardial event."},
        {"entity": "Tachycardia HR 112", "category": "Vital Sign", "salience_score": 0.88, "reasoning_context": "Compensatory tachycardia consistent with pain, anxiety, or reduced cardiac output. Requires continuous monitoring."},
        {"entity": "Hypertension (amlodipine)", "category": "Medical History", "salience_score": 0.82, "reasoning_context": "Established cardiovascular risk factor. Uncontrolled BP in current presentation adds further risk stratification."},
        {"entity": "Prior episodes (weeks ago)", "category": "Duration", "salience_score": 0.79, "reasoning_context": "Antecedent unstable angina pattern. Suggests evolving coronary disease rather than a first event."},
        {"entity": "Paternal MI at 58", "category": "Medical History", "salience_score": 0.74, "reasoning_context": "Premature family history of CAD — strong independent risk factor for early-onset coronary artery disease."},
        {"entity": "Type 2 Diabetes (metformin)", "category": "Medical History", "salience_score": 0.71, "reasoning_context": "Diabetes is an independent CAD risk multiplier. May mask typical anginal symptoms — atypical presentations possible."},
    ],
    "flags": [
        "STEMI must be excluded immediately — obtain 12-lead ECG within 10 minutes of arrival",
        "Haemodynamic instability risk: tachycardia + hypertension + diaphoresis — continuous monitoring required",
        "Prior unstable angina pattern suggests evolving ACS — do not discharge without full workup",
        "Metformin should be withheld if contrast imaging (coronary angiography) is anticipated",
    ],
    "next_steps": [
        "12-lead ECG stat — repeat at 15 and 30 minutes",
        "High-sensitivity troponin I/T at 0h and 3h",
        "Aspirin 300mg PO stat (if no contraindication)",
        "Activate cath lab if STEMI confirmed — target door-to-balloon <90 min",
        "IV access x2, continuous cardiac monitoring, O2 if SpO2 <94%",
        "Chest X-ray portable (do not delay reperfusion for imaging)",
        "Heparin IV per ACS weight-based protocol",
        "Cardiology registrar + interventional cardiologist notification",
    ],
    "soap_note": """### Subjective:
63-year-old male presenting with a 45-minute history of severe (8-9/10) crushing substernal chest pain with radiation to the left arm, associated with diaphoresis, nausea, and dyspnoea. Similar but milder episodes noted in preceding weeks — not previously investigated. PMH: hypertension (amlodipine 5mg), type 2 diabetes mellitus (metformin). FH: father had MI at age 58. Current medications: atorvastatin 20mg, amlodipine 5mg, metformin.

### Objective:
BP 158/94 mmHg, HR 112 bpm (regular), RR 22/min, SpO2 not recorded. Diaphoretic. CVS: tachycardic, S1/S2 present, no murmurs, rubs, or gallops. Respiratory: tachypnoeic, CTAB bilaterally. Abdomen: soft, non-tender. Neuro: A&Ox3, GCS 15, no focal deficits. No peripheral oedema.

### Assessment:
High-probability acute coronary syndrome (ACS) — STEMI vs NSTEMI pending ECG and troponin results. Significant cardiovascular risk profile including hypertension, type 2 diabetes, family history of premature CAD, and prior unstable angina pattern. Haemodynamically stressed but currently compensated.

### Plan:
Immediate: 12-lead ECG stat, hs-troponin at 0h/3h, aspirin 300mg PO, IV access x2, continuous cardiac monitoring. If STEMI confirmed: activate cath lab, target D2B <90 minutes, heparin per protocol. Notify cardiology. Withhold metformin if contrast study anticipated. ICU/HDU bed requested. Full ACS protocol initiated.""",
}


# =====================================================================
# PDF GENERATION (unchanged)
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


def generate_clinical_pdf(soap_text: str, specialty: str, report_type: str = "clinical") -> bytes:
    if not FPDF_AVAILABLE:
        raise RuntimeError("fpdf2 is not installed.")
    pdf = FPDF()
    pdf.set_margins(left=15, top=10, right=15)
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    header_color = (2, 132, 199) if report_type == "clinical" else (5, 150, 105)
    pdf.set_fill_color(*header_color)
    pdf.rect(0, 0, 210, 38, "F")
    pdf.set_xy(0, 8)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 18)
    title = "SALIENCE OS | CLINICAL REPORT" if report_type == "clinical" else "SALIENCE OS | PHARMACY REPORT"
    pdf.cell(210, 12, title, new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.set_font("Helvetica", "I", 10)
    pdf.cell(
        210, 5,
        sanitize_for_pdf(f"Specialty: {specialty} | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"),
        new_x="LMARGIN", new_y="NEXT", align="C",
    )
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
            pdf.set_text_color(*header_color)
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


def generate_pharmacy_report(salience_map: list, soap_note: str, specialty: str) -> str:
    """Generate a medication-focused pharmacy summary from existing analysis data."""
    med_signals = [
        item for item in salience_map
        if item.get("category", "").lower() in ("medication", "medical history")
        or any(kw in item.get("entity", "").lower()
               for kw in ["mg", "tablet", "dose", "drug", "medication", "metformin",
                          "aspirin", "heparin", "statin", "atorvastatin", "amlodipine"])
    ]
    lines = ["### Pharmacy / Medication Summary\n"]
    lines.append("**Identified Medications & Clinical Context**\n")
    if med_signals:
        for item in med_signals:
            lines.append(f"- {item['entity']}: {item.get('reasoning_context', '')}")
    else:
        lines.append("- No specific medications identified in transcript.")
    lines.append("\n### Clinical Notes for Dispensing\n")
    for line in soap_note.split("\n"):
        if any(kw in line.lower() for kw in
               ["medication", "mg", "drug", "prescription", "dose", "withhold",
                "aspirin", "heparin", "metformin", "contrast"]):
            lines.append(line)
    lines.append("\n### Prescriber Declaration\n")
    lines.append(f"Report generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("Specialty: " + specialty)
    lines.append("\n**Note: This report is generated by an AI documentation assistant. "
                 "Final prescription authority rests with the treating clinician.**")
    return "\n".join(lines)


# =====================================================================
# PAGE CONFIG
# =====================================================================
st.set_page_config(
    page_title="Salience OS",
    page_icon="⬡",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# =====================================================================
# SESSION STATE
# =====================================================================
_DEFAULTS: dict = {
    # Core analysis state
    "transcript": "",
    "classification": {},
    "salience_map": [],
    "soap_note": "",
    "flags": [],
    "next_steps": [],
    "pipeline_execution_time": 0.0,
    "chart_locked": False,
    # Navigation
    "nav_page": "home",
    # Onboarding
    "onboarding_dismissed": False,
    # Settings
    "sc_specialty": "Cardiology",
    "sc_language": "Mixed",
    "sc_theme": "Dark",
    "_groq_override": "",
    "_gemini_override": "",
    # Patient dashboard log
    "consultation_history": [],
    # Demo mode flag
    "is_demo": False,
    # Patient name (optional, for reports)
    "patient_ref": "",
}
for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v


# =====================================================================
# SECRETS
# =====================================================================
try:
    _has_vault_groq   = "groq_api_key"   in st.secrets
    _has_vault_gemini = "gemini_api_key" in st.secrets
    _vault_groq   = st.secrets.get("groq_api_key",   "") if _has_vault_groq   else ""
    _vault_gemini = st.secrets.get("gemini_api_key", "") if _has_vault_gemini else ""
except Exception:
    _has_vault_groq = _has_vault_gemini = False
    _vault_groq = _vault_gemini = ""


# =====================================================================
# CSS
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
  --tier-critical:  #EF4444;
  --tier-high:      #F59E0B;
  --tier-medium:    #3B82F6;
  --tier-low:       #10B981;
  --radius-sm: 5px; --radius-md: 9px; --radius-lg: 14px;
  --font-mono: 'JetBrains Mono','Fira Code','SF Mono',ui-monospace,monospace;
  --transition: 150ms cubic-bezier(0.4,0,0.2,1);
}
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
  padding-top: 0 !important;
  padding-left: 16px !important;
  padding-right: 16px !important;
  padding-bottom: 60px !important;
  max-width: 100% !important;
}
::-webkit-scrollbar { width: 4px; }
::-webkit-scrollbar-thumb { background: var(--border-default); border-radius: 99px; }

/* ── Nav bar ── */
.os-nav {
  display: flex; align-items: center; gap: 0;
  background: rgba(8,11,16,0.92);
  backdrop-filter: blur(20px);
  border-bottom: 1px solid var(--border-subtle);
  padding: 0 20px;
  height: 50px;
}
.os-wordmark {
  font-size: 14px; font-weight: 700; letter-spacing: 0.3px;
  color: var(--text-primary); margin-right: 28px; flex-shrink: 0;
}
.os-wordmark span { color: var(--accent-blue); }
.os-nav-items { display: flex; gap: 2px; flex: 1; }
.os-nav-item {
  padding: 6px 14px; border-radius: var(--radius-sm);
  font-size: 12.5px; font-weight: 500; color: var(--text-muted);
  cursor: pointer; border: none; background: transparent;
  transition: all var(--transition); white-space: nowrap;
}
.os-nav-item:hover { color: var(--text-secondary); background: var(--bg-hover); }
.os-nav-item.active { color: var(--text-primary); background: var(--bg-elevated); }
.os-nav-right { margin-left: auto; display: flex; align-items: center; gap: 8px; }

/* ── Workflow stepper ── */
.workflow-stepper {
  display: flex; align-items: flex-start; gap: 0;
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg);
  padding: 16px 20px; margin-bottom: 24px;
  overflow-x: auto;
}
.workflow-step {
  display: flex; flex-direction: column; align-items: center;
  gap: 6px; flex: 1; min-width: 80px; position: relative;
}
.workflow-step:not(:last-child)::after {
  content: ''; position: absolute; top: 14px; left: calc(50% + 14px);
  right: calc(-50% + 14px); height: 1px;
  background: var(--border-subtle);
}
.ws-circle {
  width: 28px; height: 28px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 11px; font-weight: 700; flex-shrink: 0;
  border: 2px solid;
}
.ws-circle.done     { background: rgba(16,185,129,0.15); border-color: var(--accent-emerald); color: var(--accent-emerald); }
.ws-circle.active   { background: rgba(59,130,246,0.15); border-color: var(--accent-blue);    color: var(--accent-blue); }
.ws-circle.pending  { background: var(--bg-elevated);    border-color: var(--border-default); color: var(--text-muted); }
.ws-label { font-size: 10px; font-weight: 500; color: var(--text-muted); text-align: center; line-height: 1.3; }
.ws-label.active  { color: var(--text-secondary); }
.ws-label.done    { color: var(--accent-emerald); }

/* ── Welcome card ── */
.welcome-card {
  background: linear-gradient(135deg, rgba(59,130,246,0.08) 0%, rgba(139,92,246,0.06) 100%);
  border: 1px solid rgba(59,130,246,0.2);
  border-radius: var(--radius-lg); padding: 28px 32px; margin-bottom: 24px;
}
.welcome-title { font-size: 20px; font-weight: 700; color: var(--text-primary); margin-bottom: 6px; }
.welcome-subtitle { font-size: 13.5px; color: var(--text-secondary); line-height: 1.6; margin-bottom: 18px; }
.welcome-grid {
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 20px;
}
.welcome-stat {
  background: var(--bg-elevated); border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md); padding: 12px 14px;
}
.welcome-stat-label { font-size: 9.5px; font-weight: 700; letter-spacing: 0.8px;
  text-transform: uppercase; color: var(--text-muted); margin-bottom: 3px; }
.welcome-stat-value { font-size: 13px; font-weight: 600; color: var(--text-primary); }

/* ── Section label ── */
.section-label {
  font-size: 10px; font-weight: 700; letter-spacing: 1px;
  text-transform: uppercase; color: var(--text-muted);
  margin: 0 0 12px; display: flex; align-items: center; gap: 10px;
}
.section-label::after { content:''; flex:1; height:1px; background: var(--border-subtle); }

/* ── Help card ── */
.help-card {
  background: var(--bg-elevated); border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md); padding: 14px 16px; margin-bottom: 8px;
}
.help-card-title { font-size: 12px; font-weight: 600; color: var(--text-primary); margin-bottom: 5px; }
.help-card-body  { font-size: 12px; color: var(--text-secondary); line-height: 1.6; }

/* ── Urgency banner ── */
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
  display:inline-flex; align-items:center; gap:4px; padding:3px 9px;
  background:var(--bg-elevated); border:1px solid var(--border-subtle);
  border-radius:99px; font-size:11px; color:var(--text-secondary);
}
.metric-chip .chip-label { font-size:10.5px; color:var(--text-muted); }

/* ── Signal rows ── */
.signal-row {
  display:flex; align-items:flex-start; gap:12px;
  padding:10px 6px; border-bottom:1px solid var(--border-subtle);
  border-radius:var(--radius-sm); transition:background var(--transition);
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

/* ── Flag & step items ── */
.flag-item {
  display:flex; align-items:flex-start; gap:10px; padding:11px 14px;
  background:rgba(239,68,68,0.06); border:1px solid rgba(239,68,68,0.15);
  border-left:3px solid var(--tier-critical); border-radius:var(--radius-md);
  margin-bottom:8px; font-size:13px; color:#FCA5A5; line-height:1.55;
}
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
  font-size:14px; line-height:1.9; color:var(--text-primary);
}
.soap-section-header {
  font-size:10px; font-weight:700; letter-spacing:1.1px; text-transform:uppercase;
  color:var(--accent-blue); margin-top:24px; margin-bottom:10px;
  padding-bottom:7px; border-bottom:1px solid var(--border-subtle);
}
.soap-section-header:first-child { margin-top:0; }
.soap-body-p { margin:0 0 2px; color:var(--text-secondary); }
.soap-bold   { color:var(--text-primary); font-weight:600; }
.soap-meta-row {
  display:flex; align-items:center; gap:16px; flex-wrap:wrap;
  padding:12px 0; margin-bottom:8px; border-bottom:1px solid var(--border-subtle);
}
.soap-meta-item { display:flex; flex-direction:column; gap:2px; }
.soap-meta-label { font-size:9.5px; font-weight:700; letter-spacing:.8px; text-transform:uppercase; color:var(--text-muted); }
.soap-meta-value { font-size:12.5px; font-weight:500; color:var(--text-secondary); font-family:var(--font-mono); }

/* ── Empty state ── */
.empty-state {
  display:flex; flex-direction:column; align-items:center; justify-content:center;
  padding:44px 24px; text-align:center; gap:10px;
}
.empty-state-icon  { font-size:28px; opacity:.2; }
.empty-state-title { font-size:13.5px; font-weight:600; color:var(--text-secondary); }
.empty-state-body  { font-size:12px; color:var(--text-muted); line-height:1.7; max-width:320px; }

/* ── Dashboard card ── */
.dash-card {
  background:var(--bg-surface); border:1px solid var(--border-subtle);
  border-radius:var(--radius-md); padding:14px 16px; margin-bottom:10px;
}
.dash-card-header { display:flex; align-items:center; justify-content:space-between; margin-bottom:8px; }
.dash-card-title  { font-size:13px; font-weight:600; color:var(--text-primary); }
.dash-card-meta   { font-size:11px; color:var(--text-muted); font-family:var(--font-mono); }
.dash-card-body   { font-size:12px; color:var(--text-secondary); line-height:1.6; }

/* ── Disclaimer footer ── */
.clinical-disclaimer {
  position: fixed; bottom: 0; left: 0; right: 0; z-index: 999;
  background: rgba(8,11,16,0.94); backdrop-filter: blur(12px);
  border-top: 1px solid var(--border-subtle);
  padding: 8px 24px; text-align: center;
  font-size: 11px; color: var(--text-muted); line-height: 1.4;
}

/* ── Control center label ── */
.ctrl-label {
  font-size:9.5px; font-weight:700; letter-spacing:1px;
  text-transform:uppercase; color:var(--text-muted);
  display:block; margin-bottom:8px; margin-top:16px;
}
.ctrl-label:first-child { margin-top:0; }

/* ── Misc overrides ── */
section[data-testid="stSidebar"] { background:var(--bg-surface) !important; border-right:1px solid var(--border-subtle) !important; }
.stTextInput > div > div > input, .stTextArea > div > div > textarea {
  background:var(--bg-elevated) !important; border:1px solid var(--border-default) !important;
  border-radius:var(--radius-md) !important; color:var(--text-primary) !important; font-size:13px !important;
}
.stButton > button[kind="primary"] {
  background:var(--accent-blue) !important; color:#fff !important; border:none !important;
  border-radius:var(--radius-md) !important; font-weight:600 !important; font-size:13px !important; height:40px !important;
}
.stButton > button[kind="primary"]:hover { background:var(--accent-blue-dim) !important; }
.stButton > button[kind="secondary"], .stButton > button:not([kind]) {
  background:var(--bg-elevated) !important; color:var(--text-primary) !important;
  border:1px solid var(--border-default) !important; border-radius:var(--radius-md) !important;
  font-weight:500 !important; font-size:13px !important; height:40px !important;
}
.stButton > button:disabled { background:var(--bg-elevated) !important; color:var(--text-muted) !important; border-color:var(--border-subtle) !important; }
.stDownloadButton > button { background:var(--bg-elevated) !important; color:var(--text-primary) !important; border:1px solid var(--border-default) !important; border-radius:var(--radius-md) !important; font-weight:500 !important; height:40px !important; }
.stTabs [data-baseweb="tab-list"] { background:transparent !important; border-bottom:1px solid var(--border-subtle) !important; gap:0 !important; padding:0 !important; }
.stTabs [data-baseweb="tab"] { background:transparent !important; color:var(--text-muted) !important; font-size:12.5px !important; font-weight:500 !important; padding:9px 16px !important; border-bottom:2px solid transparent !important; border-radius:0 !important; }
.stTabs [aria-selected="true"] { color:var(--text-primary) !important; border-bottom:2px solid var(--accent-blue) !important; }
.stTabs [data-baseweb="tab-panel"] { padding:18px 0 0 !important; }
[data-testid="stSegmentedControl"] > div { background:var(--bg-elevated) !important; border:1px solid var(--border-default) !important; border-radius:var(--radius-md) !important; padding:3px !important; gap:2px !important; }
[data-testid="stSegmentedControl"] button { background:transparent !important; color:var(--text-secondary) !important; border-radius:var(--radius-sm) !important; font-size:12.5px !important; font-weight:500 !important; border:none !important; }
[data-testid="stSegmentedControl"] button[aria-checked="true"] { background:var(--accent-blue) !important; color:#fff !important; }
[data-testid="stPills"] button { background:var(--bg-elevated) !important; color:var(--text-secondary) !important; border:1px solid var(--border-default) !important; border-radius:99px !important; font-size:12px !important; font-weight:500 !important; }
[data-testid="stPills"] button[aria-pressed="true"] { background:rgba(59,130,246,0.15) !important; color:var(--accent-blue) !important; border-color:rgba(59,130,246,.3) !important; }
[data-testid="stAudioInput"]   { background:var(--bg-elevated) !important; border:1px solid var(--border-default) !important; border-radius:var(--radius-md) !important; }
[data-testid="stFileUploader"] { background:var(--bg-elevated) !important; border:1px dashed var(--border-default) !important; border-radius:var(--radius-md) !important; }
hr { border-color:var(--border-subtle) !important; margin:20px 0 !important; }
[data-testid="stStatusWidget"] { background:var(--bg-elevated) !important; border:1px solid var(--border-default) !important; border-radius:var(--radius-md) !important; }
label[data-testid="stWidgetLabel"] { color:var(--text-secondary) !important; font-size:12px !important; }
.stCaption { color:var(--text-muted) !important; font-size:11.5px !important; }
p { color:var(--text-secondary) !important; }
[data-testid="stPopover"] > div { background:var(--bg-elevated) !important; border:1px solid var(--border-default) !important; border-radius:var(--radius-lg) !important; box-shadow:0 16px 48px rgba(0,0,0,.7) !important; }
</style>
""", unsafe_allow_html=True)


# =====================================================================
# HELPERS
# =====================================================================
def load_demo_patient() -> None:
    """Populate session state with the demo patient case."""
    st.session_state.transcript              = DEMO_OUTPUT["transcript"]
    st.session_state.classification          = DEMO_OUTPUT["classification"]
    st.session_state.salience_map            = DEMO_OUTPUT["salience_map"]
    st.session_state.soap_note               = DEMO_OUTPUT["soap_note"]
    st.session_state.flags                   = DEMO_OUTPUT["flags"]
    st.session_state.next_steps              = DEMO_OUTPUT["next_steps"]
    st.session_state.pipeline_execution_time = 3.2
    st.session_state.chart_locked            = False
    st.session_state.is_demo                 = True
    st.session_state.patient_ref             = "DEMO-001 (Acute Chest Pain)"
    st.session_state.nav_page                = "consultation"


def reset_consultation() -> None:
    for k in ["transcript", "classification", "salience_map", "soap_note",
              "flags", "next_steps", "pipeline_execution_time", "chart_locked",
              "is_demo", "patient_ref"]:
        st.session_state[k] = _DEFAULTS[k]


def save_to_history() -> None:
    """Save current consultation to session-based patient dashboard."""
    if not st.session_state.transcript:
        return
    entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "patient_ref": st.session_state.patient_ref or "Unnamed",
        "specialty": SPECIALTY_MAP.get(st.session_state.sc_specialty, ""),
        "urgency": st.session_state.classification.get("urgency_tier", "—"),
        "trigger": st.session_state.classification.get("primary_clinical_trigger", ""),
        "n_signals": len(st.session_state.salience_map),
        "n_flags": len(st.session_state.flags),
        "soap_note": st.session_state.soap_note,
        "is_demo": st.session_state.is_demo,
    }
    st.session_state.consultation_history.append(entry)


def get_workflow_step() -> int:
    """Return current workflow step index (0-based) for the stepper."""
    if st.session_state.chart_locked:
        return 5
    if st.session_state.soap_note:
        return 4
    if st.session_state.salience_map:
        return 3
    if st.session_state.transcript:
        return 3
    return 0


def render_workflow_stepper() -> None:
    current = get_workflow_step()
    steps = [
        ("1", "Input\nConsultation"),
        ("2", "Add Exam\nFindings"),
        ("3", "Run\nAnalysis"),
        ("4", "Review\nSignals"),
        ("5", "SOAP\nNote"),
        ("6", "Sign &\nExport"),
    ]
    circles = []
    for i, (num, label) in enumerate(steps):
        if i < current:
            c_cls = "done"
            icon  = "✓"
            l_cls = "done"
        elif i == current:
            c_cls = "active"
            icon  = num
            l_cls = "active"
        else:
            c_cls = "pending"
            icon  = num
            l_cls = ""
        circles.append(
            f'<div class="workflow-step">'
            f'<div class="ws-circle {c_cls}">{icon}</div>'
            f'<div class="ws-label {l_cls}">{label}</div>'
            f'</div>'
        )
    st.markdown(
        f'<div class="workflow-stepper">{"".join(circles)}</div>',
        unsafe_allow_html=True,
    )


def render_signal_list(salience_map: list, show_reasoning: bool = False) -> None:
    if not salience_map:
        st.markdown("""
        <div class="empty-state">
          <div class="empty-state-icon">◎</div>
          <div class="empty-state-title">No signals extracted</div>
          <div class="empty-state-body">Run clinical analysis to generate salience-weighted signals from the consultation transcript.</div>
        </div>""", unsafe_allow_html=True)
        return
    for item in sorted(salience_map, key=lambda x: x.get("salience_score", 0), reverse=True):
        score    = float(item.get("salience_score", 0.0))
        entity   = str(item.get("entity", ""))
        category = str(item.get("category", ""))
        reason   = str(item.get("reasoning_context", ""))
        pct      = int(score * 100)
        if score >= 0.85:   ring_cls, bc = "score-critical", "var(--tier-critical)"
        elif score >= 0.70: ring_cls, bc = "score-high",     "var(--tier-high)"
        elif score >= 0.50: ring_cls, bc = "score-medium",   "var(--tier-medium)"
        else:               ring_cls, bc = "score-low",      "var(--tier-low)"
        reasoning_html = f'<div class="signal-reasoning">{reason}</div>' if show_reasoning else ""
        st.markdown(f"""
        <div class="signal-row">
          <div class="signal-score-ring {ring_cls}">{pct}</div>
          <div class="signal-body">
            <div class="signal-entity">{entity}</div>
            <span class="signal-category-chip">{category}</span>
            {reasoning_html}
            <div class="signal-bar-track">
              <div class="signal-bar-fill" style="width:{pct}%;background:{bc}"></div>
            </div>
          </div>
        </div>""", unsafe_allow_html=True)


def render_soap_html(soap_raw: str) -> None:
    rendered: list[str] = []
    for line in soap_raw.split("\n"):
        s = line.strip()
        if s.startswith("###"):
            rendered.append(f'<div class="soap-section-header">{s.replace("###","").strip().rstrip(":")}</div>')
        elif s.startswith("**") and s.endswith("**"):
            rendered.append(f'<span class="soap-bold">{s.replace("**","").strip()}</span><br>')
        elif s:
            rendered.append(f'<p class="soap-body-p">{s}</p>')
        else:
            rendered.append('<div style="height:6px"></div>')
    st.markdown(
        f'<div class="soap-outer"><div class="soap-viewer">{"".join(rendered)}</div></div>',
        unsafe_allow_html=True,
    )


# =====================================================================
# CONTROL CENTER (popover)
# =====================================================================
def render_control_center() -> None:
    st.markdown('<span class="ctrl-label">Specialty Profile</span>', unsafe_allow_html=True)
    chosen_spec = st.segmented_control(
        "Specialty", options=SPECIALTY_OPTIONS,
        default=st.session_state.sc_specialty,
        key="sc_specialty_widget", label_visibility="collapsed",
    )
    if chosen_spec is not None:
        st.session_state.sc_specialty = chosen_spec

    st.markdown('<span class="ctrl-label">Language Matrix</span>', unsafe_allow_html=True)
    chosen_lang = st.segmented_control(
        "Language", options=LANGUAGE_OPTIONS,
        default=st.session_state.sc_language,
        key="sc_language_widget", label_visibility="collapsed",
    )
    if chosen_lang is not None:
        st.session_state.sc_language = chosen_lang

    st.markdown('<span class="ctrl-label">Theme</span>', unsafe_allow_html=True)
    chosen_theme = st.pills(
        "Theme", options=["Dark", "System", "Light"],
        default=st.session_state.sc_theme,
        key="sc_theme_widget", label_visibility="collapsed",
    )
    if chosen_theme is not None:
        st.session_state.sc_theme = chosen_theme

    st.markdown('<span class="ctrl-label">Patient Reference</span>', unsafe_allow_html=True)
    st.text_input(
        "Patient ref / case ID",
        placeholder="e.g. PT-2024-0042 or leave blank",
        key="patient_ref", label_visibility="collapsed",
    )

    st.markdown('<span class="ctrl-label">API Credentials</span>', unsafe_allow_html=True)
    if _has_vault_groq and _has_vault_gemini:
        st.caption("✓  Vault active — keys pre-loaded")
    else:
        st.text_input("Groq API Key", type="password",
                      placeholder="sk-..." if not _has_vault_groq else "🔒 Vault loaded",
                      key="_groq_override")
        st.text_input("Gemini API Key", type="password",
                      placeholder="AI..." if not _has_vault_gemini else "🔒 Vault loaded",
                      key="_gemini_override")


# Resolve final values
_raw_spec      = st.session_state.sc_specialty or "Cardiology"
_raw_lang      = st.session_state.sc_language  or "Mixed"
specialty_profile: str = SPECIALTY_MAP.get(_raw_spec, "Cardiology Clinic")
target_language:   str = LANGUAGE_MAP.get(_raw_lang, "Mixed (Multi-lingual Code-Switching)")
groq_api_key:   str = (st.session_state.get("_groq_override") or "").strip() or _vault_groq
gemini_api_key: str = (st.session_state.get("_gemini_override") or "").strip() or _vault_gemini


# =====================================================================
# NAVIGATION BAR
# =====================================================================
nav_pages = [
    ("home",         "🏠  Home"),
    ("consultation", "🧾  Consultation"),
    ("dashboard",    "📊  Dashboard"),
    ("reports",      "📄  Reports"),
    ("help",         "📚  Help"),
]

nav_cols = st.columns([3, 1, 1, 1, 1, 1, 1])
with nav_cols[0]:
    st.markdown(
        '<div style="padding:10px 0 6px;font-size:14px;font-weight:700;color:#EDF0F4;letter-spacing:.3px">'
        'SALIENCE <span style="color:#3B82F6">OS</span></div>',
        unsafe_allow_html=True,
    )

for i, (page_key, page_label) in enumerate(nav_pages):
    with nav_cols[i + 1]:
        is_active = st.session_state.nav_page == page_key
        btn_type  = "primary" if is_active else "secondary"
        if st.button(page_label, key=f"nav_{page_key}", type=btn_type, use_container_width=True):
            st.session_state.nav_page = page_key
            st.rerun()

st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

# Settings popover on right — separate row
settings_col, _ = st.columns([1, 5])
with settings_col:
    with st.popover("⚙ Settings", use_container_width=True):
        render_control_center()

st.divider()
current_page = st.session_state.nav_page


# =====================================================================
# PAGE: HOME
# =====================================================================
if current_page == "home":

    # ── Welcome card ──────────────────────────────────────────────
    if not st.session_state.onboarding_dismissed:
        st.markdown("""
        <div class="welcome-card">
          <div class="welcome-title">⬡ Welcome to Salience OS</div>
          <div class="welcome-subtitle">
            A clinical intelligence workspace for doctors, psychologists, therapists, nurses, and allied health professionals.<br>
            Record or paste any consultation — Salience OS extracts what matters most, flags risks, and generates a structured clinical note in under 60 seconds.
          </div>
          <div class="welcome-grid">
            <div class="welcome-stat">
              <div class="welcome-stat-label">Input</div>
              <div class="welcome-stat-value">Audio · Text · Dataset</div>
            </div>
            <div class="welcome-stat">
              <div class="welcome-stat-label">Output</div>
              <div class="welcome-stat-value">Signals · SOAP · Report</div>
            </div>
            <div class="welcome-stat">
              <div class="welcome-stat-label">Analysis time</div>
              <div class="welcome-stat-value">~30–60 seconds</div>
            </div>
            <div class="welcome-stat">
              <div class="welcome-stat-label">No training required</div>
              <div class="welcome-stat-value">Guided workflow</div>
            </div>
          </div>
        </div>
        """, unsafe_allow_html=True)

        wc1, wc2, wc3 = st.columns([1, 1, 3])
        with wc1:
            if st.button("🧪 Load Demo Patient", use_container_width=True):
                load_demo_patient()
                st.rerun()
        with wc2:
            if st.button("Get Started →", type="primary", use_container_width=True):
                st.session_state.onboarding_dismissed = True
                st.session_state.nav_page = "consultation"
                st.rerun()
        with wc3:
            st.caption("The demo patient loads a pre-built acute chest pain case so you can explore all outputs without real patient data.")

    # ── Workflow visualizer ────────────────────────────────────────
    st.markdown('<div class="section-label">How it works</div>', unsafe_allow_html=True)
    render_workflow_stepper()

    # ── Step detail expanders ──────────────────────────────────────
    st.markdown('<div class="section-label">Clinical workflow guide</div>', unsafe_allow_html=True)

    workflow_details = [
        ("1 · Upload or paste consultation", "⏱ 30 sec",
         "Paste the consultation transcript directly, record live audio from the room microphone, or upload a pre-recorded .wav/.mp3 file. Multi-lingual and code-switched speech is supported."),
        ("2 · Add physical examination findings", "⏱ 1–2 min",
         "Enter findings from your physical examination across Thoracic, GI/Abdomen, Neuro, and MSK systems. Pre-filled templates are provided — edit only what is relevant."),
        ("3 · Run clinical analysis", "⏱ 30–60 sec",
         "Salience OS runs a two-stage pipeline: speech-to-text via Whisper large-v3, followed by clinical reasoning via Gemini 2.5 Flash. The system extracts entities, weights clinical importance, and flags risks."),
        ("4 · Review signals and safety flags", "⏱ 1 min",
         "Clinical signals are ranked by salience score (0–100). Red flags requiring immediate attention appear in the Safety Flags tab. Review these before moving to the SOAP note."),
        ("5 · Review and amend the SOAP note", "⏱ 1–3 min",
         "The AI generates a structured Subjective, Objective, Assessment, and Plan note. You must review, amend, and verify it — it is your clinical document. The AI is an assistant, not the author."),
        ("6 · Sign, export, and share", "⏱ 30 sec",
         "Export a clinical PDF, generate a pharmacy/medication summary, or digitally sign and push to the EHR system. All exports carry a disclaimer confirming AI-assisted generation."),
    ]

    for title, timing, description in workflow_details:
        with st.expander(f"{title}  ·  {timing}"):
            st.markdown(description)

    # ── Quick start buttons ────────────────────────────────────────
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    st.markdown('<div class="section-label">Quick start</div>', unsafe_allow_html=True)
    qs1, qs2, qs3 = st.columns(3)
    with qs1:
        if st.button("🧪 Load Demo Patient", use_container_width=True, key="qs_demo"):
            load_demo_patient()
            st.rerun()
    with qs2:
        if st.button("🧾 New Consultation", type="primary", use_container_width=True):
            reset_consultation()
            st.session_state.nav_page = "consultation"
            st.rerun()
    with qs3:
        if st.button("📊 View Dashboard", use_container_width=True):
            st.session_state.nav_page = "dashboard"
            st.rerun()


# =====================================================================
# PAGE: CONSULTATION
# =====================================================================
elif current_page == "consultation":

    if st.session_state.is_demo:
        st.info("🧪 **Demo mode** — This is a pre-loaded case for exploration. No real patient data is present. "
                "Click **New Consultation** to start with your own case.")

    render_workflow_stepper()

    # ── Input section ──────────────────────────────────────────────
    if not st.session_state.transcript:
        st.markdown('<div class="section-label">Step 1 — Consultation input</div>', unsafe_allow_html=True)

        col_input, col_exam = st.columns([1.25, 1], gap="large")

        with col_input:
            input_vector: str = st.radio(
                "Input mode",
                ["Text / Paste Transcript", "Live Audio (Microphone)", "File Upload (.wav / .mp3 / .json)"],
                horizontal=False,
                label_visibility="collapsed",
                help="Choose how you want to input the consultation. Text is fastest for existing notes. Microphone records the live room. File upload accepts pre-recorded audio or a JSON dataset.",
            )

            has_valid_input: bool = False
            bypass_stt:      bool = False
            injected_text:   str  = ""

            if "Text" in input_vector:
                injected_text = st.text_area(
                    "Transcript",
                    placeholder="Paste the consultation transcript here. This can include doctor-patient dialogue, dictated notes, or clinical observations…",
                    height=220,
                    label_visibility="collapsed",
                )
                if injected_text.strip():
                    has_valid_input = True
                    bypass_stt = True

            elif "Live Audio" in input_vector:
                if not PYDUB_AVAILABLE:
                    st.warning("Audio processing unavailable on this deployment. Use Text input instead.")
                else:
                    st.caption("Position your device microphone toward the consultation, then tap the record button below.")
                    audio_file = st.audio_input(
                        "Record audio",
                        help="Records room audio for transcription. Ensure informed consent has been obtained before recording any consultation.",
                    )
                    if audio_file is not None:
                        try:
                            with open(TEMP_AUDIO, "wb") as fh:
                                fh.write(audio_file.read())
                            has_valid_input = True
                        except OSError as e:
                            st.error(f"Could not save audio: {e}")
            else:
                uploaded_file = st.file_uploader(
                    "Upload audio or dataset",
                    type=["wav", "mp3", "m4a", "json"],
                    label_visibility="collapsed",
                    help="Upload a pre-recorded consultation audio file, or a JSON dataset for batch exploration.",
                )
                if uploaded_file is not None:
                    if uploaded_file.name.endswith(".json"):
                        try:
                            json_data = json.load(uploaded_file)
                            if isinstance(json_data, list):
                                st.caption(f"Dataset loaded — {len(json_data)} cases")
                                case_idx = int(st.number_input("Case index", min_value=0,
                                                               max_value=max(len(json_data)-1,0), value=0))
                                node = json_data[case_idx]
                                injected_text = node.get("input", node.get("instruction", ""))
                                if injected_text:
                                    st.info(injected_text[:240] + ("…" if len(injected_text) > 240 else ""))
                                if injected_text.strip():
                                    has_valid_input = True
                                    bypass_stt = True
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
                                has_valid_input = True
                            except OSError as e:
                                st.error(f"Could not save file: {e}")

            if not has_valid_input:
                st.markdown("""
                <div class="empty-state" style="padding:20px 0">
                  <div class="empty-state-body">
                    No consultation loaded. Paste a transcript, record audio, or upload a file to begin.<br>
                    <strong>No real patient data?</strong> Use the demo patient to explore all outputs safely.
                  </div>
                </div>""", unsafe_allow_html=True)
                if st.button("🧪 Load Demo Patient instead", key="demo_from_input"):
                    load_demo_patient()
                    st.rerun()

        with col_exam:
            st.markdown('<div class="section-label">Step 2 — Physical examination</div>',
                        unsafe_allow_html=True)
            st.caption("Enter examination findings. Pre-filled defaults are provided — edit only relevant sections.")

            exam_tabs = st.tabs(["Thoracic", "GI / Abdomen", "Neuro / Reflex", "Musculoskeletal"])
            with exam_tabs[0]:
                notes_thoracic: str = st.text_area(
                    "Thoracic",
                    value=DEMO_EXAM["thoracic"] if st.session_state.is_demo else
                          "Cardiovascular: Tachycardic, rhythm regular. S1 and S2 distinct, no audible murmurs, rubs, or gallops. Diaphoresis noted. Respiratory: Tachypneic, shallow. CTAB bilaterally.",
                    height=130, label_visibility="collapsed",
                    help="Record cardiovascular and respiratory findings from auscultation and inspection.",
                )
            with exam_tabs[1]:
                notes_gi: str = st.text_area(
                    "GI",
                    value=DEMO_EXAM["gi"] if st.session_state.is_demo else
                          "Abdomen soft, non-distended. Bowel sounds active x4. No tenderness, guarding, or rebound. No hepatosplenomegaly.",
                    height=130, label_visibility="collapsed",
                    help="Record abdominal inspection, palpation, percussion, and auscultation findings.",
                )
            with exam_tabs[2]:
                notes_neuro: str = st.text_area(
                    "Neuro",
                    value=DEMO_EXAM["neuro"] if st.session_state.is_demo else
                          "Alert and oriented x3. PERRLA. No focal neurological deficits. Gross motor and sensory intact.",
                    height=130, label_visibility="collapsed",
                    help="Record neurological and reflex examination findings including GCS, pupils, and motor function.",
                )
            with exam_tabs[3]:
                notes_msk: str = st.text_area(
                    "MSK",
                    value=DEMO_EXAM["msk"] if st.session_state.is_demo else
                          "No peripheral oedema. Peripheral pulses present bilaterally. Full passive ROM. No joint tenderness.",
                    height=130, label_visibility="collapsed",
                    help="Record musculoskeletal findings including range of motion, joint tenderness, and peripheral circulation.",
                )

        compiled_exam: str = (
            f"- Thoracic: {notes_thoracic or 'Deferred'}\n"
            f"- GI/Abdomen: {notes_gi or 'Deferred'}\n"
            f"- Neuro/Reflex: {notes_neuro or 'Deferred'}\n"
            f"- Musculoskeletal: {notes_msk or 'Deferred'}"
        )

        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        st.markdown('<div class="section-label">Step 3 — Run analysis</div>', unsafe_allow_html=True)

        run_pipeline: bool = False
        if has_valid_input:
            tc, _ = st.columns([1, 2])
            with tc:
                run_pipeline = st.button(
                    "⬡  Analyse Consultation",
                    type="primary",
                    use_container_width=True,
                    help="Runs a two-stage AI pipeline: speech-to-text transcription followed by clinical salience analysis. Takes 30–60 seconds.",
                )
        else:
            st.button("⬡  Analyse Consultation", disabled=True, use_container_width=True,
                      help="Add a transcript or audio recording above to enable analysis.")

        # Pipeline execution
        if has_valid_input and run_pipeline:
            if not GROQ_AVAILABLE and not bypass_stt:
                st.error("Groq SDK not available. Cannot process audio.")
            elif not GENAI_AVAILABLE:
                st.error("google-generativeai SDK not available.")
            elif not groq_api_key and not bypass_stt:
                st.error("Groq API key missing. Open ⚙ Settings to add it.")
            elif not gemini_api_key:
                st.error("Gemini API key missing. Open ⚙ Settings to add it.")
            else:
                t0 = time.time()
                with st.status("Running clinical intelligence pipeline…", expanded=True) as sw:
                    try:
                        raw_text: str = ""
                        if bypass_stt:
                            st.write("✓  Text input ingested")
                            raw_text = injected_text
                        else:
                            if not PYDUB_AVAILABLE:
                                raise RuntimeError("pydub unavailable. Use Text input.")
                            if not os.path.exists(TEMP_AUDIO):
                                raise FileNotFoundError("Audio file not found. Re-upload.")
                            st.write("⬡  Compressing audio…")
                            audio = AudioSegment.from_file(TEMP_AUDIO)
                            audio = audio.set_channels(1).set_frame_rate(16000)
                            audio.export(COMP_AUDIO, format="mp3", bitrate="64k")
                            st.write("⬡  Transcribing via Whisper large-v3…")
                            gc = Groq(api_key=groq_api_key, timeout=60.0)
                            with open(COMP_AUDIO, "rb") as ab:
                                raw_text = gc.audio.transcriptions.create(
                                    file=(COMP_AUDIO, ab.read()),
                                    model="whisper-large-v3",
                                    response_format="text",
                                )
                            for p in (TEMP_AUDIO, COMP_AUDIO):
                                if os.path.exists(p): os.remove(p)
                            st.write("✓  Transcription complete")

                        if not (raw_text or "").strip():
                            raise ValueError("Transcription returned empty text.")

                        st.write("⬡  Running salience analysis via Gemini 2.5 Flash…")
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
                        resp = engine.generate_content(
                            prompt,
                            generation_config={"response_mime_type": "application/json"},
                        )
                        raw_json = resp.text or ""
                        if not raw_json.strip():
                            raise ValueError("Gemini returned empty response.")
                        try:
                            parsed = json.loads(raw_json, strict=False)
                        except json.JSONDecodeError as je:
                            raise ValueError(f"Invalid JSON from Gemini: {je}") from je

                        st.session_state.transcript              = str(parsed.get("cleaned_transcript", ""))
                        st.session_state.classification          = dict(parsed.get("classification", {}))
                        st.session_state.salience_map            = list(parsed.get("salience_weight_map", []))
                        st.session_state.soap_note               = str(parsed.get("structured_soap_chart", ""))
                        st.session_state.flags                   = list(parsed.get("clinical_safety_red_flags", []))
                        st.session_state.next_steps              = list(parsed.get("suggested_next_steps", []))
                        st.session_state.pipeline_execution_time = round(time.time() - t0, 2)
                        st.session_state.chart_locked            = False
                        st.session_state.is_demo                 = False

                        st.write("✓  Pipeline complete")
                        sw.update(label=f"Analysis complete — {st.session_state.pipeline_execution_time}s",
                                  state="complete", expanded=False)
                        st.rerun()

                    except Exception as err:
                        sw.update(label="Pipeline error", state="error", expanded=True)
                        st.error(f"**Pipeline failed:** {err}")

    # ── Output section ─────────────────────────────────────────────
    if st.session_state.transcript:
        classification = st.session_state.classification
        urgency  = str(classification.get("urgency_tier", "MEDIUM")).upper()
        trigger  = str(classification.get("primary_clinical_trigger", ""))
        elapsed  = st.session_state.pipeline_execution_time
        n_sig    = len(st.session_state.salience_map)
        n_flag   = len(st.session_state.flags)
        if urgency not in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
            urgency = "MEDIUM"

        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        st.markdown('<div class="section-label">Steps 4–6 — Review, document & sign</div>',
                    unsafe_allow_html=True)

        st.markdown(f"""
        <div class="urgency-bar {urgency}">
          <div>
            <div class="urgency-label">{urgency} Priority</div>
            <div class="urgency-text">{trigger}</div>
          </div>
          <div class="urgency-metrics">
            <span class="metric-chip"><span class="chip-label">Signals</span>{n_sig}</span>
            <span class="metric-chip"><span class="chip-label">Flags</span>{n_flag}</span>
            <span class="metric-chip"><span class="chip-label">Time</span>{elapsed}s</span>
          </div>
        </div>
        """, unsafe_allow_html=True)

        output_tabs = st.tabs([
            "Clinical Signals",
            "Safety Flags",
            "Next Steps",
            "SOAP Note",
            "Explainability",
        ])

        with output_tabs[0]:
            st.caption("Ranked by clinical salience score. Higher scores indicate greater clinical significance. "
                       "Review top signals first — they drove the urgency classification.")
            render_signal_list(st.session_state.salience_map, show_reasoning=False)

        with output_tabs[1]:
            st.caption("Items requiring immediate clinical attention or verification before sign-off.")
            if st.session_state.flags:
                for alert in st.session_state.flags:
                    st.markdown(f'<div class="flag-item"><div style="flex-shrink:0;margin-top:1px">⚑</div><div>{alert}</div></div>',
                                unsafe_allow_html=True)
            else:
                st.markdown("""
                <div class="empty-state">
                  <div class="empty-state-icon">✓</div>
                  <div class="empty-state-title">No safety flags raised</div>
                  <div class="empty-state-body">All clinical safety parameters cleared for this consultation. Proceed with standard clinical judgment.</div>
                </div>""", unsafe_allow_html=True)

        with output_tabs[2]:
            st.caption("Evidence-based next steps extracted from the clinical context. Verify against local protocols before acting.")
            if st.session_state.next_steps:
                for idx, step in enumerate(st.session_state.next_steps, 1):
                    st.markdown(f'<div class="step-item"><div class="step-num">{idx}</div><div>{step}</div></div>',
                                unsafe_allow_html=True)
            else:
                st.markdown('<div class="empty-state"><div class="empty-state-title">No next steps generated</div></div>',
                            unsafe_allow_html=True)

        with output_tabs[3]:
            soap_raw = st.session_state.soap_note
            chart_locked = st.session_state.chart_locked
            status_lbl   = "Signed & Locked" if chart_locked else "Pending Review"
            status_col   = "var(--accent-violet)" if chart_locked else "var(--accent-amber)"

            st.markdown(f"""
            <div class="soap-meta-row">
              <div class="soap-meta-item"><span class="soap-meta-label">Generated</span><span class="soap-meta-value">{datetime.now().strftime('%Y-%m-%d %H:%M')}</span></div>
              <div class="soap-meta-item"><span class="soap-meta-label">Specialty</span><span class="soap-meta-value">{specialty_profile}</span></div>
              <div class="soap-meta-item"><span class="soap-meta-label">Status</span><span class="soap-meta-value" style="color:{status_col}">{status_lbl}</span></div>
              <div class="soap-meta-item"><span class="soap-meta-label">Patient ref</span><span class="soap-meta-value">{st.session_state.patient_ref or '—'}</span></div>
            </div>
            """, unsafe_allow_html=True)

            if not chart_locked:
                st.caption("⚠️ **Review and amend this note before signing.** "
                           "This is an AI-generated draft — you are responsible for its clinical accuracy.")
                edited_soap = st.text_area(
                    "SOAP Note",
                    value=soap_raw,
                    height=440,
                    key="soap_editor",
                    label_visibility="collapsed",
                    help="Edit this note as you would any clinical document. Add, remove, or correct any information before signing.",
                )
            else:
                edited_soap = soap_raw
                render_soap_html(soap_raw)

            st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
            a1, a2, a3, a4 = st.columns(4)

            with a1:
                st.button("⎘ Copy", key="copy_btn", use_container_width=True,
                          help="Select all text in the editor above and copy.")
            with a2:
                if soap_raw.strip() and FPDF_AVAILABLE:
                    try:
                        pdf_bytes = generate_clinical_pdf(
                            edited_soap if not chart_locked else soap_raw,
                            specialty_profile,
                        )
                        st.download_button(
                            "↓ Export PDF", data=pdf_bytes,
                            file_name=f"SalienceOS_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                            mime="application/pdf", use_container_width=True,
                            help="Download a formatted clinical PDF of this SOAP note.",
                        )
                    except Exception as e:
                        st.error(f"PDF error: {e}")
                else:
                    st.button("↓ Export PDF", disabled=True, use_container_width=True)
            with a3:
                if st.button("📄 Reports", use_container_width=True,
                             help="Go to the Reports page to generate clinical and pharmacy reports."):
                    st.session_state.nav_page = "reports"
                    st.rerun()
            with a4:
                if chart_locked:
                    st.button("✓ Synced to FHIR", disabled=True, use_container_width=True)
                else:
                    if st.button("Sign & Push to EHR", type="primary", use_container_width=True,
                                 help="Digitally sign this note and push to the simulated EHR/FHIR endpoint. This action locks the note."):
                        st.session_state.soap_note = edited_soap if not chart_locked else soap_raw
                        with st.spinner("Synchronising with HL7/FHIR endpoint…"):
                            time.sleep(2.0)
                        st.session_state.chart_locked = True
                        save_to_history()
                        st.success("Chart signed and pushed to EHR. Consultation saved to dashboard.")
                        st.balloons()
                        st.rerun()

        with output_tabs[4]:
            st.caption("This tab explains why each signal was assigned its salience score. "
                       "Use this to audit the AI's reasoning before signing.")
            render_signal_list(st.session_state.salience_map, show_reasoning=True)

        # New consultation button
        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
        nc1, _ = st.columns([1, 3])
        with nc1:
            if st.button("↩ New Consultation", use_container_width=True):
                reset_consultation()
                st.rerun()


# =====================================================================
# PAGE: DASHBOARD
# =====================================================================
elif current_page == "dashboard":
    st.markdown('<div class="section-label">Patient consultation history</div>',
                unsafe_allow_html=True)
    st.caption("Sessions are stored in memory for this browser session only. "
               "Refresh clears the history. For persistent storage, export reports.")

    history = st.session_state.consultation_history

    if not history:
        st.markdown("""
        <div class="empty-state">
          <div class="empty-state-icon">📊</div>
          <div class="empty-state-title">No consultations logged yet</div>
          <div class="empty-state-body">
            Complete and sign a consultation to log it here.<br>
            The dashboard tracks all consultations from this session, including urgency tiers, signal counts, and SOAP note history.
          </div>
        </div>""", unsafe_allow_html=True)

        dc1, dc2 = st.columns([1, 1])
        with dc1:
            if st.button("🧪 Load Demo Patient", use_container_width=True, key="dash_demo"):
                load_demo_patient()
                st.session_state.nav_page = "consultation"
                st.rerun()
        with dc2:
            if st.button("🧾 Start Consultation", type="primary", use_container_width=True):
                st.session_state.nav_page = "consultation"
                st.rerun()
    else:
        # Summary metrics
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total consultations", len(history))
        critical_count = sum(1 for h in history if h.get("urgency") == "CRITICAL")
        m2.metric("Critical urgency", critical_count)
        total_signals  = sum(h.get("n_signals", 0) for h in history)
        m3.metric("Total signals extracted", total_signals)
        total_flags    = sum(h.get("n_flags", 0) for h in history)
        m4.metric("Total safety flags", total_flags)

        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
        st.markdown('<div class="section-label">Consultation log</div>', unsafe_allow_html=True)

        for i, entry in enumerate(reversed(history)):
            urgency_color = {
                "CRITICAL": "#EF4444", "HIGH": "#F59E0B",
                "MEDIUM": "#3B82F6",   "LOW":  "#10B981",
            }.get(entry.get("urgency", ""), "#7E8A9A")
            demo_tag = " · 🧪 Demo" if entry.get("is_demo") else ""

            st.markdown(f"""
            <div class="dash-card">
              <div class="dash-card-header">
                <div class="dash-card-title">{entry.get('patient_ref','Unnamed')}{demo_tag}</div>
                <div class="dash-card-meta">{entry.get('timestamp','')}</div>
              </div>
              <div style="display:flex;gap:12px;margin-bottom:6px;align-items:center">
                <span style="font-size:10px;font-weight:700;letter-spacing:.8px;text-transform:uppercase;color:{urgency_color}">
                  {entry.get('urgency','—')}
                </span>
                <span style="font-size:11px;color:var(--text-muted)">{entry.get('specialty','')}</span>
                <span style="font-size:11px;color:var(--text-muted)">
                  {entry.get('n_signals',0)} signals · {entry.get('n_flags',0)} flags
                </span>
              </div>
              <div class="dash-card-body">{entry.get('trigger','')}</div>
            </div>
            """, unsafe_allow_html=True)

            with st.expander(f"View SOAP note — {entry.get('patient_ref','Unnamed')} ({entry.get('timestamp','')})"):
                render_soap_html(entry.get("soap_note", "No SOAP note saved."))

        if st.button("Clear session history", key="clear_history"):
            st.session_state.consultation_history = []
            st.rerun()


# =====================================================================
# PAGE: REPORTS
# =====================================================================
elif current_page == "reports":
    st.markdown('<div class="section-label">Report generation</div>', unsafe_allow_html=True)

    if not st.session_state.transcript:
        st.markdown("""
        <div class="empty-state">
          <div class="empty-state-icon">📄</div>
          <div class="empty-state-title">No active consultation</div>
          <div class="empty-state-body">
            No consultation is currently loaded. Start a new consultation, load the demo patient, or complete an analysis before generating reports.
          </div>
        </div>""", unsafe_allow_html=True)
        rc1, rc2 = st.columns([1, 1])
        with rc1:
            if st.button("🧪 Load Demo Patient", use_container_width=True, key="rep_demo"):
                load_demo_patient()
                st.rerun()
        with rc2:
            if st.button("🧾 Go to Consultation", type="primary", use_container_width=True):
                st.session_state.nav_page = "consultation"
                st.rerun()
    else:
        soap_raw     = st.session_state.soap_note
        salience_map = st.session_state.salience_map

        rep_tab1, rep_tab2, rep_tab3 = st.tabs([
            "Clinical Report", "Pharmacy Report", "Patient History Insight",
        ])

        # ── Clinical report ────────────────────────────────────────
        with rep_tab1:
            st.caption("Full clinical report for the treating physician — includes SOAP note, signals, flags, and next steps.")

            urgency = st.session_state.classification.get("urgency_tier", "—")
            trigger = st.session_state.classification.get("primary_clinical_trigger", "")

            clinical_report = f"""### Clinical Intelligence Report
**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}
**Specialty:** {specialty_profile}
**Patient Ref:** {st.session_state.patient_ref or 'Not specified'}
**Urgency:** {urgency}

### Primary Clinical Trigger
{trigger}

### Clinical Safety Flags
{chr(10).join(f'- {f}' for f in st.session_state.flags) or 'None raised.'}

### Top Clinical Signals
{chr(10).join(f'- {item["entity"]} ({int(item["salience_score"]*100)}%) — {item["reasoning_context"]}' for item in sorted(salience_map, key=lambda x: x.get("salience_score",0), reverse=True)[:5])}

### Suggested Next Steps
{chr(10).join(f'- {s}' for s in st.session_state.next_steps) or 'None generated.'}

### SOAP Note
{soap_raw}

---
*Report generated by SALIENCE OS. Final clinical judgment remains the responsibility of the treating clinician.*"""

            render_soap_html(clinical_report)
            st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

            if FPDF_AVAILABLE and soap_raw.strip():
                try:
                    pdf_bytes = generate_clinical_pdf(clinical_report, specialty_profile, "clinical")
                    st.download_button(
                        "↓ Download Clinical Report PDF",
                        data=pdf_bytes,
                        file_name=f"SalienceOS_Clinical_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                        mime="application/pdf",
                        use_container_width=True,
                    )
                except Exception as e:
                    st.error(f"PDF error: {e}")

        # ── Pharmacy report ────────────────────────────────────────
        with rep_tab2:
            st.caption("Medication-focused summary for pharmacy or external referral. "
                       "Contains medication mentions, dosing context, and relevant clinical flags.")

            pharmacy_text = generate_pharmacy_report(salience_map, soap_raw, specialty_profile)
            render_soap_html(pharmacy_text)
            st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

            if FPDF_AVAILABLE:
                try:
                    pdf_bytes = generate_clinical_pdf(pharmacy_text, specialty_profile, "pharmacy")
                    st.download_button(
                        "↓ Download Pharmacy Report PDF",
                        data=pdf_bytes,
                        file_name=f"SalienceOS_Pharmacy_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                        mime="application/pdf",
                        use_container_width=True,
                    )
                except Exception as e:
                    st.error(f"PDF error: {e}")

        # ── Patient history insight ────────────────────────────────
        with rep_tab3:
            st.caption("Longitudinal patient intelligence — synthesises all consultations from this session "
                       "to surface clinical trajectories, evolving symptoms, and risk progression.")

            history = st.session_state.consultation_history
            if not history and not st.session_state.transcript:
                st.markdown("""
                <div class="empty-state">
                  <div class="empty-state-title">No consultation history available</div>
                  <div class="empty-state-body">Complete and sign at least one consultation to generate a patient history insight.</div>
                </div>""", unsafe_allow_html=True)
            else:
                all_entries = history.copy()
                if st.session_state.transcript:
                    all_entries.append({
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M") + " (current)",
                        "patient_ref": st.session_state.patient_ref or "Current",
                        "urgency": st.session_state.classification.get("urgency_tier", "—"),
                        "trigger": st.session_state.classification.get("primary_clinical_trigger", ""),
                        "n_signals": len(salience_map),
                        "n_flags": len(st.session_state.flags),
                        "soap_note": soap_raw,
                        "is_demo": st.session_state.is_demo,
                    })

                insight_lines = ["### Patient Clinical Memory Card\n"]
                insight_lines.append(f"**Total consultations in session:** {len(all_entries)}\n")

                for entry in all_entries:
                    insight_lines.append(f"### {entry.get('timestamp','')} — {entry.get('patient_ref','')}")
                    insight_lines.append(f"**Urgency:** {entry.get('urgency','—')}")
                    insight_lines.append(f"**Clinical trigger:** {entry.get('trigger','')}")
                    insight_lines.append(f"Signals: {entry.get('n_signals',0)} · Flags: {entry.get('n_flags',0)}\n")

                insight_lines.append("\n---\n")
                insight_lines.append("*This summary was generated by SALIENCE OS from session data. "
                                     "Verify accuracy before clinical use.*")

                render_soap_html("\n".join(insight_lines))

                if FPDF_AVAILABLE:
                    try:
                        pdf_bytes = generate_clinical_pdf(
                            "\n".join(insight_lines), specialty_profile, "clinical"
                        )
                        st.download_button(
                            "↓ Download Patient History PDF",
                            data=pdf_bytes,
                            file_name=f"SalienceOS_History_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                            mime="application/pdf",
                            use_container_width=True,
                        )
                    except Exception as e:
                        st.error(f"PDF error: {e}")


# =====================================================================
# PAGE: HELP
# =====================================================================
elif current_page == "help":
    st.markdown('<div class="section-label">Clinical reference guide</div>', unsafe_allow_html=True)
    st.caption("Everything you need to understand, trust, and verify Salience OS outputs.")

    help_items = [
        ("What is Salience Scoring?",
         "Salience scoring measures the clinical importance of each entity extracted from a consultation transcript. "
         "Scores range from 0 to 1 (displayed as 0–100%). A score of 85%+ indicates high clinical significance — "
         "these entities typically drove the urgency classification. Scores below 50% may represent background "
         "noise or incidental mentions with low immediate relevance."),

        ("What are Clinical Signals?",
         "Clinical signals are structured entities extracted from the transcript: symptoms, medications, diagnoses, "
         "durations, and risk factors. Each is categorised, scored, and explained. The Clinical Signals tab shows "
         "them ranked by importance — always review the top 3–5 signals before accepting the urgency classification."),

        ("What are Safety Flags?",
         "Safety flags are specific warnings generated by the AI when it detects patterns requiring immediate "
         "clinical attention: time-sensitive interventions, drug interactions, contraindications, or haemodynamic "
         "risk signals. These must be reviewed and either acted upon or explicitly dismissed by the clinician."),

        ("How are SOAP notes generated?",
         "SOAP notes are generated by Gemini 2.5 Flash using the cleaned transcript and physical examination "
         "findings as input. The Subjective section draws only from entities with a salience score ≥0.50. "
         "The Objective section incorporates examination findings. Assessment and Plan are inferred from the "
         "full clinical picture. You must review and amend the note before signing — the AI draft is a starting "
         "point, not a final document."),

        ("What must I verify before signing?",
         "Before signing the SOAP note, verify: (1) patient identifiers are correct, (2) medications and doses "
         "are accurate, (3) the assessment reflects your clinical judgment, (4) the plan aligns with local "
         "protocols, (5) all safety flags have been addressed or documented as reviewed. The AI may miss "
         "context that only the treating clinician possesses."),

        ("What is a Pharmacy Report?",
         "The Pharmacy Report extracts medication-relevant information from the analysis: drugs mentioned, "
         "dosing context, potential interactions flagged, and prescribing guidance. It is formatted for "
         "external communication with pharmacy teams. It does not replace a formal prescription — "
         "prescribing authority remains with the treating clinician."),

        ("How does the Patient Dashboard work?",
         "The dashboard logs all consultations completed and signed during the current browser session. "
         "It is session-based — clearing the browser or refreshing clears the history. For persistent "
         "patient records, export PDF reports and store them in your clinical system. The dashboard is "
         "designed as a session-level reference, not a long-term EHR."),

        ("What data does Salience OS send to external APIs?",
         "Consultation transcripts and examination findings are sent to Groq (for speech-to-text) and "
         "Google Gemini (for clinical analysis). Do not use real patient identifiers unless your institution "
         "has approved these API providers for clinical data processing. The demo patient contains no real "
         "patient data and is safe for unrestricted use."),
    ]

    for title, body in help_items:
        with st.expander(title):
            st.markdown(body)

    st.divider()
    st.markdown('<div class="section-label">Keyboard shortcuts</div>', unsafe_allow_html=True)
    st.markdown("""
    | Action | Shortcut |
    |---|---|
    | Submit text input | `Ctrl + Enter` |
    | Navigate tabs | `Arrow keys` when tab is focused |
    | Scroll output | `Page Up / Page Down` |
    """)

    st.divider()
    st.markdown('<div class="section-label">Version information</div>', unsafe_allow_html=True)
    vi1, vi2, vi3 = st.columns(3)
    vi1.metric("Platform", "Salience OS")
    vi2.metric("STT model", "Whisper large-v3")
    vi3.metric("Reasoning model", "Gemini 2.5 Flash")


# =====================================================================
# CLINICAL DISCLAIMER FOOTER
# =====================================================================
st.markdown("""
<div class="clinical-disclaimer">
  ⬡ &nbsp; <strong>SALIENCE OS</strong> is a clinical decision-support and documentation tool.
  Final clinical judgment, diagnosis, and prescribing authority remain the sole responsibility of the
  licensed healthcare professional. AI-generated outputs must be reviewed and verified before clinical use.
</div>
""", unsafe_allow_html=True)
