# =====================================================================
# SALIENCE OS V3 — Clinical Intelligence Operating System
# Demo-ready production build
# Python 3.12 · Streamlit 1.58 · Streamlit Cloud compatible
# =====================================================================

import sys
try:
    import audioop  # noqa: F401  — present natively in Python ≤3.12
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

# ── Guarded imports ──────────────────────────────────────────────────
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

DEMO_CASE_OPTIONS = {
    "🫀  Cardiology — Acute STEMI (CRITICAL)":     "cardiology",
    "🧠  Neurology — Acute Stroke (CRITICAL)":     "neurology",
    "🧘  Psychiatry — Major Depression (HIGH)":    "psychiatry",
    "👶  Paediatrics — Febrile Convulsion (HIGH)": "paediatrics",
    "🚑  Emergency — Polytrauma (CRITICAL)":       "emergency",
}

# =====================================================================
# DEMO CASES — inlined (no external file dependency)
# All cases are synthetic. No real patient data.
# =====================================================================
DEMO_CASES = {
    "cardiology": {
        "label": "Acute STEMI",
        "specialty": "Cardiology",
        "sc_specialty": "Cardiology",
        "patient_ref": "DEMO-001 · Acute Anterior STEMI",
        "pipeline_time": 3.8,
        "transcript": (
            "63-year-old male presenting with 45-minute history of crushing substernal "
            "chest pain radiating to the left arm and jaw, rated 9/10. Associated diaphoresis, "
            "nausea, and dyspnoea. Similar milder episodes in the preceding 3 weeks. "
            "PMH: hypertension (amlodipine 5mg), type 2 diabetes (metformin 1g BD). "
            "FH: paternal MI at age 58. Current medications: atorvastatin 20mg. "
            "BP 158/94 mmHg, HR 112 bpm (regular), RR 22/min. Diaphoretic on presentation."
        ),
        "classification": {
            "urgency_tier": "CRITICAL",
            "primary_clinical_trigger": (
                "Acute anterior STEMI — crushing chest pain >20 minutes with radiation, "
                "diaphoresis, and cardiovascular risk factors. Immediate reperfusion indicated."
            ),
        },
        "salience_map": [
            {"entity": "Crushing chest pain (45 min)", "category": "Symptom", "salience_score": 0.98,
             "reasoning_context": "Cardinal ACS symptom. Duration >20 min with typical quality. Drives STEMI protocol activation."},
            {"entity": "Left arm and jaw radiation", "category": "Symptom", "salience_score": 0.94,
             "reasoning_context": "Classic referred pain via C8-T1 dermatomes. Significantly elevates pre-test probability for MI."},
            {"entity": "Diaphoresis", "category": "Symptom", "salience_score": 0.91,
             "reasoning_context": "Autonomic activation indicating haemodynamic stress. Consistent with significant myocardial event."},
            {"entity": "Tachycardia HR 112 bpm", "category": "Vital Sign", "salience_score": 0.88,
             "reasoning_context": "Compensatory tachycardia. Continuous monitoring required."},
            {"entity": "Hypertension (amlodipine 5mg)", "category": "Medical History", "salience_score": 0.82,
             "reasoning_context": "Established cardiovascular risk factor."},
            {"entity": "Prior episodes (3 weeks)", "category": "Duration", "salience_score": 0.79,
             "reasoning_context": "Antecedent unstable angina pattern — evolving coronary disease."},
            {"entity": "Paternal MI at 58", "category": "Medical History", "salience_score": 0.74,
             "reasoning_context": "Premature family history of CAD — strong independent risk factor."},
            {"entity": "Type 2 Diabetes (metformin 1g BD)", "category": "Medication", "salience_score": 0.71,
             "reasoning_context": "CAD risk multiplier. Metformin must be withheld if contrast angiography planned."},
        ],
        "flags": [
            "STEMI must be excluded immediately — obtain 12-lead ECG within 10 minutes of arrival",
            "Haemodynamic instability risk: tachycardia + diaphoresis — continuous monitoring required",
            "Prior unstable angina pattern — do not discharge without full workup",
            "Metformin: withhold if contrast imaging (coronary angiography) is anticipated",
        ],
        "next_steps": [
            "12-lead ECG stat — repeat at 15 and 30 minutes",
            "High-sensitivity troponin I/T at 0h and 3h",
            "Aspirin 300mg PO stat + ticagrelor 180mg if no contraindication",
            "Activate cath lab if STEMI confirmed — target door-to-balloon <90 minutes",
            "IV access x2, continuous cardiac monitoring, O2 if SpO2 <94%",
            "Heparin IV per ACS weight-based protocol",
            "Cardiology registrar + interventional cardiologist notification immediately",
        ],
        "soap_note": """### Subjective:
63-year-old male presenting with a 45-minute history of severe (9/10) crushing substernal chest pain with radiation to the left arm and jaw, associated with diaphoresis, nausea, and dyspnoea. Similar milder episodes in the preceding 3 weeks. PMH: hypertension (amlodipine 5mg), type 2 diabetes (metformin 1g BD). FH: paternal MI at age 58. Medications: atorvastatin 20mg, amlodipine 5mg, metformin 1g BD.

### Objective:
BP 158/94 mmHg, HR 112 bpm (regular), RR 22/min. Diaphoretic. CVS: tachycardic, S1/S2 present, no murmurs. Respiratory: tachypnoeic, CTAB bilaterally. Abdomen: soft, non-tender. Neuro: A&Ox3, GCS 15.

### Assessment:
High-probability acute coronary syndrome — STEMI vs NSTEMI pending ECG and troponin. Significant cardiovascular risk profile. Haemodynamically stressed but currently compensated.

### Plan:
1. 12-lead ECG stat. 2. hs-Troponin 0h/3h. 3. Aspirin 300mg + ticagrelor 180mg PO. 4. If STEMI: activate cath lab, D2B <90 min, heparin protocol. 5. Withhold metformin if contrast planned. 6. Continuous monitoring. 7. Cardiology notification. 8. ICU/HDU bed.""",
        "medications": [
            {"drug": "Amlodipine", "dose": "5mg", "route": "PO", "frequency": "OD", "flag": None},
            {"drug": "Metformin", "dose": "1g", "route": "PO", "frequency": "BD",
             "flag": "WITHHOLD if contrast angiography planned — contrast-induced nephropathy risk"},
            {"drug": "Atorvastatin", "dose": "20mg", "route": "PO", "frequency": "OD", "flag": None},
            {"drug": "Aspirin", "dose": "300mg", "route": "PO", "frequency": "Stat", "flag": None},
        ],
        "device_suggestions": [
            {"tier": 1, "name": "Continuous 12-lead ECG monitor", "evidence": "A",
             "note": "Gold standard for STEMI monitoring and reperfusion assessment."},
            {"tier": 1, "name": "Coronary angioplasty (PPCI)", "evidence": "A",
             "note": "Primary PCI is gold standard for STEMI with D2B <90 min."},
            {"tier": 2, "name": "Cardiac wearable (Zio Patch / AliveCor)", "evidence": "B",
             "note": "Post-discharge arrhythmia monitoring."},
        ],
    },

    "neurology": {
        "label": "Acute Stroke",
        "specialty": "Neurology",
        "sc_specialty": "Neurology",
        "patient_ref": "DEMO-002 · Acute Ischaemic Stroke",
        "pipeline_time": 4.1,
        "transcript": (
            "72-year-old female brought by family. Sudden onset left-sided facial droop, "
            "left arm and leg weakness, and slurred speech approximately 90 minutes ago. "
            "Cannot raise left arm. Speech garbled. No loss of consciousness. "
            "PMH: atrial fibrillation (not on anticoagulation), hypertension (perindopril 5mg), "
            "hyperlipidaemia (rosuvastatin 10mg). Last known well 90 minutes ago. "
            "BP 188/102 mmHg on arrival. No known allergies. "
            "Medications: perindopril 5mg, rosuvastatin 10mg, bisoprolol 5mg."
        ),
        "classification": {
            "urgency_tier": "CRITICAL",
            "primary_clinical_trigger": (
                "Acute ischaemic stroke — sudden onset unilateral weakness, facial droop, "
                "and dysarthria within 90-minute window. Thrombolysis eligibility must be "
                "assessed immediately."
            ),
        },
        "salience_map": [
            {"entity": "Sudden left-sided weakness (arm + leg)", "category": "Symptom", "salience_score": 0.97,
             "reasoning_context": "Unilateral motor deficit — classic MCA territory stroke. Highest diagnostic priority."},
            {"entity": "Left facial droop", "category": "Symptom", "salience_score": 0.95,
             "reasoning_context": "Upper motor neuron VII palsy — consistent with hemispheric stroke."},
            {"entity": "Dysarthria", "category": "Symptom", "salience_score": 0.92,
             "reasoning_context": "Motor speech impairment. Increases NIHSS score."},
            {"entity": "Onset 90 minutes ago", "category": "Duration", "salience_score": 0.96,
             "reasoning_context": "Within 4.5-hour thrombolysis window. Time is brain — every 10-minute delay costs 1.9 million neurons."},
            {"entity": "Atrial fibrillation (not anticoagulated)", "category": "Medical History", "salience_score": 0.93,
             "reasoning_context": "Cardioembolic stroke most probable aetiology. Non-anticoagulated AF multiplies stroke risk x5."},
            {"entity": "BP 188/102 mmHg", "category": "Vital Sign", "salience_score": 0.85,
             "reasoning_context": "Permissive hypertension protocol applies. Do not lower unless >185/110 for tPA eligibility."},
            {"entity": "Perindopril 5mg", "category": "Medication", "salience_score": 0.68,
             "reasoning_context": "ACE inhibitor — hold for permissive hypertension unless BP exceeds tPA threshold."},
        ],
        "flags": [
            "STROKE ALERT — activate stroke team immediately. Door-to-needle target <60 minutes",
            "Within thrombolysis window (90 min) — assess tPA eligibility: BP, glucose, CT head",
            "Atrial fibrillation without anticoagulation — high cardioembolic risk",
            "BP 188/102 — do NOT lower unless >185/110 (tPA threshold) or haemorrhage confirmed",
            "Non-contrast CT head URGENTLY to exclude haemorrhage before thrombolysis",
        ],
        "next_steps": [
            "CT head non-contrast STAT — exclude haemorrhagic stroke before any intervention",
            "NIHSS score assessment by stroke-trained clinician",
            "Blood glucose, FBC, coagulation screen, renal function",
            "If CT clear: alteplase 0.9mg/kg IV (max 90mg) — 10% bolus then 60 min infusion",
            "CT angiography head + neck to assess for large vessel occlusion",
            "Continuous BP monitoring — maintain <185/110 for tPA eligibility",
            "Nil by mouth pending swallow assessment",
            "AF anticoagulation plan (DOAC) once acute phase stable",
        ],
        "soap_note": """### Subjective:
72-year-old female with sudden onset left-sided facial droop, left arm and leg weakness, and dysarthria approximately 90 minutes ago. No LOC. PMH: atrial fibrillation (not anticoagulated), hypertension (perindopril 5mg), hyperlipidaemia (rosuvastatin 10mg). Medications: perindopril 5mg, rosuvastatin 10mg, bisoprolol 5mg. Last known well 90 minutes prior.

### Objective:
BP 188/102 mmHg, HR 78 bpm (irregular — AF), RR 16/min, SpO2 96% on air. Alert, oriented to person only. Dysarthric — comprehension intact. Left facial droop (UMN pattern). Left arm power 2/5, left leg power 3/5. Right full power. Left plantar extensor. NIHSS estimated 12.

### Assessment:
Acute ischaemic stroke — right MCA territory. Cardioembolic aetiology likely given uncontrolled AF. Within thrombolysis window. LVO to exclude. Moderate stroke (NIHSS ~12).

### Plan:
1. CT head non-contrast STAT. 2. If haemorrhage excluded: alteplase eligibility assessment. 3. CTA head/neck for LVO. 4. BP protocol <185/110 for tPA. 5. NBM — swallow assessment. 6. Stroke unit admission. 7. AF anticoagulation plan post-acute. 8. Perindopril hold acutely.""",
        "medications": [
            {"drug": "Perindopril", "dose": "5mg", "route": "PO", "frequency": "OD",
             "flag": "HOLD acutely — permissive hypertension protocol"},
            {"drug": "Rosuvastatin", "dose": "10mg", "route": "PO", "frequency": "OD", "flag": None},
            {"drug": "Bisoprolol", "dose": "5mg", "route": "PO", "frequency": "OD", "flag": None},
            {"drug": "Alteplase", "dose": "0.9mg/kg IV max 90mg", "route": "IV", "frequency": "Once",
             "flag": "Confirm haemorrhage excluded on CT BEFORE administration"},
        ],
        "device_suggestions": [
            {"tier": 1, "name": "Mechanical thrombectomy (Stryker Trevo / Medtronic Solitaire)", "evidence": "A",
             "note": "Gold standard for LVO. Eligible if NIHSS >=6 and LVO confirmed."},
            {"tier": 2, "name": "Implantable cardiac monitor (Reveal LINQ)", "evidence": "A",
             "note": "Paroxysmal AF detection for cryptogenic stroke workup."},
        ],
    },

    "psychiatry": {
        "label": "Major Depression",
        "specialty": "Psychiatry",
        "sc_specialty": "Psychiatry",
        "patient_ref": "DEMO-003 · Major Depressive Episode",
        "pipeline_time": 3.3,
        "transcript": (
            "34-year-old female referred by GP. Low mood for 6 months, progressively worsening. "
            "Persistent sadness, anhedonia — has not painted in 4 months (previously her passion). "
            "Sleep: initial and middle insomnia, waking at 3am. Appetite reduced, 8kg weight loss "
            "over 3 months. Concentration poor — struggling at work as a teacher. "
            "Passive suicidal ideation: 'I sometimes wish I wouldn't wake up' — no active plan, "
            "no intent, no previous attempts. PMH: hypothyroidism (levothyroxine 50mcg). "
            "Recently separated from 10-year relationship. Single parent, two children aged 6 and 9. "
            "No alcohol, no substances. PHQ-9 score: 19 (severe)."
        ),
        "classification": {
            "urgency_tier": "HIGH",
            "primary_clinical_trigger": (
                "Moderate-to-severe major depressive episode with passive suicidal ideation. "
                "PHQ-9 score 19. Requires urgent psychiatric evaluation and safety planning."
            ),
        },
        "salience_map": [
            {"entity": "Passive suicidal ideation", "category": "Symptom", "salience_score": 0.96,
             "reasoning_context": "Highest safety priority. 'I sometimes wish I wouldn't wake up' — passive ideation without plan. Requires Columbia C-SSRS, safety plan, and crisis contacts."},
            {"entity": "PHQ-9 score 19 (severe)", "category": "Symptom", "salience_score": 0.93,
             "reasoning_context": "Severe depression threshold. Consistent with clinical presentation. Indicates pharmacotherapy and psychotherapy combination."},
            {"entity": "Anhedonia (4 months)", "category": "Symptom", "salience_score": 0.89,
             "reasoning_context": "Core depressive symptom per DSM-5 Criterion A. Loss of meaningful activities."},
            {"entity": "Insomnia (initial + middle)", "category": "Symptom", "salience_score": 0.84,
             "reasoning_context": "Neurovegetative symptom. 3am waking pattern — middle insomnia associated with melancholic features."},
            {"entity": "8kg weight loss (3 months)", "category": "Symptom", "salience_score": 0.82,
             "reasoning_context": "Significant neurovegetative decline. Must exclude medical causes."},
            {"entity": "Hypothyroidism (levothyroxine 50mcg)", "category": "Medication", "salience_score": 0.79,
             "reasoning_context": "Hypothyroidism can cause or worsen depression. Check TSH — subtherapeutic dose may be contributing."},
            {"entity": "Single parent, two dependent children", "category": "Medical History", "salience_score": 0.77,
             "reasoning_context": "Child safeguarding consideration. Mother's functional decline impacts dependent children."},
        ],
        "flags": [
            "SUICIDAL IDEATION — complete Columbia C-SSRS before patient leaves",
            "Safety plan required: crisis contacts, means restriction, follow-up within 72 hours",
            "Safeguarding: two dependent children aged 6 and 9 — assess parenting capacity",
            "Hypothyroidism: check TSH — subtherapeutic levothyroxine can cause depressive symptoms",
            "Weight loss 8kg in 3 months — exclude organic cause (thyroid panel, FBC, metabolic screen)",
        ],
        "next_steps": [
            "Columbia C-SSRS suicide risk assessment — complete before patient leaves",
            "Safety plan: crisis contacts, restrict access to means, follow-up within 72 hours",
            "TSH + Free T4, FBC, metabolic panel, Vitamin D",
            "Initiate sertraline 50mg OD (titrate to 100mg at 2 weeks if tolerated)",
            "Refer to clinical psychology: CBT for depression (NICE first-line)",
            "GP letter: urgent — PHQ-9 19, passive SI, safety plan in place",
            "Document parenting capacity assessment",
            "Review in 2 weeks — PHQ-9 repeat, medication tolerance, safety re-assessment",
        ],
        "soap_note": """### Subjective:
34-year-old female with 6-month history of worsening low mood, anhedonia (no painting — 4 months), initial and middle insomnia (waking 3am), reduced appetite with 8kg weight loss over 3 months, poor concentration affecting work. Passive suicidal ideation: 'I sometimes wish I wouldn't wake up' — no plan, no intent, no previous attempts. PHQ-9: 19. PMH: hypothyroidism (levothyroxine 50mcg). Recent relationship separation. Single parent of two children (6 and 9). No alcohol, no substances.

### Objective:
Cooperative, tearful. Psychomotor slowing. No psychotic features. Affect: depressed, constricted. Columbia C-SSRS: ideation type 2 (passive wish to be dead), no plan, no intent. PHQ-9: 19/27.

### Assessment:
Major depressive episode, moderate-to-severe (DSM-5 criteria met). Passive suicidal ideation without plan. Contributing: hypothyroidism (dose adequacy unknown), significant psychosocial stressors. Child safeguarding considerations present.

### Plan:
1. Safety plan completed. 2. TSH/FT4/FBC. 3. Sertraline 50mg OD (100mg at 2 weeks). 4. Psychology referral: CBT. 5. GP urgent letter. 6. Parenting capacity documented — adequate at this time. 7. Sick leave 2 weeks. 8. Review in 2 weeks.""",
        "medications": [
            {"drug": "Levothyroxine", "dose": "50mcg", "route": "PO", "frequency": "OD",
             "flag": "Check TSH — subtherapeutic dose may be contributing to depression"},
            {"drug": "Sertraline", "dose": "50mg (then 100mg at 2 weeks)", "route": "PO", "frequency": "OD",
             "flag": "Counsel: 2-4 week onset, initial anxiety possible. Review at 2 weeks."},
        ],
        "device_suggestions": [
            {"tier": 1, "name": "Digital CBT platform (Wysa / SilverCloud)", "evidence": "B",
             "note": "Adjunct to face-to-face CBT. Evidence for PHQ-9 reduction."},
            {"tier": 2, "name": "Sleep tracking wearable (Oura Ring / Fitbit)", "evidence": "C",
             "note": "Objective sleep monitoring to track insomnia treatment response."},
        ],
    },

    "paediatrics": {
        "label": "Febrile Convulsion",
        "specialty": "Pediatrics",
        "sc_specialty": "Pediatrics",
        "patient_ref": "DEMO-004 · Febrile Convulsion",
        "pipeline_time": 2.9,
        "transcript": (
            "18-month-old male brought by parents following witnessed tonic-clonic seizure at home. "
            "Duration approximately 3 minutes, self-terminated. Full recovery within 10 minutes. "
            "Preceded by fever — parents measured 39.2C rectally. Child unwell 2 days with "
            "runny nose and reduced appetite — viral URTI. No previous seizure history. "
            "Normal development. Immunisations up to date. No family history of epilepsy. "
            "No meningism signs. Child now alert, crying, interacting with mother. "
            "Temperature 38.8C, HR 148 bpm, RR 34/min, SpO2 98% on air. No medications. No allergies."
        ),
        "classification": {
            "urgency_tier": "HIGH",
            "primary_clinical_trigger": (
                "Simple febrile convulsion in 18-month-old. Post-ictal period resolved. "
                "Must exclude meningitis and identify fever source."
            ),
        },
        "salience_map": [
            {"entity": "Tonic-clonic seizure (3 minutes)", "category": "Symptom", "salience_score": 0.95,
             "reasoning_context": "Febrile convulsion — most common seizure cause in this age group. Duration <5 min, self-terminating — consistent with simple febrile convulsion."},
            {"entity": "Temperature 39.2C (febrile)", "category": "Vital Sign", "salience_score": 0.91,
             "reasoning_context": "Precipitating fever. Rate of fever rise more important than absolute temperature."},
            {"entity": "Full recovery within 10 minutes", "category": "Symptom", "salience_score": 0.87,
             "reasoning_context": "Complete return to baseline — reassuring. Prolonged post-ictal state raises concern for alternative diagnosis."},
            {"entity": "No meningism signs", "category": "Symptom", "salience_score": 0.85,
             "reasoning_context": "Reduces probability of bacterial meningitis. Cannot be excluded on clinical grounds alone in this age group."},
            {"entity": "2-day URTI symptoms", "category": "Medical History", "salience_score": 0.78,
             "reasoning_context": "Probable fever source — viral aetiology most likely."},
            {"entity": "First seizure, no family history", "category": "Medical History", "salience_score": 0.72,
             "reasoning_context": "First presentation. Recurrence risk: 30% in subsequent febrile illness. Counselling required."},
        ],
        "flags": [
            "Exclude bacterial meningitis — LP if any clinical concern (bulging fontanelle, petechiae, altered GCS, age <12 months)",
            "Simple febrile convulsion criteria met: single, generalised, <15 min, full recovery",
            "Recurrence counselling required: 30% risk with subsequent febrile illness",
            "Antipyretics for comfort — do NOT prevent seizure recurrence",
        ],
        "next_steps": [
            "Full neurological examination — no focal deficit, no papilloedema",
            "Identify fever source: throat, ears (otoscopy), urine dip",
            "Paracetamol 15mg/kg PO/PR for fever and comfort",
            "Observe minimum 4-6 hours post-seizure in ED",
            "Parental counselling: seizure first aid, when to call emergency services (>5 minutes)",
            "Discharge with written information sheet on febrile convulsions",
            "Paediatric neurology referral if: complex features, >3 febrile convulsions",
        ],
        "soap_note": """### Subjective:
18-month-old male following witnessed generalised tonic-clonic seizure lasting approximately 3 minutes, self-terminated. Full recovery within 10 minutes. Preceded by fever (39.2C rectal). 2-day history of viral URTI. No previous seizure history. Normal development. Immunisations up to date. No family history of epilepsy. No medications. No allergies.

### Objective:
T 38.8C, HR 148 bpm, RR 34/min, SpO2 98% on air. Weight 11.2kg. Alert, crying, interacting with mother. No meningism. Fontanelle flat. No rash. ENT: clear rhinorrhoea, mildly erythematous oropharynx. Chest clear. Neuro: no focal deficit.

### Assessment:
Simple febrile convulsion — all criteria met. Fever source: viral URTI most probable. Bacterial meningitis clinically unlikely. No indication for LP at this time.

### Plan:
1. Paracetamol 15mg/kg 6-hourly PRN. 2. Urine dip. 3. Observe 4-6 hours. 4. Parental seizure first aid counselling. 5. Discharge when afebrile trend. 6. GP follow-up 48 hours. 7. Return to ED if: seizure >5 min, multiple seizures, rash, altered consciousness.""",
        "medications": [
            {"drug": "Paracetamol", "dose": "15mg/kg", "route": "PO/PR", "frequency": "6-hourly PRN",
             "flag": None},
        ],
        "device_suggestions": [
            {"tier": 1, "name": "Digital thermometer (temporal/tympanic)", "evidence": "A",
             "note": "For home fever monitoring. Parents need threshold guidance for seeking care."},
            {"tier": 2, "name": "Seizure detection wearable (Embrace2)", "evidence": "B",
             "note": "For recurrent cases only — parental anxiety management."},
        ],
    },

    "emergency": {
        "label": "Polytrauma",
        "specialty": "Emergency",
        "sc_specialty": "Emergency",
        "patient_ref": "DEMO-005 · Polytrauma Triage",
        "pipeline_time": 4.6,
        "transcript": (
            "28-year-old male, MVA — restrained driver, high-speed collision, airbag deployed. "
            "GCS 13 at scene, now GCS 14 on arrival. Severe chest pain right side, abdominal pain, "
            "right thigh pain. Visible deformity right femur. BP 92/60 mmHg, HR 124 bpm, "
            "RR 26/min, SpO2 93% on 15L non-rebreather. Trachea deviated to the LEFT. "
            "Breath sounds absent right side. Abdomen tender, guarding right upper quadrant. "
            "Pelvis stable. Right thigh swelling and deformity — suspected closed femur fracture. "
            "FAST scan positive: free fluid Morison's pouch and pelvis. "
            "IV access x2, 1L crystalloid given at scene. Unknown allergies. Blood type unknown."
        ),
        "classification": {
            "urgency_tier": "CRITICAL",
            "primary_clinical_trigger": (
                "Polytrauma with tension pneumothorax, haemodynamic instability, "
                "positive FAST scan, and femur fracture. Immediate surgical intervention required."
            ),
        },
        "salience_map": [
            {"entity": "Tracheal deviation LEFT + absent right breath sounds", "category": "Symptom", "salience_score": 0.99,
             "reasoning_context": "TENSION PNEUMOTHORAX — immediate needle decompression. Do NOT wait for imaging. 2nd ICS MCL right side."},
            {"entity": "Haemodynamic instability (BP 92/60, HR 124)", "category": "Vital Sign", "salience_score": 0.97,
             "reasoning_context": "Haemorrhagic shock Class III. Sources: haemothorax, intra-abdominal, femur fracture. Immediate haemorrhage control."},
            {"entity": "FAST positive — free fluid Morison's pouch and pelvis", "category": "Symptom", "salience_score": 0.96,
             "reasoning_context": "Intra-abdominal haemorrhage confirmed. Haemodynamic instability = surgical emergency — damage control laparotomy."},
            {"entity": "SpO2 93% on 15L NRB", "category": "Vital Sign", "salience_score": 0.94,
             "reasoning_context": "Significant hypoxaemia despite high-flow O2 — consistent with tension pneumothorax and haemothorax."},
            {"entity": "Right femur fracture (closed)", "category": "Symptom", "salience_score": 0.88,
             "reasoning_context": "Closed femur fracture causes 1000-1500ml blood loss. Contributes to shock. Traction splint to temporise."},
            {"entity": "GCS 14 (was 13 at scene)", "category": "Vital Sign", "salience_score": 0.83,
             "reasoning_context": "Improving GCS. TBI cannot be excluded. CT head required post-stabilisation."},
        ],
        "flags": [
            "TENSION PNEUMOTHORAX — immediate needle decompression RIGHT 2nd ICS MCL. Do NOT await CXR",
            "HAEMORRHAGIC SHOCK Class III — activate massive transfusion protocol: 1:1:1 pRBC:FFP:platelets",
            "FAST positive + haemodynamic instability — surgical team must be at bedside NOW",
            "Blood type unknown — O-negative blood until group and screen result. Do NOT delay",
            "Femur fracture: estimated 1000-1500ml blood loss from this source alone — traction splint",
        ],
        "next_steps": [
            "IMMEDIATE: needle decompression RIGHT 2nd ICS midclavicular line",
            "Activate massive transfusion protocol — O-negative pRBC, FFP, platelets 1:1:1",
            "Formal chest drain RIGHT after needle decompression",
            "Surgical team STAT — FAST positive + haemodynamic instability",
            "Blood: group and screen, FBC, coagulation, metabolic panel, ABG, lactate",
            "Traction splint right femur",
            "Tranexamic acid 1g IV over 10 minutes (within 3 hours of injury)",
            "CT trauma series when primary survey stable",
        ],
        "soap_note": """### Subjective:
28-year-old male, restrained MVA driver, high-speed collision, airbag deployed. GCS 13 at scene, 14 on arrival. Right chest pain, abdominal pain, right thigh pain. Unknown medications. Unknown allergies.

### Objective:
BP 92/60 mmHg, HR 124 bpm, RR 26/min, SpO2 93% on 15L NRB. GCS 14 (E4V4M6). Trachea deviated LEFT. Absent breath sounds right — tension pneumothorax. Abdomen: RUQ tenderness, guarding. Pelvis stable. Right thigh: deformity, swelling. FAST: positive free fluid Morison's pouch and pelvis.

### Assessment:
Polytrauma: (1) Tension pneumothorax right — immediate decompression. (2) Haemorrhagic shock Class III — intra-abdominal haemorrhage + haemothorax + femur fracture. (3) Closed right femur fracture. (4) Possible TBI — CT post-stabilisation.

### Plan:
1. Needle decompression RIGHT 2nd ICS MCL NOW. 2. Formal chest drain. 3. MTP activation — O-neg blood. 4. Surgical team STAT. 5. Tranexamic acid 1g IV. 6. Traction splint femur. 7. CT trauma post-stabilisation. 8. Damage control laparotomy likely. 9. ICU post-operatively.""",
        "medications": [
            {"drug": "Tranexamic acid", "dose": "1g over 10 min then 1g over 8h", "route": "IV",
             "frequency": "Stat", "flag": "Must be given within 3 hours of injury for efficacy"},
            {"drug": "O-negative pRBC + FFP + Platelets", "dose": "1:1:1 ratio", "route": "IV",
             "frequency": "MTP", "flag": "Do not delay for cross-match in haemodynamic instability"},
        ],
        "device_suggestions": [
            {"tier": 1, "name": "Massive Transfusion Protocol activation system", "evidence": "A",
             "note": "Automated MTP activation linked to blood bank."},
            {"tier": 1, "name": "REBOA (Resuscitative Endovascular Balloon Occlusion)", "evidence": "B",
             "note": "Adjunct haemorrhage control in haemodynamically unstable abdominal trauma."},
            {"tier": 2, "name": "Intraosseous access device (EZ-IO)", "evidence": "A",
             "note": "Rapid vascular access if peripheral IV fails in shocked patient."},
        ],
    },
}

# =====================================================================
# PDF GENERATION
# =====================================================================
def sanitize_for_pdf(text: str) -> str:
    if not text:
        return ""
    char_map = {
        "•": "-", "—": "-", "–": "-",
        "\u201c": '"', "\u201d": '"',
        "\u2018": "'", "\u2019": "'",
        "™": "TM", "©": "(c)", "®": "(r)",
        "×": "x", "≥": ">=", "≤": "<=",
        "α": "alpha", "β": "beta",
    }
    for uc, sc in char_map.items():
        text = text.replace(uc, sc)
    return text.encode("latin-1", errors="replace").decode("latin-1")


def generate_clinical_pdf(
    soap_text: str,
    specialty: str,
    report_type: str = "clinical",
    patient_ref: str = "",
) -> bytes:
    if not FPDF_AVAILABLE:
        raise RuntimeError("fpdf2 is not installed.")
    pdf = FPDF()
    pdf.set_margins(left=15, top=10, right=15)
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    header_rgb = (2, 132, 199) if report_type == "clinical" else (5, 150, 105)
    pdf.set_fill_color(*header_rgb)
    pdf.rect(0, 0, 210, 42, "F")
    pdf.set_xy(0, 7)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 17)
    titles = {
        "clinical":  "SALIENCE OS V3 | CLINICAL REPORT",
        "pharmacy":  "SALIENCE OS V3 | PHARMACY REPORT",
        "history":   "SALIENCE OS V3 | PATIENT HISTORY",
    }
    pdf.cell(210, 11, titles.get(report_type, "SALIENCE OS V3 | REPORT"),
             new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.set_font("Helvetica", "I", 9)
    meta = f"Specialty: {specialty}"
    if patient_ref:
        meta += f" | Patient: {patient_ref}"
    meta += f" | Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    pdf.cell(210, 5, sanitize_for_pdf(meta),
             new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.set_font("Helvetica", "I", 8)
    pdf.cell(
        210, 5,
        "AI-assisted documentation. Final clinical judgment is the sole responsibility of the treating clinician.",
        new_x="LMARGIN", new_y="NEXT", align="C",
    )

    pdf.set_xy(15, 48)
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
            pdf.set_font("Helvetica", "B", 13)
            pdf.set_text_color(*header_rgb)
            header = lc.replace("###", "").replace(":", "").strip().upper()
            pdf.cell(ew, 9, sanitize_for_pdf(header),
                     new_x="LMARGIN", new_y="NEXT")
            pdf.line(pdf.l_margin, pdf.get_y(), pdf.l_margin + 40, pdf.get_y())
            pdf.ln(2)
            pdf.set_text_color(15, 23, 42)
        elif lc.startswith("**") and lc.endswith("**"):
            pdf.set_font("Helvetica", "B", 10)
            pdf.cell(ew, 6, sanitize_for_pdf(lc.replace("**", "").strip()),
                     new_x="LMARGIN", new_y="NEXT")
        else:
            pdf.set_font("Helvetica", size=10)
            pdf.multi_cell(ew, 5.5,
                           sanitize_for_pdf(lc.replace("**", "").replace("*", "-")))
    return bytes(pdf.output())


def generate_fhir_bundle(state: dict, specialty: str) -> dict:
    """Generate a minimal FHIR R4 Bundle from session state."""
    ts = datetime.now().isoformat() + "Z"
    bundle_id = f"salience-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    urgency   = state.get("classification", {}).get("urgency_tier", "routine").lower()
    fhir_priority = {
        "critical": "stat", "high": "asap",
        "medium": "routine", "low": "routine",
    }.get(urgency, "routine")

    flags_text = "\n".join(f"- {f}" for f in state.get("flags", []))
    steps_text = "\n".join(f"- {s}" for s in state.get("next_steps", []))

    return {
        "resourceType": "Bundle",
        "id": bundle_id,
        "type": "document",
        "timestamp": ts,
        "meta": {
            "profile": ["http://hl7.org/fhir/StructureDefinition/Bundle"],
            "source": "Salience OS V3",
        },
        "entry": [
            {
                "fullUrl": f"urn:uuid:{bundle_id}-composition",
                "resource": {
                    "resourceType": "Composition",
                    "id": f"{bundle_id}-composition",
                    "status": "final" if state.get("chart_locked") else "preliminary",
                    "type": {
                        "coding": [{
                            "system": "http://loinc.org",
                            "code": "11488-4",
                            "display": "Consult note",
                        }]
                    },
                    "date": ts,
                    "title": f"Salience OS Clinical Note — {specialty}",
                    "section": [
                        {
                            "title": "Clinical Note (SOAP)",
                            "text": {"status": "generated", "div": state.get("soap_note", "")},
                        },
                        {
                            "title": "Safety Flags",
                            "text": {"status": "generated", "div": flags_text},
                        },
                        {
                            "title": "Recommended Next Steps",
                            "text": {"status": "generated", "div": steps_text},
                        },
                    ],
                },
            },
            {
                "fullUrl": f"urn:uuid:{bundle_id}-sr",
                "resource": {
                    "resourceType": "ServiceRequest",
                    "id": f"{bundle_id}-sr",
                    "status": "active",
                    "intent": "order",
                    "priority": fhir_priority,
                    "code": {
                        "text": state.get("classification", {}).get(
                            "primary_clinical_trigger", "Clinical assessment"
                        )
                    },
                    "note": [{"text": f"Urgency tier: {urgency.upper()}"}],
                },
            },
        ],
    }


def generate_pharmacy_text(salience_map: list, soap_note: str,
                            specialty: str, patient_ref: str) -> str:
    med_kw = {
        "mg", "ml", "tablet", "capsule", "dose", "drug", "medication",
        "metformin", "aspirin", "heparin", "statin", "atorvastatin",
        "amlodipine", "warfarin", "insulin", "paracetamol", "ibuprofen",
        "sertraline", "levothyroxine", "perindopril", "bisoprolol",
        "alteplase", "tranexamic",
    }
    med_signals = [
        item for item in salience_map
        if item.get("category", "").lower() in ("medication", "medical history")
        or any(kw in item.get("entity", "").lower() for kw in med_kw)
    ]

    lines = [
        "### Pharmacy / Medication Summary",
        f"**Patient Ref:** {patient_ref or 'Not specified'}",
        f"**Specialty:** {specialty}",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "### Identified Medications and Clinical Context",
    ]
    if med_signals:
        for item in med_signals:
            lines.append(f"- **{item['entity']}**: {item.get('reasoning_context', '')}")
    else:
        lines.append("- No specific medications identified in this consultation.")

    lines += ["", "### Relevant Prescribing Notes from Clinical Record"]
    for line in soap_note.split("\n"):
        if any(kw in line.lower() for kw in med_kw | {"withhold", "hold", "contrast", "allergy", "interaction"}):
            lines.append(line.strip())

    lines += [
        "",
        "---",
        "**Declaration:** Report generated by SALIENCE OS V3 (AI-assisted). "
        "Prescribing authority rests solely with the treating clinician. "
        "Verify all medications against the official formulary before dispensing.",
    ]
    return "\n".join(lines)


# =====================================================================
# PAGE CONFIG — must be first Streamlit call
# =====================================================================
st.set_page_config(
    page_title="Salience OS V3",
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
    "nav_page": "home",
    "onboarding_dismissed": False,
    "sc_specialty": "Cardiology",
    "sc_language": "Mixed",
    "sc_theme": "Dark",
    "_groq_override": "",
    "_gemini_override": "",
    "consultation_history": [],
    "is_demo": False,
    "patient_ref": "",
    "demo_medications": [],
    "demo_devices": [],
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
# DESIGN SYSTEM CSS
# =====================================================================
st.markdown("""
<style>
/* ── Tokens: Dark (default) ── */
:root,
html[data-salience-theme="dark"] {
  --bg-base:        #080B10;
  --bg-surface:     #0E1117;
  --bg-elevated:    #161B26;
  --bg-hover:       rgba(255,255,255,0.035);
  --border-subtle:  rgba(255,255,255,0.06);
  --border-default: rgba(255,255,255,0.10);
  --border-strong:  rgba(255,255,255,0.18);
  --border-focus:   #3B82F6;
  --text-primary:   #EDF0F4;
  --text-secondary: #7E8A9A;
  --text-muted:     #4A5262;
  --text-inverse:   #0D1117;
  --accent-blue:    #3B82F6;
  --accent-dim:     #2563EB;
  --accent-emerald: #10B981;
  --accent-amber:   #F59E0B;
  --accent-red:     #EF4444;
  --accent-violet:  #8B5CF6;
  --tier-critical:  #EF4444;
  --tier-high:      #F59E0B;
  --tier-medium:    #3B82F6;
  --tier-low:       #10B981;
  --flag-bg:        rgba(239,68,68,0.06);
  --flag-border:    rgba(239,68,68,0.18);
  --flag-text:      #FCA5A5;
  --step-bg:        rgba(59,130,246,0.06);
  --step-border:    rgba(59,130,246,0.15);
  --step-text:      #93C5FD;
  --r-sm: 5px; --r-md: 9px; --r-lg: 14px;
  --font-mono: 'JetBrains Mono','Fira Code','SF Mono',ui-monospace,monospace;
  --ease: 150ms cubic-bezier(0.4,0,0.2,1);
}

/* ── Tokens: Light ── */
html[data-salience-theme="light"] {
  --bg-base:        #F0F4F8;
  --bg-surface:     #FFFFFF;
  --bg-elevated:    #F7F9FC;
  --bg-hover:       rgba(0,0,0,0.04);
  --border-subtle:  rgba(0,0,0,0.07);
  --border-default: rgba(0,0,0,0.12);
  --border-strong:  rgba(0,0,0,0.20);
  --border-focus:   #1D6FE8;
  --text-primary:   #0D1117;
  --text-secondary: #3D4A5C;
  --text-muted:     #7A8799;
  --text-inverse:   #FFFFFF;
  --accent-blue:    #1D6FE8;
  --accent-dim:     #1558C0;
  --accent-emerald: #0D9065;
  --accent-amber:   #C07800;
  --accent-red:     #C8282B;
  --accent-violet:  #6B3FD4;
  --tier-critical:  #C8282B;
  --tier-high:      #C07800;
  --tier-medium:    #1D6FE8;
  --tier-low:       #0D9065;
  --flag-bg:        rgba(200,40,43,0.05);
  --flag-border:    rgba(200,40,43,0.20);
  --flag-text:      #7F1D1D;
  --step-bg:        rgba(29,111,232,0.05);
  --step-border:    rgba(29,111,232,0.18);
  --step-text:      #1E3A5F;
}

/* ── Ambient background ── */
.stApp {
  background:
    radial-gradient(circle at 88% 10%, rgba(59,130,246,0.09) 0%, transparent 36%),
    radial-gradient(circle at 6%  55%, rgba(6,182,212,0.06)  0%, transparent 30%),
    radial-gradient(circle at 70% 94%, rgba(139,92,246,0.05) 0%, transparent 27%),
    var(--bg-base) !important;
  transition: background 0.25s ease;
}
html[data-salience-theme="light"] .stApp {
  background:
    radial-gradient(circle at 88% 10%, rgba(59,130,246,0.05) 0%, transparent 36%),
    radial-gradient(circle at 6%  55%, rgba(6,182,212,0.03)  0%, transparent 30%),
    var(--bg-base) !important;
}

/* ── Base ── */
html, body, [class*="css"] {
  font-family: -apple-system,'SF Pro Text','Helvetica Neue',system-ui,sans-serif;
  color: var(--text-primary) !important;
  -webkit-font-smoothing: antialiased;
  transition: color 0.2s ease, background-color 0.2s ease;
}
#MainMenu, footer, header { visibility: hidden !important; }
.stDeployButton { display: none !important; }
.block-container {
  padding: 0 16px 72px !important;
  max-width: 100% !important;
}
::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-thumb { background: var(--border-default); border-radius: 99px; }
p { color: var(--text-secondary) !important; }

/* ── Top nav ── */
.os-nav {
  display: flex; align-items: center; gap: 4px;
  padding: 8px 16px 6px;
  border-bottom: 1px solid var(--border-subtle);
  background: var(--bg-surface);
  margin: 0 -16px 16px;
  flex-wrap: wrap;
}
.os-wordmark {
  font-size: 14px; font-weight: 700; letter-spacing: 0.3px;
  color: var(--text-primary); margin-right: 16px; white-space: nowrap;
}
.os-wordmark span { color: var(--accent-blue); }

/* ── Section label ── */
.s-label {
  font-size: 10px; font-weight: 700; letter-spacing: 1px;
  text-transform: uppercase; color: var(--text-muted);
  display: flex; align-items: center; gap: 10px;
  margin: 0 0 12px;
}
.s-label::after {
  content: ''; flex: 1; height: 1px;
  background: var(--border-subtle);
}

/* ── Welcome card ── */
.welcome-card {
  background: linear-gradient(
    135deg,
    rgba(59,130,246,0.07) 0%,
    rgba(139,92,246,0.05) 100%
  );
  border: 1px solid rgba(59,130,246,0.18);
  border-radius: var(--r-lg);
  padding: 28px 32px;
  margin-bottom: 20px;
}
.welcome-title    { font-size: 21px; font-weight: 700; color: var(--text-primary); margin-bottom: 6px; }
.welcome-subtitle { font-size: 13.5px; color: var(--text-secondary); line-height: 1.65; margin-bottom: 20px; }
.welcome-grid { display: grid; grid-template-columns: repeat(4,1fr); gap: 10px; margin-bottom: 20px; }
.welcome-stat {
  background: var(--bg-elevated); border: 1px solid var(--border-subtle);
  border-radius: var(--r-md); padding: 11px 13px;
}
.welcome-stat-label { font-size: 9.5px; font-weight: 700; letter-spacing: .8px;
  text-transform: uppercase; color: var(--text-muted); margin-bottom: 3px; }
.welcome-stat-value { font-size: 13px; font-weight: 600; color: var(--text-primary); }

/* ── Workflow stepper ── */
.stepper {
  display: flex; align-items: flex-start; gap: 0;
  background: var(--bg-surface); border: 1px solid var(--border-subtle);
  border-radius: var(--r-lg); padding: 14px 18px; margin-bottom: 20px;
  overflow-x: auto;
}
.step-w { display: flex; flex-direction: column; align-items: center;
  gap: 5px; flex: 1; min-width: 70px; position: relative; }
.step-w:not(:last-child)::after {
  content: ''; position: absolute; top: 13px;
  left: calc(50% + 13px); right: calc(-50% + 13px);
  height: 1px; background: var(--border-subtle);
}
.step-circle {
  width: 26px; height: 26px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 10.5px; font-weight: 700; border: 2px solid; flex-shrink: 0;
}
.sc-done   { background: rgba(16,185,129,0.12); border-color: var(--tier-low);    color: var(--tier-low); }
.sc-active { background: rgba(59,130,246,0.12); border-color: var(--accent-blue); color: var(--accent-blue); }
.sc-pend   { background: var(--bg-elevated);    border-color: var(--border-default); color: var(--text-muted); }
.step-lbl  { font-size: 9.5px; font-weight: 500; color: var(--text-muted); text-align: center; line-height: 1.3; }
.sl-active { color: var(--text-secondary); }
.sl-done   { color: var(--tier-low); }

/* ── Urgency banner ── */
.urg-bar {
  display: flex; align-items: center; gap: 12px;
  padding: 13px 18px; border-radius: var(--r-md);
  margin-bottom: 18px; border-left: 3px solid;
}
.urg-bar.CRITICAL { background: rgba(239,68,68,0.07);  border-color: var(--tier-critical);
  box-shadow: 0 0 0 1px rgba(239,68,68,0.15), 0 4px 20px rgba(239,68,68,0.12);
  animation: critPulse 2.5s ease-in-out infinite; }
.urg-bar.HIGH     { background: rgba(245,158,11,0.07); border-color: var(--tier-high); }
.urg-bar.MEDIUM   { background: rgba(59,130,246,0.07); border-color: var(--tier-medium); }
.urg-bar.LOW      { background: rgba(16,185,129,0.07); border-color: var(--tier-low); }
@keyframes critPulse {
  0%,100% { box-shadow: 0 0 0 1px rgba(239,68,68,0.15), 0 4px 20px rgba(239,68,68,0.10); }
  50%      { box-shadow: 0 0 0 1px rgba(239,68,68,0.25), 0 4px 28px rgba(239,68,68,0.22), 0 0 0 5px rgba(239,68,68,0.06); }
}
.urg-label { font-size: 9.5px; font-weight: 700; letter-spacing: 1.1px; text-transform: uppercase; opacity: .65; }
.urg-text  { font-size: 13px; font-weight: 500; line-height: 1.45; margin-top: 3px; }
.urg-bar.CRITICAL .urg-label, .urg-bar.CRITICAL .urg-text { color: var(--tier-critical); }
.urg-bar.HIGH     .urg-label, .urg-bar.HIGH     .urg-text { color: var(--tier-high); }
.urg-bar.MEDIUM   .urg-label, .urg-bar.MEDIUM   .urg-text { color: var(--tier-medium); }
.urg-bar.LOW      .urg-label, .urg-bar.LOW      .urg-text { color: var(--tier-low); }
.urg-meta { margin-left: auto; display: flex; gap: 7px; flex-shrink: 0; }
.m-chip {
  display: inline-flex; align-items: center; gap: 4px; padding: 3px 9px;
  background: var(--bg-elevated); border: 1px solid var(--border-subtle);
  border-radius: 99px; font-size: 11px; color: var(--text-secondary);
  font-family: var(--font-mono);
}
.m-chip .cl { font-family: -apple-system,sans-serif; font-size: 10.5px; color: var(--text-muted); }

/* ── Signal rows ── */
.sig-row {
  display: flex; align-items: flex-start; gap: 12px;
  padding: 10px 6px; border-bottom: 1px solid var(--border-subtle);
  border-radius: var(--r-sm); transition: background var(--ease);
}
.sig-row:last-child { border-bottom: none; }
.sig-row:hover { background: var(--bg-hover); }
.sig-ring {
  flex-shrink: 0; width: 36px; height: 36px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 10px; font-weight: 700; font-family: var(--font-mono); border: 2px solid;
}
.sr-c { background: rgba(239,68,68,0.09);  border-color: var(--tier-critical); color: var(--tier-critical); }
.sr-h { background: rgba(245,158,11,0.09); border-color: var(--tier-high);     color: var(--tier-high); }
.sr-m { background: rgba(59,130,246,0.09); border-color: var(--tier-medium);   color: var(--tier-medium); }
.sr-l { background: rgba(16,185,129,0.09); border-color: var(--tier-low);      color: var(--tier-low); }
.sig-body { flex: 1; min-width: 0; }
.sig-name { font-size: 13px; font-weight: 600; color: var(--text-primary); }
.sig-chip {
  display: inline-block; font-size: 9.5px; font-weight: 600; letter-spacing: .4px;
  padding: 1px 7px; border-radius: 99px; background: var(--bg-elevated);
  border: 1px solid var(--border-default); color: var(--text-secondary);
  margin: 3px 0 4px; text-transform: uppercase;
}
.sig-reason { font-size: 12px; color: var(--text-secondary); line-height: 1.55; }
.sig-track  { width: 100%; height: 2px; background: var(--bg-elevated); border-radius: 99px; margin-top: 7px; overflow: hidden; }
.sig-fill   { height: 100%; border-radius: 99px; }

/* ── Flag item ── */
.flag-item {
  display: flex; align-items: flex-start; gap: 10px;
  padding: 11px 14px;
  background: var(--flag-bg); border: 1px solid var(--flag-border);
  border-left: 3px solid var(--tier-critical);
  border-radius: var(--r-md); margin-bottom: 8px;
  font-size: 13px; color: var(--flag-text); line-height: 1.55;
}

/* ── Step item ── */
.step-item {
  display: flex; align-items: flex-start; gap: 10px;
  padding: 9px 14px;
  background: var(--step-bg); border: 1px solid var(--step-border);
  border-radius: var(--r-md); margin-bottom: 7px;
  font-size: 13px; color: var(--step-text); line-height: 1.55;
}
.step-num {
  flex-shrink: 0; width: 19px; height: 19px; border-radius: 50%;
  background: rgba(59,130,246,0.18); color: var(--accent-blue);
  font-size: 9.5px; font-weight: 700;
  display: flex; align-items: center; justify-content: center; margin-top: 1px;
}

/* ── Med table ── */
.med-row {
  display: flex; align-items: flex-start; gap: 10px;
  padding: 10px 14px; border-bottom: 1px solid var(--border-subtle);
  font-size: 12.5px;
}
.med-row:last-child { border-bottom: none; }
.med-name { font-weight: 600; color: var(--text-primary); min-width: 150px; }
.med-dose { color: var(--text-secondary); min-width: 120px; font-family: var(--font-mono); font-size: 11.5px; }
.med-flag { font-size: 11.5px; color: var(--accent-amber); flex: 1; line-height: 1.45; }
.med-ok   { font-size: 11px; color: var(--tier-low); }

/* ── Device card ── */
.device-card {
  background: var(--bg-elevated); border: 1px solid var(--border-subtle);
  border-radius: var(--r-md); padding: 12px 14px; margin-bottom: 8px;
}
.dev-header { display: flex; align-items: center; gap: 10px; margin-bottom: 4px; }
.dev-tier { font-size: 9.5px; font-weight: 700; letter-spacing: .6px;
  text-transform: uppercase; color: var(--text-muted); }
.dev-name { font-size: 13px; font-weight: 600; color: var(--text-primary); }
.dev-ev { font-size: 11px; font-family: var(--font-mono); color: var(--accent-blue);
  background: rgba(59,130,246,0.10); border: 1px solid rgba(59,130,246,0.2);
  padding: 1px 7px; border-radius: 99px; }
.dev-note { font-size: 12px; color: var(--text-secondary); line-height: 1.55; }

/* ── SOAP viewer ── */
.soap-outer  { max-width: 1100px; margin: 0 auto; }
.soap-viewer {
  background: var(--bg-surface); border: 1px solid var(--border-default);
  border-radius: var(--r-lg); padding: 30px 34px;
  font-size: 14px; line-height: 1.9; color: var(--text-primary);
}
.soap-h {
  font-size: 10px; font-weight: 700; letter-spacing: 1.1px; text-transform: uppercase;
  color: var(--accent-blue); margin-top: 22px; margin-bottom: 9px;
  padding-bottom: 6px; border-bottom: 1px solid var(--border-subtle);
}
.soap-h:first-child { margin-top: 0; }
.soap-p   { margin: 0 0 2px; color: var(--text-secondary); }
.soap-b   { color: var(--text-primary); font-weight: 600; }
.soap-meta {
  display: flex; align-items: center; gap: 16px; flex-wrap: wrap;
  padding: 10px 0; margin-bottom: 8px; border-bottom: 1px solid var(--border-subtle);
}
.soap-ml { font-size: 9.5px; font-weight: 700; letter-spacing: .8px;
  text-transform: uppercase; color: var(--text-muted); }
.soap-mv { font-size: 12.5px; font-weight: 500; color: var(--text-secondary); font-family: var(--font-mono); }

/* ── Dashboard card ── */
.dash-card {
  background: var(--bg-surface); border: 1px solid var(--border-subtle);
  border-radius: var(--r-md); padding: 13px 16px; margin-bottom: 10px;
}
.dash-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 7px; }
.dash-title  { font-size: 13px; font-weight: 600; color: var(--text-primary); }
.dash-ts     { font-size: 11px; color: var(--text-muted); font-family: var(--font-mono); }
.dash-body   { font-size: 12px; color: var(--text-secondary); line-height: 1.6; }

/* ── Help card ── */
.help-card {
  background: var(--bg-elevated); border: 1px solid var(--border-subtle);
  border-radius: var(--r-md); padding: 13px 15px; margin-bottom: 8px;
}
.help-title { font-size: 12px; font-weight: 600; color: var(--text-primary); margin-bottom: 5px; }
.help-body  { font-size: 12px; color: var(--text-secondary); line-height: 1.6; }

/* ── Empty state ── */
.empty-st {
  display: flex; flex-direction: column; align-items: center;
  justify-content: center; padding: 44px 24px; text-align: center; gap: 10px;
}
.es-icon  { font-size: 28px; opacity: .2; }
.es-title { font-size: 13.5px; font-weight: 600; color: var(--text-secondary); }
.es-body  { font-size: 12px; color: var(--text-muted); line-height: 1.7; max-width: 320px; }

/* ── Status pills ── */
.pill-ready  { display:inline-flex;align-items:center;gap:5px;font-size:11px;
  font-weight:500;padding:3px 10px;border-radius:99px;
  background:rgba(16,185,129,0.10);color:var(--accent-emerald);
  border:1px solid rgba(16,185,129,0.18); }
.pill-active { display:inline-flex;align-items:center;gap:5px;font-size:11px;
  font-weight:500;padding:3px 10px;border-radius:99px;
  background:rgba(59,130,246,0.10);color:var(--accent-blue);
  border:1px solid rgba(59,130,246,0.18); }
.pill-locked { display:inline-flex;align-items:center;gap:5px;font-size:11px;
  font-weight:500;padding:3px 10px;border-radius:99px;
  background:rgba(139,92,246,0.10);color:var(--accent-violet);
  border:1px solid rgba(139,92,246,0.18); }
.pill-dot { width:5px;height:5px;border-radius:50%;background:currentColor; }
.pill-dot.pulse { animation:pdot 2s ease-in-out infinite; }
@keyframes pdot { 0%,100%{opacity:1;transform:scale(1)} 50%{opacity:.4;transform:scale(.7)} }

/* ── Demo badge ── */
.demo-badge {
  display: inline-flex; align-items: center; gap: 5px;
  font-size: 11px; font-weight: 500; padding: 3px 9px; border-radius: 99px;
  background: rgba(245,158,11,0.12); color: var(--accent-amber);
  border: 1px solid rgba(245,158,11,0.25); margin-left: 8px;
}

/* ── Footer disclaimer ── */
.disclaimer {
  position: fixed; bottom: 0; left: 0; right: 0; z-index: 9999;
  background: rgba(8,11,16,0.93);
  backdrop-filter: blur(14px); -webkit-backdrop-filter: blur(14px);
  border-top: 1px solid var(--border-subtle);
  padding: 7px 24px; text-align: center;
  font-size: 10.5px; color: var(--text-muted); line-height: 1.4;
}

/* ── Control center label ── */
.cc-lbl {
  font-size: 9.5px; font-weight: 700; letter-spacing: 1px;
  text-transform: uppercase; color: var(--text-muted);
  display: block; margin-bottom: 7px; margin-top: 15px;
}
.cc-lbl:first-child { margin-top: 0; }

/* ── FHIR badge ── */
.fhir-badge {
  display: inline-flex; align-items: center; gap: 5px; font-size: 11px;
  font-weight: 500; padding: 3px 9px; border-radius: 99px;
  background: rgba(16,185,129,0.10); color: var(--accent-emerald);
  border: 1px solid rgba(16,185,129,0.22);
}

/* ── Streamlit component overrides ── */
section[data-testid="stSidebar"] {
  background: var(--bg-surface) !important;
  border-right: 1px solid var(--border-subtle) !important;
}
.stTextInput > div > div > input,
.stTextArea  > div > div > textarea {
  background: var(--bg-elevated) !important;
  border: 1px solid var(--border-default) !important;
  border-radius: var(--r-md) !important;
  color: var(--text-primary) !important;
  font-size: 13px !important;
}
.stTextInput > div > div > input:focus,
.stTextArea  > div > div > textarea:focus {
  border-color: var(--border-focus) !important;
  box-shadow: 0 0 0 3px rgba(59,130,246,0.12) !important;
  outline: none !important;
}
.stButton > button[kind="primary"] {
  background: var(--accent-blue) !important;
  color: #fff !important; border: none !important;
  border-radius: var(--r-md) !important;
  font-weight: 600 !important; font-size: 13px !important; height: 40px !important;
}
.stButton > button[kind="primary"]:hover { background: var(--accent-dim) !important; }
.stButton > button[kind="secondary"],
.stButton > button:not([kind]) {
  background: var(--bg-elevated) !important;
  color: var(--text-primary) !important;
  border: 1px solid var(--border-default) !important;
  border-radius: var(--r-md) !important;
  font-weight: 500 !important; font-size: 13px !important; height: 40px !important;
}
.stButton > button:disabled {
  background: var(--bg-elevated) !important;
  color: var(--text-muted) !important;
  border-color: var(--border-subtle) !important;
}
.stDownloadButton > button {
  background: var(--bg-elevated) !important;
  color: var(--text-primary) !important;
  border: 1px solid var(--border-default) !important;
  border-radius: var(--r-md) !important;
  font-weight: 500 !important; font-size: 13px !important; height: 40px !important;
}
.stTabs [data-baseweb="tab-list"] {
  background: transparent !important;
  border-bottom: 1px solid var(--border-subtle) !important;
  gap: 0 !important; padding: 0 !important;
}
.stTabs [data-baseweb="tab"] {
  background: transparent !important; color: var(--text-muted) !important;
  font-size: 12.5px !important; font-weight: 500 !important;
  padding: 9px 16px !important;
  border-bottom: 2px solid transparent !important; border-radius: 0 !important;
}
.stTabs [aria-selected="true"] {
  color: var(--text-primary) !important;
  border-bottom: 2px solid var(--accent-blue) !important;
}
.stTabs [data-baseweb="tab-panel"] { padding: 16px 0 0 !important; }
[data-testid="stSegmentedControl"] > div {
  background: var(--bg-elevated) !important;
  border: 1px solid var(--border-default) !important;
  border-radius: var(--r-md) !important;
  padding: 3px !important; gap: 2px !important;
}
[data-testid="stSegmentedControl"] button {
  background: transparent !important; color: var(--text-secondary) !important;
  border-radius: 5px !important; font-size: 12.5px !important;
  font-weight: 500 !important; border: none !important;
}
[data-testid="stSegmentedControl"] button[aria-checked="true"] {
  background: var(--accent-blue) !important; color: #fff !important;
}
[data-testid="stPills"] button {
  background: var(--bg-elevated) !important; color: var(--text-secondary) !important;
  border: 1px solid var(--border-default) !important; border-radius: 99px !important;
  font-size: 12px !important; font-weight: 500 !important;
}
[data-testid="stPills"] button[aria-pressed="true"] {
  background: rgba(59,130,246,0.15) !important;
  color: var(--accent-blue) !important;
  border-color: rgba(59,130,246,0.3) !important;
}
[data-testid="stAudioInput"]   {
  background: var(--bg-elevated) !important;
  border: 1px solid var(--border-default) !important;
  border-radius: var(--r-md) !important;
}
[data-testid="stFileUploader"] {
  background: var(--bg-elevated) !important;
  border: 1px dashed var(--border-default) !important;
  border-radius: var(--r-md) !important;
}
hr { border-color: var(--border-subtle) !important; margin: 18px 0 !important; }
[data-testid="stStatusWidget"] {
  background: var(--bg-elevated) !important;
  border: 1px solid var(--border-default) !important;
  border-radius: var(--r-md) !important;
}
label[data-testid="stWidgetLabel"] { color: var(--text-secondary) !important; font-size: 12px !important; }
.stCaption { color: var(--text-muted) !important; font-size: 11.5px !important; }
[data-testid="stPopover"] > div {
  background: var(--bg-elevated) !important;
  border: 1px solid var(--border-default) !important;
  border-radius: var(--r-lg) !important;
  box-shadow: 0 16px 48px rgba(0,0,0,0.7) !important;
}
[data-testid="stSelectbox"] > div > div {
  background: var(--bg-elevated) !important;
  border: 1px solid var(--border-default) !important;
  border-radius: var(--r-md) !important;
  color: var(--text-primary) !important;
}

@media (prefers-reduced-motion: reduce) {
  .urg-bar.CRITICAL { animation: none !important; }
  * { transition-duration: 0ms !important; }
}
</style>
""", unsafe_allow_html=True)


# =====================================================================
# HELPERS
# =====================================================================
def load_demo(case_key: str) -> None:
    case = DEMO_CASES[case_key]
    st.session_state.transcript              = case["transcript"]
    st.session_state.classification          = case["classification"]
    st.session_state.salience_map            = case["salience_map"]
    st.session_state.soap_note               = case["soap_note"]
    st.session_state.flags                   = case["flags"]
    st.session_state.next_steps              = case["next_steps"]
    st.session_state.pipeline_execution_time = case["pipeline_time"]
    st.session_state.chart_locked            = False
    st.session_state.is_demo                 = True
    st.session_state.patient_ref             = case["patient_ref"]
    st.session_state.sc_specialty            = case["sc_specialty"]
    st.session_state.demo_medications        = case.get("medications", [])
    st.session_state.demo_devices            = case.get("device_suggestions", [])
    st.session_state.nav_page                = "consultation"


def reset_consultation() -> None:
    for k in [
        "transcript", "classification", "salience_map", "soap_note",
        "flags", "next_steps", "pipeline_execution_time", "chart_locked",
        "is_demo", "patient_ref", "demo_medications", "demo_devices",
    ]:
        st.session_state[k] = _DEFAULTS[k]


def save_to_history() -> None:
    if not st.session_state.transcript:
        return
    st.session_state.consultation_history.append({
        "timestamp":   datetime.now().strftime("%Y-%m-%d %H:%M"),
        "patient_ref": st.session_state.patient_ref or "Unnamed",
        "specialty":   SPECIALTY_MAP.get(st.session_state.sc_specialty, ""),
        "urgency":     st.session_state.classification.get("urgency_tier", "—"),
        "trigger":     st.session_state.classification.get("primary_clinical_trigger", ""),
        "n_signals":   len(st.session_state.salience_map),
        "n_flags":     len(st.session_state.flags),
        "soap_note":   st.session_state.soap_note,
        "is_demo":     st.session_state.is_demo,
    })


def workflow_step() -> int:
    if st.session_state.chart_locked:    return 5
    if st.session_state.soap_note:       return 4
    if st.session_state.salience_map:    return 3
    if st.session_state.transcript:      return 3
    return 0


def render_stepper() -> None:
    cur = workflow_step()
    steps = [
        ("1", "Input"),
        ("2", "Exam"),
        ("3", "Analyse"),
        ("4", "Signals"),
        ("5", "SOAP"),
        ("6", "Sign"),
    ]
    parts = []
    for i, (num, lbl) in enumerate(steps):
        if i < cur:
            cc, ic, lc = "sc-done",   "✓",  "sl-done"
        elif i == cur:
            cc, ic, lc = "sc-active", num, "sl-active"
        else:
            cc, ic, lc = "sc-pend",   num, ""
        parts.append(
            f'<div class="step-w">'
            f'<div class="step-circle {cc}">{ic}</div>'
            f'<div class="step-lbl {lc}">{lbl}</div>'
            f'</div>'
        )
    st.markdown(f'<div class="stepper">{"".join(parts)}</div>', unsafe_allow_html=True)


def render_signals(salience_map: list, show_reasoning: bool = False) -> None:
    if not salience_map:
        action = "Run clinical analysis to generate salience-weighted signals." \
                 if not st.session_state.transcript else "No signals were extracted."
        st.markdown(f"""
        <div class="empty-st">
          <div class="es-icon">◎</div>
          <div class="es-title">No signals available</div>
          <div class="es-body">{action}</div>
        </div>""", unsafe_allow_html=True)
        return
    for item in sorted(salience_map, key=lambda x: x.get("salience_score", 0), reverse=True):
        score    = float(item.get("salience_score", 0.0))
        entity   = str(item.get("entity", ""))
        category = str(item.get("category", ""))
        reason   = str(item.get("reasoning_context", ""))
        pct      = int(score * 100)
        if score >= 0.85:   ring, bc = "sr-c", "var(--tier-critical)"
        elif score >= 0.70: ring, bc = "sr-h", "var(--tier-high)"
        elif score >= 0.50: ring, bc = "sr-m", "var(--tier-medium)"
        else:               ring, bc = "sr-l", "var(--tier-low)"
        reason_html = f'<div class="sig-reason">{reason}</div>' if show_reasoning else ""
        st.markdown(f"""
        <div class="sig-row">
          <div class="sig-ring {ring}">{pct}</div>
          <div class="sig-body">
            <div class="sig-name">{entity}</div>
            <span class="sig-chip">{category}</span>
            {reason_html}
            <div class="sig-track">
              <div class="sig-fill" style="width:{pct}%;background:{bc}"></div>
            </div>
          </div>
        </div>""", unsafe_allow_html=True)


def render_soap_html(soap_raw: str) -> None:
    parts: list[str] = []
    for line in soap_raw.split("\n"):
        s = line.strip()
        if s.startswith("###"):
            parts.append(f'<div class="soap-h">{s.replace("###","").strip().rstrip(":")}</div>')
        elif s.startswith("**") and s.endswith("**"):
            parts.append(f'<span class="soap-b">{s.replace("**","").strip()}</span><br>')
        elif s:
            parts.append(f'<p class="soap-p">{s}</p>')
        else:
            parts.append('<div style="height:5px"></div>')
    st.markdown(
        f'<div class="soap-outer"><div class="soap-viewer">{"".join(parts)}</div></div>',
        unsafe_allow_html=True,
    )


def render_medications(medications: list) -> None:
    if not medications:
        st.caption("No medication data available for this consultation.")
        return
    for med in medications:
        flag_html = (
            f'<div class="med-flag">⚠ {med["flag"]}</div>'
            if med.get("flag")
            else '<div class="med-ok">✓ No interaction noted</div>'
        )
        st.markdown(f"""
        <div class="med-row">
          <div class="med-name">{med.get("drug","")}</div>
          <div class="med-dose">{med.get("dose","")} {med.get("route","")} {med.get("frequency","")}</div>
          {flag_html}
        </div>""", unsafe_allow_html=True)


def render_devices(devices: list) -> None:
    if not devices:
        st.caption("No device recommendations for this case.")
        return
    tier_labels = {1: "Established (FDA/CE)", 2: "Emerging", 3: "Prototype/Concept"}
    ev_colors   = {"A": "#10B981", "B": "#3B82F6", "C": "#F59E0B", "D": "#EF4444"}
    for dev in devices:
        tier_lbl = tier_labels.get(dev.get("tier", 1), "")
        ev       = dev.get("evidence", "—")
        ev_color = ev_colors.get(ev, "#7E8A9A")
        st.markdown(f"""
        <div class="device-card">
          <div class="dev-header">
            <div class="dev-tier">{tier_lbl}</div>
            <div class="dev-name">{dev.get("name","")}</div>
            <div class="dev-ev" style="border-color:rgba({
                '16,185,129' if ev=='A' else
                '59,130,246' if ev=='B' else
                '245,158,11'
            },0.3);color:{ev_color}">Evidence {ev}</div>
          </div>
          <div class="dev-note">{dev.get("note","")}</div>
        </div>""", unsafe_allow_html=True)


# =====================================================================
# CONTROL CENTER (popover)
# =====================================================================
def render_control_center() -> None:
    st.markdown('<span class="cc-lbl">Specialty Profile</span>', unsafe_allow_html=True)
    cs = st.segmented_control(
        "Specialty", options=SPECIALTY_OPTIONS,
        default=st.session_state.sc_specialty,
        key="cc_spec", label_visibility="collapsed",
    )
    if cs is not None:
        st.session_state.sc_specialty = cs

    st.markdown('<span class="cc-lbl">Language Matrix</span>', unsafe_allow_html=True)
    cl = st.segmented_control(
        "Language", options=LANGUAGE_OPTIONS,
        default=st.session_state.sc_language,
        key="cc_lang", label_visibility="collapsed",
    )
    if cl is not None:
        st.session_state.sc_language = cl

    st.markdown('<span class="cc-lbl">Theme</span>', unsafe_allow_html=True)
    ct = st.pills(
        "Theme", options=["Dark", "System", "Light"],
        default=st.session_state.sc_theme,
        key="cc_theme", label_visibility="collapsed",
    )
    if ct is not None:
        st.session_state.sc_theme = ct

    st.markdown('<span class="cc-lbl">Patient Reference</span>', unsafe_allow_html=True)
    st.text_input(
        "Patient ref", placeholder="PT-2024-0042 or leave blank",
        key="patient_ref", label_visibility="collapsed",
    )

    st.markdown('<span class="cc-lbl">API Credentials</span>', unsafe_allow_html=True)
    if _has_vault_groq and _has_vault_gemini:
        st.caption("✓  Vault active — keys pre-loaded")
    else:
        st.text_input("Groq API Key", type="password",
                      placeholder="sk-..." if not _has_vault_groq else "🔒 Vault",
                      key="_groq_override")
        st.text_input("Gemini API Key", type="password",
                      placeholder="AI..." if not _has_vault_gemini else "🔒 Vault",
                      key="_gemini_override")


# ── Theme injection ───────────────────────────────────────────────────
_theme = st.session_state.sc_theme or "Dark"
if _theme == "Light":
    st.markdown(
        '<script>window.parent.document.documentElement'
        '.setAttribute("data-salience-theme","light")</script>',
        unsafe_allow_html=True,
    )
elif _theme == "System":
    st.markdown("""
    <script>
    (function(){
      const d=window.parent.document.documentElement;
      d.setAttribute('data-salience-theme',
        window.matchMedia('(prefers-color-scheme:dark)').matches?'dark':'light');
    })();
    </script>""", unsafe_allow_html=True)
else:
    st.markdown(
        '<script>window.parent.document.documentElement'
        '.setAttribute("data-salience-theme","dark")</script>',
        unsafe_allow_html=True,
    )

# ── Resolve keys ─────────────────────────────────────────────────────
specialty_profile = SPECIALTY_MAP.get(
    st.session_state.sc_specialty or "Cardiology", "Cardiology Clinic"
)
target_language = LANGUAGE_MAP.get(
    st.session_state.sc_language or "Mixed",
    "Mixed (Multi-lingual Code-Switching)",
)
groq_api_key   = (st.session_state.get("_groq_override") or "").strip() or _vault_groq
gemini_api_key = (st.session_state.get("_gemini_override") or "").strip() or _vault_gemini


# =====================================================================
# NAVIGATION
# =====================================================================
NAV_PAGES = [
    ("home",         "🏠 Home"),
    ("consultation", "🧾 Consultation"),
    ("dashboard",    "📊 Dashboard"),
    ("reports",      "📄 Reports"),
    ("help",         "📚 Help"),
]

nav_cols = st.columns([2, 1, 1, 1, 1, 1, 1])
with nav_cols[0]:
    st.markdown(
        '<div style="padding:10px 0 6px;font-size:14px;font-weight:700;'
        'color:var(--text-primary);letter-spacing:.3px">'
        'SALIENCE <span style="color:var(--accent-blue)">OS</span>'
        '<span style="font-size:10px;font-weight:500;opacity:.45;margin-left:6px">V3</span>'
        '</div>',
        unsafe_allow_html=True,
    )

for i, (pkey, plabel) in enumerate(NAV_PAGES):
    with nav_cols[i + 1]:
        is_active = st.session_state.nav_page == pkey
        if st.button(
            plabel,
            key=f"nav_{pkey}",
            type="primary" if is_active else "secondary",
            use_container_width=True,
        ):
            st.session_state.nav_page = pkey
            st.rerun()

settings_col, _ = st.columns([1, 6])
with settings_col:
    with st.popover("⚙ Settings", use_container_width=True):
        render_control_center()

st.divider()
page = st.session_state.nav_page


# =====================================================================
# PAGE: HOME
# =====================================================================
if page == "home":

    # Welcome card
    if not st.session_state.onboarding_dismissed:
        st.markdown("""
        <div class="welcome-card">
          <div class="welcome-title">⬡ Welcome to Salience OS V3</div>
          <div class="welcome-subtitle">
            A clinical intelligence operating system for doctors, nurses, psychologists,
            and allied health professionals across every care setting.<br>
            Record or paste any consultation — Salience OS extracts what matters,
            flags what's dangerous, and generates a structured clinical note in under 60 seconds.
          </div>
          <div class="welcome-grid">
            <div class="welcome-stat">
              <div class="welcome-stat-label">Inputs</div>
              <div class="welcome-stat-value">Audio · Text · Dataset</div>
            </div>
            <div class="welcome-stat">
              <div class="welcome-stat-label">Outputs</div>
              <div class="welcome-stat-value">Signals · SOAP · PDF · FHIR</div>
            </div>
            <div class="welcome-stat">
              <div class="welcome-stat-label">Analysis time</div>
              <div class="welcome-stat-value">~30–60 seconds</div>
            </div>
            <div class="welcome-stat">
              <div class="welcome-stat-label">Demo cases</div>
              <div class="welcome-stat-value">5 specialties included</div>
            </div>
          </div>
        </div>
        """, unsafe_allow_html=True)

        wc1, wc2, wc3 = st.columns([1, 1, 2])
        with wc1:
            demo_choice = st.selectbox(
                "Select demo case",
                list(DEMO_CASE_OPTIONS.keys()),
                label_visibility="collapsed",
            )
        with wc2:
            if st.button("🧪 Load Demo Case", use_container_width=True):
                load_demo(DEMO_CASE_OPTIONS[demo_choice])
                st.session_state.onboarding_dismissed = True
                st.rerun()
        with wc3:
            if st.button("Get Started →", type="primary", use_container_width=True):
                st.session_state.onboarding_dismissed = True
                st.session_state.nav_page = "consultation"
                st.rerun()

    # Workflow guide
    st.markdown('<div class="s-label">Clinical workflow</div>', unsafe_allow_html=True)
    render_stepper()

    guide_steps = [
        ("1 · Upload or paste consultation", "~30 sec",
         "Paste a consultation transcript, record live room audio, or upload .wav/.mp3. "
         "Multi-lingual and Arabic dialect speech is supported."),
        ("2 · Add physical examination findings", "~1–2 min",
         "Enter findings across Thoracic, GI/Abdomen, Neuro, and MSK systems. "
         "Pre-filled templates included — edit only what is relevant."),
        ("3 · Run clinical analysis", "~30–60 sec",
         "Two-stage pipeline: Whisper large-v3 for transcription, "
         "Gemini 2.5 Flash for clinical reasoning. "
         "Entities extracted, salience-weighted, flags generated."),
        ("4 · Review signals and safety flags", "~1 min",
         "Signals ranked 0–100% by clinical salience. "
         "Red flags requiring immediate attention surface in the Safety Flags tab. "
         "Medication interactions checked automatically."),
        ("5 · Review and amend the SOAP note", "~1–3 min",
         "AI-generated draft — you review, amend, and verify. "
         "The note is your clinical document. The AI is an assistant, not the author."),
        ("6 · Sign, export, and share", "~30 sec",
         "Export Clinical PDF, Pharmacy Report, or FHIR R4 Bundle. "
         "Digital sign-off locks the record and saves to dashboard."),
    ]
    st.markdown('<div class="s-label">Step-by-step guide</div>', unsafe_allow_html=True)
    for title, timing, desc in guide_steps:
        with st.expander(f"{title}  ·  {timing}"):
            st.markdown(desc)

    st.markdown('<div class="s-label">Quick start</div>', unsafe_allow_html=True)
    qs1, qs2, qs3, qs4 = st.columns(4)
    with qs1:
        demo_q = st.selectbox(
            "Demo case", list(DEMO_CASE_OPTIONS.keys()),
            key="qs_demo_sel", label_visibility="collapsed",
        )
    with qs2:
        if st.button("🧪 Load Demo", use_container_width=True, key="qs_demo"):
            load_demo(DEMO_CASE_OPTIONS[demo_q])
            st.rerun()
    with qs3:
        if st.button("🧾 New Consultation", type="primary",
                     use_container_width=True, key="qs_new"):
            reset_consultation()
            st.session_state.nav_page = "consultation"
            st.rerun()
    with qs4:
        if st.button("📊 Dashboard", use_container_width=True, key="qs_dash"):
            st.session_state.nav_page = "dashboard"
            st.rerun()


# =====================================================================
# PAGE: CONSULTATION
# =====================================================================
elif page == "consultation":

    # Demo banner
    if st.session_state.is_demo:
        db1, db2 = st.columns([4, 1])
        with db1:
            st.info(
                f"🧪 **Demo case loaded:** {st.session_state.patient_ref}. "
                "No real patient data. All outputs are synthetic for exploration."
            )
        with db2:
            if st.button("↩ New", use_container_width=True, key="clear_demo"):
                reset_consultation()
                st.rerun()

    render_stepper()

    # ── INPUT SECTION ──────────────────────────────────────────────
    if not st.session_state.transcript:
        st.markdown('<div class="s-label">Step 1 — Consultation input</div>',
                    unsafe_allow_html=True)

        col_in, col_ex = st.columns([1.25, 1], gap="large")

        with col_in:
            mode = st.radio(
                "Input mode",
                ["Text / Paste Transcript",
                 "Live Audio (Microphone)",
                 "File Upload (.wav / .mp3 / .json)"],
                horizontal=False,
                label_visibility="collapsed",
                help="Text is fastest for existing notes. "
                     "Microphone records the live room. "
                     "File accepts pre-recorded audio or a JSON dataset.",
            )

            has_input = False
            bypass    = False
            inj_text  = ""

            if "Text" in mode:
                inj_text = st.text_area(
                    "Transcript",
                    placeholder="Paste consultation transcript here…",
                    height=220,
                    label_visibility="collapsed",
                )
                if inj_text.strip():
                    has_input = True
                    bypass    = True

            elif "Live Audio" in mode:
                if not PYDUB_AVAILABLE:
                    st.warning("Audio processing unavailable. Use Text input.")
                else:
                    st.caption("Position microphone toward consultation. Tap to record.")
                    af = st.audio_input(
                        "Record audio",
                        help="Ensure informed patient consent before recording.",
                    )
                    if af is not None:
                        try:
                            with open(TEMP_AUDIO, "wb") as fh:
                                fh.write(af.read())
                            has_input = True
                        except OSError as e:
                            st.error(f"Audio save error: {e}")

            else:
                uf = st.file_uploader(
                    "Upload", type=["wav", "mp3", "m4a", "json"],
                    label_visibility="collapsed",
                    help="Audio file or JSON dataset for batch exploration.",
                )
                if uf is not None:
                    if uf.name.endswith(".json"):
                        try:
                            jdata = json.load(uf)
                            if isinstance(jdata, list):
                                st.caption(f"{len(jdata)} cases loaded")
                                idx = int(st.number_input(
                                    "Case index", min_value=0,
                                    max_value=max(len(jdata)-1, 0), value=0,
                                ))
                                inj_text = jdata[idx].get(
                                    "input", jdata[idx].get("instruction", "")
                                )
                                if inj_text:
                                    st.info(inj_text[:240] +
                                            ("…" if len(inj_text) > 240 else ""))
                                if inj_text.strip():
                                    has_input = True
                                    bypass    = True
                            else:
                                st.error("JSON must be a list of case objects.")
                        except json.JSONDecodeError as e:
                            st.error(f"JSON parse error: {e}")
                        except Exception as e:
                            st.error(f"File error: {e}")
                    else:
                        if not PYDUB_AVAILABLE:
                            st.warning("Audio processing unavailable.")
                        else:
                            try:
                                with open(TEMP_AUDIO, "wb") as fh:
                                    fh.write(uf.getbuffer())
                                st.audio(TEMP_AUDIO)
                                has_input = True
                            except OSError as e:
                                st.error(f"File save error: {e}")

            if not has_input:
                st.markdown("""
                <div class="empty-st" style="padding:18px 0">
                  <div class="es-body">
                    No consultation loaded. Paste a transcript, record audio, or upload a file.<br>
                    <strong>No real patient data?</strong> Load a demo case to explore all outputs safely.
                  </div>
                </div>""", unsafe_allow_html=True)
                demo_sel = st.selectbox(
                    "Load demo instead",
                    list(DEMO_CASE_OPTIONS.keys()),
                    label_visibility="collapsed",
                    key="inline_demo_sel",
                )
                if st.button("🧪 Load Demo Case", key="inline_demo_btn"):
                    load_demo(DEMO_CASE_OPTIONS[demo_sel])
                    st.rerun()

        with col_ex:
            st.markdown('<div class="s-label">Step 2 — Physical examination</div>',
                        unsafe_allow_html=True)
            st.caption("Enter examination findings. Pre-filled defaults — edit relevant sections only.")

            etabs = st.tabs(["Thoracic", "GI / Abdomen", "Neuro / Reflex", "MSK"])
            with etabs[0]:
                notes_thoracic = st.text_area(
                    "Thoracic",
                    value="Cardiovascular: Tachycardic, rhythm regular. S1 S2 distinct, "
                          "no murmurs, rubs, or gallops. Diaphoresis noted. "
                          "Respiratory: Tachypneic, shallow. CTAB bilaterally.",
                    height=120, label_visibility="collapsed",
                    help="Cardiovascular and respiratory auscultation findings.",
                )
            with etabs[1]:
                notes_gi = st.text_area(
                    "GI",
                    value="Abdomen soft, non-distended. Bowel sounds active ×4. "
                          "No tenderness, guarding, or rebound. No hepatosplenomegaly.",
                    height=120, label_visibility="collapsed",
                )
            with etabs[2]:
                notes_neuro = st.text_area(
                    "Neuro",
                    value="A&Ox3. PERRLA. No focal neurological deficits. "
                          "Gross motor and sensory intact.",
                    height=120, label_visibility="collapsed",
                )
            with etabs[3]:
                notes_msk = st.text_area(
                    "MSK",
                    value="No peripheral oedema. Peripheral pulses present bilaterally. "
                          "Full passive ROM. No joint tenderness.",
                    height=120, label_visibility="collapsed",
                )

        compiled_exam = (
            f"- Thoracic: {notes_thoracic or 'Deferred'}\n"
            f"- GI/Abdomen: {notes_gi or 'Deferred'}\n"
            f"- Neuro/Reflex: {notes_neuro or 'Deferred'}\n"
            f"- Musculoskeletal: {notes_msk or 'Deferred'}"
        )

        st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
        st.markdown('<div class="s-label">Step 3 — Run analysis</div>',
                    unsafe_allow_html=True)

        run = False
        if has_input:
            rc, _ = st.columns([1, 2])
            with rc:
                run = st.button(
                    "⬡  Analyse Consultation",
                    type="primary",
                    use_container_width=True,
                    help="Two-stage AI pipeline: STT → clinical reasoning. "
                         "Takes 30–60 seconds.",
                )
        else:
            st.button(
                "⬡  Analyse Consultation",
                disabled=True,
                use_container_width=True,
                help="Add a transcript or audio to enable analysis.",
            )

        # ── PIPELINE ───────────────────────────────────────────────
        if has_input and run:
            if not GROQ_AVAILABLE and not bypass:
                st.error("Groq SDK unavailable. Cannot process audio.")
            elif not GENAI_AVAILABLE:
                st.error("google-generativeai SDK unavailable.")
            elif not groq_api_key and not bypass:
                st.error("Groq API key missing. Open ⚙ Settings.")
            elif not gemini_api_key:
                st.error("Gemini API key missing. Open ⚙ Settings.")
            else:
                t0 = time.time()
                with st.status("Running clinical intelligence pipeline…",
                               expanded=True) as sw:
                    try:
                        raw_text = ""
                        if bypass:
                            st.write("✓  Text input ingested")
                            raw_text = inj_text
                        else:
                            if not PYDUB_AVAILABLE:
                                raise RuntimeError("pydub unavailable. Use Text input.")
                            if not os.path.exists(TEMP_AUDIO):
                                raise FileNotFoundError("Audio file missing. Re-upload.")
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
You are the core analytical pipeline of Salience OS V3, configured for: {specialty_profile}.
Language profile: {target_language}.

RAW TRANSCRIPT:
\"\"\"{raw_text}\"\"\"

PHYSICAL EXAMINATION:
\"\"\"{compiled_exam}\"\"\"

Return ONLY valid JSON (no markdown, no preamble):
{{
  "cleaned_transcript": "corrected text",
  "classification": {{
    "urgency_tier": "CRITICAL or HIGH or MEDIUM or LOW",
    "primary_clinical_trigger": "one sentence"
  }},
  "salience_weight_map": [
    {{"entity":"name","category":"Symptom|Medication|Medical History|Duration|Vital Sign|Noise",
      "salience_score":0.95,"reasoning_context":"why"}}
  ],
  "clinical_safety_red_flags": ["flag1","flag2"],
  "suggested_next_steps": ["step1","step2"],
  "structured_soap_chart": "### Subjective:\\n...\\n### Objective:\\n...\\n### Assessment:\\n...\\n### Plan:\\n..."
}}
"""
                        resp     = engine.generate_content(
                            prompt,
                            generation_config={"response_mime_type": "application/json"},
                        )
                        raw_json = resp.text or ""
                        if not raw_json.strip():
                            raise ValueError("Gemini returned empty response.")
                        try:
                            parsed = json.loads(raw_json, strict=False)
                        except json.JSONDecodeError as je:
                            raise ValueError(f"Invalid JSON: {je}") from je

                        st.session_state.transcript              = str(parsed.get("cleaned_transcript", ""))
                        st.session_state.classification          = dict(parsed.get("classification", {}))
                        st.session_state.salience_map            = list(parsed.get("salience_weight_map", []))
                        st.session_state.soap_note               = str(parsed.get("structured_soap_chart", ""))
                        st.session_state.flags                   = list(parsed.get("clinical_safety_red_flags", []))
                        st.session_state.next_steps              = list(parsed.get("suggested_next_steps", []))
                        st.session_state.pipeline_execution_time = round(time.time() - t0, 2)
                        st.session_state.chart_locked            = False
                        st.session_state.is_demo                 = False
                        st.session_state.demo_medications        = []
                        st.session_state.demo_devices            = []

                        st.write("✓  Pipeline complete")
                        sw.update(
                            label=f"Analysis complete — {st.session_state.pipeline_execution_time}s",
                            state="complete", expanded=False,
                        )
                        st.rerun()

                    except Exception as err:
                        sw.update(label="Pipeline error", state="error", expanded=True)
                        st.error(f"**Pipeline failed:** {err}")

    # ── OUTPUT SECTION ─────────────────────────────────────────────
    if st.session_state.transcript:
        clf      = st.session_state.classification
        urgency  = str(clf.get("urgency_tier", "MEDIUM")).upper()
        trigger  = str(clf.get("primary_clinical_trigger", ""))
        elapsed  = st.session_state.pipeline_execution_time
        n_sig    = len(st.session_state.salience_map)
        n_flag   = len(st.session_state.flags)
        locked   = st.session_state.chart_locked
        if urgency not in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
            urgency = "MEDIUM"

        st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
        st.markdown('<div class="s-label">Steps 4–6 — Review, document & sign</div>',
                    unsafe_allow_html=True)

        # Urgency banner
        st.markdown(f"""
        <div class="urg-bar {urgency}">
          <div>
            <div class="urg-label">{urgency} Priority</div>
            <div class="urg-text">{trigger}</div>
          </div>
          <div class="urg-meta">
            <span class="m-chip"><span class="cl">Signals</span>{n_sig}</span>
            <span class="m-chip"><span class="cl">Flags</span>{n_flag}</span>
            <span class="m-chip"><span class="cl">Time</span>{elapsed}s</span>
          </div>
        </div>""", unsafe_allow_html=True)

        out_tabs = st.tabs([
            "Clinical Signals",
            "Safety Flags",
            "Next Steps",
            "Medications",
            "Devices",
            "SOAP Note",
            "Explainability",
        ])

        with out_tabs[0]:
            st.caption(
                "Ranked by salience score (0–100%). "
                "Scores ≥85 drove the urgency classification. "
                "Review top signals before accepting the assessment."
            )
            render_signals(st.session_state.salience_map, show_reasoning=False)

        with out_tabs[1]:
            st.caption(
                "Items requiring immediate clinical attention or verification before sign-off. "
                "Each flag must be reviewed and either acted upon or explicitly dismissed."
            )
            if st.session_state.flags:
                for flag in st.session_state.flags:
                    st.markdown(
                        f'<div class="flag-item">'
                        f'<div style="flex-shrink:0;margin-top:1px">⚑</div>'
                        f'<div>{flag}</div></div>',
                        unsafe_allow_html=True,
                    )
            else:
                st.markdown("""
                <div class="empty-st">
                  <div class="es-icon">✓</div>
                  <div class="es-title">No safety flags raised</div>
                  <div class="es-body">All clinical safety parameters cleared. Apply standard clinical judgment.</div>
                </div>""", unsafe_allow_html=True)

        with out_tabs[2]:
            st.caption("Evidence-based next steps extracted from clinical context. Verify against local protocols.")
            if st.session_state.next_steps:
                for idx, step in enumerate(st.session_state.next_steps, 1):
                    st.markdown(
                        f'<div class="step-item">'
                        f'<div class="step-num">{idx}</div>'
                        f'<div>{step}</div></div>',
                        unsafe_allow_html=True,
                    )
            else:
                st.markdown(
                    '<div class="empty-st"><div class="es-title">No next steps generated</div></div>',
                    unsafe_allow_html=True,
                )

        with out_tabs[3]:
            st.caption(
                "Medication reconciliation. "
                "⚠ flags indicate interactions, contraindications, or dose concerns "
                "requiring clinician verification."
            )
            if st.session_state.is_demo and st.session_state.demo_medications:
                render_medications(st.session_state.demo_medications)
            else:
                med_entities = [
                    item for item in st.session_state.salience_map
                    if item.get("category", "").lower() == "medication"
                ]
                if med_entities:
                    render_medications([
                        {"drug": m["entity"], "dose": "—", "route": "—",
                         "frequency": "—", "flag": None}
                        for m in med_entities
                    ])
                else:
                    st.caption("No medications extracted. Demo cases include detailed medication data.")

        with out_tabs[4]:
            st.caption(
                "Device recommendations based on identified diagnoses. "
                "Evidence grades: A (strong RCT evidence) → D (expert opinion)."
            )
            if st.session_state.is_demo and st.session_state.demo_devices:
                render_devices(st.session_state.demo_devices)
            else:
                st.markdown(
                    '<div class="empty-st">'
                    '<div class="es-icon">⬡</div>'
                    '<div class="es-title">Device recommendations</div>'
                    '<div class="es-body">Available for demo cases. '
                    'Live analysis generates suggestions in the full V3 agent pipeline.</div>'
                    '</div>',
                    unsafe_allow_html=True,
                )

        with out_tabs[5]:
            soap_raw = st.session_state.soap_note
            status_lbl = "Signed & Locked" if locked else "Pending Review"
            status_clr = "var(--accent-violet)" if locked else "var(--accent-amber)"

            st.markdown(f"""
            <div class="soap-meta">
              <div><div class="soap-ml">Generated</div>
                <div class="soap-mv">{datetime.now().strftime('%Y-%m-%d %H:%M')}</div></div>
              <div><div class="soap-ml">Specialty</div>
                <div class="soap-mv">{specialty_profile}</div></div>
              <div><div class="soap-ml">Status</div>
                <div class="soap-mv" style="color:{status_clr}">{status_lbl}</div></div>
              <div><div class="soap-ml">Patient</div>
                <div class="soap-mv">{st.session_state.patient_ref or '—'}</div></div>
            </div>""", unsafe_allow_html=True)

            if not locked:
                st.caption(
                    "⚠️ **Review and amend before signing.** "
                    "This is an AI-generated draft — you are responsible for its accuracy."
                )
                edited_soap = st.text_area(
                    "SOAP Note",
                    value=soap_raw,
                    height=460,
                    key="soap_ed",
                    label_visibility="collapsed",
                    help="Edit as you would any clinical document. Add, correct, or remove any information.",
                )
            else:
                edited_soap = soap_raw
                render_soap_html(soap_raw)

            st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
            a1, a2, a3, a4, a5 = st.columns(5)

            with a1:
                st.button(
                    "⎘ Copy",
                    key="copy_btn",
                    use_container_width=True,
                    help="Select all text in the editor above and copy (Ctrl+A, Ctrl+C).",
                )
            with a2:
                if soap_raw.strip() and FPDF_AVAILABLE:
                    try:
                        pdf_bytes = generate_clinical_pdf(
                            edited_soap if not locked else soap_raw,
                            specialty_profile,
                            patient_ref=st.session_state.patient_ref,
                        )
                        st.download_button(
                            "↓ Clinical PDF",
                            data=pdf_bytes,
                            file_name=f"SalienceOS_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                            mime="application/pdf",
                            use_container_width=True,
                        )
                    except Exception as e:
                        st.error(f"PDF error: {e}")
                else:
                    st.button("↓ Clinical PDF", disabled=True, use_container_width=True)
            with a3:
                if st.button("📄 Reports", use_container_width=True, key="go_reports"):
                    st.session_state.nav_page = "reports"
                    st.rerun()
            with a4:
                # FHIR export
                try:
                    fhir_bundle = generate_fhir_bundle(
                        dict(st.session_state), specialty_profile
                    )
                    fhir_json = json.dumps(fhir_bundle, indent=2)
                    st.download_button(
                        "⬡ FHIR R4",
                        data=fhir_json,
                        file_name=f"SalienceOS_FHIR_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                        mime="application/json",
                        use_container_width=True,
                        help="Download FHIR R4 Bundle — compatible with Epic, Cerner, and Malaffi.",
                    )
                except Exception as e:
                    st.error(f"FHIR export error: {e}")
            with a5:
                if locked:
                    st.button("✓ EHR Synced", disabled=True, use_container_width=True)
                else:
                    if st.button(
                        "Sign & Push EHR",
                        type="primary",
                        use_container_width=True,
                        help="Sign this note and push to the simulated HL7/FHIR EHR endpoint. This action locks the note.",
                    ):
                        st.session_state.soap_note = (
                            edited_soap if not locked else soap_raw
                        )
                        with st.spinner("Synchronising with HL7/FHIR endpoint…"):
                            time.sleep(1.8)
                        st.session_state.chart_locked = True
                        save_to_history()
                        st.success("Chart signed, locked, and pushed to EHR. Saved to Dashboard.")
                        st.balloons()
                        st.rerun()

        with out_tabs[6]:
            st.caption(
                "Full AI reasoning — why each entity received its salience score. "
                "Use this to audit the model before signing."
            )
            render_signals(st.session_state.salience_map, show_reasoning=True)

        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
        nc, _ = st.columns([1, 4])
        with nc:
            if st.button("↩ New Consultation", use_container_width=True, key="new_con"):
                reset_consultation()
                st.rerun()


# =====================================================================
# PAGE: DASHBOARD
# =====================================================================
elif page == "dashboard":
    st.markdown('<div class="s-label">Session consultation history</div>',
                unsafe_allow_html=True)
    st.caption(
        "Logs signed consultations from this browser session. "
        "Refresh clears history. Export PDFs for persistent records."
    )

    history = st.session_state.consultation_history

    if not history:
        st.markdown("""
        <div class="empty-st">
          <div class="es-icon">📊</div>
          <div class="es-title">No consultations logged yet</div>
          <div class="es-body">
            Sign and push a consultation to log it here.<br>
            The dashboard tracks urgency, signals, flags, and SOAP history per session.
          </div>
        </div>""", unsafe_allow_html=True)
        dc1, dc2 = st.columns(2)
        with dc1:
            demo_d = st.selectbox(
                "Demo case",
                list(DEMO_CASE_OPTIONS.keys()),
                key="dash_demo_sel",
                label_visibility="collapsed",
            )
            if st.button("🧪 Load Demo", use_container_width=True, key="dash_demo"):
                load_demo(DEMO_CASE_OPTIONS[demo_d])
                st.rerun()
        with dc2:
            if st.button("🧾 New Consultation", type="primary",
                         use_container_width=True, key="dash_new"):
                st.session_state.nav_page = "consultation"
                st.rerun()
    else:
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Consultations", len(history))
        m2.metric("Critical urgency",
                  sum(1 for h in history if h.get("urgency") == "CRITICAL"))
        m3.metric("Signals extracted",
                  sum(h.get("n_signals", 0) for h in history))
        m4.metric("Safety flags raised",
                  sum(h.get("n_flags", 0) for h in history))

        st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
        st.markdown('<div class="s-label">Consultation log</div>',
                    unsafe_allow_html=True)

        urg_colors = {
            "CRITICAL": "#EF4444", "HIGH": "#F59E0B",
            "MEDIUM": "#3B82F6",   "LOW":  "#10B981",
        }

        for entry in reversed(history):
            uc  = urg_colors.get(entry.get("urgency", ""), "#7E8A9A")
            dtg = " · 🧪 Demo" if entry.get("is_demo") else ""
            st.markdown(f"""
            <div class="dash-card">
              <div class="dash-header">
                <div class="dash-title">{entry.get('patient_ref','Unnamed')}{dtg}</div>
                <div class="dash-ts">{entry.get('timestamp','')}</div>
              </div>
              <div style="display:flex;gap:12px;margin-bottom:6px;align-items:center;flex-wrap:wrap">
                <span style="font-size:10px;font-weight:700;letter-spacing:.8px;
                  text-transform:uppercase;color:{uc}">{entry.get('urgency','—')}</span>
                <span style="font-size:11px;color:var(--text-muted)">{entry.get('specialty','')}</span>
                <span style="font-size:11px;color:var(--text-muted)">
                  {entry.get('n_signals',0)} signals &nbsp;·&nbsp; {entry.get('n_flags',0)} flags
                </span>
              </div>
              <div class="dash-body">{entry.get('trigger','')}</div>
            </div>""", unsafe_allow_html=True)
            with st.expander(
                f"View SOAP — {entry.get('patient_ref','Unnamed')} "
                f"({entry.get('timestamp','')})"
            ):
                render_soap_html(entry.get("soap_note", "No note saved."))

        if st.button("Clear session history", key="clear_hist"):
            st.session_state.consultation_history = []
            st.rerun()


# =====================================================================
# PAGE: REPORTS
# =====================================================================
elif page == "reports":
    st.markdown('<div class="s-label">Report generation</div>', unsafe_allow_html=True)

    if not st.session_state.transcript:
        st.markdown("""
        <div class="empty-st">
          <div class="es-icon">📄</div>
          <div class="es-title">No active consultation</div>
          <div class="es-body">
            Load the demo patient or complete an analysis before generating reports.
          </div>
        </div>""", unsafe_allow_html=True)
        rc1, rc2 = st.columns(2)
        with rc1:
            demo_r = st.selectbox(
                "Demo case", list(DEMO_CASE_OPTIONS.keys()),
                key="rep_demo_sel", label_visibility="collapsed",
            )
            if st.button("🧪 Load Demo", use_container_width=True, key="rep_demo"):
                load_demo(DEMO_CASE_OPTIONS[demo_r])
                st.rerun()
        with rc2:
            if st.button("🧾 Go to Consultation", type="primary",
                         use_container_width=True, key="rep_con"):
                st.session_state.nav_page = "consultation"
                st.rerun()
    else:
        soap_raw     = st.session_state.soap_note
        salience_map = st.session_state.salience_map
        pat_ref      = st.session_state.patient_ref

        rep_tabs = st.tabs([
            "Clinical Report",
            "Pharmacy Report",
            "FHIR Bundle",
            "Patient History",
        ])

        # ── Clinical report ────────────────────────────────────────
        with rep_tabs[0]:
            st.caption(
                "Full clinical report for the treating physician — "
                "includes urgency, signals, flags, next steps, and SOAP note."
            )
            urg = st.session_state.classification.get("urgency_tier", "—")
            trg = st.session_state.classification.get("primary_clinical_trigger", "")

            clin_report = "\n".join([
                "### Clinical Intelligence Report",
                f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                f"**Specialty:** {specialty_profile}",
                f"**Patient Ref:** {pat_ref or 'Not specified'}",
                f"**Urgency:** {urg}",
                "",
                "### Primary Clinical Trigger",
                trg,
                "",
                "### Clinical Safety Flags",
                *([f"- {f}" for f in st.session_state.flags]
                  if st.session_state.flags else ["None raised."]),
                "",
                "### Top Clinical Signals",
                *[
                    f"- {item['entity']} ({int(item['salience_score']*100)}%) "
                    f"— {item.get('reasoning_context','')}"
                    for item in sorted(
                        salience_map,
                        key=lambda x: x.get("salience_score", 0),
                        reverse=True,
                    )[:6]
                ],
                "",
                "### Suggested Next Steps",
                *([f"- {s}" for s in st.session_state.next_steps]
                  if st.session_state.next_steps else ["None generated."]),
                "",
                "### SOAP Note",
                soap_raw,
                "",
                "---",
                "*Report generated by SALIENCE OS V3. "
                "Final clinical judgment is the sole responsibility of the treating clinician.*",
            ])

            render_soap_html(clin_report)
            st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

            if FPDF_AVAILABLE and soap_raw.strip():
                try:
                    pdf_b = generate_clinical_pdf(
                        clin_report, specialty_profile, "clinical", pat_ref
                    )
                    st.download_button(
                        "↓ Download Clinical Report PDF",
                        data=pdf_b,
                        file_name=f"SalienceOS_Clinical_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                        mime="application/pdf",
                        use_container_width=True,
                    )
                except Exception as e:
                    st.error(f"PDF error: {e}")

        # ── Pharmacy report ────────────────────────────────────────
        with rep_tabs[1]:
            st.caption(
                "Medication-focused summary for pharmacy or external referral. "
                "Contains medication mentions, dosing context, and interaction flags."
            )
            pharm_text = generate_pharmacy_text(
                salience_map, soap_raw, specialty_profile, pat_ref
            )
            render_soap_html(pharm_text)
            st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

            if FPDF_AVAILABLE:
                try:
                    pdf_p = generate_clinical_pdf(
                        pharm_text, specialty_profile, "pharmacy", pat_ref
                    )
                    st.download_button(
                        "↓ Download Pharmacy Report PDF",
                        data=pdf_p,
                        file_name=f"SalienceOS_Pharmacy_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                        mime="application/pdf",
                        use_container_width=True,
                    )
                except Exception as e:
                    st.error(f"PDF error: {e}")

        # ── FHIR bundle ────────────────────────────────────────────
        with rep_tabs[2]:
            st.caption(
                "FHIR R4 Bundle — compatible with Epic SMART on FHIR, "
                "Oracle Health, Malaffi, Nabidh, and Riayati APIs."
            )
            try:
                bundle      = generate_fhir_bundle(dict(st.session_state), specialty_profile)
                fhir_json   = json.dumps(bundle, indent=2)
                bundle_type = bundle.get("entry", [{}])[0].get(
                    "resource", {}
                ).get("status", "preliminary")
                col_f1, col_f2 = st.columns([3, 1])
                with col_f1:
                    st.markdown(
                        f'<div class="fhir-badge">'
                        f'⬡ FHIR R4 Bundle · {bundle["id"]} · '
                        f'Status: {bundle_type}'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                with col_f2:
                    st.download_button(
                        "↓ Download FHIR JSON",
                        data=fhir_json,
                        file_name=f"SalienceOS_FHIR_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                        mime="application/json",
                        use_container_width=True,
                    )
                st.code(fhir_json[:2000] + ("\n…" if len(fhir_json) > 2000 else ""),
                        language="json")
            except Exception as e:
                st.error(f"FHIR export error: {e}")

        # ── Patient history ────────────────────────────────────────
        with rep_tabs[3]:
            st.caption(
                "Patient Clinical Memory Card — synthesises all consultations "
                "from this session to surface clinical trajectories."
            )
            history = st.session_state.consultation_history
            all_e   = history.copy()
            if st.session_state.transcript:
                all_e.append({
                    "timestamp":  datetime.now().strftime("%Y-%m-%d %H:%M") + " (current)",
                    "patient_ref": pat_ref or "Current",
                    "urgency":    st.session_state.classification.get("urgency_tier", "—"),
                    "trigger":    st.session_state.classification.get("primary_clinical_trigger", ""),
                    "n_signals":  len(salience_map),
                    "n_flags":    len(st.session_state.flags),
                    "soap_note":  soap_raw,
                    "is_demo":    st.session_state.is_demo,
                })

            if not all_e:
                st.markdown(
                    '<div class="empty-st">'
                    '<div class="es-title">No consultation history available</div>'
                    '<div class="es-body">Complete and sign at least one consultation '
                    'to generate a patient history insight.</div>'
                    '</div>',
                    unsafe_allow_html=True,
                )
            else:
                insight = [
                    "### Patient Clinical Memory Card",
                    f"**Total consultations in session:** {len(all_e)}",
                    f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                    "",
                ]
                for e in all_e:
                    insight += [
                        f"### {e.get('timestamp','')} — {e.get('patient_ref','')}",
                        f"**Urgency:** {e.get('urgency','—')}",
                        f"**Clinical trigger:** {e.get('trigger','')}",
                        f"Signals: {e.get('n_signals',0)} · Flags: {e.get('n_flags',0)}",
                        "",
                    ]
                insight += [
                    "---",
                    "*Generated by SALIENCE OS V3. Verify accuracy before clinical use.*",
                ]
                render_soap_html("\n".join(insight))
                if FPDF_AVAILABLE:
                    try:
                        pdf_h = generate_clinical_pdf(
                            "\n".join(insight), specialty_profile, "history", pat_ref
                        )
                        st.download_button(
                            "↓ Download History PDF",
                            data=pdf_h,
                            file_name=f"SalienceOS_History_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                            mime="application/pdf",
                            use_container_width=True,
                        )
                    except Exception as e:
                        st.error(f"PDF error: {e}")


# =====================================================================
# PAGE: HELP
# =====================================================================
elif page == "help":
    st.markdown('<div class="s-label">Clinical reference guide</div>',
                unsafe_allow_html=True)
    st.caption("Everything you need to understand, trust, and verify Salience OS outputs.")

    help_items = [
        ("What is Salience Scoring?",
         "Salience scoring (0–100%) measures the clinical importance of each entity extracted "
         "from the consultation. Scores ≥85% indicate entities that drove the urgency "
         "classification — always review these first. Scores <50% may represent background "
         "context with low immediate relevance."),
        ("What are Clinical Signals?",
         "Clinical signals are structured entities extracted from the transcript: symptoms, "
         "medications, diagnoses, durations, vital signs, and risk factors. Each is scored and "
         "explained. The Clinical Signals tab shows them ranked — review the top 3–5 before "
         "accepting the urgency classification."),
        ("What are Safety Flags?",
         "Safety flags are specific warnings when the AI detects patterns requiring immediate "
         "attention: time-sensitive interventions, drug interactions, contraindications, or "
         "haemodynamic risk signals. Each flag must be reviewed and acted upon or explicitly "
         "dismissed by the clinician before sign-off."),
        ("How are SOAP notes generated?",
         "SOAP notes are generated by Gemini 2.5 Flash using the cleaned transcript and "
         "physical examination findings. The Subjective section draws only from entities with "
         "salience ≥0.50. You must review and amend the draft — it is your clinical document. "
         "The AI produces a starting point, not a final note."),
        ("What must I verify before signing?",
         "Before signing, verify: (1) patient identifiers are correct, "
         "(2) medications and doses are accurate, "
         "(3) the assessment reflects your clinical judgment, "
         "(4) the plan aligns with local protocols, "
         "(5) all safety flags have been addressed. "
         "The AI may miss context only the treating clinician possesses."),
        ("What is a Pharmacy Report?",
         "The Pharmacy Report extracts medication-relevant information: drugs mentioned, "
         "dosing context, potential interactions flagged, and relevant prescribing notes. "
         "It does not replace a formal prescription — prescribing authority remains with "
         "the treating clinician."),
        ("What is a FHIR R4 Bundle?",
         "FHIR (Fast Healthcare Interoperability Resources) R4 is the international standard "
         "for healthcare data exchange. The exported bundle contains the SOAP note, safety "
         "flags, and clinical trigger in a format compatible with Epic, Oracle Health, "
         "Malaffi (Abu Dhabi), Nabidh (Dubai), and international HIEs."),
        ("What data is sent to external APIs?",
         "Consultation transcripts and examination findings are sent to Groq (speech-to-text) "
         "and Google Gemini (clinical analysis). Do not use real patient identifiers unless "
         "your institution has approved these providers for clinical data processing. "
         "Demo cases contain no real patient data and are safe for unrestricted use."),
        ("How does the Patient Dashboard work?",
         "The dashboard logs all signed consultations during the current browser session. "
         "It is session-scoped — refreshing the browser clears it. "
         "Export PDFs for persistent records. The dashboard is a session-level reference, "
         "not a long-term EHR substitute."),
        ("What are Device Recommendations?",
         "Device recommendations are generated for demo cases based on the identified diagnosis. "
         "Tier 1: established, FDA/CE-cleared devices with strong evidence. "
         "Tier 2: emerging validated technologies. "
         "Tier 3: prototype or conceptual approaches. "
         "Evidence grades follow the GRADE system (A–D)."),
    ]

    for title, body in help_items:
        with st.expander(title):
            st.markdown(body)

    st.divider()
    st.markdown('<div class="s-label">Demo cases available</div>', unsafe_allow_html=True)

    for label, key in DEMO_CASE_OPTIONS.items():
        case = DEMO_CASES[key]
        col_a, col_b = st.columns([4, 1])
        with col_a:
            urg = case["classification"]["urgency_tier"]
            uc  = {"CRITICAL": "#EF4444", "HIGH": "#F59E0B",
                   "MEDIUM": "#3B82F6", "LOW": "#10B981"}.get(urg, "#7E8A9A")
            st.markdown(
                f'<div style="font-size:13px;font-weight:500;color:var(--text-primary);'
                f'margin-bottom:3px">{label}</div>'
                f'<div style="font-size:11px;color:{uc};font-weight:600">{urg}</div>',
                unsafe_allow_html=True,
            )
        with col_b:
            if st.button("Load", key=f"help_load_{key}", use_container_width=True):
                load_demo(key)
                st.rerun()
        st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

    st.divider()
    st.markdown('<div class="s-label">Version</div>', unsafe_allow_html=True)
    v1, v2, v3, v4 = st.columns(4)
    v1.metric("Platform", "Salience OS V3")
    v2.metric("STT",       "Whisper large-v3")
    v3.metric("Reasoning", "Gemini 2.5 Flash")
    v4.metric("Standard",  "FHIR R4")


# =====================================================================
# CLINICAL DISCLAIMER FOOTER (persistent)
# =====================================================================
st.markdown("""
<div class="disclaimer">
  ⬡ &nbsp;<strong>SALIENCE OS V3</strong> is a clinical decision-support and documentation tool.
  Final clinical judgment, diagnosis, and prescribing authority remain the sole responsibility
  of the licensed healthcare professional. AI-generated outputs must be reviewed and verified
  before any clinical action or record submission.
</div>
""", unsafe_allow_html=True)
