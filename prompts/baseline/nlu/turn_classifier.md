You detect whether a patient is correcting something they said earlier, in a conversation with an appointment booking assistant.

Return JSON with three fields:
- is_correction: true if the patient changes an earlier answer, false otherwise
- correction_field: which answer changed, one of doctor, days, session_type, phone, problem, or null
- new_value: the new value as the patient said it, or null

Examples:

Reply: actually make that Wednesday
JSON: {"is_correction": true, "correction_field": "days", "new_value": "Wednesday"}

Reply: sorry, I meant Dr Rao not Dr Khan
JSON: {"is_correction": true, "correction_field": "doctor", "new_value": "Dr Rao"}

Reply: the first one
JSON: {"is_correction": false, "correction_field": null, "new_value": null}

Reply: wait, my number is 9123456780, I gave the wrong one
JSON: {"is_correction": true, "correction_field": "phone", "new_value": "9123456780"}

Reply: yes, first time
JSON: {"is_correction": false, "correction_field": null, "new_value": null}

Reply: {{ user_text }}
JSON:
