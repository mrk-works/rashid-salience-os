with output_tabs[3]:
    soap_raw = st.session_state.soap_note
    chart_status_label = "Signed & Locked" if chart_locked else "Pending Review"
    chart_status_color = "var(--accent-violet)" if chart_locked else "var(--accent-amber)"
    generated_at       = datetime.now().strftime("%Y-%m-%d %H:%M")

    st.markdown(f"""
    <div class="soap-meta-row">
      <div class="soap-meta-item"><span class="soap-meta-label">Generated</span><span class="soap-meta-value">{generated_at}</span></div>
      <div class="soap-meta-item"><span class="soap-meta-label">Specialty</span><span class="soap-meta-value">{specialty_profile}</span></div>
      <div class="soap-meta-item"><span class="soap-meta-label">Status</span><span class="soap-meta-value" style="color:{chart_status_color}">{chart_status_label}</span></div>
      <div class="soap-meta-item"><span class="soap-meta-label">Time</span><span class="soap-meta-value">{elapsed}s</span></div>
    </div>
    """, unsafe_allow_html=True)

    # Editable SOAP note — doctor reviews and amends before sign-off
    if not chart_locked:
        st.caption("Review and amend the note below before signing.")
        edited_soap = st.text_area(
            "SOAP Note",
            value=soap_raw,
            height=420,
            key="soap_editor",
            label_visibility="collapsed",
        )
    else:
        # Locked — show styled read-only render
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
        st.button("⎘  Copy SOAP", key="copy_soap_btn", use_container_width=True,
                  help="Select all text above, then Ctrl+C / Cmd+C")

    with act2:
        # PDF uses the edited version, not raw session state
        if edited_soap.strip() and FPDF_AVAILABLE:
            try:
                pdf_bytes = generate_clinical_pdf(edited_soap, specialty_profile)
                st.download_button(
                    "↓  Export PDF", data=pdf_bytes,
                    file_name=f"SalienceOS_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                    mime="application/pdf", use_container_width=True,
                )
            except Exception as pdf_err:
                st.error(f"PDF failed: {pdf_err}")
        else:
            st.button("↓  Export PDF", disabled=True, use_container_width=True)

    with act3:
        if chart_locked:
            st.button("✓  Synced to FHIR", disabled=True, use_container_width=True)
        else:
            if st.button("Sign & Push to EHR", type="primary", use_container_width=True):
                # Save the edited version back to session state before locking
                st.session_state.soap_note = edited_soap
                with st.spinner("Synchronising with HL7/FHIR endpoint…"):
                    time.sleep(2.0)
                st.session_state.chart_locked = True
                st.success("Chart signed and pushed to simulated EHR database.")
                st.balloons()
                st.rerun()
