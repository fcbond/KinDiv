#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["langcodes", "language_data"]
# ///
"""Find recurring Kinbank meanings that KinDiv has no concept for.

A meaning is the set of positions a Kinbank term covers (see `kinbank_words.py`;
only terms whose boundaries are verified count). It is proposed as a concept when
it is

- **recurrent**: lexicalized in at least `MIN_FAMILIES` language families and
  `MIN_AREAS` macroareas, so it is not an accident of one lineage or one contact
  area; isolates count as families of their own; and
- **natural**: covered exactly by at most `MAX_PARTS` kin-type codes of the kind
  KinDiv writes (ego sex, a chain of kin letters that may be general -- parent,
  sibling, child, spouse -- and at most one relative age). "Father = father's
  brother" is ``Fa`` + ``Fa;Br``; a scatter of positions needs many parts.

Writes ``kinbank-new-concepts.tsv`` for review. With ``--write``, appends the
concepts that pass the admission rule (see `selected`) to ``extra-concepts.tsv``
and their hierarchy, computed from the kin types they cover, to
``extra-relations.tsv``.

Usage: uv run wn/kinbank_concepts.py [path/to/kinbank]
       uv run wn/kinbank_concepts.py --write
"""

from __future__ import annotations

import itertools
import logging
import sys
from collections import defaultdict
from functools import cache
from pathlib import Path

import build
import kinbank_words as kw

logger = logging.getLogger(__name__)

MIN_FAMILIES = 5
MIN_AREAS = 3
MAX_PARTS = 3

#: letters a KinDiv-style code may use, with KinDiv's names for them
LETTERS = {
    "F": "Fa",
    "M": "Mo",
    "P": "Pa",
    "B": "Br",
    "Z": "Ss",
    "Q": "Sb",
    "S": "So",
    "D": "Da",
    "C": "Ch",
    "H": "Hu",
    "W": "Wi",
    "E": "Sp",
}
ROLES = [set("FMP"), set("BZQ"), set("SDC"), set("HWE")]


@cache
def part_atoms(ego: str, letters: str, age: str) -> frozenset:
    """Atoms of one code: ego sexes, a letter chain, an age at the age slot."""
    concrete = letters.translate(str.maketrans("PQCE", "FBSH"))
    slot = kw.age_slot(concrete)
    if age and slot is None:
        return frozenset()
    links = [("", letter) for letter in letters]
    if age:
        links[slot] = (age, letters[slot])
    return frozenset(kw.expand(ego, links))


def parts_within(atoms: frozenset) -> list[tuple[str, str, str]]:
    """All codes whose atoms lie inside `atoms`, keeping only maximal ones."""
    inside = []
    for length in (1, 2, 3):
        for letters in itertools.product(LETTERS, repeat=length):
            letters = "".join(letters)
            for ego in ("mf", "m", "f"):
                for age in ("", "e", "y"):
                    part = part_atoms(ego, letters, age)
                    if part and part <= atoms:
                        inside.append((ego, letters, age))
    return [
        p for p in inside if not any(part_atoms(*p) < part_atoms(*q) for q in inside)
    ]


def cover(atoms: frozenset) -> list[tuple[str, str, str]] | None:
    """The fewest codes (at most MAX_PARTS) whose atoms union to exactly `atoms`."""
    candidates = parts_within(atoms)
    for size in range(1, MAX_PARTS + 1):
        for combo in itertools.combinations(candidates, size):
            if frozenset().union(*(part_atoms(*p) for p in combo)) == atoms:
                return list(combo)
    return None


def to_code(ego: str, letters: str, age: str) -> str:
    """Write a part as a KinDiv code: ``("m", "FB", "e")`` -> ``x;Fa;El;Br``."""
    tokens = [LETTERS[letter] for letter in letters]
    if age:
        slot = kw.age_slot(letters.translate(str.maketrans("PQCE", "FBSH")))
        marker = "El" if age == "e" else "Yn"
        if len(letters) == 3 and slot == 2:  # a cousin's age goes first in KinDiv
            tokens.insert(0, marker)
        else:
            tokens.insert(slot, marker)
    prefix = {"m": ["x"], "f": ["o"]}.get(ego, [])
    return ";".join(prefix + tokens)


def main() -> None:
    """Write kinbank-new-concepts.tsv."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    root = Path(sys.argv[1] if len(sys.argv) > 1 else build.DATA.parent / "kinbank")
    concepts = build.read_concepts()
    known = {
        frozenset(atoms)
        for code, concept in concepts.items()
        if (atoms := kw.kindiv_atoms(code, concept.subdomain))
    }
    languages, forms = kw.read_kinbank(root / "kinbank" / "cldf")

    families: dict[frozenset, set[str]] = defaultdict(set)
    areas: dict[frozenset, set[str]] = defaultdict(set)
    examples: dict[frozenset, list[str]] = defaultdict(list)
    for language_id, words in forms.items():
        language = languages[language_id]
        seen = set()
        for form, atoms, broader in kw.verified_extents(words):
            if atoms in known or atoms in seen or broader:
                continue
            seen.add(atoms)
            families[atoms].add(language["Family"] or language["Glottocode"])
            areas[atoms].add(language["Macroarea"])
            examples[atoms].append(f"{language['Name']} {form}")

    recurrent = [
        atoms
        for atoms in families
        if len(families[atoms]) >= MIN_FAMILIES and len(areas[atoms]) >= MIN_AREAS
    ]
    rows = []
    for atoms in recurrent:
        parts = cover(atoms)
        if parts:
            codes = sorted(to_code(*p) for p in parts)
            rows.append((atoms, codes))
    rows.sort(key=lambda r: (-len(families[r[0]]), -len(examples[r[0]])))
    with (build.HERE / "kinbank-new-concepts.tsv").open("w", encoding="utf8") as out:
        out.write("union_of\tfamilies\tmacroareas\tlanguages\texamples\n")
        for atoms, codes in rows:
            out.write(
                f"{' | '.join(codes)}\t{len(families[atoms])}\t{len(areas[atoms])}\t"
                f"{len(examples[atoms])}\t{'; '.join(examples[atoms][:4])}\n"
            )
    logger.info(
        "%d recurrent meanings (>= %d families, >= %d areas); %d natural (<= %d parts)",
        len(recurrent),
        MIN_FAMILIES,
        MIN_AREAS,
        len(rows),
        MAX_PARTS,
    )


#: a merger of kin types needs more evidence than a single kin type
MIN_FAMILIES_MERGER = 8
MAX_PARTS_MERGER = 2


def selected(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """Apply the admission rule to kinbank-new-concepts.tsv rows.

    A single kin type needs MIN_FAMILIES families in MIN_AREAS macroareas (the
    table's own threshold); a merger of kin types needs MIN_FAMILIES_MERGER
    families and at most MAX_PARTS_MERGER parts.
    """
    chosen = []
    for row in rows:
        parts = row["union_of"].split(" | ")
        if len(parts) == 1 or (
            len(parts) <= MAX_PARTS_MERGER
            and int(row["families"]) >= MIN_FAMILIES_MERGER
        ):
            chosen.append(row)
    return chosen


def hypernyms(atoms: dict[str, frozenset]) -> dict[str, set[str]]:
    """Each concept's closest strict supersets, by the kin types they cover."""
    found = {}
    for code, own in atoms.items():
        above = [c for c, other in atoms.items() if own < other]
        found[code] = {c for c in above if not any(atoms[c] > atoms[d] for d in above)}
    return found


def write() -> None:
    """Append the admitted concepts, and their hierarchy, to the extra-* tables."""
    concepts = build.read_concepts()
    new = []
    for row in selected(build.read_tsv(build.HERE / "kinbank-new-concepts.tsv")):
        code = "|".join(row["union_of"].split(" | "))
        if code in concepts:
            continue
        subdomain = build.subdomain_of(code)
        source = (
            f"Kinbank: {row['languages']} languages, {row['families']} families,"
            f" {row['macroareas']} macroareas"
        )
        label = build.phrase(code, subdomain)
        new.append((subdomain, label, code, source))
    atoms = {
        code: frozenset(a)
        for code, concept in concepts.items()
        if (a := kw.kindiv_atoms(code, concept.subdomain))
    }
    for subdomain, _, code, _ in new:
        atoms[code] = frozenset(kw.kindiv_atoms(code, subdomain))
    parents = hypernyms(atoms)
    new_codes = {code for _, _, code, _ in new}
    with (build.HERE / "extra-concepts.tsv").open("a", encoding="utf8") as out:
        for subdomain, label, code, source in new:
            definition = build.define(code, subdomain) if "|" in code else ""
            out.write(f"{subdomain}\t{label}\t{code}\t{source}\t{definition}\n")
    relations = set()
    for child, above in parents.items():
        for parent in above:
            if child in new_codes or parent in new_codes:
                relations.add((child, parent))
    for subdomain, _, code, _ in new:
        if not parents[code]:  # nothing narrower than Rel/InL contains it
            relations.add((code, "InL" if subdomain == "in-laws" else "Rel"))
    with (build.HERE / "extra-relations.tsv").open("a", encoding="utf8") as out:
        for child, parent in sorted(relations):
            out.write(f"kinbank\t{child}\t{parent}\n")
    logger.info("added %d concepts and %d relations", len(new), len(relations))


if __name__ == "__main__":
    if "--write" in sys.argv:
        logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
        write()
    else:
        main()
