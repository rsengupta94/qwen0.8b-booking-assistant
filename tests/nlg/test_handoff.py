from app.nlg import handoff as m


def test_handoff_gives_customer_care_number():
    t = m.template({"kind": "handoff", "reason": "reask_limit:no_days"})
    assert "1800-000-0000" in t and "understand" in t


def test_ended_template():
    assert "ended" in m.template({"kind": "ended"})
