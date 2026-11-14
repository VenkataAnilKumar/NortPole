from nortpole.work.tasks.claims import open_unsupported, split_claims, visible_text


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


def test_decisions_carry_only_to_unchanged_unsupported_sentences() -> None:
    from nortpole.work.tasks.claims import carry_decisions

    old = split_claims("A is true [1]. B is a guess. C is a guess.")
    old[1]["decision"] = "keep"
    old[2]["decision"] = "remove"
    new = carry_decisions(split_claims("A is true [1]. B is a guess. C is now a different guess."), old)
    assert [c.get("decision") for c in new] == [None, "keep", None]


def test_unknown_citations_are_listed() -> None:
    from nortpole.work.tasks.claims import unknown_citations

    assert unknown_citations("x [1] y [3] z [9]", {1, 2, 3}) == [9]
