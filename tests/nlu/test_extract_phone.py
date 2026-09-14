from app.nlu import extract_phone as m


def test_ten_digits_present_in_text_pass():
    assert m.validate({"digits": "9876543210"}, {"user_text": "it's 98765 43210"}) == ({"digits": "9876543210"}, True, "ok")


def test_country_code_is_stripped():
    assert m.validate({"digits": "919876543210"}, {"user_text": "+91 9876543210"})[0] == {"digits": "9876543210"}


def test_digits_not_in_user_text_are_rejected():
    out, ok, reason = m.validate({"digits": "9000000000"}, {"user_text": "my number is 9876543210"})
    assert (out, ok, reason) == ({"digits": ""}, False, "digits_not_in_text")


def test_wrong_length_rejected():
    assert m.validate({"digits": "12345"}, {"user_text": "12345"})[2] == "not_ten_digits"


def test_empty_means_no_number_and_is_ok():
    assert m.validate({"digits": ""}, {"user_text": "I forgot"}) == ({"digits": ""}, True, "ok")
