You read which appointment slot a patient picked, from their reply to an appointment booking assistant.

The assistant offered these slots:
{% for s in offered_slots %}{{ loop.index }}. {{ s.weekday | capitalize }} {{ s.start[:10] }} at {{ s.start[11:] }}
{% endfor %}
Return JSON with three fields:
- choice_index: the number of the slot the patient picked (1, 2, 3 ...), or null
- wants_other: true if the patient wants different slots instead
- other: anything else the patient asked for, or null

Examples:

Reply: the first one
JSON: {"choice_index": 1, "wants_other": false, "other": null}

Reply: 2
JSON: {"choice_index": 2, "wants_other": false, "other": null}

Reply: none of these work, anything later in the week?
JSON: {"choice_index": null, "wants_other": true, "other": "later in the week"}

Reply: I'll take the 3pm slot
JSON: {"choice_index": 1, "wants_other": false, "other": null}

Reply: do you have anything in the evening?
JSON: {"choice_index": null, "wants_other": true, "other": "evening"}

Reply: {{ user_text }}
JSON:
