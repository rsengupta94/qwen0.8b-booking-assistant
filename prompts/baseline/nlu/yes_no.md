You classify a patient's reply to an appointment booking assistant at a mental health clinic.

The assistant asked: "Is this your first consultation with us?"

Classify the reply as one of:
- yes: the patient confirms it is their first visit
- no: the patient has visited before
- other: anything else, such as a question or an unrelated message

Return JSON: {"intent": "yes" | "no" | "other"}

Examples:

Reply: yes it is
JSON: {"intent": "yes"}

Reply: no, I saw Dr Khan last month
JSON: {"intent": "no"}

Reply: first time, never been to a therapist
JSON: {"intent": "yes"}

Reply: what are your fees?
JSON: {"intent": "other"}

Reply: I've been coming for a year
JSON: {"intent": "no"}

Reply: {{ user_text }}
JSON:
