#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Build a multilingual WN-LMF wordnet from the KinDiv kinship database.

Each language with attested words becomes one lexicon. A synset stands for a
KinDiv concept (a Murdock kin type such as ``Fa;Br;So``) and is written when the
language either lexicalizes the concept or is recorded as having a gap for it;
gaps become ``lexicalized="false"`` synsets.

Concepts with an exact counterpart in the Collaborative Interlingual Index are
linked with ``ili=``. Inexact counterparts (``broader``/``narrower``) are kept as
``dc:relation`` and a note, never as ``ili=``, since ``ili=`` asserts identity.
Every other lexicalized concept is written as a new-ILI candidate (``ili="in"``)
with an ``ILIDefinition``, and listed in ``ili-proposals.tsv`` with its
attestation counts.

Usage: uv run wn/build.py
"""

from __future__ import annotations

import csv
import logging
import shutil
import tarfile
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

logger = logging.getLogger(__name__)

HERE = Path(__file__).resolve().parent
DATA = HERE.parent

VERSION = "0.1"
EMAIL = "bond@ieee.org"
LICENSE = "https://creativecommons.org/licenses/by-sa/3.0/"
URL = "https://github.com/fcbond/KinDiv"
CITATION = (
    "Temuulen Khishigsuren, Gábor Bella, Khuyagbaatar Batsuren, Abed Alhakim Freihat, "
    "Nandu Chandran Nair, Amarsanaa Ganbold, Hadi Khalilia, Yamini Chandrashekar and "
    "Fausto Giunchiglia (2022) Using Linguistic Typology to Enrich Multilingual "
    "Lexicons: the Case of Lexical Gaps in Kinship. LREC 2022."
)
DOCTYPE = (
    "<!DOCTYPE LexicalResource SYSTEM "
    '"http://globalwordnet.github.io/schemas/WN-LMF-1.4.dtd">'
)
DC_NAMESPACE = "https://globalwordnet.github.io/schemas/dc/"


#: Murdock's kin-type primitives as English nouns.
NOUNS = {
    "Fa": "father",
    "Mo": "mother",
    "Pa": "parent",
    "Pr": "parent",
    "Hu": "husband",
    "Wi": "wife",
    "Sp": "spouse",
    "Br": "brother",
    "Ss": "sister",
    "Sb": "sibling",
    "So": "son",
    "Da": "daughter",
    "Ch": "child",
}
#: Copy-paste debris in `words`: zero-width spaces inside Japanese words and
#: left-to-right marks after Arabic, Hebrew and Persian ones. ZWJ is kept, as
#: Sinhala and Malayalam spelling needs it.
INVISIBLE = str.maketrans("", "", "\u200b\u200e")
#: The kind of relative each subdomain holds; appended to every definition so the
#: shortest ("a son of one's son") still meet CILI's 20-character minimum.
GENUS = {
    "grandparents": "a grandparent",
    "grandchildren": "a grandchild",
    "siblings": "a sibling",
    "uncles and aunts": "an uncle or aunt",
    "nephews and nieces": "a nephew or niece",
    "cousins": "a cousin",
    "parents": "a parent",
    "children": "a child",
    "spouses": "a spouse",
    "in-laws": "an in-law",
    "relatives": "a relative",
}
#: General kin nouns spelled out when they would only repeat their genus
SPELLED_OUT = {
    "child": "son or daughter",
    "parent": "father or mother",
    "sibling": "brother or sister",
    "spouse": "husband or wife",
}
#: Kin terms that take "the": "the father of one's spouse", not "a father"
UNIQUE = {"father", "mother", "husband", "wife"}
EGO = {
    "": ("a person", "one's", "oneself"),
    "x": ("a man", "a man's", "him"),
    "o": ("a woman", "a woman's", "her"),
}


def read_tsv(path: Path) -> list[dict[str, str]]:
    """Read a KinDiv TSV; quoted fields may span lines (Manchu script)."""
    with path.open(encoding="utf8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


#: KinDiv language names to BCP 47 tags, from `langcodes.find` and checked by hand
#: (Laboya is Lamboya, lmy, not Labo, mwi, as langcodes guesses).
LANGUAGE_TAGS = {
    row["language"]: row["tag"] for row in read_tsv(HERE / "languages.tsv")
}


def slug(code: str) -> str:
    """Turn a kin-type code into an XML-safe id: ``x;Fa;Br;So`` -> ``x-Fa-Br-So``.

    A union of kin types (``Fa|Fa;Br``, "father or father's brother") joins its
    parts with ``_``.
    """
    return code.replace(";", "-").replace("|", "_")


def subdomain_of(code: str) -> str:
    """Guess a kin type's subdomain from its shape (for concepts outside KinDiv).

    >>> subdomain_of("Hu;Fa"), subdomain_of("x;Ss;Da"), subdomain_of("El;Fa;Br;So")
    ('in-laws', 'nephews and nieces', 'cousins')
    >>> subdomain_of("Fa|Fa;Br")
    'mergers'
    """
    if "|" in code:
        parts = {subdomain_of(part) for part in code.split("|")}
        return parts.pop() if len(parts) == 1 else "mergers"
    terms = [t for t in code.split(";") if t not in ("x", "o", "El", "Yn")]
    if any(t in ("Hu", "Wi", "Sp") for t in terms):
        return "spouses" if len(terms) == 1 else "in-laws"
    role = "".join(
        "P" if t in ("Fa", "Mo", "Pa") else "S" if t in ("Br", "Ss", "Sb") else "C"
        for t in terms
    )
    return {
        "P": "parents",
        "S": "siblings",
        "C": "children",
        "PP": "grandparents",
        "CC": "grandchildren",
        "PS": "uncles and aunts",
        "SC": "nephews and nieces",
        "PSC": "cousins",
    }.get(role, "relatives")


def parse(code: str, subdomain: str) -> tuple[str, str, list[str]]:
    """Read a Murdock kin-type code as (ego sex, relative age, chain of kin terms).

    ``El``/``Yn`` modify the following kin term (``Pa;El;Br`` is a parent's elder
    brother), except in the cousins subdomain, where KinDiv uses them for a cousin
    older or younger than self ("elder, son of father's brother").

    >>> parse("x;Fa;El;Br", "uncles and aunts")
    ('x', '', ['father', 'elder brother'])
    >>> parse("Yn;Fa;Br;So", "cousins")
    ('', 'younger', ['father', 'brother', 'son'])
    """
    parts = code.split(";")
    sex = parts.pop(0) if parts[0] in EGO else ""
    relative_age = ""
    chain: list[str] = []
    pending = ""
    for part in parts:
        if part in ("El", "Yn"):
            if subdomain == "cousins":
                relative_age = "older" if part == "El" else "younger"
            else:
                pending = ("elder" if part == "El" else "younger") + " "
        elif part == "Gr":
            chain.append(
                pending + ("child" if subdomain == "grandchildren" else "parent")
            )
            pending = ""
        elif part == "Pb":
            chain.extend(["parent", "sibling"])
        else:
            chain.append(pending + NOUNS[part])
            pending = ""
    return sex, relative_age, chain


def define(code: str, subdomain: str) -> str:
    """Compose an English definition from a Murdock kin-type code.

    A union is defined by its parts: "the father of a person or a brother of
    one's father".
    """
    if "|" in code:
        parts = [define(part, subdomain_of(part)) for part in code.split("|")]
        return " or ".join(part.rsplit(" (", 1)[0] for part in parts)
    sex, relative_age, chain = parse(code, subdomain)
    ego, ego_poss, ego_obj = EGO[sex]
    head, possessors = chain[-1], chain[:-1]
    article = "the" if head in UNIQUE else ("an" if head[0] in "aeiou" else "a")
    genus = GENUS[subdomain]
    if possessors:
        text = f"{article} {head} of {ego_poss} " + "'s ".join(possessors)
    elif genus == f"{article} {head}":
        # "a child of a man" says nothing its genus does not: spell the noun out
        noun = head.split()[-1]
        head = head.replace(noun, SPELLED_OUT.get(noun, noun))
        text = f"{article} {head} of {ego}"
    else:
        text = f"{article} {head} of {ego}"
    if relative_age:
        text += f", who is {relative_age} than {ego_obj if sex else 'oneself'}"
    # "the father of a person (a parent)" is fine; "a son or daughter of a man (a
    # child)" repeats itself
    return (
        text
        if genus.split()[-1] in head.split() or head in SPELLED_OUT.values()
        else (f"{text} ({genus})")
    )


def phrase(code: str, subdomain: str) -> str:
    """Compose the English phrase for a kin type, for concepts English has no word for.

    >>> phrase("Fa;Ss;Hu", "uncles and aunts")
    "father's sister's husband"
    >>> phrase("x;Gr;Fa", "grandparents")
    "man's parent's father"
    >>> phrase("El;Fa;Br;So", "cousins")
    "father's brother's son (older than self)"
    """
    if "|" in code:
        return " or ".join(phrase(part, subdomain_of(part)) for part in code.split("|"))
    sex, relative_age, chain = parse(code, subdomain)
    text = "'s ".join(([EGO[sex][0].removeprefix("a ")] if sex else []) + chain)
    return f"{text} ({relative_age} than self)" if relative_age else text


@dataclass
class Concept:
    """One KinDiv concept with whatever ILI link it has."""

    code: str
    label: str
    subdomain: str
    source: str
    definition: str
    ili: str = ""
    relation: str = ""
    near_ili: str = ""
    languages: set[str] = field(default_factory=set)
    gaps: set[str] = field(default_factory=set)

    @property
    def id(self) -> str:
        return slug(self.code)


def read_concepts() -> dict[str, Concept]:
    """Read KinDiv's concepts and ours, and attach the curated ILI mapping.

    `extra-concepts.tsv` adds nodes KinDiv lacks, such as English *uncle*, which
    covers relatives by marriage as well as by blood. Their definitions are given,
    not composed from the code.
    """
    rows = read_tsv(DATA / "concepts") + read_tsv(HERE / "extra-concepts.tsv")
    concepts = {
        row["Abreviation"]: Concept(
            code=row["Abreviation"],
            label=row["Concept"],
            subdomain=row["Subdomain"],
            source=row["Source"],
            definition=row.get("Definition")
            or define(row["Abreviation"], row["Subdomain"]),
        )
        for row in rows
    }
    for row in read_tsv(HERE / "concept-ili.tsv"):
        concept = concepts[row["concept"]]
        if row["relation"] == "exact":
            concept.ili = row["ili"]
        else:
            concept.relation, concept.near_ili = row["relation"], row["ili"]
    return concepts


def read_hierarchy(concepts: dict[str, Concept]) -> dict[str, set[str]]:
    """Return every concept's ancestors, bridging any nodes missing from `concepts`.

    Upstream KinDiv used ``Fa;Sb;So`` and ``Fa;Sb;Da`` in `relations` and `gaps`
    without listing them in `concepts` (added in this fork); bridging keeps the
    hierarchy intact should that happen again.
    """
    parents: dict[str, set[str]] = defaultdict(set)
    for row in read_tsv(DATA / "relations") + read_tsv(HERE / "extra-relations.tsv"):
        if row["Hypernym_concept"] != "#":
            parents[row["Hyponym_concept"]].add(row["Hypernym_concept"])

    def ancestors(code: str, seen: frozenset[str] = frozenset()) -> set[str]:
        found: set[str] = set()
        for parent in parents[code] - seen:
            found |= {parent} | ancestors(parent, seen | {code})
        return found

    return {code: ancestors(code) & concepts.keys() for code in concepts}


def nearest(included: set[str], ancestry: dict[str, set[str]]) -> dict[str, set[str]]:
    """Map each included concept to its closest included ancestors."""
    result = {}
    for code in included:
        above = ancestry[code] & included
        result[code] = {a for a in above if not any(a in ancestry[b] for b in above)}
    return result


@dataclass
class Language:
    """Words and gaps recorded for one language."""

    name: str
    tag: str
    #: written form -> [(concept code, source)]
    words: dict[str, list[tuple[str, str]]] = field(
        default_factory=lambda: defaultdict(list)
    )
    #: concept code -> evidence
    gaps: dict[str, str] = field(default_factory=dict)
    #: compositional phrase -> concept code, for concepts with no word
    phrases: dict[str, str] = field(default_factory=dict)


def add_phrases(language: Language, concepts: dict[str, Concept]) -> None:
    """Give every concept the language has no word for its compositional phrase.

    Only English, for now: "father's sister's husband" names a kin type English
    has no word for. The phrase is written as an unlexicalized sense.
    """
    attested = {code for senses in language.words.values() for code, _ in senses}
    for code, concept in concepts.items():
        if code not in attested:
            # named nodes (Rel, InL, Unc, ...) are not kin-type codes: use the label
            text = concept.label if code.isalpha() else phrase(code, concept.subdomain)
            language.phrases[text] = code


def add_word(
    languages: dict[str, Language], name: str, form: str, concept: Concept, source: str
) -> None:
    """Record that `form` in language `name` lexicalizes `concept`."""
    language = languages.setdefault(name, Language(name, LANGUAGE_TAGS[name]))
    form = " ".join(form.translate(INVISIBLE).split())
    if form and (concept.code, source) not in language.words[form]:
        language.words[form].append((concept.code, source))
        concept.languages.add(name)


def read_languages(concepts: dict[str, Concept]) -> dict[str, Language]:
    """Read KinDiv's words (plus `extra-words.tsv`); gaps come later (`add_gaps`)."""
    by_label = {c.label: c for c in concepts.values()}
    languages: dict[str, Language] = {}
    for row in read_tsv(DATA / "words") + read_tsv(HERE / "extra-words.tsv"):
        # one Kannada cell holds two comma-separated words
        for form in row["Word"].split(","):
            add_word(
                languages,
                row["Language"],
                form,
                by_label[row["Concept"]],
                row["Source"],
            )
    return languages


def add_gaps(languages: dict[str, Language], concepts: dict[str, Concept]) -> None:
    """Attach KinDiv's recorded lexical gaps, matching languages by name.

    Call this after every word source has been added: a language that first
    appears through TUFS, an attestation or Kinbank still gets its KinDiv gaps,
    and a clash between its new words and those gaps is then reported. Gaps of
    languages with no words are counted on the concept but not written.
    """
    for row in read_tsv(DATA / "gaps"):
        code = row["Gap concept"]
        if code not in concepts:
            continue
        concepts[code].gaps.add(row["Language"])
        if row["Language"] in languages:
            languages[row["Language"]].gaps[code] = row["Inference based upon"]


def add_tufs(languages: dict[str, Language], concepts: dict[str, Concept]) -> None:
    """Add the TUFS words mapped in `tufs-kindiv.tsv`.

    Rows without a concept (kin types KinDiv has no node for) and low-confidence
    rows stay in the table for review but are not added.
    """
    name_of = {tag: name for name, tag in LANGUAGE_TAGS.items()}
    for row in read_tsv(HERE / "tufs-kindiv.tsv"):
        if row["concept"] and row["confidence"] != "low":
            source = (
                f"TUFS Basic Vocabulary ({row['tufs_lang']}, word {row['tufs_wid']})"
            )
            add_word(
                languages,
                name_of[row["tag"]],
                row["form"],
                concepts[row["concept"]],
                source,
            )


def add_attestations(
    languages: dict[str, Language], concepts: dict[str, Concept]
) -> None:
    """Add words found for concepts no other source attests (`attested-words.tsv`).

    Each row was checked against the source it cites; only ``exact`` matches are
    kept (the table also records broader and narrower near-misses).
    """
    for row in read_tsv(HERE / "attested-words.tsv"):
        if row["match"] == "exact":
            name = register_language(row["language"], row["tag"])
            add_word(
                languages,
                name,
                row["word"],
                concepts[row["concept"]],
                row["source_url"],
            )


def add_kinbank(languages: dict[str, Language], concepts: dict[str, Concept]) -> None:
    """Add the Kinbank terms that match a concept exactly (`kinbank-candidates.tsv`).

    Matches flagged with a broader synonym are left out: there the term's absence
    from a neighbouring position may only mean Kinbank recorded one word per slot.
    """
    for row in read_tsv(HERE / "kinbank-candidates.tsv"):
        if not row["broader_synonym"]:
            name = register_language(row["language"], row["tag"])
            source = f"Kinbank {row['kinbank_language']}: {row['positions']}"
            add_word(languages, name, row["form"], concepts[row["concept"]], source)


def register_language(name: str, tag: str) -> str:
    """Return the name we use for `tag`, registering a new language if need be.

    A new language keeps its source's name, qualified by its tag if another
    language already has that name.
    """
    for known, known_tag in LANGUAGE_TAGS.items():
        if known_tag == tag:
            return known
    if name in LANGUAGE_TAGS:
        name = f"{name} ({tag})"
    LANGUAGE_TAGS[name] = tag
    return name


def attrs(pairs: list[tuple[str, str]]) -> str:
    """Render optional attributes, dropping empty ones."""
    return "".join(f" {name}={quoteattr(value)}" for name, value in pairs if value)


BASE = "kindiv"
#: kin terms share OEWN's noun.person with every other kind of person; WN-LMF's
#: lexfile attribute is free text, so they get a file of their own
LEXFILE = "noun.kin"


def synset_id(code: str) -> str:
    """Return the id of a concept's synset in the shared lexicon."""
    return f"{BASE}-{slug(code)}"


def lexicon_open(lexicon_id: str, label: str, tag: str) -> str:
    """Render the opening tag of a Lexicon."""
    return (
        f'  <Lexicon id="{lexicon_id}" label={quoteattr(label)} language="{tag}"'
        f' email="{EMAIL}" license="{LICENSE}" version="{VERSION}" url="{URL}"'
        f" citation={quoteattr(CITATION)}>"
    )


def write_base(
    lines: list[str], concepts: dict[str, Concept], ancestry: dict[str, set[str]]
) -> None:
    """Append the shared lexicon: every concept, its ILI and the whole hierarchy.

    Like KinDiv's interlingual layer, it is language-independent (``mul``) and
    every synset is unlexicalized: words come only from the language
    lexicons. WN-LMF requires a Lexicon to have entries, so each concept gets
    its kin-type code (``Fa;Br;So``) as an unlexicalized sense, which also lets
    the concepts be looked up by code. New-ILI candidates carry their
    ``ILIDefinition`` here, once, rather than in every language.
    """
    lines.append(lexicon_open(BASE, "KinDiv concepts", "mul"))
    for code in concepts:
        entry_id = f"{BASE}-e-{slug(code)}"
        lines.append(f'    <LexicalEntry id="{entry_id}">')
        lines.append(f'      <Lemma writtenForm={quoteattr(code)} partOfSpeech="n"/>')
        lines.append(
            f'      <Sense id="{entry_id}-1" synset="{synset_id(code)}" lexicalized="false"/>'
        )
        lines.append("    </LexicalEntry>")

    hypernyms = nearest(set(concepts), ancestry)
    hyponyms: dict[str, set[str]] = defaultdict(set)
    for child, parents in hypernyms.items():
        for parent in parents:
            hyponyms[parent].add(child)
    for code, concept in concepts.items():
        ili = concept.ili or ("in" if concept.languages else "")
        note = ""
        if concept.near_ili:
            note = (
                f"KinDiv concept is narrower than {concept.near_ili}"
                f" (OEWN is {concept.relation})"
            )
        lines.append(
            f'    <Synset id="{synset_id(code)}" ili="{ili}" partOfSpeech="n"'
            f' lexicalized="false" lexfile="{LEXFILE}"'
            + attrs(
                [
                    ("dc:identifier", f"KinDiv:{code}"),
                    ("dc:subject", concept.subdomain),
                    ("dc:description", concept.label),
                    ("dc:source", concept.source),
                    ("dc:relation", concept.near_ili),
                    ("note", note),
                ]
            )
            + ">"
        )
        definition = escape(concept.definition)
        lines.append(f'      <Definition language="en">{definition}</Definition>')
        if ili == "in":
            lines.append(f"      <ILIDefinition>{definition}</ILIDefinition>")
        for rel_type, targets in (
            ("hypernym", hypernyms[code]),
            ("hyponym", hyponyms[code]),
        ):
            for target in sorted(targets):
                lines.append(
                    f'      <SynsetRelation relType="{rel_type}" target="{synset_id(target)}"/>'
                )
        lines.append("    </Synset>")
    lines.append("  </Lexicon>")


def write_language(
    lines: list[str], language: Language, concepts: dict[str, Concept]
) -> dict[str, int]:
    """Append one language as a standalone lexicon of its words.

    It has one synset per concept it lexicalizes, and an unlexicalized one per
    recorded gap or compositional phrase (the phrase is an unlexicalized sense),
    but no relations: the hierarchy lives in the shared lexicon and
    is reached through the ILI (``wn.Wordnet(..., expand="kindiv")``). New-ILI
    candidates are proposed once, in the shared lexicon, so here they have an
    empty ``ili``; ``dc:identifier`` holds the kin-type code either way.
    """
    lexicon_id = f"{BASE}-{language.tag}"
    attested = {code for senses in language.words.values() for code, _ in senses}
    gaps = language.gaps.keys() - attested
    phrased = set(language.phrases.values())

    def local_id(code: str) -> str:
        return f"{lexicon_id}-{slug(code)}"

    lines.append(lexicon_open(lexicon_id, f"KinDiv {language.name}", language.tag))
    senses = 0
    forms = sorted(language.words.keys() | language.phrases.keys())
    for index, form in enumerate(forms, 1):
        entry_id = f"{lexicon_id}-e{index:04d}"
        meanings = language.words.get(form, [])
        lines.append(f'    <LexicalEntry id="{entry_id}">')
        lines.append(f'      <Lemma writtenForm={quoteattr(form)} partOfSpeech="n"/>')
        if form in language.phrases:
            code = language.phrases[form]
            lines.append(
                f'      <Sense id="{entry_id}-{slug(code)}" synset="{local_id(code)}"'
                ' lexicalized="false"/>'
            )
        for code in dict.fromkeys(code for code, _ in meanings):
            sources = "; ".join(sorted({s for c, s in meanings if c == code}))
            lines.append(
                f'      <Sense id="{entry_id}-{slug(code)}" synset="{local_id(code)}"'
                + attrs([("dc:source", sources)])
                + "/>"
            )
            senses += 1
        lines.append("    </LexicalEntry>")
    for code in sorted(attested | gaps | phrased):
        concept = concepts[code]
        gap = code in gaps
        lines.append(
            f'    <Synset id="{local_id(code)}" ili="{concept.ili}" partOfSpeech="n"'
            f' lexfile="{LEXFILE}"'
            + ("" if code in attested else ' lexicalized="false"')
            + attrs(
                [
                    ("dc:identifier", f"KinDiv:{code}"),
                    ("dc:description", concept.label),
                    ("dc:source", language.gaps[code] if gap else ""),
                    ("note", f"lexical gap: no {language.name} word" if gap else ""),
                    ("dc:type", "phrase" if code in phrased else ""),
                ]
            )
            + ">"
        )
        lines.append(
            f'      <Definition language="en">{escape(concept.definition)}</Definition>'
        )
        lines.append("    </Synset>")
    lines.append("  </Lexicon>")
    return {
        "entries": len(language.words),
        "senses": senses,
        "concepts": len(attested),
        "linked": sum(bool(concepts[c].ili) for c in attested),
        "proposed": sum(not concepts[c].ili for c in attested),
        "gaps": len(gaps),
        "phrases": len(phrased),
    }


def write_package(collection: Path, lexicon_id: str, body: list[str]) -> None:
    """Write one WN-LMF package: a directory holding a single XML file."""
    package = collection / lexicon_id
    package.mkdir(parents=True, exist_ok=True)
    document = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        DOCTYPE,
        f'<LexicalResource xmlns:dc="{DC_NAMESPACE}">',
        *body,
        "</LexicalResource>",
    ]
    path = package / f"{lexicon_id}-{VERSION}.xml"
    path.write_text("\n".join(document) + "\n", encoding="utf8")


def write_collection(
    concepts: dict[str, Concept],
    ancestry: dict[str, set[str]],
    languages: dict[str, Language],
) -> list[tuple[Language, dict[str, int]]]:
    """Write the wn collection and its .tar.xz; return per-language counts.

    Every lexicon gets its own package, so a language can be installed alone.
    """
    collection = HERE / "release" / f"{BASE}-{VERSION}"
    shutil.rmtree(collection, ignore_errors=True)
    lines: list[str] = []
    write_base(lines, concepts, ancestry)
    write_package(collection, BASE, lines)
    stats = []
    for name in sorted(languages, key=lambda n: LANGUAGE_TAGS[n]):
        lines = []
        stats.append(
            (languages[name], write_language(lines, languages[name], concepts))
        )
        write_package(collection, f"{BASE}-{languages[name].tag}", lines)
    for extra in (HERE / "collection").iterdir():
        shutil.copy(extra, collection / extra.name)
    with tarfile.open(collection.parent / f"{collection.name}.tar.xz", "w:xz") as tar:
        tar.add(collection, arcname=collection.name)
    return stats


def write_gap_conflicts(languages: dict[str, Language]) -> None:
    """List words for concepts KinDiv records as gaps in the same language.

    The word wins in the wordnet; the table is for checking which source is
    wrong (or whether the word is a transparent compound KinDiv discounted).
    """
    rows = []
    for language in languages.values():
        for form, meanings in language.words.items():
            for code, source in meanings:
                if code in language.gaps:
                    rows.append(
                        (
                            language.name,
                            language.tag,
                            code,
                            form,
                            source,
                            language.gaps[code],
                        )
                    )
    with (HERE / "gap-conflicts.tsv").open("w", encoding="utf8") as out:
        out.write("language\ttag\tconcept\tword\tword_source\tgap_evidence\n")
        for row in sorted(rows):
            out.write("\t".join(row) + "\n")
    logger.info(
        "%d words contradict a KinDiv gap in %d languages: see gap-conflicts.tsv",
        len(rows),
        len({r[0] for r in rows}),
    )


def main() -> None:
    """Build the collection, ili-proposals.tsv and lexicons.tsv."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    concepts = read_concepts()
    ancestry = read_hierarchy(concepts)
    languages = read_languages(concepts)
    add_tufs(languages, concepts)
    add_attestations(languages, concepts)
    add_kinbank(languages, concepts)
    add_gaps(languages, concepts)
    add_phrases(languages["English"], concepts)

    stats = write_collection(concepts, ancestry, languages)
    write_gap_conflicts(languages)

    with (HERE / "lexicons.tsv").open("w", encoding="utf8") as out:
        out.write(
            "lexicon\tlanguage\ttag\tentries\tsenses\tconcepts\tili_linked\tili_proposed\tgaps\tphrases\n"
        )
        for language, c in stats:
            out.write(
                f"kindiv-{language.tag}\t{language.name}\t{language.tag}\t{c['entries']}\t"
                f"{c['senses']}\t{c['concepts']}\t{c['linked']}\t{c['proposed']}\t{c['gaps']}\t{c['phrases']}\n"
            )

    with (HERE / "ili-proposals.tsv").open("w", encoding="utf8") as out:
        out.write(
            "concept\tlabel\tsubdomain\tstatus\tili\tn_languages\tn_gaps\t"
            "languages\tili_definition\n"
        )
        for concept in concepts.values():
            if concept.ili:
                status = "linked"
            elif concept.languages:
                status = "propose"
            else:
                status = "unattested"
            out.write(
                f"{concept.code}\t{concept.label}\t{concept.subdomain}\t{status}\t"
                f"{concept.ili or concept.near_ili}\t{len(concept.languages)}\t"
                f"{len(concept.gaps)}\t{', '.join(sorted(concept.languages))}\t"
                f"{concept.definition}\n"
            )
    logger.info("wrote the shared lexicon and %d language lexicons", len(stats))


if __name__ == "__main__":
    main()
