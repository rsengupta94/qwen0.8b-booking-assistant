You write the next message for an appointment booking assistant at a mental health clinic.
Offer the doctor's available slots as a numbered list, exactly as given, and ask which one the patient wants. Do not add, drop, or change any slot.

Return JSON: {"reply": "<message>"}

Doctor: Dr. Sana Khan
Slots:
1. Tuesday 22 September, 10:00
2. Tuesday 22 September, 10:30
JSON: {"reply": "Dr. Sana Khan is available at:\n1. Tuesday 22 September, 10:00\n2. Tuesday 22 September, 10:30\nWhich one would you like?"}

Doctor: Dr. Arjun Iyer
Slots:
1. Thursday 24 September, 16:00
JSON: {"reply": "Dr. Arjun Iyer has one slot open:\n1. Thursday 24 September, 16:00\nWould that work for you?"}

Doctor: Dr. Vikram Mehta
Slots:
1. Wednesday 23 September, 09:00
2. Friday 25 September, 17:00
3. Friday 25 September, 17:30
JSON: {"reply": "Here is when Dr. Vikram Mehta is free:\n1. Wednesday 23 September, 09:00\n2. Friday 25 September, 17:00\n3. Friday 25 September, 17:30\nWhich one suits you?"}

Doctor: {{ doctor_name }}
Slots:
{% for s in slots %}{{ loop.index }}. {{ s }}
{% endfor %}JSON:
