# =====================================================================
# SALIENCE OS — Clinical Intelligence Workspace
# Production build — Python 3.12 / Streamlit Cloud
# Onboarding Pass: Welcome panel, workflow guide, tooltips,
#   sample case, help drawer, disclaimer, actionable empty states
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


# =====================================================================
# DEMO PATIENT DATA  (Goal 5 — Sample Case)
# A realistic cardiology consultation used as a safe demo.
# =====================================================================
DEMO_TRANSCRIPT = """Patient is a 58-year-old male presenting with a 3-hour history of central crushing chest pain radiating to the left jaw and left arm, rated 8 out of 10 in severity. Associated symptoms include profuse diaphoresis, nausea without vomiting, and significant shortness of breath on exertion. The patient reports the pain began while climbing stairs at home and has not resolved with rest. He has a background history of hypertension for 12 years, type 2 diabetes mellitus for 8 years, and hypercholesterolaemia. He is a current smoker with a 30 pack-year history. Current medications include metformin 1g twice daily, amlodipine 10mg once daily, and atorvastatin 40mg once daily. He denies any recent trauma, fever, or productive cough. No family history of sudden cardiac death. He has never had a previous cardiac event."""

DEMO_THORACIC = "Cardiovascular: Tachycardic at 108 bpm, rhythm regular. S1 and S2 present, no audible murmurs, rubs, or gallops. Significant chest wall diaphoresis noted; patient actively clutching retrosternal area. Respiratory: Tachypneic at 22 breaths/min, shallow respirations. Lungs clear to auscultation bilaterally (CTAB) with no wheezing, rales, or rhonchi."
DEMO_ABDOMINAL = "Abdomen soft, symmetric, and non-distended. Bowel sounds active in all 4 quadrants. No localized tenderness, guarding, or rebound to light/deep palpation. No hepatosplenomegaly. Epigastric region non-tender."
DEMO_NEURO = "Patient alert and oriented to person, place, and time (A&Ox3). Pupils equal, round, and reactive to light (PEERRLA). No focal neurological deficits. Mild anxiety noted. GCS 15/15."
DEMO_ORTHO = "No peripheral oedema. Left shoulder passive range of motion intact. Left mandibular jaw — no tenderness on palpation. No musculoskeletal abnormalities of clinical significance."

DEMO_SALIENCE_MAP = [
    {"entity": "Central crushing chest pain", "category": "Symptom", "salience_score": 0.98, "reasoning_context": "Cardinal symptom of ACS. Retrosternal, crushing quality with radiation to left jaw and arm — classic STEMI/NSTEMI presentation requiring immediate workup."},
    {"entity": "Radiation to left jaw and arm", "category": "Symptom", "salience_score": 0.95, "reasoning_context": "Left-sided radiation pattern is highly specific for myocardial ischaemia. Increases pre-test probability of ACS significantly."},
    {"entity": "Profuse diaphoresis", "category": "Symptom", "salience_score": 0.91, "reasoning_context": "Autonomic activation accompanying acute myocardial ischaemia. Strong predictor of major cardiac event in chest pain presentations."},
    {"entity": "3-hour symptom duration", "category": "Duration", "salience_score": 0.88, "reasoning_context": "Time-critical window for reperfusion therapy. Door-to-balloon time targets apply. Informs thrombolysis eligibility."},
    {"entity": "Hypertension (12 years)", "category": "Medical History", "salience_score": 0.82, "reasoning_context": "Major modifiable cardiac risk factor. Contributes to atherosclerotic burden and left ventricular hypertrophy risk."},
    {"entity": "Type 2 diabetes mellitus", "category": "Medical History", "salience_score": 0.79, "reasoning_context": "Independent cardiovascular risk multiplier. Diabetic patients may present with atypical ACS symptoms. Influences antiplatelet and reperfusion choices."},
    {"entity": "Active smoking (30 pack-years)", "category": "Medical History", "salience_score": 0.76, "reasoning_context": "Significant atherosclerotic risk factor. Smoking cessation must be addressed in management plan."},
    {"entity": "Tachycardia 108 bpm", "category": "Symptom", "salience_score": 0.74, "reasoning_context": "Haemodynamic response to ischaemic pain and autonomic activation. Monitor for progression to arrhythmia."},
    {"entity": "Shortness of breath on exertion", "category": "Symptom", "salience_score": 0.68, "reasoning_context": "Suggests reduced left ventricular function or early pulmonary oedema. Requires echo assessment."},
    {"entity": "Atorvastatin 40mg", "category": "Medication", "salience_score": 0.55, "reasoning_context": "Current statin therapy. Consider dose escalation to high-intensity statin (80mg) post-ACS per NICE guidelines."},
]

DEMO_FLAGS = [
    "STEMI equivalent presentation — immediate 12-lead ECG and cardiology review required.",
    "Symptom duration exceeds 3 hours — reperfusion window narrowing. Assess for primary PCI eligibility.",
    "Diabetic patient: atypical presentation possible — maintain high index of suspicion despite pain severity.",
    "Current smoker: increased thrombotic risk — dual antiplatelet therapy considerations apply.",
]

DEMO_NEXT_STEPS = [
    "Obtain immediate 12-lead ECG and continuous cardiac monitoring.",
    "Urgent troponin I/T, FBC, U&E, LFTs, coagulation screen, and group & save.",
    "Chest X-ray (portable if haemodynamically unstable).",
    "Aspirin 300mg loading dose stat (unless contraindicated); consider P2Y12 inhibitor.",
    "Refer urgently to cardiology / activate PPCI pathway if STEMI confirmed on ECG.",
    "IV access × 2, IV morphine for pain, IV antiemetic, supplemental O2 if SpO2 < 94%.",
    "Bedside echocardiogram to assess wall motion and ejection fraction.",
    "Reassess blood glucose and review metformin — hold peri-procedure.",
]

DEMO_SOAP = """### Subjective
**Chief Complaint:** Central crushing chest pain, 8/10 severity, 3-hour duration.

**History of Presenting Illness:** Mr. [DEMO] is a 58-year-old male presenting to the emergency department with a 3-hour history of central crushing chest pain. The pain radiates to the left jaw and left arm. It commenced during exertion (stair climbing) and has not resolved with rest. He reports associated profuse diaphoresis, nausea, and shortness of breath on exertion. Pain onset was sudden with no preceding trauma or illness.

**Past Medical History:** Hypertension (12 years), Type 2 Diabetes Mellitus (8 years), Hypercholesterolaemia.

**Medications:** Metformin 1g BD, Amlodipine 10mg OD, Atorvastatin 40mg OD.

**Social History:** Active smoker, 30 pack-year history. Independent functional status prior to today.

**Allergies:** Not recorded — to be clarified.

### Objective
**Vital Signs:** HR 108 bpm (tachycardic), RR 22/min (tachypnoeic). Temperature and BP not recorded in transcript — obtain urgently.

**Cardiovascular:** S1/S2 present, no murmurs. Diaphoresis noted. Clutching retrosternal area.

**Respiratory:** CTAB. No wheeze or crepitations.

**Abdomen:** Soft, non-tender, non-distended. Bowel sounds present.

**Neurological:** GCS 15/15. A&Ox3. No focal deficits.

**MSK:** No peripheral oedema. Left shoulder and jaw — full passive ROM, non-tender.

### Assessment
**Primary Differential:** Acute Coronary Syndrome — STEMI or NSTEMI pending ECG and troponin results. Presentation is high-probability ACS based on symptom quality, radiation pattern, associated diaphoresis, cardiovascular risk factor burden, and exertional onset.

**Urgency Tier:** CRITICAL — time-sensitive reperfusion window.

**Risk Stratification:** High-risk. TIMI/GRACE score to be calculated on arrival of bloods. Multiple major risk factors present (DM, HTN, hypercholesterolaemia, active smoking).

### Plan
1. Immediate 12-lead ECG and continuous cardiac monitoring.
2. Urgent bloods: Troponin, FBC, U&E, LFTs, glucose, coagulation, G&S.
3. Aspirin 300mg loading dose stat (confirm no contraindications).
4. Activate PPCI pathway if STEMI pattern on ECG — door-to-balloon target 90 minutes.
5. IV access, IV morphine 2.5–5mg titrated, IV antiemetic, O2 if SpO2 < 94%.
6. Portable CXR.
7. Urgent cardiology referral.
8. Hold metformin pending renal function and procedure planning.
9. High-intensity statin (atorvastatin 80mg) post-stabilisation per NICE ACS guidelines.
10. Smoking cessation counselling and referral at appropriate stage of admission."""

DEMO_CLASSIFICATION = {
    "urgency_tier": "CRITICAL",
    "primary_clinical_trigger": "High-probability ACS in a 58-year-old male with 3 hours of crushing chest pain, radiation to jaw/arm, diaphoresis, and multiple cardiac risk factors.",
}


# =====================================================================
# PDF GENERATION
# =====================================================================
def sanitize_for_pdf(text: str) -> str:
    if not text:
        return ""
    for uc, sc in {
        "•": "-", "—": "-", "–": "-",
        "\u201c": '"', "\u201d": '"',
        "\u2018": "'", "\u2019": "'",
        "™": "TM", "©": "(c)", "®": "(r)",
    }.items():
        text = text.replace(uc, sc)
    return text.encode("latin-1", errors="replace").decode("latin-1")


def generate_clinical_pdf(soap_text: str, specialty: str) -> bytes:
    if not FPDF_AVAILABLE:
        raise RuntimeError("fpdf2 is not installed.")
    pdf = FPDF()
    pdf.set_margins(left=15, top=10, right=15)
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_fill_color(2, 132, 199)
    pdf.rect(0, 0, 210, 38, "F")
    pdf.set_xy(0, 8)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(210, 12, "SALIENCE OS | CLINICAL NOTE MATRIX",
             new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.set_font("Helvetica", "I", 10)
    pdf.cell(210, 5,
             sanitize_for_pdf(f"Specialty: {specialty} | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"),
             new_x="LMARGIN", new_y="NEXT", align="C")
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
            pdf.set_text_color(2, 132, 199)
            pdf.cell(ew, 10, sanitize_for_pdf(lc.replace("###", "").replace(":", "").strip().upper()),
                     new_x="LMARGIN", new_y="NEXT")
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
    "transcript": "",
    "classification": {},
    "salience_map": [],
    "soap_note": "",
    "flags": [],
    "next_steps": [],
    "pipeline_execution_time": 0.0,
    "chart_locked": False,
    "sc_specialty": "Cardiology",
    "sc_language": "Mixed",
    "sc_theme": "Dark",
    "_groq_override": "",
    "_gemini_override": "",
    # Onboarding state
    "onboarding_dismissed": False,
    "demo_thoracic": DEMO_THORACIC,
    "demo_abdominal": DEMO_ABDOMINAL,
    "demo_neuro": DEMO_NEURO,
    "demo_ortho": DEMO_ORTHO,
    "demo_loaded": False,
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
    _has_vault_groq   = False
    _has_vault_gemini = False
    _vault_groq       = ""
    _vault_gemini     = ""


# =====================================================================
# CSS — extended with onboarding component styles
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
  --radius-sm: 5px;
  --radius-md: 9px;
  --radius-lg: 14px;
  --font-mono: 'JetBrains Mono','Fira Code','SF Mono',ui-monospace,monospace;
  --transition: 150ms cubic-bezier(0.4,0,0.2,1);
  --soap-font-size: 14px;
  --soap-line-height: 1.9;
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
  padding-top: 12px !important;
  padding-left: 16px !important;
  padding-right: 16px !important;
  padding-bottom: 80px !important;
  max-width: 100% !important;
}
::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border-default); border-radius: 99px; }

/* ── Header ── */
.os-header {
  display:flex; align-items:center; justify-content:space-between;
  padding:10px 0 14px; border-bottom:1px solid var(--border-subtle); margin-bottom:20px;
}
.os-wordmark { font-size:15px; font-weight:700; letter-spacing:.3px; color:var(--text-primary); }
.os-wordmark span { color:var(--accent-blue); }
.os-header-meta { display:flex; align-items:center; gap:12px; }
.os-status-pill {
  display:inline-flex; align-items:center; gap:5px;
  font-size:11px; font-weight:500; padding:3px 10px;
  border-radius:99px; letter-spacing:.2px;
}
.os-status-pill.ready  { background:rgba(16,185,129,.10); color:var(--accent-emerald); border:1px solid rgba(16,185,129,.18); }
.os-status-pill.active { background:rgba(59,130,246,.10); color:var(--accent-blue);    border:1px solid rgba(59,130,246,.18); }
.os-status-pill.locked { background:rgba(139,92,246,.10); color:var(--accent-violet);  border:1px solid rgba(139,92,246,.18); }
.os-dot { width:5px; height:5px; border-radius:50%; background:currentColor; }
.os-dot.pulse { animation:pulse-dot 2s ease-in-out infinite; }
@keyframes pulse-dot { 0%,100%{opacity:1;transform:scale(1)} 50%{opacity:.4;transform:scale(.75)} }
.os-time { font-size:11px; font-family:var(--font-mono); color:var(--text-muted); font-variant-numeric:tabular-nums; }

/* ── Welcome panel ── */
.welcome-panel {
  background: linear-gradient(135deg, rgba(59,130,246,0.06) 0%, rgba(139,92,246,0.04) 100%);
  border: 1px solid rgba(59,130,246,0.18);
  border-radius: var(--radius-lg);
  padding: 24px 28px 20px;
  margin-bottom: 20px;
  position: relative;
}
.welcome-title {
  font-size: 15px; font-weight: 700; color: var(--text-primary);
  margin-bottom: 4px; letter-spacing: -0.2px;
}
.welcome-subtitle {
  font-size: 12.5px; color: var(--text-secondary); margin-bottom: 18px; line-height: 1.6;
}
.welcome-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}
.welcome-card {
  background: var(--bg-elevated);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  padding: 12px 14px;
}
.welcome-card-icon { font-size: 16px; margin-bottom: 6px; }
.welcome-card-title {
  font-size: 10.5px; font-weight: 700; letter-spacing: 0.5px;
  text-transform: uppercase; color: var(--text-muted); margin-bottom: 4px;
}
.welcome-card-body { font-size: 12px; color: var(--text-secondary); line-height: 1.55; }

/* ── Workflow steps ── */
.workflow-strip {
  display: flex;
  align-items: center;
  gap: 0;
  padding: 14px 18px;
  background: var(--bg-elevated);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  margin-bottom: 20px;
  overflow-x: auto;
  flex-wrap: nowrap;
}
.workflow-step {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
  white-space: nowrap;
}
.workflow-step-num {
  width: 22px; height: 22px; border-radius: 50%;
  background: var(--bg-surface);
  border: 1.5px solid var(--border-default);
  color: var(--text-muted);
  font-size: 10px; font-weight: 700;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.workflow-step-num.done {
  background: rgba(16,185,129,0.12);
  border-color: var(--accent-emerald);
  color: var(--accent-emerald);
}
.workflow-step-num.active {
  background: rgba(59,130,246,0.14);
  border-color: var(--accent-blue);
  color: var(--accent-blue);
}
.workflow-step-label {
  font-size: 11.5px; font-weight: 500; color: var(--text-secondary);
}
.workflow-step-label.active { color: var(--accent-blue); font-weight: 600; }
.workflow-step-label.done { color: var(--accent-emerald); }
.workflow-arrow {
  color: var(--text-muted); font-size: 11px;
  margin: 0 8px; flex-shrink: 0;
}

/* ── Section label ── */
.section-label {
  font-size:10px; font-weight:700; letter-spacing:1px;
  text-transform:uppercase; color:var(--text-muted);
  margin:0 0 12px; display:flex; align-items:center; gap:10px;
}
.section-label::after { content:''; flex:1; height:1px; background:var(--border-subtle); }

/* ── Urgency banner ── */
.urgency-bar {
  display:flex; align-items:center; gap:12px;
  padding:13px 18px; border-radius:var(--radius-md);
  margin-bottom:20px; border-left:3px solid;
}
.urgency-bar.CRITICAL { background:rgba(239,68,68,.07);  border-color:var(--tier-critical); }
.urgency-bar.HIGH     { background:rgba(245,158,11,.07); border-color:var(--tier-high); }
.urgency-bar.MEDIUM   { background:rgba(59,130,246,.07); border-color:var(--tier-medium); }
.urgency-bar.LOW      { background:rgba(16,185,129,.07); border-color:var(--tier-low); }
.urgency-label { font-size:9.5px; font-weight:700; letter-spacing:1.1px; text-transform:uppercase; opacity:.65; }
.urgency-text  { font-size:13px; font-weight:500; line-height:1.45; margin-top:2px; }
.urgency-bar.CRITICAL .urgency-label,.urgency-bar.CRITICAL .urgency-text { color:var(--tier-critical); }
.urgency-bar.HIGH     .urgency-label,.urgency-bar.HIGH     .urgency-text { color:var(--tier-high); }
.urgency-bar.MEDIUM   .urgency-label,.urgency-bar.MEDIUM   .urgency-text { color:var(--tier-medium); }
.urgency-bar.LOW      .urgency-label,.urgency-bar.LOW      .urgency-text { color:var(--tier-low); }
.urgency-metrics { margin-left:auto; display:flex; gap:8px; flex-shrink:0; }
.metric-chip {
  display:inline-flex; align-items:center; gap:4px;
  padding:3px 9px; background:var(--bg-elevated);
  border:1px solid var(--border-subtle); border-radius:99px;
  font-size:11px; color:var(--text-secondary); font-family:var(--font-mono);
}
.metric-chip .chip-label { font-family:-apple-system,sans-serif; font-size:10.5px; color:var(--text-muted); }

/* ── Signal rows ── */
.signal-row {
  display:flex; align-items:flex-start; gap:12px;
  padding:10px 6px; border-bottom:1px solid var(--border-subtle);
  transition:background var(--transition); border-radius:var(--radius-sm);
}
.signal-row:last-child { border-bottom:none; }
.signal-row:hover { background:var(--bg-hover); }
.signal-score-ring {
  flex-shrink:0; width:38px; height:38px; border-radius:50%;
  display:flex; align-items:center; justify-content:center;
  font-size:10.5px; font-weight:700; font-family:var(--font-mono); border:2px solid;
}
.score-critical { background:rgba(239,68,68,.09);  border-color:var(--tier-critical); color:var(--tier-critical); }
.score-high     { background:rgba(245,158,11,.09); border-color:var(--tier-high);     color:var(--tier-high); }
.score-medium   { background:rgba(59,130,246,.09); border-color:var(--tier-medium);   color:var(--tier-medium); }
.score-low      { background:rgba(16,185,129,.09); border-color:var(--tier-low);      color:var(--tier-low); }
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

/* ── Flag & Step items ── */
.flag-item {
  display:flex; align-items:flex-start; gap:10px; padding:11px 14px;
  background:rgba(239,68,68,.06); border:1px solid rgba(239,68,68,.15);
  border-left:3px solid var(--tier-critical); border-radius:var(--radius-md);
  margin-bottom:8px; font-size:13px; color:#FCA5A5; line-height:1.55;
}
.flag-icon { flex-shrink:0; color:var(--tier-critical); font-size:13px; margin-top:1px; }
.step-item {
  display:flex; align-items:flex-start; gap:10px; padding:9px 14px;
  background:rgba(59,130,246,.055); border:1px solid rgba(59,130,246,.12);
  border-radius:var(--radius-md); margin-bottom:7px;
  font-size:13px; color:#93C5FD; line-height:1.55;
}
.step-num {
  flex-shrink:0; width:19px; height:19px; border-radius:50%;
  background:rgba(59,130,246,.18); color:var(--accent-blue);
  font-size:9.5px; font-weight:700; display:flex; align-items:center;
  justify-content:center; margin-top:1px;
}

/* ── SOAP viewer ── */
.soap-outer  { max-width:1100px; margin:0 auto; }
.soap-viewer {
  background:var(--bg-surface); border:1px solid var(--border-default);
  border-radius:var(--radius-lg); padding:32px 36px;
  font-size:var(--soap-font-size); line-height:var(--soap-line-height);
  color:var(--text-primary);
}
.soap-section-header {
  font-size:10px; font-weight:700; letter-spacing:1.1px;
  text-transform:uppercase; color:var(--accent-blue);
  margin-top:24px; margin-bottom:10px;
  padding-bottom:7px; border-bottom:1px solid var(--border-subtle);
}
.soap-section-header:first-child { margin-top:0; }
.soap-body-p { margin:0 0 2px; color:var(--text-secondary); font-size:var(--soap-font-size); line-height:var(--soap-line-height); }
.soap-bold   { color:var(--text-primary); font-weight:600; font-size:var(--soap-font-size); }
.soap-meta-row {
  display:flex; align-items:center; gap:16px;
  padding:12px 0; margin-bottom:8px;
  border-bottom:1px solid var(--border-subtle); flex-wrap:wrap;
}
.soap-meta-item { display:flex; flex-direction:column; gap:2px; }
.soap-meta-label { font-size:9.5px; font-weight:700; letter-spacing:.8px; text-transform:uppercase; color:var(--text-muted); }
.soap-meta-value { font-size:12.5px; font-weight:500; color:var(--text-secondary); font-family:var(--font-mono); }

/* ── Empty state ── */
.empty-state {
  display:flex; flex-direction:column; align-items:center; justify-content:center;
  padding:44px 24px; text-align:center; gap:10px;
}
.empty-state-icon  { font-size:24px; opacity:.25; }
.empty-state-title { font-size:13.5px; font-weight:600; color:var(--text-secondary); }
.empty-state-body  { font-size:12px; color:var(--text-muted); line-height:1.6; max-width:280px; }
.empty-state-hint  { font-size:11.5px; color:var(--accent-blue); opacity:.8; }

/* ── Help item ── */
.help-item {
  padding: 14px 0;
  border-bottom: 1px solid var(--border-subtle);
}
.help-item:last-child { border-bottom: none; }
.help-item-q {
  font-size: 12.5px; font-weight: 600; color: var(--text-primary);
  margin-bottom: 5px;
}
.help-item-a {
  font-size: 12px; color: var(--text-secondary); line-height: 1.65;
}

/* ── Disclaimer footer ── */
.disclaimer-footer {
  margin-top: 32px;
  padding: 14px 18px;
  background: rgba(245,158,11,0.05);
  border: 1px solid rgba(245,158,11,0.14);
  border-radius: var(--radius-md);
  display: flex; align-items: flex-start; gap: 10px;
}
.disclaimer-icon { font-size: 13px; color: var(--accent-amber); flex-shrink: 0; margin-top: 1px; }
.disclaimer-text { font-size: 11.5px; color: var(--text-muted); line-height: 1.6; }
.disclaimer-text strong { color: var(--text-secondary); }

/* ── Demo badge ── */
.demo-badge {
  display: inline-flex; align-items: center; gap: 5px;
  font-size: 10px; font-weight: 700; letter-spacing: 0.5px;
  text-transform: uppercase; padding: 2px 8px;
  background: rgba(245,158,11,0.12);
  border: 1px solid rgba(245,158,11,0.22);
  border-radius: 99px; color: var(--accent-amber);
  margin-left: 8px; vertical-align: middle;
}

/* ── Control center label ── */
.ctrl-label {
  font-size:9.5px; font-weight:700; letter-spacing:1px;
  text-transform:uppercase; color:var(--text-muted);
  display:block; margin-bottom:8px; margin-top:16px;
}
.ctrl-label:first-child { margin-top:0; }

/* ── Native overrides ── */
section[data-testid="stSidebar"] { background:var(--bg-surface) !important; border-right:1px solid var(--border-subtle) !important; }
.stTextInput > div > div > input,
.stTextArea  > div > div > textarea {
  background:var(--bg-elevated) !important; border:1px solid var(--border-default) !important;
  border-radius:var(--radius-md) !important; color:var(--text-primary) !important; font-size:13px !important;
}
.stTextInput > div > div > input:focus,
.stTextArea  > div > div > textarea:focus {
  border-color:var(--accent-blue) !important; box-shadow:0 0 0 3px rgba(59,130,246,.12) !important; outline:none !important;
}
.stSelectbox > div > div > div {
  background:var(--bg-elevated) !important; border:1px solid var(--border-default) !important;
  border-radius:var(--radius-md) !important; color:var(--text-primary) !important; font-size:13px !important;
}
.stButton > button[kind="primary"] {
  background:var(--accent-blue) !important; color:#fff !important; border:none !important;
  border-radius:var(--radius-md) !important; font-weight:600 !important; font-size:13px !important;
  height:40px !important; letter-spacing:.2px !important;
  transition:background var(--transition),box-shadow var(--transition) !important;
}
.stButton > button[kind="primary"]:hover { background:var(--accent-blue-dim) !important; box-shadow:0 0 0 3px rgba(59,130,246,.22) !important; }
.stButton > button[kind="secondary"],
.stButton > button:not([kind]) {
  background:var(--bg-elevated) !important; color:var(--text-primary) !important;
  border:1px solid var(--border-default) !important; border-radius:var(--radius-md) !important;
  font-weight:500 !important; font-size:13px !important; height:40px !important;
}
.stButton > button:disabled { background:var(--bg-elevated) !important; color:var(--text-muted) !important; border-color:var(--border-subtle) !important; }
.stDownloadButton > button {
  background:var(--bg-elevated) !important; color:var(--text-primary) !important;
  border:1px solid var(--border-default) !important; border-radius:var(--radius-md) !important;
  font-weight:500 !important; font-size:13px !important; height:40px !important;
}
.stDownloadButton > button:hover { border-color:var(--accent-blue) !important; color:var(--accent-blue) !important; }
.stTabs [data-baseweb="tab-list"] { background:transparent !important; border-bottom:1px solid var(--border-subtle) !important; gap:0 !important; padding:0 !important; }
.stTabs [data-baseweb="tab"] { background:transparent !important; color:var(--text-muted) !important; font-size:12.5px !important; font-weight:500 !important; padding:9px 16px !important; border-bottom:2px solid transparent !important; border-radius:0 !important; }
.stTabs [aria-selected="true"] { color:var(--text-primary) !important; border-bottom:2px solid var(--accent-blue) !important; }
.stTabs [data-baseweb="tab-panel"] { padding:18px 0 0 !important; }
[data-testid="stSegmentedControl"] > div { background:var(--bg-elevated) !important; border:1px solid var(--border-default) !important; border-radius:var(--radius-md) !important; padding:3px !important; gap:2px !important; }
[data-testid="stSegmentedControl"] button { background:transparent !important; color:var(--text-secondary) !important; border-radius:var(--radius-sm) !important; font-size:12.5px !important; font-weight:500 !important; border:none !important; }
[data-testid="stSegmentedControl"] button[aria-checked="true"] { background:var(--accent-blue) !important; color:#fff !important; box-shadow:0 1px 4px rgba(0,0,0,.4) !important; }
[data-testid="stPills"] button { background:var(--bg-elevated) !important; color:var(--text-secondary) !important; border:1px solid var(--border-default) !important; border-radius:99px !important; font-size:12px !important; font-weight:500 !important; }
[data-testid="stPills"] button[aria-pressed="true"] { background:rgba(59,130,246,.15) !important; color:var(--accent-blue) !important; border-color:rgba(59,130,246,.3) !important; }
.stRadio > label { color:var(--text-secondary) !important; font-size:12.5px !important; }
.stRadio > div > label { color:var(--text-secondary) !important; font-size:13px !important; }
[data-testid="stAudioInput"]   { background:var(--bg-elevated) !important; border:1px solid var(--border-default) !important; border-radius:var(--radius-md) !important; }
[data-testid="stFileUploader"] { background:var(--bg-elevated) !important; border:1px dashed var(--border-default) !important; border-radius:var(--radius-md) !important; }
.stNumberInput > div > div > input { background:var(--bg-elevated) !important; border:1px solid var(--border-default) !important; border-radius:var(--radius-md) !important; color:var(--text-primary) !important; }
[data-baseweb="notification"] { border-radius:var(--radius-md) !important; font-size:13px !important; }
hr { border-color:var(--border-subtle) !important; margin:20px 0 !important; }
[data-testid="stStatusWidget"] { background:var(--bg-elevated) !important; border:1px solid var(--border-default) !important; border-radius:var(--radius-md) !important; }
label[data-testid="stWidgetLabel"] { color:var(--text-secondary) !important; font-size:12px !important; }
.stCaption { color:var(--text-muted) !important; font-size:11.5px !important; }
p { color:var(--text-secondary) !important; }
[data-testid="stPopover"] > div { background:var(--bg-elevated) !important; border:1px solid var(--border-default) !important; border-radius:var(--radius-lg) !important; box-shadow:0 16px 48px rgba(0,0,0,.7) !important; }
</style>
""", unsafe_allow_html=True)


# =====================================================================
# CONTROL CENTER
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


# Resolve effective values
specialty_profile: str = SPECIALTY_MAP.get(st.session_state.sc_specialty or "Cardiology", "Cardiology Clinic")
target_language:   str = LANGUAGE_MAP.get(st.session_state.sc_language or "Mixed", "Mixed (Multi-lingual Code-Switching)")
groq_api_key:   str = (st.session_state.get("_groq_override") or "").strip() or _vault_groq
gemini_api_key: str = (st.session_state.get("_gemini_override") or "").strip() or _vault_gemini


# =====================================================================
# HEADER
# =====================================================================
has_results  = bool(st.session_state.transcript)
chart_locked = st.session_state.chart_locked

if chart_locked:
    status_cls, status_txt, dot_cls = "locked", "Signed",  "os-dot"
elif has_results:
    status_cls, status_txt, dot_cls = "active", "Review",  "os-dot pulse"
else:
    status_cls, status_txt, dot_cls = "ready",  "Ready",   "os-dot pulse"

demo_label = '<span class="demo-badge">Demo</span>' if st.session_state.demo_loaded else ""

hcol1, hcol2 = st.columns([5, 1])
with hcol1:
    st.markdown(f"""
    <div class="os-header">
      <div class="os-wordmark">SALIENCE<span> OS</span>{demo_label}</div>
      <div class="os-header-meta">
        <div class="os-status-pill {status_cls}">
          <div class="{dot_cls}"></div>{status_txt}
        </div>
        <div class="os-time">{datetime.now().strftime('%H:%M')}</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

with hcol2:
    with st.popover("⚙ Settings", use_container_width=True):
        render_control_center()


# =====================================================================
# GOAL 1 — WELCOME PANEL (dismissible, first-load only)
# =====================================================================
if not st.session_state.onboarding_dismissed:
    st.markdown("""
    <div class="welcome-panel">
      <div class="welcome-title">Welcome to Salience OS — Clinical Intelligence Workspace</div>
      <div class="welcome-subtitle">
        An ambient clinical intelligence platform that identifies, prioritises, and explains clinically relevant signals
        from consultation audio and examination findings — before documentation begins.
      </div>
      <div class="welcome-grid">
        <div class="welcome-card">
          <div class="welcome-card-icon">👩‍⚕️</div>
          <div class="welcome-card-title">For clinicians</div>
          <div class="welcome-card-body">Consultant physicians, surgeons, emergency doctors, GPs, residents, nurses, and allied health professionals.</div>
        </div>
        <div class="welcome-card">
          <div class="welcome-card-icon">📥</div>
          <div class="welcome-card-title">Accepted inputs</div>
          <div class="welcome-card-body">Live audio recording, uploaded audio files (.wav .mp3 .m4a), pasted transcripts, or JSON datasets.</div>
        </div>
        <div class="welcome-card">
          <div class="welcome-card-icon">📤</div>
          <div class="welcome-card-title">Generated outputs</div>
          <div class="welcome-card-body">Prioritised clinical signals, safety flags, suggested next steps, structured SOAP note, and explainability reasoning.</div>
        </div>
        <div class="welcome-card">
          <div class="welcome-card-icon">⏱</div>
          <div class="welcome-card-title">Analysis time</div>
          <div class="welcome-card-body">Typically 15–40 seconds for a standard consultation. Audio files may take slightly longer during transcription.</div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    ob_col1, ob_col2, ob_col3 = st.columns([1, 1, 4])
    with ob_col1:
        if st.button("✓  Got it — dismiss", use_container_width=True):
            st.session_state.onboarding_dismissed = True
            st.rerun()
    with ob_col2:
        if st.button("⬡  Load Demo Patient", use_container_width=True,
                     help="Populate the workspace with a realistic cardiology case so you can explore all features without real patient data."):
            st.session_state.transcript              = DEMO_TRANSCRIPT
            st.session_state.classification          = DEMO_CLASSIFICATION
            st.session_state.salience_map            = DEMO_SALIENCE_MAP
            st.session_state.soap_note               = DEMO_SOAP
            st.session_state.flags                   = DEMO_FLAGS
            st.session_state.next_steps              = DEMO_NEXT_STEPS
            st.session_state.pipeline_execution_time = 0.0
            st.session_state.chart_locked            = False
            st.session_state.demo_loaded             = True
            st.session_state.onboarding_dismissed    = True
            st.rerun()


# =====================================================================
# GOAL 2 — GUIDED WORKFLOW STRIP
# Determine current step based on session state for active/done classes
# =====================================================================
def _workflow_step(num: int, label: str, step_cls: str, arrow: bool = True) -> str:
    html = f"""<div class="workflow-step">
      <div class="workflow-step-num {step_cls}">{num}</div>
      <span class="workflow-step-label {step_cls}">{label}</span>
    </div>"""
    if arrow:
        html += '<span class="workflow-arrow">›</span>'
    return html

_has_input   = has_results or st.session_state.demo_loaded
_has_signals = bool(st.session_state.salience_map)
_has_soap    = bool(st.session_state.soap_note)

def _step_cls(condition_done: bool, condition_active: bool) -> str:
    if condition_done:   return "done"
    if condition_active: return "active"
    return ""

s1 = _step_cls(_has_input, not _has_input)
s2 = _step_cls(_has_input, not _has_input)
s3 = _step_cls(_has_signals, _has_input and not _has_signals)
s4 = _step_cls(_has_signals, _has_signals and not _has_soap)
s5 = _step_cls(_has_soap, _has_signals and not _has_soap)
s6 = _step_cls(chart_locked, _has_soap and not chart_locked)

workflow_html = '<div class="workflow-strip">'
workflow_html += _workflow_step(1, "Paste / Upload / Record",  s1)
workflow_html += _workflow_step(2, "Add Exam Findings",        s2)
workflow_html += _workflow_step(3, "Run Analysis",             s3)
workflow_html += _workflow_step(4, "Review Signals",           s4)
workflow_html += _workflow_step(5, "Review SOAP Note",         s5)
workflow_html += _workflow_step(6, "Export or Sign Chart",     s6, arrow=False)
workflow_html += "</div>"
st.markdown(workflow_html, unsafe_allow_html=True)


# =====================================================================
# INPUT WORKSPACE
# =====================================================================
st.markdown('<div class="section-label">Consultation Input</div>', unsafe_allow_html=True)

# Demo load button outside welcome panel (persistent, accessible after dismiss)
if not st.session_state.demo_loaded:
    demo_col, _ = st.columns([1, 4])
    with demo_col:
        if st.button("⬡  Load Demo Patient",
                     help="Populate with a realistic cardiology case — 58-year-old male with ACS presentation. No real patient data required.",
                     use_container_width=True):
            st.session_state.transcript              = DEMO_TRANSCRIPT
            st.session_state.classification          = DEMO_CLASSIFICATION
            st.session_state.salience_map            = DEMO_SALIENCE_MAP
            st.session_state.soap_note               = DEMO_SOAP
            st.session_state.flags                   = DEMO_FLAGS
            st.session_state.next_steps              = DEMO_NEXT_STEPS
            st.session_state.pipeline_execution_time = 0.0
            st.session_state.chart_locked            = False
            st.session_state.demo_loaded             = True
            st.rerun()
else:
    clear_col, _ = st.columns([1, 4])
    with clear_col:
        if st.button("✕  Clear Demo Data",
                     help="Remove demo case and start a fresh consultation.",
                     use_container_width=True):
            for k in ("transcript", "salience_map", "soap_note", "flags", "next_steps", "classification"):
                st.session_state[k] = _DEFAULTS[k]
            st.session_state.demo_loaded  = False
            st.session_state.chart_locked = False
            st.session_state.pipeline_execution_time = 0.0
            st.rerun()

col_input, col_exam = st.columns([1.25, 1], gap="large")

with col_input:
    input_vector: str = st.radio(
        "Input mode",
        ["Text / Paste Transcript", "Live Audio (Microphone)", "File Upload (.wav / .mp3 / .json)"],
        horizontal=False,
        label_visibility="collapsed",
        help=(
            "Choose how to provide consultation data.\n\n"
            "• Text: paste a transcript or typed notes directly.\n"
            "• Live Audio: record the consultation room using your device microphone.\n"
            "• File Upload: upload a pre-recorded audio file or a JSON dataset."
        ),
    )

    has_valid_audio_payload: bool = False
    bypass_audio_stt:        bool = False
    injected_text_payload:   str  = ""

    if "Text" in input_vector:
        injected_text_payload = st.text_area(
            "Transcript",
            placeholder=(
                "Paste a consultation transcript, clinical notes, or dictated text here.\n\n"
                "Include the patient's presenting complaint, history, and any verbal examination findings."
            ),
            height=200, label_visibility="collapsed",
        )
        if injected_text_payload.strip():
            has_valid_audio_payload = True
            bypass_audio_stt = True

    elif "Live Audio" in input_vector:
        if not PYDUB_AVAILABLE:
            st.warning("Audio processing unavailable on this deployment. Switch to Text input to continue.")
        else:
            st.caption("Place your device near the consultation. Press record, speak, then press stop when finished.")
            audio_file = st.audio_input(
                "Record audio",
                help="Captures room audio using your microphone. The recording is processed locally and sent securely to the transcription service.",
            )
            if audio_file is not None:
                try:
                    with open(TEMP_AUDIO, "wb") as fh:
                        fh.write(audio_file.read())
                    has_valid_audio_payload = True
                except OSError as e:
                    st.error(f"Could not save audio: {e}")

    else:
        st.caption("Supported: .wav, .mp3, .m4a audio files, or a JSON case dataset.")
        uploaded_file = st.file_uploader(
            "Upload audio or dataset", type=["wav", "mp3", "m4a", "json"],
            label_visibility="collapsed",
        )
        if uploaded_file is not None:
            if uploaded_file.name.endswith(".json"):
                try:
                    json_data = json.load(uploaded_file)
                    if isinstance(json_data, list):
                        st.caption(f"Dataset loaded — {len(json_data)} cases")
                        case_idx = int(st.number_input(
                            "Case index", min_value=0,
                            max_value=max(len(json_data) - 1, 0), value=0,
                        ))
                        node = json_data[case_idx]
                        injected_text_payload = node.get("input", node.get("instruction", ""))
                        if injected_text_payload:
                            st.info(injected_text_payload[:240] +
                                    ("…" if len(injected_text_payload) > 240 else ""))
                        if injected_text_payload.strip():
                            has_valid_audio_payload = True
                            bypass_audio_stt = True
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
                        has_valid_audio_payload = True
                    except OSError as e:
                        st.error(f"Could not save file: {e}")

with col_exam:
    st.markdown('<div class="section-label">Physical Examination</div>', unsafe_allow_html=True)
    st.caption(
        "Enter your bedside findings by system. These are merged with the consultation transcript "
        "during analysis to improve signal accuracy and SOAP note completeness."
    )
    exam_tabs = st.tabs(["Thoracic", "GI / Abdomen", "Neuro / Reflex", "Musculoskeletal"])
    with exam_tabs[0]:
        st.caption("Cardiovascular and respiratory examination findings — heart sounds, rhythm, breath sounds, oedema.")
        notes_thoracic: str = st.text_area("Thoracic",
            value=st.session_state.demo_thoracic if st.session_state.demo_loaded else
                  "Cardiovascular: Tachycardic, rhythm regular. S1 and S2 distinct, no audible murmurs, rubs, or gallops. Significant chest wall diaphoresis noted; patient actively clutching retrosternal area. Respiratory: Tachypneic, shallow respirations. Lungs clear to auscultation bilaterally (CTAB).",
            height=120, label_visibility="collapsed",
            help="Include heart rate, rhythm, heart sounds, murmurs, respiratory rate, and chest auscultation findings.")
    with exam_tabs[1]:
        st.caption("Abdominal examination — tenderness, guarding, bowel sounds, organomegaly.")
        notes_abdominal: str = st.text_area("GI",
            value=st.session_state.demo_abdominal if st.session_state.demo_loaded else
                  "Abdomen soft, symmetric, and non-distended. Bowel sounds active in all 4 quadrants. No localized tenderness, guarding, or rebound. No hepatosplenomegaly. Epigastric region non-tender.",
            height=120, label_visibility="collapsed",
            help="Document abdominal tenderness, rigidity, guarding, rebound, and any organomegaly.")
    with exam_tabs[2]:
        st.caption("Neurological examination — orientation, pupils, reflexes, focal deficits.")
        notes_neuro: str = st.text_area("Neuro",
            value=st.session_state.demo_neuro if st.session_state.demo_loaded else
                  "Patient alert and oriented to person, place, and time (A&Ox3). Pupils equal, round, and reactive to light (PEERRLA). Observable orthostatic lightheadedness upon sitting up. Gross motor and sensory function intact.",
            height=120, label_visibility="collapsed",
            help="Record GCS, pupillary responses, orientation, focal weakness, sensory deficits, and reflexes.")
    with exam_tabs[3]:
        st.caption("Musculoskeletal examination — range of motion, joint tenderness, swelling.")
        notes_ortho: str = st.text_area("MSK",
            value=st.session_state.demo_ortho if st.session_state.demo_loaded else
                  "Mild focal tenderness over lumbar paraspinal muscles. Left shoulder and left mandibular jaw display full passive range of motion with zero localized joint or bone tenderness.",
            height=120, label_visibility="collapsed",
            help="Include range of motion, joint tenderness, swelling, crepitus, and any deformity.")

compiled_exam: str = (
    f"- Thoracic: {notes_thoracic or 'Deferred/Normal'}\n"
    f"- GI/Abdomen: {notes_abdominal or 'Deferred/Normal'}\n"
    f"- Neuro/Reflex: {notes_neuro or 'Deferred/Normal'}\n"
    f"- Musculoskeletal: {notes_ortho or 'Deferred/Normal'}"
)


# =====================================================================
# ANALYSIS TRIGGER
# =====================================================================
st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
run_pipeline: bool = False

if has_valid_audio_payload:
    trigger_col, _ = st.columns([1, 2])
    with trigger_col:
        run_pipeline = st.button(
            "⬡  Analyse Consultation",
            type="primary",
            use_container_width=True,
            help=(
                "Start the clinical intelligence pipeline.\n\n"
                "The system will:\n"
                "1. Transcribe audio (if applicable)\n"
                "2. Extract and weight clinical entities\n"
                "3. Identify safety flags\n"
                "4. Generate a structured SOAP note\n\n"
                "Typical duration: 15–40 seconds."
            ),
        )
else:
    if not st.session_state.transcript:
        st.markdown("""
        <div class="empty-state">
          <div class="empty-state-icon">⬡</div>
          <div class="empty-state-title">No consultation loaded</div>
          <div class="empty-state-body">
            Paste a transcript using the Text input above, record live audio, or upload an audio file to begin analysis.
          </div>
          <div class="empty-state-hint">
            New here? Use ⬡ Load Demo Patient to explore the platform with a sample case.
          </div>
        </div>
        """, unsafe_allow_html=True)


# =====================================================================
# PIPELINE EXECUTION
# =====================================================================
if has_valid_audio_payload and run_pipeline:
    if not GENAI_AVAILABLE:
        st.error("google-generativeai SDK is not installed.")
    elif not GROQ_AVAILABLE and not bypass_audio_stt:
        st.error("Groq SDK is not installed. Cannot process audio.")
    elif not gemini_api_key:
        st.error("Gemini API key missing. Open ⚙ Settings to add it.")
    elif not groq_api_key and not bypass_audio_stt:
        st.error("Groq API key missing. Open ⚙ Settings to add it.")
    else:
        t0 = time.time()
        with st.status("Running clinical intelligence pipeline…", expanded=True) as status_widget:
            try:
                extracted_raw_text: str = ""
                if bypass_audio_stt:
                    st.write("✓  Text input detected — bypassing STT")
                    extracted_raw_text = injected_text_payload
                else:
                    if not PYDUB_AVAILABLE:
                        raise RuntimeError("pydub not available. Use Text input mode.")
                    if not os.path.exists(TEMP_AUDIO):
                        raise FileNotFoundError(f"Audio file missing at {TEMP_AUDIO!r}. Re-upload.")
                    st.write("⬡  Compressing audio…")
                    raw_audio = AudioSegment.from_file(TEMP_AUDIO)
                    processed = raw_audio.set_channels(1).set_frame_rate(16000)
                    processed.export(COMP_AUDIO, format="mp3", bitrate="64k")
                    st.write("⬡  Transcribing via Whisper large-v3…")
                    gc = Groq(api_key=groq_api_key, timeout=60.0)
                    with open(COMP_AUDIO, "rb") as ab:
                        extracted_raw_text = gc.audio.transcriptions.create(
                            file=(COMP_AUDIO, ab.read()),
                            model="whisper-large-v3",
                            response_format="text",
                        )
                    for p in (TEMP_AUDIO, COMP_AUDIO):
                        try:
                            if os.path.exists(p):
                                os.remove(p)
                        except OSError:
                            pass
                    st.write("✓  Transcription complete")

                if not (extracted_raw_text or "").strip():
                    raise ValueError("Transcription returned empty text. Check audio quality or API key.")

                st.write("⬡  Running salience analysis via Gemini 2.5 Flash…")
                genai.configure(api_key=gemini_api_key)
                engine = genai.GenerativeModel("gemini-2.5-flash")

                prompt = f"""
You are the core analytical pipeline of Salience OS, configured for the specialty: {specialty_profile}.
The incoming data stream was ingested with an expected localization matrix profile of: {target_language}.

RAW INPUT DATA TRANSCRIPT:
\"\"\"{extracted_raw_text}\"\"\"

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
                raw_json: str = resp.text or ""
                if not raw_json.strip():
                    raise ValueError("Gemini returned empty response. Check API key and quota.")

                try:
                    parsed: dict = json.loads(raw_json, strict=False)
                except json.JSONDecodeError as je:
                    raise ValueError(
                        f"Gemini response was not valid JSON: {je}. "
                        f"First 300 chars: {raw_json[:300]}"
                    ) from je

                st.session_state.transcript              = str(parsed.get("cleaned_transcript", ""))
                st.session_state.classification          = dict(parsed.get("classification", {}))
                st.session_state.salience_map            = list(parsed.get("salience_weight_map", []))
                st.session_state.soap_note               = str(parsed.get("structured_soap_chart", ""))
                st.session_state.flags                   = list(parsed.get("clinical_safety_red_flags", []))
                st.session_state.next_steps              = list(parsed.get("suggested_next_steps", []))
                st.session_state.pipeline_execution_time = round(time.time() - t0, 2)
                st.session_state.chart_locked            = False
                st.session_state.demo_loaded             = False

                st.write("✓  Pipeline complete")
                status_widget.update(
                    label=f"Analysis complete — {st.session_state.pipeline_execution_time}s",
                    state="complete", expanded=False,
                )
                st.rerun()

            except Exception as err:
                status_widget.update(label="Pipeline error", state="error", expanded=True)
                st.error(f"**Pipeline failed:** {err}")


# =====================================================================
# RESULTS WORKSPACE
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
    if urgency not in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
        urgency = "MEDIUM"

    elapsed_label = f"{elapsed}s" if elapsed > 0 else "Demo"
    st.markdown(f"""
    <div class="urgency-bar {urgency}">
      <div>
        <div class="urgency-label">{urgency} Priority</div>
        <div class="urgency-text">{trigger}</div>
      </div>
      <div class="urgency-metrics">
        <span class="metric-chip"><span class="chip-label">Signals</span>{n_signals}</span>
        <span class="metric-chip"><span class="chip-label">Flags</span>{n_flags}</span>
        <span class="metric-chip"><span class="chip-label">Time</span>{elapsed_label}</span>
      </div>
    </div>
    """, unsafe_allow_html=True)

    output_tabs = st.tabs([
        "Clinical Signals", "Safety Flags", "Next Steps", "SOAP Note", "Explainability",
    ])

    # ── Tab 1: Clinical Signals ────────────────────────────────────
    with output_tabs[0]:
        if st.session_state.salience_map:
            st.caption(
                "Entities ranked by clinical salience — a weighted measure of urgency, specificity, and diagnostic relevance. "
                "Score ≥ 85 = critical priority. 70–84 = high. 50–69 = medium. < 50 = low or contextual noise."
            )
            for item in sorted(st.session_state.salience_map,
                               key=lambda x: x.get("salience_score", 0), reverse=True):
                score    = float(item.get("salience_score", 0.0))
                entity   = str(item.get("entity", ""))
                category = str(item.get("category", ""))
                reasoning = str(item.get("reasoning_context", ""))
                pct      = int(score * 100)
                if score >= 0.85:   ring_cls, bc = "score-critical", "var(--tier-critical)"
                elif score >= 0.70: ring_cls, bc = "score-high",     "var(--tier-high)"
                elif score >= 0.50: ring_cls, bc = "score-medium",   "var(--tier-medium)"
                else:               ring_cls, bc = "score-low",      "var(--tier-low)"
                st.markdown(f"""
                <div class="signal-row">
                  <div class="signal-score-ring {ring_cls}">{pct}</div>
                  <div class="signal-body">
                    <div class="signal-entity">{entity}</div>
                    <span class="signal-category-chip">{category}</span>
                    <div class="signal-reasoning">{reasoning}</div>
                    <div class="signal-bar-track">
                      <div class="signal-bar-fill" style="width:{pct}%;background:{bc}"></div>
                    </div>
                  </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div class="empty-state">
              <div class="empty-state-icon">◎</div>
              <div class="empty-state-title">No clinical signals extracted yet</div>
              <div class="empty-state-body">
                Run an analysis on a consultation transcript or audio recording.
                Signals will appear here ranked by clinical importance.
              </div>
            </div>""", unsafe_allow_html=True)

    # ── Tab 2: Safety Flags ────────────────────────────────────────
    with output_tabs[1]:
        if st.session_state.flags:
            st.caption("Critical alerts identified by the safety screening layer. Each flag should be reviewed before signing the clinical note.")
            for alert in st.session_state.flags:
                st.markdown(f'<div class="flag-item"><div class="flag-icon">⚑</div><div>{alert}</div></div>',
                            unsafe_allow_html=True)
        else:
            st.markdown("""
            <div class="empty-state">
              <div class="empty-state-icon">✓</div>
              <div class="empty-state-title">No safety flags raised</div>
              <div class="empty-state-body">
                The safety screening layer found no critical alerts for this consultation.
                Always apply independent clinical judgement before sign-off.
              </div>
            </div>""", unsafe_allow_html=True)

    # ── Tab 3: Next Steps ──────────────────────────────────────────
    with output_tabs[2]:
        if st.session_state.next_steps:
            st.caption("Suggested investigations, referrals, and management actions based on the extracted clinical signals. Review and adapt to your clinical context.")
            for idx, step in enumerate(st.session_state.next_steps, 1):
                st.markdown(f'<div class="step-item"><div class="step-num">{idx}</div><div>{step}</div></div>',
                            unsafe_allow_html=True)
        else:
            st.markdown("""
            <div class="empty-state">
              <div class="empty-state-icon">→</div>
              <div class="empty-state-title">No next steps generated yet</div>
              <div class="empty-state-body">
                Run an analysis to receive suggested investigations, referrals, and management actions.
              </div>
            </div>""", unsafe_allow_html=True)

    # ── Tab 4: SOAP Note ───────────────────────────────────────────
    with output_tabs[3]:
        soap_raw: str = st.session_state.soap_note
        chart_status_label = "Signed & Locked" if chart_locked else "Pending Review"
        chart_status_color = "var(--accent-violet)" if chart_locked else "var(--accent-amber)"
        generated_at       = datetime.now().strftime("%Y-%m-%d %H:%M")

        st.markdown(f"""
        <div class="soap-meta-row">
          <div class="soap-meta-item"><span class="soap-meta-label">Generated</span><span class="soap-meta-value">{generated_at}</span></div>
          <div class="soap-meta-item"><span class="soap-meta-label">Specialty</span><span class="soap-meta-value">{specialty_profile}</span></div>
          <div class="soap-meta-item"><span class="soap-meta-label">Status</span><span class="soap-meta-value" style="color:{chart_status_color}">{chart_status_label}</span></div>
          <div class="soap-meta-item"><span class="soap-meta-label">Time</span><span class="soap-meta-value">{elapsed_label}</span></div>
        </div>
        """, unsafe_allow_html=True)

        if not chart_locked:
            st.caption(
                "Review and amend the AI-generated note below. "
                "Correct any inaccuracies, add missing clinical details, and verify all four sections "
                "before signing. The note is fully editable until signed."
            )
            edited_soap = st.text_area(
                "SOAP Note",
                value=soap_raw,
                height=420,
                key="soap_editor",
                label_visibility="collapsed",
            )
        else:
            edited_soap = soap_raw
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

        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
        act1, act2, act3 = st.columns(3)

        with act1:
            st.button(
                "⎘  Copy SOAP", key="copy_soap_btn", use_container_width=True,
                help="Select all text in the editor above (Ctrl+A / Cmd+A), then copy (Ctrl+C / Cmd+C).",
            )

        with act2:
            if edited_soap.strip() and FPDF_AVAILABLE:
                try:
                    pdf_bytes: bytes = generate_clinical_pdf(edited_soap, specialty_profile)
                    st.download_button(
                        label="↓  Export PDF",
                        data=pdf_bytes,
                        file_name=f"SalienceOS_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                        mime="application/pdf",
                        use_container_width=True,
                        help="Download the SOAP note as a formatted PDF document. The exported PDF reflects the current state of the editable note.",
                    )
                except Exception as pdf_err:
                    st.error(f"PDF error: {pdf_err}")
            else:
                st.button("↓  Export PDF", disabled=True, use_container_width=True,
                          help="Generate a note by running analysis first, then export to PDF.")

        with act3:
            if chart_locked:
                st.button("✓  Synced to FHIR", disabled=True, use_container_width=True,
                          help="This chart has been signed and pushed to the simulated EHR. No further edits are permitted.")
            else:
                if st.button(
                    "Sign & Push to EHR",
                    type="primary",
                    use_container_width=True,
                    help=(
                        "Digitally sign the SOAP note and push it to the simulated EHR system.\n\n"
                        "⚠ Before signing, verify:\n"
                        "• Patient identity and date of birth\n"
                        "• All four SOAP sections are accurate\n"
                        "• Safety flags have been reviewed\n"
                        "• Allergies and medications are correct\n\n"
                        "Signing is irreversible in a live EHR system."
                    ),
                ):
                    st.session_state.soap_note = edited_soap
                    with st.spinner("Synchronising with HL7/FHIR endpoint…"):
                        time.sleep(2.0)
                    st.session_state.chart_locked = True
                    st.success("Chart signed and pushed to simulated EHR database.")
                    st.balloons()
                    st.rerun()

    # ── Tab 5: Explainability ──────────────────────────────────────
    with output_tabs[4]:
        if st.session_state.salience_map:
            st.caption(
                "Full reasoning trace for each extracted entity. "
                "Salience scores reflect the model's assessment of clinical urgency, specificity, and diagnostic relevance "
                "within the context of the selected specialty. Always apply independent clinical judgement."
            )
            for idx, item in enumerate(
                sorted(st.session_state.salience_map,
                       key=lambda x: x.get("salience_score", 0), reverse=True), 1
            ):
                score    = float(item.get("salience_score", 0.0))
                entity   = str(item.get("entity", ""))
                reason   = str(item.get("reasoning_context", ""))
                category = str(item.get("category", ""))
                pct      = int(score * 100)
                sc = ("var(--tier-critical)" if score >= 0.85
                      else "var(--tier-high)"    if score >= 0.70
                      else "var(--tier-medium)"   if score >= 0.50
                      else "var(--tier-low)")
                st.markdown(f"""
                <div class="signal-row" style="padding:11px 6px">
                  <div style="flex-shrink:0;width:26px;font-size:10.5px;font-family:var(--font-mono);
                              color:var(--text-muted);text-align:right;padding-top:2px">{idx:02d}</div>
                  <div class="signal-body">
                    <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">
                      <span class="signal-entity">{entity}</span>
                      <span class="signal-category-chip">{category}</span>
                      <span style="margin-left:auto;font-size:11.5px;font-weight:700;
                                   font-family:var(--font-mono);color:{sc}">{pct}%</span>
                    </div>
                    <div class="signal-reasoning">{reason}</div>
                    <div class="signal-bar-track" style="margin-top:8px">
                      <div class="signal-bar-fill" style="width:{pct}%;background:{sc}"></div>
                    </div>
                  </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div class="empty-state">
              <div class="empty-state-icon">◈</div>
              <div class="empty-state-title">No reasoning data available yet</div>
              <div class="empty-state-body">
                Run an analysis to see the model's full reasoning for each extracted clinical signal.
              </div>
            </div>""", unsafe_allow_html=True)


# =====================================================================
# GOAL 6 — HELP & DOCUMENTATION DRAWER
# =====================================================================
st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
with st.expander("❓ Clinical Documentation Help", expanded=False):
    st.markdown("""
    <div class="help-item">
      <div class="help-item-q">What is Salience Scoring?</div>
      <div class="help-item-a">
        Salience scoring is a weighted measure (0–100%) of how clinically important each extracted entity is
        within the context of this consultation and specialty. It combines urgency, diagnostic specificity,
        and relevance to the chief complaint. Scores of 85% or above are flagged as critical priority.
        Scores below 50% typically represent contextual noise or low-relevance background information.
      </div>
    </div>
    <div class="help-item">
      <div class="help-item-q">What are Clinical Signals?</div>
      <div class="help-item-a">
        Clinical signals are named entities extracted from the consultation — symptoms, diagnoses, medications,
        durations, and examination findings — ranked by their salience score. The "Clinical Signals" tab
        shows the top-priority entities the system identified as most likely to influence your clinical decision-making.
        Always cross-reference with the full transcript and your bedside assessment.
      </div>
    </div>
    <div class="help-item">
      <div class="help-item-q">What are Safety Flags?</div>
      <div class="help-item-a">
        Safety flags are critical alerts generated by the safety screening layer — for example, time-sensitive
        presentations (STEMI, stroke), high-risk drug interactions, or missing critical assessments. They are not
        diagnoses. They are prompts to verify that important safety checks have been performed before signing
        the clinical note. The absence of flags does not exclude a serious diagnosis.
      </div>
    </div>
    <div class="help-item">
      <div class="help-item-q">How are SOAP notes generated?</div>
      <div class="help-item-a">
        The SOAP note is generated from consultation transcript entities with a salience score of 0.5 or above,
        combined with your physical examination findings. Subjective content is derived exclusively from
        high-salience transcript entities. Objective content incorporates your documented examination findings.
        Assessment and Plan are AI-generated based on the synthesised clinical picture and specialty context.
        The note is fully editable before sign-off.
      </div>
    </div>
    <div class="help-item">
      <div class="help-item-q">What should clinicians verify before signing?</div>
      <div class="help-item-a">
        Before signing, verify: (1) patient identity and date of birth are correct; (2) the chief complaint
        and history accurately reflect what was documented; (3) examination findings in the Objective section
        match your bedside findings; (4) the Assessment reflects your clinical judgement — not just the AI output;
        (5) the Plan is appropriate for your patient's context, allergies, comorbidities, and local guidelines;
        (6) all Safety Flags have been reviewed and addressed; (7) medications and allergies are accurately listed.
      </div>
    </div>
    """, unsafe_allow_html=True)


# =====================================================================
# GOAL 7 — CLINICAL DISCLAIMER FOOTER
# =====================================================================
st.markdown("""
<div class="disclaimer-footer">
  <div class="disclaimer-icon">⚠</div>
  <div class="disclaimer-text">
    <strong>Clinical Decision Support Tool — Not a Substitute for Clinical Judgement.</strong>
    SALIENCE OS is designed to assist with clinical documentation and signal identification.
    It does not diagnose, prescribe, or replace the assessment of a qualified healthcare professional.
    All outputs must be reviewed, verified, and amended by the responsible clinician before use in patient care.
    Final clinical judgement, including documentation sign-off, remains the sole responsibility of the
    treating healthcare professional.
  </div>
</div>
""", unsafe_allow_html=True)
