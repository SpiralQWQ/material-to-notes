"""Exhaustive fidelity check: every number in the note, traced back to the source.

This replaces "sample five fact points and eyeball them" with a full sweep. It is
deterministic — no model is called — so its verdict is evidence, not an opinion.

The hard part is normalisation, and it is not optional. MinerU's OCR splits
numbers apart with spaces: the source literally contains ``1. 8 5 3 2`` where the
author wrote ``1.8532``. A naive substring search then reports the note's faithful
``1.8532`` as a number that "does not exist in the source" — a false hallucination.
So the source is normalised (spaces inside numeric runs collapsed) before anything
is compared, and every normalisation applied is printed for review.

Three buckets come out:

  MISSING_IN_SOURCE  a number the note has and the source does not — the only
                     bucket that fails the run. Numbers on a line carrying a
                     「源文未述」 marker are 讲解举例 and are excused.
  MISSING_IN_NOTE    a number the source has and the note does not — a possible
                     omission; reported, never failing on its own.
  NORMALISED         what the OCR repair changed, so nothing is fixed silently.

Usage:
    python scripts/verify_fidelity.py --note <note.md> --src <cleaned.txt>
"""

from __future__ import annotations

import argparse
import re
import sys

# A number is "worth checking" when it carries information: a decimal point, an
# exponent, or at least three digits. Bare 1- and 2-digit integers are everywhere
# (list numbering, page numbers) and would drown the signal.
_NUMBER = re.compile(r"\d+(?:\.\d+)?(?:[eE][+-]?\d+)?")

# --- normalisation: undo what the OCR did to numbers ------------------------
# Deliberately narrow. A first version collapsed *any* space between digits and
# produced pure noise: it glued the chromosome bit strings ("1100 0101 1111" ->
# "110001011111") and half-repaired decimals ("1. 8 5 3 2" -> "1. 8532"), turning
# one faithful note into 17 "hallucinations". Only these two shapes are repaired:
#   a dotted number whose fractional digits are space-separated  -> 1. 8 5 3 2
#   a long integer whose digits are space-separated             -> 1 0 4
# The separator is [ \t], never \s: a newline is a line break, not a split number.
# (A version using \s joined digits across lines and invented numbers like
# "60278514" out of a column of separate figures.)
_DOTTED_SPACED = re.compile(r"(?<=\d)\.([ \t]*\d)(?:[ \t]+\d)+")
_INT_SPACED = re.compile(r"(?<!\d)\d(?:[ \t]+\d){2,}(?!\d)")

# --- things that look like numbers but are not measurements -----------------
# Citations into the source ("源文 line 1012", "lines 401、438、1020"), ISO dates,
# and §-numbered sections are structure, not content. Comparing them produces
# only false leads — seven of the twelve in the first real run were citations.
_CITATION = re.compile(r"\blines?\s*\d+(?:(?:\s*[、,，]\s*|\s*[–—-]\s*)\d+)*", re.I)
_CITATION_ZH = re.compile(r"第\s*\d+\s*[行页]")
_ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
_SECTION = re.compile(r"§+\s*\d+(?:\.\d+)*")
_FRONTMATTER = re.compile(r"\A---\s*\n.*?\n---\s*\n", re.S)

# A line that says its numbers are the writer's own is not a hallucination.
_EXCUSED = ("源文未述", "此处为讲解", "讲解举例", "非论文数据")

# Unit conversions the note performs itself (10.25 百万元 -> 1025 万元).
_SCALE = (10, 100, 1000, 10000)

MARKERS = ("MISSING_IN_SOURCE", "MISSING_IN_NOTE", "NORMALISED")


def _worth_checking(token: str) -> bool:
    if "." in token or "e" in token.lower():
        return True
    return len(token.lstrip("0")) >= 3


def _strip_non_measurements(text: str) -> str:
    """Remove frontmatter, citations, dates and section numbers before comparing.

    Frontmatter is blanked rather than deleted: dropping those lines would shift
    every line number below it, and a report that points at the wrong line sends
    the reader somewhere else entirely. Citations and §-numbers sit inside a line,
    so they can go without changing the shape.
    """
    text = _FRONTMATTER.sub(lambda m: "\n" * m.group(0).count("\n"), text)
    for pattern in (_CITATION, _CITATION_ZH, _ISO_DATE, _SECTION):
        text = pattern.sub(" ", text)
    return text


def _join(match) -> str:
    return re.sub(r"\s+", "", match.group(0))


def normalise_ocr_spacing(text: str) -> tuple:
    """Repair only the two OCR shapes. Returns (normalised_text, changes)."""
    changes = []

    def record(pattern, value):
        for found in pattern.finditer(value):
            changes.append(found.group(0))
        return pattern.sub(_join, value)

    out = record(_DOTTED_SPACED, text)
    out = record(_INT_SPACED, out)
    return out, sorted(set(changes))


def numbers_in(text: str) -> dict:
    """{number: line_number} for every number worth checking."""
    found = {}
    for lineno, line in enumerate(text.splitlines(), 1):
        for match in _NUMBER.finditer(line):
            token = match.group(0)
            if _worth_checking(token):
                found.setdefault(token, lineno)
    return found


def line_is_excused(line: str) -> bool:
    return any(marker in line for marker in _EXCUSED)


def _is_derived(token: str, source_numbers) -> bool:
    """True when the note's number is a unit conversion of a number in the source."""
    try:
        value = float(token)
    except ValueError:
        return False
    return any(abs(value - float(other) * scale) < 1e-9
               for other in source_numbers for scale in _SCALE)


def run(note_text: str, src_text: str) -> dict:
    normalised_src, changes = normalise_ocr_spacing(_strip_non_measurements(src_text))
    src_numbers = numbers_in(normalised_src)
    clean_note = _strip_non_measurements(note_text)
    note_lines = clean_note.splitlines()

    missing_in_source, derived = [], []
    for token, lineno in sorted(numbers_in(clean_note).items()):
        if token in src_numbers:
            continue
        line = note_lines[lineno - 1] if lineno <= len(note_lines) else ""
        item = {"number": token, "line": lineno, "excused": line_is_excused(line),
                "text": line.strip()}
        if not item["excused"] and _is_derived(token, src_numbers):
            item["excused"] = True
            item["derived"] = True
        (derived if item.get("derived") else missing_in_source).append(item)

    missing_in_note = sorted(t for t in src_numbers if t not in numbers_in(note_text))
    return {
        "missing_in_source": missing_in_source,
        "derived": derived,
        "missing_in_note": missing_in_note,
        "normalised": changes,
        "note_numbers": len(numbers_in(clean_note)),
        "source_numbers": len(src_numbers),
    }


def _excerpt(text: str, limit: int = 90) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit] + "…"


def render(report: dict) -> str:
    out = []
    real = [item for item in report["missing_in_source"] if not item["excused"]]
    noted = [item for item in report["missing_in_source"] if item["excused"]]
    derived = report.get("derived", [])

    out.append(f"笔记数字 {report['note_numbers']} 个 | 源文数字 {report['source_numbers']} 个")
    out.append("")

    out.append(f"MISSING_IN_SOURCE — 笔记有、源文无（{len(real)} 条）"
               + ("：**需逐条定性，未标注即判幻觉**" if real else "：无"))
    for item in real:
        out.append(f"  ! {item['number']}  (笔记第 {item['line']} 行)  {_excerpt(item['text'])}")

    if noted:
        out.append("")
        out.append(f"  已标注为讲解补充、不计（{len(noted)} 条）：" + "、".join(
            f"{i['number']}(第{i['line']}行)" for i in noted))

    if derived:
        out.append("")
        out.append(f"  笔记自行换算、不计（{len(derived)} 条）：" + "、".join(
            f"{i['number']}(第{i['line']}行)" for i in derived))

    out.append("")
    out.append(f"MISSING_IN_NOTE — 源文有、笔记无（{len(report['missing_in_note'])} 条，仅供参考）")
    if report["missing_in_note"]:
        out.append("  " + ", ".join(report["missing_in_note"][:40])
                   + ("…" if len(report["missing_in_note"]) > 40 else ""))

    if report["normalised"]:
        out.append("")
        out.append(f"NORMALISED — OCR 拆开的数字，已修复后再比（{len(report['normalised'])} 处）")
        out.append("  " + "; ".join(f"{c!r} -> {re.sub(chr(92)+'s+', '', c)!r}"
                                    for c in report["normalised"][:20]))

    out.append("")
    out.append(f"判定: {'FAIL' if real else 'PASS'}")
    return "\n".join(out)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="笔记数字全量回源核对")
    parser.add_argument("--note", required=True)
    parser.add_argument("--src", required=True)
    args = parser.parse_args(argv)

    with open(args.note, encoding="utf-8", errors="replace") as handle:
        note_text = handle.read()
    with open(args.src, encoding="utf-8", errors="replace") as handle:
        src_text = handle.read()

    report = run(note_text, src_text)
    print(render(report))
    return 1 if any(not item["excused"] for item in report["missing_in_source"]) else 0


if __name__ == "__main__":
    sys.exit(main())
