#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["unidecode", "wn>=1.1"]  # build.py, cygnet_wordnets.py
# ///
"""Write kinship lexicons as TOML for human review.

One file per language in ``review/``, one table per concept the language has a
word for: the lemmas, the concept's English lemmas (or those of its closest
broader concept, with ``english_via``), its label and definition, where each
lemma comes from, and an empty ``comment``. KinDiv's recorded gaps follow as
tables with no lemmas, since a gap is a claim to check too.

For Cantonese, ``review/kinterms-yue-proposed.tsv`` adds proposed terms (characters and
Jyutping) that are not yet in the build.

Usage: uv run kin_review.py [tag ...]   (default: en cmn ja id cs yue; run build.py first)
"""

from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from functools import cache
from pathlib import Path
from xml.etree import ElementTree

import build
import cygnet_wordnets

HERE = Path(__file__).resolve().parent
DC = "{https://globalwordnet.github.io/schemas/dc/}"


def s(value: str) -> str:
    """A TOML basic string."""
    return json.dumps(value, ensure_ascii=False)


def array(values: list[str]) -> str:
    """A TOML array of strings."""
    return "[" + ", ".join(s(v) for v in values) + "]"


def read_lexicon(tag: str) -> tuple[dict, set[str], dict[str, str]]:
    """Code -> lemma -> sources, the codes recorded as gaps, and code -> phrase.

    A phrase is an unlexicalized sense: English *father's sister's husband* names
    a kin type English has no word for.
    """
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
    phrases: dict[str, str] = {}
    for entry in root.iter("LexicalEntry"):
        lemma = entry.find("Lemma").get("writtenForm")
        for sense in entry.iter("Sense"):
            if sense.get("lexicalized") == "false":
                phrases[code_of[sense.get("synset")]] = lemma
                continue
            sources = {
                src.split(":")[0].split()[0]
                for src in (sense.get(DC + "source") or "").split("; ")
                if src
            }
            words[code_of[sense.get("synset")]][lemma] = sources
    return words, gaps, phrases


@cache
def kin_ilis() -> frozenset[str]:
    """The ILIs KinDiv's concepts link to (*relative*, *spouse*, *grandfather*...)."""
    return frozenset(c.ili for c in build.read_concepts().values() if c.ili)


def kin_like(synset: cygnet_wordnets.wn.Synset) -> bool:
    """Whether an existing synset could be a kinship sense.

    Kept: synsets whose ILI is, or is below in OEWN, one KinDiv links to (a
    synset with no ILI is judged by its hypernyms), and synsets with neither
    (TUFS's own). That drops other senses of the same words: *brother* the monk
    or the buddy, *uncle* the benefactor, Polish *babka* the cake.
    """
    return cygnet_wordnets.under(synset, kin_ilis()) is not False


def existing_lines(tag: str, ili: str, lemmas: list[str]) -> list[str]:
    """What the language's Cygnet wordnets already have, to check against.

    ``existing_by_ili``: their synsets for the concept's ILI, where it has one.
    ``existing_by_lemma``: their noun synsets for each of our lemmas that could
    be kinship senses (`kin_like`); ``existing_hidden`` counts the others.
    """
    lines = []
    found = cygnet_wordnets.by_ili(tag, ili)
    if found:
        lines.append(f"existing_by_ili = {array(found)}")
    hits, hidden = [], 0
    for lemma in lemmas:
        kept, dropped = cygnet_wordnets.by_lemma(tag, lemma, "n", kin_like)
        hits += [f"{lemma} -> {synset}" for synset in kept]
        hidden += dropped
    if hits:
        lines.append(f"existing_by_lemma = {array(hits)}")
    if hidden:
        lines.append(f"existing_hidden = {hidden}  # other senses of these lemmas")
    return lines


def read_sounds(tag: str) -> dict[str, list[tuple[str, str]]]:
    """Lemma -> its pronunciations as (text, notation).

    ``source-transcription`` marks a lemma that is itself a transcription (a
    Kinbank romanization with no word in the language's own script).
    """
    lexicon = f"kindiv-{tag}"
    path = (
        HERE
        / "release"
        / f"kindiv-{build.VERSION}"
        / lexicon
        / f"{lexicon}-{build.VERSION}.xml"
    )
    sounds: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for lemma in ElementTree.parse(path).getroot().iter("Lemma"):
        for sound in lemma.iter("Pronunciation"):
            sounds[lemma.get("writtenForm")].append(
                (sound.text or "", sound.get("notation") or "")
            )
    return sounds


def sound_lines(lemmas: list[str], sounds: dict) -> list[str]:
    """``pronunciations`` (IPA, romanization) and ``transcribed`` lemmas, if any."""
    heard = [
        f"{lemma}: {text} ({notation})"
        for lemma in lemmas
        for text, notation in sounds.get(lemma, ())
        if notation != "source-transcription"
    ]
    transcribed = [
        lemma
        for lemma in lemmas
        if any(n == "source-transcription" for _, n in sounds.get(lemma, ()))
    ]
    lines = []
    if heard:
        lines.append(f"pronunciations = {array(heard)}")
    if transcribed:
        lines.append(
            f"transcribed = {array(transcribed)}"
            "  # romanized in the source; no word in the native script here"
        )
    return lines


def ancestors(code: str, parents: dict[str, set[str]]) -> list[str]:
    """Every concept above `code` in the shared hierarchy, nearest first.

    The hierarchy is a lattice (*x;El;Br* is under both *El;Br* and *x;Br*), so
    this is the union of all the hypernym chains up to the root, by distance.
    """
    found: list[str] = []
    layer = sorted(parents.get(code, ()))
    while layer:
        layer = [c for c in dict.fromkeys(layer) if c not in found]
        found += layer
        layer = sorted({p for c in layer for p in parents.get(c, ())})
    return found


def hierarchy_lines(code: str, parents: dict[str, set[str]]) -> list[str]:
    """The ``hypernyms`` (direct) and ``ancestors`` (all, nearest first) lines."""
    return [
        f"hypernyms = {array(sorted(parents.get(code, ())))}",
        f"ancestors = {array(ancestors(code, parents))}",
    ]


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
    path = HERE / "review" / f"kinterms-{tag}-proposed.tsv"
    found: dict[str, list[dict[str, str]]] = defaultdict(list)
    if path.exists():
        with path.open(encoding="utf8") as handle:
            for row in csv.DictReader(handle, delimiter="\t"):
                found[row["code"]].append(row)
    return found


def write(
    tag: str, concepts: dict, parents: dict, ancestry: dict, english: dict
) -> Path:
    """Write review/kinterms-<tag>.toml.

    Besides the concepts with words and the recorded gaps, every concept above
    them in the shared hierarchy gets a table, marked as having no word in the
    language, so that each table's ``ancestors`` can be read in the file.
    """
    words, gaps, phrases = read_lexicon(tag)
    sounds = read_sounds(tag)
    proposed = proposals(tag)
    order = list(concepts)
    listed = set(words) | set(proposed) | gaps
    above = {a for code in listed for a in ancestors(code, parents)}
    lines = [
        f"# KinDiv kinship terms for {tag}, from the built lexicon kindiv-{tag}.",
        "# One table per concept. Edit `comment`; leave the rest as generated.",
        (
            "# hypernyms: direct hypernyms in the shared (mul) hierarchy;"
            " ancestors: all of them, nearest first."
        ),
        (
            "# Concepts with no word here are included where the hierarchy needs them"
            " (status `unlexicalized`)."
        ),
        (
            "# existing_by_ili, existing_by_lemma: synsets in the language's Cygnet"
            " wordnets (oewn, omw-pl, ...), as"
        ),
        (
            "#   lexicon id [ILI] lemmas: definition; (CILI) marks a definition taken"
            " from the ILI."
        ),
        (
            "#   Lemma matches keep only kinship senses (no ILI, or under an ILI"
            " KinDiv links to, by OEWN);"
        ),
        "#   existing_hidden counts the rest.",
    ]
    if proposed:
        lines.append(
            "# `proposed` lemmas are NOT in the build: written by Claude Opus 5.5 from its"
            " own knowledge, for a speaker to check (Jyutping romanization)."
        )
    lines.append("")
    written = sorted(set(words) | set(proposed) | (above - gaps), key=order.index)
    for code in written:
        concept = concepts[code]
        lines.append(f"[{s(code)}]")
        lines.append(f"lemmas = {array(list(words.get(code, {})))}")
        lines += sound_lines(list(words.get(code, {})), sounds)
        if code in gaps:
            lines.append(
                'status = "KinDiv records a gap here, but there are words: check"'
            )
        elif code not in words and code not in proposed:
            lines.append(
                f'status = "unlexicalized: no {tag} word; included for the hierarchy"'
            )
        if code in phrases:
            lines.append(f"phrase = {s(phrases[code])}  # unlexicalized")
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
        mine = list(words.get(code, {})) + [p["lemma"] for p in proposed.get(code, [])]
        lines += existing_lines(tag, concept.ili, mine)
        lines += hierarchy_lines(code, parents)
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
        if code in phrases:
            lines.append(f"phrase = {s(phrases[code])}  # unlexicalized")
        lines.append(f"label = {s(concept.label)}")
        lines.append(f"definition = {s(concept.definition)}")
        lines += existing_lines(tag, concept.ili, [])
        lines += hierarchy_lines(code, parents)
        lines.append('comment = ""')
        lines.append("")
    out = HERE / "review" / f"kinterms-{tag}.toml"
    out.write_text("\n".join(lines), encoding="utf8")
    return out


def main() -> None:
    """Write the review files."""
    tags = sys.argv[1:] or ["en", "cmn", "ja", "id", "cs", "yue"]
    concepts = build.read_concepts()
    ancestry = build.read_hierarchy(concepts)
    parents = build.nearest(set(concepts), ancestry)
    english, _, _ = read_lexicon("en")
    english = {code: list(lemmas) for code, lemmas in english.items()}
    (HERE / "review").mkdir(exist_ok=True)
    for tag in tags:
        path = write(tag, concepts, parents, ancestry, english)
        print(path.relative_to(HERE), file=sys.stderr)


if __name__ == "__main__":
    main()
