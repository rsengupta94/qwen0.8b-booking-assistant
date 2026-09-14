A new patient at a mental health clinic was asked: "Could you tell me briefly what you would like help with?"
Pick the one category that fits their reply, then summarise the reply in one short sentence.

Categories:
{% for c in categories %}- {{ c }}
{% endfor %}
Return JSON: {"category": "<one category>", "summary": "<one sentence>"}

Reply: I've been feeling anxious all the time and my heart races
JSON: {"category": "anxiety", "summary": "constant anxiety with racing heart"}

Reply: my father passed away two months ago and I can't cope
JSON: {"category": "grief", "summary": "struggling to cope after father's death"}

Reply: I can't fall asleep and wake up at 3am every night
JSON: {"category": "sleep", "summary": "trouble falling asleep and waking at night"}

Reply: my wife and I keep fighting and I don't know what to do
JSON: {"category": "relationships", "summary": "frequent conflict with spouse"}

Reply: I feel empty and nothing interests me anymore
JSON: {"category": "depression", "summary": "persistent low mood and loss of interest"}

Reply: {{ user_text }}
JSON:
