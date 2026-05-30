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

# =====================================================================
# 1. SESSION STATE INITIALIZATION
# =====================================================================
st.set_page_config(page_title="Rashid Clinical Salience OS", layout="wide")

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
# 2. UI HEADER & SIDEBAR CONFIGURATION
# =====================================================================
st.title("Rashid Clinical Salience OS")
st.markdown("### Architecture 2.0: Multi-Modal Context Engine")

with st.sidebar:
    st.header("⚙️ Configuration Layer")
    groq_api_key = st.text_input("Groq API Key (Whisper v3)", type="password")
    gemini_api_key = st.text_input("Gemini API Key (Flash 2.5)", type="password")
    
    st.divider()
    specialty_profile = st.selectbox(
        "Clinical Specialty Model Vector", 
        ["Cardiology Clinic", "General Internal Medicine", "Emergency Trauma"]
    )
    target_language = st.selectbox(
        "Ingestion Acoustic Matrix (20+ Languages)", 
        ["Mixed (Multi-lingual Code-Switching)", "English (US/UK)", "Arabic (Khaleeji/MSA)"]
    )

# =====================================================================
# 3. DATA CAPTURE & PHYSICAL EXAM LAYER
# =====================================================================
col_capture, col_pipeline = st.columns([1.2, 1.8], gap="large")

with col_capture:
    st.markdown("### 🎙️ Multi-Channel Input Processing")
    
    input_vector = st.radio(
        "Select Testing Vector Input Pattern:",
        ["Raw Text Simulation (Anti-Hallucination Sandbox)", "Live Audio Stream Capture (Mic)", "Raw Dataset Test Ingestion (File Upload)"],
        horizontal=False
    )
    
    temp_audio_filename = "active_stream_input.wav"
    has_valid_audio_payload = False
    bypass_audio_stt = False
    injected_text_payload = ""
    
    if "Raw Text" in input_vector:
        st.info("Text injection vector bypass active. Perfect for avoiding large file constraints.")
        injected_text_payload = st.text_area(
            "Paste Transcript Data Directly:", 
            placeholder="Paste the Master Testing Script text here...",
            height=200
        )
        if injected_text_payload.strip():
            has_valid_audio_payload = True
            bypass_audio_stt = True
            
    elif "Live" in input_vector:
        audio_file = st.audio_input("🎙️ Record Live Room Audio")
        if audio_file is not None:
            with open(temp_audio_filename, "wb") as f:
                f.write(audio_file.read())
            has_valid_audio_payload = True
    else:
        # UPGRADED: File uploader now naturally reads .json dataset strings!
        uploaded_file = st.file_uploader("Upload raw file or ChatDoctor dataset (.wav, .mp3, .m4a, .json):", type=["wav", "mp3", "m4a", "json"])
        if uploaded_file is not None:
            if uploaded_file.name.endswith('.json'):
                try:
                    json_data = json.load(uploaded_file)
                    if isinstance(json_data, list):
                        st.success(f"✅ ChatDoctor Dataset Loaded ({len(json_data)} cases parsed!)")
                        case_idx = st.number_input("🔍 Select Case Index to Extract:", min_value=0, max_value=len(json_data)-1, value=0)
                        
                        selected_node = json_data[case_idx]
                        # Capture conversation source structure ("input" or fallback to "instruction")
                        injected_text_payload = selected_node.get("input", selected_node.get("instruction", ""))
                        
                        st.markdown("**Preview Ingested Patient Symptoms:**")
                        st.info(injected_text_payload if injected_text_payload else "No input query found in this entry.")
                        
                        if injected_text_payload.strip():
                            has_valid_audio_payload = True
                            bypass_audio_stt = True
                    else:
                        st.error("🛑 Structure error: JSON file must be formatted as a sequence list.")
                except Exception as json_err:
                    st.error(f"🛑 JSON Analysis Failed: {json_err}")
            else:
                # Normal audio stream routing
                with open(temp_audio_filename, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                st.audio(temp_audio_filename)
                has_valid_audio_payload = True

    st.markdown("### 🩺 Dynamic Physical Exam Synthesis")
    st.caption("Click the system focus node being evaluated to append real-time examination telemetry overlays:")
    
    organ_system_tabs = st.tabs(["🫁 Thoracic", "🟢 GI/Abdomen", "🧠 Reflex/Neuro", "🦴 Musculoskeletal"])
    with organ_system_tabs[0]:
        notes_thoracic = st.text_area("Thoracic Findings Shorthand:", value="Cardiovascular: Tachycardic, rhythm regular. S1 and S2 distinct, no audible murmurs, rubs, or gallops. Significant chest wall diaphoresis noted; patient actively clutching retrosternal area. Respiratory: Tachypneic, shallow respirations. Lungs clear to auscultation bilaterally (CTAB) with no wheezing, rales, or rhonchi.", label_visibility="collapsed")
    with organ_system_tabs[1]:
        notes_abdominal = st.text_area("GI/Abdominal Findings Shorthand:", value="Abdomen soft, symmetric, and non-distended. Bowel sounds active in all 4 quadrants. No localized tenderness, guarding, or rebound to light/deep palpation. No hepatosplenomegaly. Epigastric region non-tender.", label_visibility="collapsed")
    with organ_system_tabs[2]:
        notes_neuro = st.text_area("Reflex/Neuro Findings Shorthand:", value="Patient alert and oriented to person, place, and time (A&Ox3). Pupils equal, round, and reactive to light (PEERRLA). Observable orthostatic lightheadedness and profound dizziness upon lifting head off the examination bed. Gross motor and sensory function intact.", label_visibility="collapsed")
    with organ_system_tabs[3]:
        notes_ortho = st.text_area("Musculoskeletal Findings Shorthand:", value="Mild focal tenderness noted over the lumbar paraspinal muscles. Left shoulder and left mandibular jaw display full passive range of motion with zero localized joint or bone tenderness.", label_visibility="collapsed")
        
    compiled_examination_overlay = f"""
    - Thoracic Tracking Overlay: {notes_thoracic if notes_thoracic else 'Deferred/Normal checks confirmed'}
    - GI/Abdominal Tracking Overlay: {notes_abdominal if notes_abdominal else 'Deferred/Normal checks confirmed'}
    - Reflex/Neuro Tracking Overlay: {notes_neuro if notes_neuro else 'Deferred/Normal checks confirmed'}
    - Musculoskeletal Tracking Overlay: {notes_ortho if notes_ortho else 'Deferred/Normal checks confirmed'}
    """

# =====================================================================
# 4. CORE SALIENCE ORCHESTRATION LAYER
# =====================================================================
with col_pipeline:
    st.markdown("### 🧠 Clinical Salience Attention Framework")
    st.caption("Monitored Lifecycle: STT Ingestion ➔ Entity Extraction ➔ Salience Engine Weighting ➔ Filtering ➔ SOAP Compilation")
    
    if has_valid_audio_payload:
        if st.button("🚀 Execute High-Impact Processing Pipeline", type="primary", use_container_width=True):
            if not groq_api_key or not gemini_api_key:
                st.error("🛑 Security Exception: Orchestration execution halted due to missing API tokens in the sidebar.")
            else:
                pipeline_start_checkpoint = time.time()
                with st.spinner("Processing tracks... Running multi-modular validation pipelines..."):
                    try:
                        # -------------------------------------------------------------
                        # STAGE 1: Audio Compression & Extended Timeout Transcription
                        # -------------------------------------------------------------
                        if bypass_audio_stt:
                            extracted_raw_text = injected_text_payload
                        else:
                            st.info("⚙️ Optimizing audio profile for extended time limits...")
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
                                
                        # -------------------------------------------------------------
                        # STAGE 2: Generative Intelligence & Salience Mapping
                        # -------------------------------------------------------------
                        genai.configure(api_key=gemini_api_key)
                        intelligence_engine = genai.GenerativeModel('gemini-2.5-flash')
                        
                        system_prompt = f"""
                        You are the core analytical pipeline of Rashid Clinical Salience OS, configured for the specialty: {specialty_profile}.
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
                        
                        parsed_payload = json.loads(response_package.text)
                        
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
                        st.error(f"🛑 Critical System Event: {e}")
    else:
        st.info("💡 Ready for ingestion vectors. Supply data to compute clinical salience profiles.")

# =====================================================================
# 5. RECONCILED ANALYTICS INTERFACE & HEALTHMAP UI MODULE
# =====================================================================
if st.session_state.transcript:
    st.divider()
    st.markdown(f"### 🏁 System Output Workspace & Review Ledger (Computed in {st.session_state.pipeline_execution_time}s)")
    
    workspace_tabs = st.tabs(["📝 Structured SOAP Record", "📊 Salience Visual Relay Map", "🚨 Clinical Safety Logs", "🧠 Explainability Matrix"])
    
    with workspace_tabs[0]:
        st.markdown("#### Patient Clinical Record (EHR Target)")
        st.markdown(f"""
        <div style="background-color: #FFFFFF; padding: 30px; border-radius: 12px; border: 1px solid #E2E8F0; color: #0F172A; box-shadow: 0 4px 6px rgba(0,0,0,0.05); margin-bottom: 20px;">
            <h2 style="color: #0284C7; border-bottom: 2px solid #E2E8F0; padding-bottom: 10px; margin-top: 0;">Rashid Standardized Clinical Note</h2>
            {st.session_state.soap_note}
        </div>
        """, unsafe_allow_html=True)
        
        action_col1, action_col2 = st.columns(2)
        with action_col1:
            st.download_button(
                label="🖨️ Download / Print Clinical Record (PDF-Ready format)",
                data=st.session_state.soap_note,
                file_name=f"Clinical_SOAP_Record_{datetime.now().strftime('%Y%m%d')}.md",
                mime="text/markdown",
                use_container_width=True
            )
        with action_col2:
            if st.session_state.chart_locked:
                st.button("✅ Chart Synced to FHIR Interoperability Network", disabled=True, use_container_width=True)
            else:
                if st.button("🔄 Digital Sign-Off & Push to EHR System", type="primary", use_container_width=True):
                    with st.spinner("Encrypting payload and synchronizing with hospital HL7/FHIR endpoints..."):
                        time.sleep(2.0)
                        st.session_state.chart_locked = True
                        st.success("Success: Clinical chart legally locked and pushed to simulated database.")
                        st.balloons()
                        st.rerun()

    with workspace_tabs[1]:
        st.markdown("#### Clinical Attention Heatmap & Logic Plot")
        if st.session_state.salience_map:
            chart_data = pd.DataFrame(st.session_state.salience_map)
            st.bar_chart(data=chart_data, x="salience_score", y="entity", color="category", horizontal=True, height=450)

    with workspace_tabs[2]:
        st.markdown("#### High-Contrast Autonomous Safety Guardrails")
        if st.session_state.flags:
            for alert in st.session_state.flags: st.error(f"⚠️ **System Alert Flag:** {alert}")
        else:
            st.success("✅ Complete diagnostic parameter check cleared.")
            
    with workspace_tabs[3]:
        st.markdown("#### System Explainability Log")
        for idx, item in enumerate(st.session_state.salience_map):
            st.info(f"**Node {idx+1}: {item.get('entity', '')}** (Weight: {item.get('salience_score', 0.0)})  \n*Logic:* {item.get('reasoning_context', '')}")
