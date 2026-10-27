from rulebook.search import jurisdictions


def test_jurisdictions_named_in_english_and_greek():
    assert jurisdictions("Is there a monthly deposit cap across operators in Germany?") == ["DE"]
    assert jurisdictions("Compare self-exclusion in Great Britain, Germany and Finland.") == ["UK", "DE", "FI"]
    assert jurisdictions("Επιτρέπεται σε Γερμανούς παρόχους να δανείζουν χρήματα;") == ["DE"]
    assert jurisdictions("Ποια είναι η ελάχιστη ηλικία για τυχερά παίγνια στην Ελλάδα;") == ["EL"]
    assert jurisdictions("What does the GlüStV say about bonuses?") == ["DE"]


def test_no_jurisdiction_means_search_everything():
    assert jurisdictions("What is a reasonable monthly deposit limit?") == []
    assert jurisdictions("Can a student play poker online?") == []  # 'uk' only as a whole word
