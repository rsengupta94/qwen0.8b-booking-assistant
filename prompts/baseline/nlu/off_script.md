You decide whether a patient's reply is a question for the clinic rather than an answer to what the assistant asked.

The assistant asked: "{{ question }}"

Return JSON with two fields:
- is_question: true if the patient is asking the clinic something
- topic: a one or two word topic such as fees, hours, location, first_visit, or null

Examples:

Reply: what are your fees?
JSON: {"is_question": true, "topic": "fees"}

Reply: are you open on weekends?
JSON: {"is_question": true, "topic": "hours"}

Reply: hmm not sure
JSON: {"is_question": false, "topic": null}

Reply: what counts as a first visit?
JSON: {"is_question": true, "topic": "first_visit"}

Reply: ok
JSON: {"is_question": false, "topic": null}

Reply: {{ user_text }}
JSON:
