#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Write kinship lexicons as TOML for human review.

One file per language in ``review/``, one table per concept the language has a
word for: the lemmas, the concept's English lemmas (or those of its closest
broader concept, with ``english_via``), its label and definition, where each
lemma comes from, and an empty ``comment``. KinDiv's recorded gaps follow as
tables with no lemmas, since a gap is a claim to check too.

For Cantonese, ``review/yue-proposed.tsv`` adds proposed terms (characters and
Jyutping) that are not yet in the build.

Usage: uv run kin_review.py [tag ...]   (default: en cmn ja id cs yue; run build.py first)
"""

from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path
from xml.etree import ElementTree

import build

HERE = Path(__file__).resolve().parent
DC = "{https://globalwordnet.github.io/schemas/dc/}"


def s(value: str) -> str:
    """A TOML basic string."""
    return json.dumps(value, ensure_ascii=False)


def array(values: list[str]) -> str:
    """A TOML array of strings."""
    return "[" + ", ".join(s(v) for v in values) + "]"


def read_lexicon(tag: str) -> tuple[dict, set[str]]:
    """Code -> lemma -> sources, and the codes recorded as gaps."""
    lexicon = f"kindiv-{tag}"
    path = (
        HERE
        / "release"
        / f"kindiv-{build.VERSION}"
        / lexicon
        / f"{lexicon}-{build.VERSION}.xml"
    )
    root = ElementTree.parse(path).getroot()
    code_of, gaps = {}, set()
    for synset in root.iter("Synset"):
        code = synset.get(DC + "identifier").removeprefix("KinDiv:")
        code_of[synset.get("id")] = code
        if "lexical gap" in (synset.get("note") or ""):
            gaps.add(code)
    words: dict[str, dict[str, set[str]]] = defaultdict(dict)
    for entry in root.iter("LexicalEntry"):
        lemma = entry.find("Lemma").get("writtenForm")
        for sense in entry.iter("Sense"):
            if sense.get("lexicalized") == "false":
                continue  # English phrases for unnamed concepts
            sources = {
                src.split(":")[0].split()[0]
                for src in (sense.get(DC + "source") or "").split("; ")
                if src
            }
            words[code_of[sense.get("synset")]][lemma] = sources
    return words, gaps


def english_for(code: str, english: dict, ancestry: dict) -> tuple[list[str], str]:
    """English lemmas of a concept, or of its closest broader concept that has some."""
    if english.get(code):
        return list(english[code]), ""
    above = [a for a in ancestry.get(code, ()) if english.get(a)]
    closest = [a for a in above if not any(a in ancestry.get(b, ()) for b in above)]
    if not closest:
        return [], ""
    via = min(closest)
    return list(english[via]), via


def proposals(tag: str) -> dict[str, list[dict[str, str]]]:
    """Proposed terms not yet in the build (only Cantonese so far)."""
    path = HERE / "review" / f"{tag}-proposed.tsv"
    found: dict[str, list[dict[str, str]]] = defaultdict(list)
    if path.exists():
        with path.open(encoding="utf8") as handle:
            for row in csv.DictReader(handle, delimiter="\t"):
                found[row["code"]].append(row)
    return found


def write(tag: str, concepts: dict, ancestry: dict, english: dict) -> Path:
    """Write review/<tag>.toml."""
    words, gaps = read_lexicon(tag)
    proposed = proposals(tag)
    order = list(concepts)
    lines = [
        f"# KinDiv kinship terms for {tag}, from the built lexicon kindiv-{tag}.",
        "# One table per concept. Edit `comment`; leave the rest as generated.",
    ]
    if proposed:
        lines.append(
            "# `proposed` lemmas are NOT in the build: written by Claude Opus 5.5 from its"
            " own knowledge, for a speaker to check (Jyutping romanization)."
        )
    lines.append("")
    written = sorted(set(words) | set(proposed), key=order.index)
    for code in written:
        concept = concepts[code]
        lines.append(f"[{s(code)}]")
        lines.append(f"lemmas = {array(list(words.get(code, {})))}")
        if code in gaps:
            lines.append(
                'status = "KinDiv records a gap here, but there are words: check"'
            )
        if proposed.get(code):
            lines.append(f"proposed = {array([p['lemma'] for p in proposed[code]])}")
            lines.append(f"jyutping = {array([p['jyutping'] for p in proposed[code]])}")
            lines.append(
                f"confidence = {array([p['confidence'] for p in proposed[code]])}"
            )
            notes = [f"{p['lemma']}: {p['note']}" for p in proposed[code] if p["note"]]
            if notes:
                lines.append(f"notes = {array(notes)}")
        if tag != "en":
            eng, via = english_for(code, english, ancestry)
            if eng:
                lines.append(f"english = {array(eng)}")
            if via:
                lines.append(f"english_via = {s(via)}")
        lines.append(f"label = {s(concept.label)}")
        lines.append(f"definition = {s(concept.definition)}")
        sources = [
            f"{w} <- {', '.join(sorted(src))}" for w, src in words.get(code, {}).items()
        ]
        if sources:
            lines.append(f"sources = {array(sources)}")
        lines.append('comment = ""')
        lines.append("")
    for code in sorted(gaps - set(written), key=order.index):
        concept = concepts[code]
        lines.append(f"[{s(code)}]")
        lines.append("lemmas = []")
        lines.append('status = "recorded gap (KinDiv): no word for this"')
        lines.append(f"label = {s(concept.label)}")
        lines.append(f"definition = {s(concept.definition)}")
        lines.append('comment = ""')
        lines.append("")
    out = HERE / "review" / f"{tag}.toml"
    out.write_text("\n".join(lines), encoding="utf8")
    return out


def main() -> None:
    """Write the review files."""
    tags = sys.argv[1:] or ["en", "cmn", "ja", "id", "cs", "yue"]
    concepts = build.read_concepts()
    ancestry = build.read_hierarchy(concepts)
    english, _ = read_lexicon("en")
    english = {code: list(lemmas) for code, lemmas in english.items()}
    (HERE / "review").mkdir(exist_ok=True)
    for tag in tags:
        path = write(tag, concepts, ancestry, english)
        print(path.relative_to(HERE), file=sys.stderr)


if __name__ == "__main__":
    main()
