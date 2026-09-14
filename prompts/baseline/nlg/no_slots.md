You write the next message for an appointment booking assistant at a mental health clinic.
Tell the patient the doctor has no free slots on the days they asked for, and ask which other days would work. Keep the doctor's name and the days exactly as given.

Return JSON: {"reply": "<message>"}

Doctor: Dr. Meera Rao
Days: Sunday 27 September
JSON: {"reply": "Sorry, Dr. Meera Rao has no free slots on Sunday 27 September. Would another day work for you?"}

Doctor: Dr. Sana Khan
Days: Wednesday 23 September, Friday 25 September
JSON: {"reply": "Unfortunately Dr. Sana Khan is fully booked on Wednesday 23 September and Friday 25 September. Which other days could you do?"}

Doctor: Dr. Arjun Iyer
Days: Monday 21 September
JSON: {"reply": "Dr. Arjun Iyer has nothing open on Monday 21 September, I'm afraid. Is there another day that suits you?"}

Doctor: {{ doctor_name }}
Days: {{ days | join(", ") }}
JSON:
