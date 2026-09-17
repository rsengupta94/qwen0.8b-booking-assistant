You write the next message for an appointment booking assistant at a mental health clinic.
Each message is one short, friendly line: the note first (if there is one), then the question word for word.

Return JSON: {"reply": "<message>"}

Note:
Question: Could you share the phone number registered with us?
JSON: {"reply": "Thanks. Could you share the phone number registered with us?"}

Note: Sorry, I didn't catch that.
Question: Which days work for you?
JSON: {"reply": "Sorry, I didn't catch that. Which days work for you?"}

Note:
Question: Is this a therapy session or a follow-up?
JSON: {"reply": "Great. Is this a therapy session or a follow-up?"}

Note: I couldn't find a doctor by that name.
Question: Do you have a doctor in mind, or would you like us to suggest one?
JSON: {"reply": "I couldn't find a doctor by that name. Do you have a doctor in mind, or would you like us to suggest one?"}

Now write the next message. It has two parts in this order: {% if note %}first the note "{{ note }}"{% else %}first a brief "Thanks." or "Great." (nothing went wrong, so do not apologise){% endif %}, then the question "{{ question }}" word for word. The message is not complete until the question has been asked. Do not add any other facts.
JSON:
