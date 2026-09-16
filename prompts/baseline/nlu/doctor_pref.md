You classify a patient's reply about which doctor they want, for an appointment booking assistant at a mental health clinic.

The assistant asked: "Do you have a doctor in mind, or would you like us to suggest one?"

Return JSON with two fields:
- doctor_name: the name as the patient said it, or null
- mode: "named" if the patient names a doctor, "you_decide" if they want the clinic to choose or suggest, "other" for anything else

Examples:

Reply: Dr Rao please
JSON: {"doctor_name": "Dr Rao", "mode": "named"}

Reply: you decide, I don't know anyone there
JSON: {"doctor_name": null, "mode": "you_decide"}

Reply: I'd like to see Sana Khan again
JSON: {"doctor_name": "Sana Khan", "mode": "named"}

Reply: whoever is available soonest
JSON: {"doctor_name": null, "mode": "you_decide"}

Reply: how much does a session cost?
JSON: {"doctor_name": null, "mode": "other"}

Reply: {{ user_text }}
JSON:
