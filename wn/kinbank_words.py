#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["langcodes", "language_data"]
# ///
"""Find Kinbank terms that lexicalize KinDiv concepts exactly.

Kinbank (Passmore et al. 2023, CC BY 4.0) records, for each language, the term
used at each genealogical position: ``mFeB`` is a man's father's older brother.
A term's meaning is the set of positions it is listed under, and a KinDiv concept
is a set of positions too, so the two can be compared directly.

Positions are reduced to *atoms*: ego sex, a chain of kin letters
(F M B Z S D H W), and relative age only where KinDiv distinguishes it (ego's
sibling, a parent's sibling, the sibling whose child is meant, a cousin relative
to ego, the brother or sister in FBW/FZH). Coarse positions expand: ``mB`` is both
``meB`` and ``myB``, ``mC`` is ``mS`` and ``mD``.

A term matches a concept **exactly** when its atoms equal the concept's atoms, it
is listed under no position outside the atom space, and the language was asked
about every *neighbouring* atom (flip ego sex, the sex or side of any link, or the
relative age) -- so we know the term does not extend there. Without that check, a
language recorded for male ego only would seem to have "male speaking" terms
everywhere.

Writes ``kinbank-candidates.tsv``.

Usage: uv run wn/kinbank_words.py [path/to/kinbank]
"""

from __future__ import annotations

import csv
import itertools
import logging
import re
import sys
import unicodedata
from collections import defaultdict
from functools import cache
from pathlib import Path

import langcodes

import build

logger = logging.getLogger(__name__)

#: an atom: (ego sex, ((age, letter), ...)), age "" where not distinguished
Atom = tuple[str, tuple[tuple[str, str], ...]]

#: Kinbank letters that stand for a choice of concrete kin letters
DISJUNCTIONS = {"C": "SD", "P": "FM", "E": "HW", "G": "BZ", "Q": "BZ"}
CONCRETE = set("FMBZSDHW")
FLIP = {"F": "M", "M": "F", "B": "Z", "Z": "B", "S": "D", "D": "S", "H": "W", "W": "H"}
GENERAL = re.compile(r"[CPEG]")
KINBANK = re.compile(r"([mf])((?:[ey]?[A-Z])+)")


def age_slot(letters: str) -> int | None:
    """Return the index of the link whose relative age KinDiv distinguishes.

    >>> age_slot("B"), age_slot("FB"), age_slot("BS"), age_slot("FBS"), age_slot("FBW")
    (0, 1, 0, 2, 1)
    >>> age_slot("FF") is None
    True
    """
    parent, sibling, child, spouse = set("FM"), set("BZ"), set("SD"), set("HW")
    sets = [parent, sibling, child, spouse]
    shape = tuple(next(i for i, s in enumerate(sets) if c in s) for c in letters)
    return {(1,): 0, (0, 1): 1, (1, 2): 0, (0, 1, 2): 2, (0, 1, 3): 1}.get(shape)


def expand(egos: str, links: list[tuple[str, str]]) -> set[Atom]:
    """Expand ego sexes, disjunctive letters and unspecified ages into atoms."""
    atoms: set[Atom] = set()
    choices = [DISJUNCTIONS.get(letter, letter) for _, letter in links]
    for ego in egos:
        for letters in itertools.product(*choices):
            slot = age_slot("".join(letters))
            ages = [""] * len(letters)
            if slot is not None:
                given = links[slot][0]
                for age in (given,) if given else ("e", "y"):
                    ages[slot] = age
                    atoms.add((ego, tuple(zip(ages, letters))))
            else:
                atoms.add((ego, tuple(zip(ages, letters))))
    return atoms


def kinbank_atoms(parameter: str) -> set[Atom] | None:
    """Atoms of a Kinbank position, or None if it lies outside the atom space.

    >>> sorted(kinbank_atoms("mB"))
    [('m', (('e', 'B'),)), ('m', (('y', 'B'),))]
    >>> kinbank_atoms("mFeBS") == kinbank_atoms("mFBS")   # parent's age is not kept
    True
    >>> kinbank_atoms("mA") is None
    True
    >>> kinbank_atoms("mG") == kinbank_atoms("mB") | kinbank_atoms("mZ")
    True
    """
    match = KINBANK.fullmatch(parameter)
    if not match:
        return None
    ego, body = match.groups()
    links = re.findall(r"([ey]?)([A-Z])", body)
    # G is a sibling: parameters.csv calls mG "Grandparent", but the forms under it
    # are English "sibling", Swedish "syskon", Hungarian "testvér"
    if any(letter not in CONCRETE and letter not in "CPEG" for _, letter in links):
        return None
    atoms = expand(ego, links)
    return {atom for atom in atoms if atom[1]}


#: KinDiv kin terms as Kinbank letters (Q: sibling)
KINDIV_LETTERS = {
    "Fa": "F",
    "Mo": "M",
    "Pa": "P",
    "Pr": "P",
    "Br": "B",
    "Ss": "Z",
    "Sb": "Q",
    "So": "S",
    "Da": "D",
    "Ch": "C",
    "Hu": "H",
    "Wi": "W",
    "Sp": "E",
}
#: KinDiv nodes that are unions of kin types
UNIONS = {
    "Unc": ("Pa;Br", "Pa;Ss;Hu"),
    "Aun": ("Pa;Ss", "Pa;Br;Wi"),
    "BrL": ("Sp;Br", "Ss;Hu"),
    "SsL": ("Sp;Ss", "Br;Wi"),
}


def kindiv_atoms(code: str, subdomain: str) -> set[Atom] | None:
    """Atoms of a KinDiv concept, or None for nodes too broad to match (Rel, InL).

    >>> sorted(kindiv_atoms("x;Fa;El;Br", "uncles and aunts"))
    [('m', (('', 'F'), ('e', 'B')))]
    >>> len(kindiv_atoms("Pa;Sb;Ch", "cousins"))   # 2 egos x 8 kin types x 2 ages
    32
    """
    if "|" in code:
        parts = [
            kindiv_atoms(part, build.subdomain_of(part)) for part in code.split("|")
        ]
        return None if None in parts else set().union(*parts)
    if code in UNIONS:
        return set().union(*(kindiv_atoms(part, subdomain) for part in UNIONS[code]))
    parts = code.split(";")
    egos = {"x": "m", "o": "f"}.get(parts[0], "mf")
    if parts[0] in ("x", "o"):
        parts = parts[1:]
    links: list[list[str]] = []
    age = ""
    for part in parts:
        if part in ("El", "Yn"):
            age = "e" if part == "El" else "y"
            continue
        if part == "Gr":
            letter = "C" if subdomain == "grandchildren" else "P"
            links.append(["", letter])
        elif part == "Pb":
            links.extend([["", "P"], ["", "Q"]])
        elif part in KINDIV_LETTERS:
            links.append(["", KINDIV_LETTERS[part]])
        else:
            return None
        if age and subdomain != "cousins":
            links[-1][0], age = age, ""
    if age:  # cousins: the age is the cousin's, relative to ego
        links[-1][0] = age
    return expand(egos, [tuple(link) for link in links])


def neighbours(atom: Atom) -> set[Atom]:
    """Atoms one step away: flip ego sex, one link's sex or side, or the age."""
    ego, links = atom
    found = {({"m": "f", "f": "m"}[ego], links)}
    for i, (age, letter) in enumerate(links):
        flipped = list(links)
        flipped[i] = (age, FLIP[letter])
        if age_slot("".join(l for _, l in flipped)) == age_slot(
            "".join(l for _, l in links)
        ):
            found.add((ego, tuple(flipped)))
        if age:
            flipped = list(links)
            flipped[i] = ({"e": "y", "y": "e"}[age], letter)
            found.add((ego, tuple(flipped)))
    return found


def word_atoms(parameters: set[str]) -> frozenset[Atom] | None:
    """Atoms of all the positions a term is listed under, or None if any is unmappable."""
    atom_sets = [kinbank_atoms(p) for p in parameters]
    if any(a is None for a in atom_sets):
        return None
    return frozenset(set().union(*atom_sets))


def broader_synonym(
    form: str,
    atoms: frozenset[Atom],
    outside: set[Atom],
    extent: dict[str, frozenset[Atom] | None],
) -> str:
    """Name another term that covers `form`'s positions and a neighbour it lacks.

    Kinbank often records one term per position, so German *Opa* appears only
    under MF because FF got *Großvater*. When a broader term like *Großvater*
    spans both, `form`'s absence from the neighbour is weak evidence, and the
    match is flagged.
    """
    for other, other_atoms in extent.items():
        if (
            other != form
            and other_atoms
            and atoms < other_atoms
            and other_atoms & outside
        ):
            return other
    return ""


#: Kinbank varieties that transcribe a language written in Latin script: English
#: and German in IPA or dictionary respelling
TRANSCRIBED = {"p_englishstan1293", "p_germanstan1295"}
#: characters of dictionary respelling (Webster's *ŭngʹkəl*), not IPA
RESPELLING = set("ĭŭăĕŏʹ'")


#: languages whose likely script in CLDR is not what their texts use: Old Norse
#: and Old Irish are edited in Latin letters, not runes or ogham
LATIN_WRITTEN = {"non", "sga"}


@cache
def likely_script(tag: str) -> str:
    """The script a language is usually written in (ISO 15924), or ''."""
    if tag in LATIN_WRITTEN:
        return "Latn"
    try:
        return langcodes.Language.get(tag).maximize().script or ""
    except (ValueError, LookupError):
        return ""


def transcription(form: str, tag: str, variety: str) -> str:
    """How a Kinbank form transcribes the language, or '' if it is written normally.

    ``IPA`` or ``respelling`` for the transcribing English and German varieties;
    ``romanization`` for a Latin-letter form of a language usually written in
    another script (Mandarin *xiong di*, Hindi *bhāī*, Russian *brat*).

    >>> transcription("xiong di", "cmn", "v_mandarinchinamand1415")
    'romanization'
    >>> transcription("брат", "ru", "p_russianruss1263a")
    ''
    >>> transcription("brat", "pl", "v_polishpoli1260")
    ''
    """
    if variety in TRANSCRIBED:
        return "respelling" if RESPELLING & set(form) else "IPA"
    script = likely_script(tag)
    latin = any(
        ch.isalpha() and unicodedata.name(ch, "").startswith("LATIN") for ch in form
    )
    return "romanization" if latin and script not in ("", "Latn") else ""


def iso_to_tag(iso: str) -> str:
    """Our tag for an ISO 639-3 code: the one languages.tsv uses, if any.

    >>> iso_to_tag("cmn"), iso_to_tag("hbs"), iso_to_tag("eng"), iso_to_tag("taf")
    ('cmn', 'sh', 'en', 'taf')
    """
    return OUR_TAGS.get(iso) or langcodes.standardize_tag(iso)


#: Kinbank's individual-language codes whose macrolanguage we already tag
MACRO = {
    "tgl": "tl",  # langcodes would make this fil
    "hbs": "sh",
    "pes": "fa",
    "arb": "ar",
    "zsm": "ms",
    "swh": "sw",
    "ekk": "et",
    "lvs": "lv",
    "als": "sq",
    "khk": "mn",
    "azj": "az",
    "ydd": "yi",
    "kmr": "ku",
}

#: ISO 639-3 -> the tag languages.tsv already uses for that language
OUR_TAGS = {
    langcodes.get(tag).to_alpha3(): tag for tag in build.LANGUAGE_TAGS.values()
} | MACRO


def read_kinbank(
    cldf: Path,
) -> tuple[dict[str, dict[str, str]], dict[str, dict[str, set[str]]]]:
    """Return Kinbank's languages by id, and each language's forms with positions."""
    languages = {row["ID"]: row for row in build_rows(cldf / "languages.csv")}
    forms: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    for row in build_rows(cldf / "forms.csv"):
        if row["Form"]:
            forms[row["Language_ID"]][row["Form"]].add(row["Parameter_ID"])
    return languages, forms


def verified_extents(
    words: dict[str, set[str]],
) -> list[tuple[str, frozenset[Atom], str]]:
    """Return (form, atoms, broader synonym) for one language's verifiable terms.

    A term is verifiable when it names only mappable positions and the language
    was asked about every neighbouring atom, so its boundaries are known.
    """
    elicited: set[Atom] = set()
    filled: dict[str, int] = defaultdict(int)
    for parameters in words.values():
        for parameter in parameters:
            elicited |= kinbank_atoms(parameter) or set()
            filled[parameter] += 1
    # a general position (sibling, child, parent, spouse) filled with several
    # words records alternatives ("hermano/hermana"), not one broad term
    alternatives = {p for p, n in filled.items() if n > 1 and GENERAL.search(p[1:])}
    extent = {
        form: word_atoms(parameters - alternatives or parameters)
        for form, parameters in words.items()
    }
    found = []
    for form, atoms in extent.items():
        if atoms is None:
            continue  # also names a kin type outside the atom space
        outside = {n for a in atoms for n in neighbours(a)} - atoms
        if outside <= elicited:
            found.append((form, atoms, broader_synonym(form, atoms, outside, extent)))
    return found


def main() -> None:
    """Write kinbank-candidates.tsv."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    root = Path(sys.argv[1] if len(sys.argv) > 1 else build.DATA.parent / "kinbank")
    cldf = root / "kinbank" / "cldf"
    concepts = build.read_concepts()
    by_atoms: dict[frozenset[Atom], list[str]] = defaultdict(list)
    for code, concept in concepts.items():
        atoms = kindiv_atoms(code, concept.subdomain)
        if atoms:
            by_atoms[frozenset(atoms)].append(code)

    languages, forms = read_kinbank(cldf)
    rows = []
    skipped_no_iso = 0
    for language_id, words in forms.items():
        language = languages[language_id]
        if not language["ISO639P3code"]:
            skipped_no_iso += 1
            continue
        for form, atoms, broader in verified_extents(words):
            tag = iso_to_tag(language["ISO639P3code"])
            for code in by_atoms.get(atoms, []):
                rows.append(
                    (
                        code,
                        tag,
                        language["ISO639P3code"],
                        language["Glottolog_Name"] or language["Name"],
                        form,
                        language_id,
                        ";".join(sorted(words[form])),
                        broader,
                        transcription(form, tag, language_id),
                    )
                )
    with (build.HERE / "kinbank-candidates.tsv").open("w", encoding="utf8") as out:
        out.write(
            "concept\ttag\tiso639_3\tlanguage\tform\tkinbank_language\tpositions"
            "\tbroader_synonym\ttranscription\n"
        )
        for row in sorted(rows):
            out.write("\t".join(row) + "\n")
    logger.info(
        "%d exact matches in %d Kinbank languages (%d languages skipped: no ISO code)",
        len(rows),
        len({r[5] for r in rows}),
        skipped_no_iso,
    )


def build_rows(path: Path) -> list[dict[str, str]]:
    """Read a CLDF CSV table."""
    with path.open(encoding="utf8", newline="") as handle:
        return list(csv.DictReader(handle))


if __name__ == "__main__":
    main()
