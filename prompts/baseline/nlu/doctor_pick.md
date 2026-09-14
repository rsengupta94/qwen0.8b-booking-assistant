You choose the best doctor for a new patient at a mental health clinic, from a shortlist.

Patient's concern: {{ user_text }}

Shortlist:
{% for d in shortlist %}- id: {{ d.id }} | {{ d.name }}, {{ d.degree }}, {{ d.years_experience }} years | {{ d.skills }}
{% endfor %}
Return JSON with two fields:
- doctor_id: the id of one doctor from the shortlist
- reason: one sentence on why this doctor fits the concern

Examples:

Patient's concern: constant anxiety with racing heart
Shortlist:
- id: d_a | Dr. A, MD Psychiatry, 14 years | Anxiety disorders, panic, low mood. Medication review and CBT-informed therapy.
- id: d_b | Dr. B, PhD Clinical Psychology, 9 years | Work stress, burnout, insomnia. Short-term structured therapy.
JSON: {"doctor_id": "d_a", "reason": "Dr. A specialises in anxiety and panic and can review medication."}

Patient's concern: trouble falling asleep and waking at night
Shortlist:
- id: d_b | Dr. B, PhD Clinical Psychology, 9 years | Work stress, burnout, insomnia. Short-term structured therapy.
- id: d_c | Dr. C, MPhil Clinical Psychology, 6 years | Couples and family issues, stress management, sleep routines.
JSON: {"doctor_id": "d_b", "reason": "Dr. B treats insomnia with structured short-term therapy."}

Patient's concern: frequent conflict with spouse
Shortlist:
- id: d_d | Dr. D, MD Psychiatry, 20 years | Depression, grief and loss, relationship difficulties. Long-term therapy.
- id: d_c | Dr. C, MPhil Clinical Psychology, 6 years | Couples and family issues, stress management, sleep routines.
JSON: {"doctor_id": "d_c", "reason": "Dr. C works with couples and family conflict."}

Now the patient's concern is: {{ user_text }}
JSON:
