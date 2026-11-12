from evolvxsi.tasks.claims import open_unsupported, split_claims, visible_text


def test_sentences_with_citations_are_supported() -> None:
    claims = split_claims("Receipts are due in 30 days [1]. Flights are economy. The office opens at 08:00 [2].")
    assert [(c["status"], c["cites"]) for c in claims] == [("supported", [1]), ("unsupported", []), ("supported", [2])]
    assert open_unsupported(claims) == 1


def test_decisions_shape_the_visible_text() -> None:
    claims = split_claims("A is true [1]. B is a guess. C is another guess.")
    claims[1]["decision"] = "keep"
    claims[2]["decision"] = "remove"
    assert open_unsupported(claims) == 0
    assert visible_text(claims) == "A is true [1]. B is a guess."
    assert visible_text(claims, label_unsupported=True) == "A is true [1]. B is a guess. _(unsupported)_"


def test_decimal_numbers_do_not_split_sentences() -> None:
    assert len(split_claims("The limit is 1.5 days [1]. Next.")) == 2
