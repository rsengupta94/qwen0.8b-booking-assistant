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

Reply: I keep checking the locks and washing my hands, I know it's irrational
JSON: {"category": "ocd", "summary": "repeated checking and hand-washing compulsions"}

Reply: I want to stop drinking, it has got out of hand
JSON: {"category": "addiction", "summary": "wants help to stop drinking"}

Reply: it's for my 12 year old, the school says he can't sit still or focus
JSON: {"category": "child_adolescent", "summary": "12-year-old with attention and restlessness concerns at school"}

Reply: my mother is 78 and has become forgetful and withdrawn
JSON: {"category": "geriatric", "summary": "78-year-old mother with memory loss and withdrawal"}

Reply: I had my baby three weeks ago and I cry all day
JSON: {"category": "perinatal", "summary": "low mood three weeks after childbirth"}

Reply: I was in a bad accident last year and I still get flashbacks
JSON: {"category": "trauma", "summary": "flashbacks after an accident a year ago"}

Reply: {{ user_text }}
JSON:
