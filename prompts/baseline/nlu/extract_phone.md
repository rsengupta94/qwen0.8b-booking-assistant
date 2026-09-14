You extract a phone number from a patient's reply to an appointment booking assistant.

The assistant asked: "Could you share the phone number registered with us?"

Return JSON: {"digits": "<the 10-digit number, digits only>"} or {"digits": ""} if there is no phone number in the reply.

Examples:

Reply: 9876543210
JSON: {"digits": "9876543210"}

Reply: it's 98765 43210
JSON: {"digits": "9876543210"}

Reply: my number is +91 91234 56780
JSON: {"digits": "9123456780"}

Reply: I don't remember which number I gave
JSON: {"digits": ""}

Reply: sure, 9000012345 is mine
JSON: {"digits": "9000012345"}

Reply: {{ user_text }}
JSON:
