from app.services.pdf import chunk_text, split_sentences
from app.services.red_flags import scan_red_flags


def test_chunk_text_respects_limit_and_keeps_content():
    text = "\n".join(f"line {i} " + "x" * 40 for i in range(200))
    chunks = chunk_text(text, 500)
    assert all(len(c) <= 500 for c in chunks)
    assert "\n".join(chunks).count("line ") == 200


def test_chunk_text_splits_oversized_line():
    assert all(len(c) <= 100 for c in chunk_text("y" * 450, 100))


def test_split_sentences_drops_markers_and_tables():
    text = "[PAGE 1]\nRevenue grew strongly this quarter. Operating margins improved a lot!\n| a | b |\n|---|---|"
    s = split_sentences(text)
    assert s == ["Revenue grew strongly this quarter.", "Operating margins improved a lot!"]


def test_red_flags_score_drops_with_mentions():
    clean = scan_red_flags("Everything went well. " * 500)
    bad = scan_red_flags("There is substantial doubt about going concern and a material weakness. " * 50)
    assert clean["score"] > bad["score"]
    assert {f["flag"]: f["mentions"] for f in bad["flags"]}["Going concern doubt"] > 0
