"""Look up the existing wordnets that Cygnet is built from, for the review files.

Cygnet's sources are listed in ``~/git/cygnet/wordnets.toml`` (language -> source
archives) and downloaded to ``~/git/cygnet/bin/raw_wns``. The ones for a language
are loaded with Wn into a database of their own (``~/.cache/cygnet-review-wn``),
never into the user's ``~/.wn_data``. Set ``CYGNET_DIR`` to use another clone.

omw-pronoun and KinDiv each keep a copy of this file; keep the two in step.
"""

from __future__ import annotations

import csv
import os
from collections.abc import Callable
from functools import cache
from pathlib import Path

import tomllib
import wn

CYGNET = Path(os.environ.get("CYGNET_DIR", Path.home() / "git" / "cygnet"))
CACHE = Path.home() / ".cache" / "cygnet-review-wn"
#: our language tags -> Cygnet's keys
TAGS = {"zh": "cmn"}
#: how many lemmas of an existing synset to show
SHOW = 6


def sources(tag: str) -> list[Path]:
    """The raw wordnet files Cygnet uses for a language (none for Czech)."""
    with (CYGNET / "wordnets.toml").open("rb") as handle:
        urls = tomllib.load(handle).get(TAGS.get(tag, tag), [])
    raw = CYGNET / "bin" / "raw_wns"
    found = []
    for url in urls:
        name = url.rsplit("/", 1)[-1]
        stem = name.removesuffix(".tar.xz").removesuffix(".tar.gz")
        # omw-pl-2.0.tar.xz is unpacked as omw-pl.xml
        candidates = [name, f"{stem}.xml", f"{stem.rsplit('-', 1)[0]}.xml"]
        found += [raw / c for c in candidates if (raw / c).is_file()][:1]
    return found


@cache
def wordnets(tag: str) -> tuple[wn.Wordnet, ...]:
    """The language's Cygnet wordnets, added to the private database on first use.

    A marker file per source records the lexicons it added, so later runs skip
    the slow ``wn.add``.
    """
    CACHE.mkdir(parents=True, exist_ok=True)
    wn.config.data_directory = CACHE
    assert wn.config.database_path.is_relative_to(CACHE)
    specs: list[str] = []
    for path in sources(tag):
        marker = CACHE / f"{path.name}.lexicons"
        if not marker.is_file():
            before = {f"{lx.id}:{lx.version}" for lx in wn.lexicons()}
            wn.add(str(path), progress_handler=None)
            after = {f"{lx.id}:{lx.version}" for lx in wn.lexicons()}
            marker.write_text("\n".join(sorted(after - before)))
        specs += marker.read_text().split()
    # CantoWN also ships an English lexicon: keep only the language's own
    wanted = {tag, TAGS.get(tag, tag)}
    return tuple(
        w
        for w in (wn.Wordnet(lexicon=spec) for spec in specs)
        if w.lexicons()[0].language.split("-")[0] in wanted
    )


@cache
def cili() -> dict[str, str]:
    """ILI -> its CILI definition, from Cygnet's copy of the index."""
    with (CYGNET / "bin" / "cili.tsv").open(encoding="utf8") as handle:
        return {
            row["ili_id"]: row["definition"]
            for row in csv.DictReader(handle, delimiter="\t")
        }


def describe(synset: wn.Synset) -> str:
    """One line for an existing synset: lexicon, id, ILI, lemmas and definition.

    OMW wordnets have few definitions of their own; those synsets show the
    CILI definition, marked ``(CILI)``.
    """
    lemmas = synset.lemmas()
    shown = ", ".join(lemmas[:SHOW]) + (", ..." if len(lemmas) > SHOW else "")
    ili = synset.ili or "-"
    definition = synset.definition() or (
        f"(CILI) {cili()[ili]}" if ili in cili() else ""
    )
    lexicon = synset.lexicon().id
    return f"{lexicon} {synset.id} [{ili}] {shown}: {definition}".rstrip(": ")


def by_ili(tag: str, ili: str) -> list[str]:
    """The language's existing synsets for an ILI."""
    if not ili or not ili.startswith("i"):
        return []
    return [describe(s) for w in wordnets(tag) for s in w.synsets(ili=ili)]


def by_lemma(
    tag: str,
    lemma: str,
    pos: str | None = None,
    keep: Callable[[wn.Synset], bool] | None = None,
) -> tuple[list[str], int]:
    """The language's existing synsets with `lemma` that pass `keep`.

    Returns the kept synsets, described, and how many others were hidden.
    """
    found = [s for w in wordnets(tag) for s in w.synsets(lemma, pos=pos)]
    kept = [s for s in found if keep is None or keep(s)]
    return [describe(s) for s in kept], len(found) - len(kept)


# --- filters, through OEWN: OMW wordnets mostly lack lexicographer files and
# hypernyms of their own, but their synsets carry ILIs


@cache
def oewn() -> wn.Wordnet:
    """Open English WordNet, the reference for lexicographer files and hypernyms."""
    wordnets("en")
    return wn.Wordnet(lexicon="oewn:2025")


@cache
def oewn_synset(ili: str) -> wn.Synset | None:
    """OEWN's synset for an ILI, if it has one."""
    found = oewn().synsets(ili=ili)
    return found[0] if found else None


def lexfile(synset: wn.Synset) -> str:
    """The synset's lexicographer file: its own, else its OEWN counterpart's."""
    own = synset.lexfile()
    if own:
        return own
    counterpart = oewn_synset(synset.ili) if synset.ili else None
    return counterpart.lexfile() or "" if counterpart else ""


@cache
def ili_ancestors(ili: str) -> frozenset[str]:
    """The ILIs of everything above `ili` in OEWN (hypernyms and instance hypernyms)."""
    synset = oewn_synset(ili)
    if synset is None:
        return frozenset()
    above = synset.closure("hypernym", "instance_hypernym")
    return frozenset(s.ili for s in above if s.ili)


def under(synset: wn.Synset, roots: frozenset[str]) -> bool | None:
    """Whether the synset is one of the `roots` ILIs or below one, by OEWN.

    A synset with no ILI is judged by its own hypernyms (OEWN's new synsets
    have them); with neither, the answer is unknown (``None``), as for the
    TUFS synsets made from NTUMC's pronouns.
    """
    if synset.ili:
        return synset.ili in roots or bool(ili_ancestors(synset.ili) & roots)
    above = [h.ili for h in synset.hypernyms() if h.ili]
    if not above:
        return None
    return any(i in roots or ili_ancestors(i) & roots for i in above)
