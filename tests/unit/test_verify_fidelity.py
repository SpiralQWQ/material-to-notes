"""Tests for scripts/verify_fidelity.py — the exhaustive number trace-back.

Every case here is one the first real run actually produced. That run reported 17
"hallucinations" and all 17 were artefacts of the checker, so the tests are mostly
about what the checker must NOT flag.
"""

import verify_fidelity as V


def _numbers(text):
    return set(V.numbers_in(text))


# --- OCR normalisation -----------------------------------------------------

def test_spaced_decimal_is_repaired():
    # The real source contains "1. 8 5 3 2" where the author wrote 1.8532.
    # The match starts at the dot, so that is what gets recorded as changed.
    text, changes = V.normalise_ocr_spacing("got $\\lambda = 1. 8 5 3 2$ here")
    assert "1.8532" in text
    assert changes == [". 8 5 3 2"]


def test_spaced_integer_is_repaired():
    text, changes = V.normalise_ocr_spacing("value 1 0 4 end")
    assert "104" in text and changes == ["1 0 4"]


def test_bit_strings_are_not_glued_together():
    # "1100 0101 1111" is three groups, not one number. An earlier version merged
    # them and invented 110001011111.
    text, changes = V.normalise_ocr_spacing("A:1100 0101 1111")
    assert text == "A:1100 0101 1111"
    assert changes == []


def test_two_numbers_on_one_line_are_not_glued():
    text, _ = V.normalise_ocr_spacing("轮廓值 0.49 0.455 0.385")
    assert text == "轮廓值 0.49 0.455 0.385"


def test_a_newline_is_not_a_split_number():
    # Using \s here joined digits across lines and invented numbers like 60278514.
    text, changes = V.normalise_ocr_spacing("6 0 2\n7 8 5")
    assert text == "602\n785"                  # each line repaired on its own
    assert changes == ["6 0 2", "7 8 5"]       # never joined across the break


# --- what is not a measurement ---------------------------------------------

def test_source_line_citations_are_ignored():
    assert "1012" not in V._strip_non_measurements("调用（源文 line 1012 `silhouette`）")
    assert "393" not in V._strip_non_measurements("（源文 lines 383–393）")
    assert "438" not in V._strip_non_measurements("（源文 lines 401、438、1020 等）")


def test_dates_and_section_numbers_are_ignored():
    assert "2026" not in V._strip_non_measurements("generated: 2026-10-13")
    assert "5" not in V._strip_non_measurements("见 §5.2 节")


def test_frontmatter_is_ignored():
    note = "---\ntitle: t\ndate: 2026-10-13\n---\n\n正文 424\n"
    assert _numbers(V._strip_non_measurements(note)) == {"424"}


# --- the three buckets ------------------------------------------------------

def test_number_absent_from_the_source_is_reported():
    report = V.run("笔记写了 7.777 这个数。", "源文里没有这个数。")
    assert [i["number"] for i in report["missing_in_source"]] == ["7.777"]
    assert V.main.__module__  # sanity: importable as a script


def test_a_marked_example_is_excused():
    # It stays in the list (so the report can show it) but is flagged excused, and
    # only unexcused entries can fail the run.
    note = "想象只能放 8000 人（源文未述，此处为讲解举例）。"
    report = V.run(note, "源文没有这个数。")
    assert [i["number"] for i in report["missing_in_source"]] == ["8000"]
    assert all(i["excused"] for i in report["missing_in_source"])
    assert "判定: PASS" in V.render(report)


def test_a_unit_conversion_is_excused():
    # The note turns "10.25 million yuan" into 1025 万元 — derived, not hallucinated.
    report = V.run("交易额超过 1025 万元。", "exceeded 10.25 million yuan")
    assert report["missing_in_source"] == []
    assert [i["number"] for i in report["derived"]] == ["1025"]


def test_a_faithful_note_passes_end_to_end():
    src = "got 1. 8 5 3 2 and 0. 0 0 4 6 (see lines 401、438)\n"
    note = "得到 1.8532 与 0.0046（源文 lines 401、438）\n"
    report = V.run(note, src)
    assert report["missing_in_source"] == []
    assert ". 8 5 3 2" in report["normalised"]


def test_numbers_only_in_the_source_are_informational():
    report = V.run("笔记只有一个数 42。", "源文有 42 和 999。")
    assert report["missing_in_note"] == ["999"]
    assert report["missing_in_source"] == []


def test_render_says_pass_when_nothing_is_unexplained():
    assert "判定: PASS" in V.render(V.run("数字 42。", "数字 42。"))
    assert "判定: FAIL" in V.render(V.run("数字 12345。", "没有这个数。"))


def test_reported_line_numbers_match_the_file():
    # Blanking frontmatter must not shift every line below it: a report that
    # points at the wrong line sends the reader somewhere else entirely.
    note = "---\ntitle: t\ndate: 2026-10-13\n---\n\n正文\n\n这一行有 7.777 这个数\n"
    report = V.run(note, "源文里没有。")
    hit = report["missing_in_source"][0]
    assert hit["number"] == "7.777"
    assert note.splitlines()[hit["line"] - 1].strip() == "这一行有 7.777 这个数"


def test_frontmatter_is_blanked_not_deleted():
    note = "---\ntitle: t\n---\n\nx\n"
    stripped = V._strip_non_measurements(note)
    assert len(stripped.splitlines()) == len(note.splitlines())
