You choose the best doctor for a new patient at a mental health clinic, from a shortlist.

Patient's concern: {{ user_text }}

Shortlist:
{% for d in shortlist %}- id: {{ d.id }} | {{ d.name }}, {{ d.degree }}, {{ d.years_experience }} years | {{ d.subspecialty }} | treats: {{ d.conditions | join(", ") }} | {{ d.skills }}
{% endfor %}
Return JSON with two fields:
- doctor_id: the id of one doctor from the shortlist
- reason: one sentence on why this doctor fits the concern

Examples:

Patient's concern: constant anxiety with racing heart
Shortlist:
- id: d_a | Dr. A, MD Psychiatry, 14 years | General adult psychiatry | treats: generalised anxiety, panic attacks, major depression | Anxiety disorders, panic, low mood. Medication review and CBT-informed therapy.
- id: d_b | Dr. B, PhD Clinical Psychology, 9 years | Stress and sleep psychology | treats: work burnout, insomnia | Work stress, burnout, insomnia. Short-term structured therapy.
JSON: {"doctor_id": "d_a", "reason": "Dr. A specialises in anxiety and panic and can review medication."}

Patient's concern: trouble falling asleep and waking at night
Shortlist:
- id: d_b | Dr. B, PhD Clinical Psychology, 9 years | Stress and sleep psychology | treats: work burnout, insomnia, CBT for insomnia | Work stress, burnout, insomnia. Short-term structured therapy.
- id: d_c | Dr. C, MD Psychiatry, 20 years | Mood, trauma and loss | treats: recurrent depression, bereavement, PTSD | Long-standing depression, grief and loss. Long-term therapy.
JSON: {"doctor_id": "d_b", "reason": "Dr. B treats insomnia with structured short-term therapy."}

Patient's concern: low mood since my mother died last year, nothing helps
Shortlist:
- id: d_a | Dr. A, MD Psychiatry, 14 years | General adult psychiatry | treats: generalised anxiety, panic attacks, major depression, medication review | Anxiety disorders, panic, OCD and depression in adults.
- id: d_c | Dr. C, MD Psychiatry, 20 years | Mood, trauma and loss | treats: recurrent depression, bereavement, PTSD | Long-standing depression, grief and loss. Long-term therapy.
JSON: {"doctor_id": "d_c", "reason": "Dr. C specialises in depression linked to bereavement and offers long-term therapy."}

Now the patient's concern is: {{ user_text }}
JSON:
