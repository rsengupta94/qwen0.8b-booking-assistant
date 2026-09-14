A returning patient at a mental health clinic was asked: "Is this a therapy session or a follow-up?"
Decide which they want.

- followup = a follow up, follow-up, review, check-in, or checkup
- therapy = a therapy, counselling, or regular session
- other = only when the reply is a question or unrelated

Return JSON: {"type": "therapy" | "followup" | "other"}

Reply: follow up
JSON: {"type": "followup"}

Reply: therapy
JSON: {"type": "therapy"}

Reply: follow-up please
JSON: {"type": "followup"}

Reply: my regular counselling session
JSON: {"type": "therapy"}

Reply: a review of my medication
JSON: {"type": "followup"}

Reply: what's the difference?
JSON: {"type": "other"}

Reply: {{ user_text }}
JSON:
