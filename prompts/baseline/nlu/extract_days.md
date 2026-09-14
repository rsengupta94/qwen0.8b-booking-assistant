A patient was asked: "Which days work for you?"
Extract the time of day, if any, and the days they named.

time_pref is "morning", "afternoon", "evening", or null if they did not say.
Days must be from this list: {{ day_terms | join(", ") }}. Expand short forms (mon = monday, tue = tuesday, wed = wednesday, thu = thursday, fri = friday, sat = saturday, sun = sunday).

Return JSON: {"time_pref": ..., "days": [...]}

Reply: wednesday afternoon
JSON: {"time_pref": "afternoon", "days": ["wednesday"]}

Reply: tomorrow, mornings are best
JSON: {"time_pref": "morning", "days": ["tomorrow"]}

Reply: Monday or Thursday
JSON: {"time_pref": null, "days": ["monday", "thursday"]}

Reply: today if possible, after 5
JSON: {"time_pref": "evening", "days": ["today"]}

Reply: fri
JSON: {"time_pref": null, "days": ["friday"]}

Reply: {{ user_text }}
JSON:
