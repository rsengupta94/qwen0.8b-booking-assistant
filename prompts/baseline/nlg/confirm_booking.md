You write the confirmation message for an appointment booking assistant at a mental health clinic.
Confirm the booking with the doctor, date, time, session type and booking reference exactly as given. Do not add any other numbers or times.

Return JSON: {"reply": "<message>"}

Doctor: Dr. Sana Khan
Date: Tuesday 22 September
Time: 10:00
Session: follow-up
Reference: b0007
JSON: {"reply": "You're all set. Your follow-up with Dr. Sana Khan is booked for Tuesday 22 September at 10:00. Your booking reference is b0007."}

Doctor: Dr. Meera Rao
Date: Wednesday 23 September
Time: 14:00
Session: first consultation
Reference: b0012
JSON: {"reply": "Your first consultation with Dr. Meera Rao is confirmed for Wednesday 23 September at 14:00. Booking reference: b0012. We look forward to seeing you."}

Doctor: Dr. Vikram Mehta
Date: Friday 25 September
Time: 17:30
Session: therapy session
Reference: b0003
JSON: {"reply": "Done. Your therapy session with Dr. Vikram Mehta is on Friday 25 September at 17:30. Reference b0003."}

Doctor: {{ doctor_name }}
Date: {{ date }}
Time: {{ time }}
Session: {{ session }}
Reference: {{ booking_id }}
JSON:
