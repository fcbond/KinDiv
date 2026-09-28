#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Extract TUFS kinship words and match them against KinDiv words.

Words come from two places, because neither is complete on its own:

- ``tufs-vocab.tsv``, rows whose TUFS concept id is a kinship concept;
- the raw TUFS SQL dumps (``tufsdata/vmod_*.sql``), usages filed under a
  kinship class of the Bunrui Goihyō. `munge.py` drops some of these words
  (e.g. zh 姑姑, 表妹; ar عم), and some never received a concept id.

Writes ``tufs-candidates.tsv``: one row per TUFS word form, with the KinDiv
concepts that the same form already has in the same language (``auto``). This is
the starting point for the hand-checked ``tufs-kindiv.tsv`` that `build.py` reads.

Usage: uv run wn/tufs_words.py [path/to/tufs]
"""

from __future__ import annotations

import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

import build

#: TUFS concept ids for kinship terms, with a Japanese gloss
TUFS_CONCEPTS = {
    "16190": "おじさん",
    "16192": "おばさん",
    "16223": "おじいさん",
    "16229": "おばあさん",
    "16592": "祖母（母方）",
    "16593": "祖父（母方）",
    "16751": "孫",
    "16780": "兄弟",
    "16783": "姉妹",
    "16785": "兄",
    "16797": "お兄さん",
    "16799": "姉",
    "16806": "お姉さん",
    "16809": "弟",
    "16810": "弟さん",
    "16811": "妹",
    "16812": "妹さん",
    "16863": "おじ・おば（母方）",
    "16866": "叔父，伯父",
    "16869": "叔母，伯母",
    "16870": "伯母（父の兄の妻）",
    "16888": "甥",
    "16343": "夫",
    "16351": "ご主人",
    "16364": "妻",
    "16402": "奥さん",
    "16488": "両親",
    "16495": "父",
    "16496": "母",
    "16500": "お父さん",
    "16507": "お母さん",
    "16585": "舅",
    "16647": "息子",
    "16892": "いとこ",
    "16893": "従兄弟（母方）",
    "16896": "従姉妹",
}

#: Bunrui Goihyō headings (`midasi`) in the family classes 1.211-1.215 that name
#: a kin type. Left out: 家族 (family), 夫婦 (couple), 既婚者 (married person),
#: 奥様 (madam), 王子/王女 (prince/princess), 親戚 (relatives, as a group).
KIN_HEADINGS = {
    "おじいさん",
    "祖母",
    "孫",
    "兄",
    "姉",
    "弟",
    "妹",
    "妹さん",
    "弟さん",
    "お兄さん",
    "お姉さん",
    "兄弟（きょうだい）",
    "姉妹（しまい）",
    "いとこ",
    "おい",
    "伯母（おば）",
    "伯母・叔母（おば）",
    "伯父・叔父（おじ）",
    "従兄弟",
    "従姉妹",
    "母方",
}

#: TUFS language codes that differ from the KinDiv tags. TUFS `as` is Syrian
#: Arabic, not Assamese; `pb` is Brazilian Portuguese.
TUFS_TAGS = {"as": "apc", "pb": "pt", "zh": "cmn"}

#: Dumps named ``vmod_<lang>_<ui>.sql`` repeat <lang> with another interface
#: language; only the monolingual ``vmod_<lang>.sql`` are read.
DUMP = re.compile(r"vmod_([a-z]+)\.sql")
COPY = re.compile(r"COPY (\w+) \(([^)]*)\) FROM stdin;")
ANNOTATION = re.compile(r"\((?:orth|morph):[^)]*\)|（[^）]*）|\([^)]*\)")
PINYIN = re.compile(r"\s+[a-zāáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜü]+$")


def normalize(form: str) -> str:
    """Drop Arabic-script vowel marks and case so vocalized forms still match."""
    decomposed = unicodedata.normalize("NFD", form)
    stripped = "".join(ch for ch in decomposed if not "ً" <= ch <= "ٟ")
    return unicodedata.normalize("NFC", stripped).casefold()


def forms_of(lemma: str, lang: str) -> list[str]:
    """Split a TUFS lemma cell into its word forms, without annotations.

    >>> forms_of("(သူတစ်ပါးရဲ့)အစ်ကို; ကိုကို", "my")
    ['အစ်ကို', 'ကိုကို']
    >>> forms_of("伯母 bómǔ", "zh")
    ['伯母']
    """
    parts = (
        ANNOTATION.sub("", p) for p in re.split(r"[;；/]", lemma.replace("\\n", " "))
    )
    cleaned = [" ".join(p.split()).rstrip("\u200f") for p in parts]
    if lang == "zh":  # the raw dumps append pinyin: "伯母 bómǔ"
        cleaned = [PINYIN.sub("", f) for f in cleaned]
    # NFC puts Arabic marks in canonical order: TUFS writes shadda before tanwin
    return [unicodedata.normalize("NFC", f) for f in cleaned if f]


def read_dump(path: Path) -> dict[str, list[dict[str, str]]]:
    """Read the COPY blocks of a PostgreSQL dump into rows keyed by table."""
    tables: dict[str, list[dict[str, str]]] = {}
    columns: list[str] = []
    table = ""
    with path.open(encoding="utf8") as handle:
        for line in handle:
            if match := COPY.match(line):
                table, columns = match[1], [c.strip() for c in match[2].split(",")]
                tables[table] = []
            elif table and line.startswith("\\."):
                table = ""
            elif table:
                tables[table].append(dict(zip(columns, line.rstrip("\n").split("\t"))))
    return tables


def raw_kin_words(tufsdata: Path) -> set[tuple[str, str, str]]:
    """Return (lang, word id, lemma) for usages under a kinship Bunrui heading."""
    found = set()
    for path in sorted(tufsdata.glob("vmod_*.sql")):
        if not (match := DUMP.fullmatch(path.name)):
            continue
        tables = read_dump(path)
        words = {w["id"]: w["basic"] for w in tables["t_word"]}
        word_of = {u["usage_id"]: u["word_id"] for u in tables["t_usage"]}
        for row in tables["t_usage_classified_rel"]:
            if row["midasi"] in KIN_HEADINGS and row["usage_id"] in word_of:
                wid = word_of[row["usage_id"]]
                found.add((match[1], wid, words.get(wid, "")))
    return found


def main() -> None:
    """Write tufs-candidates.tsv."""
    tufs = Path(sys.argv[1] if len(sys.argv) > 1 else build.DATA.parent / "tufs")
    concepts = build.read_concepts()
    languages = build.read_languages(concepts)
    by_tag: dict[tuple[str, str], set[str]] = defaultdict(set)
    for language in languages.values():
        for form, meanings in language.words.items():
            by_tag[language.tag, normalize(form)] |= {code for code, _ in meanings}

    cid_of: dict[tuple[str, str], str] = {}
    words: set[tuple[str, str, str, str]] = set()
    for row in build.read_tsv(tufs / "tufs-vocab.tsv"):
        cid_of.setdefault((row["lang"], row["wid"]), row["cid"])
        if row["cid"] in TUFS_CONCEPTS:
            words.add((row["cid"], row["lang"], row["wid"], row["lemma"]))
    for lang, wid, lemma in raw_kin_words(tufs / "tufsdata"):
        cid = cid_of.get((lang, wid), "None")
        if cid not in TUFS_CONCEPTS:
            # not reachable through tufs-vocab.tsv under a kinship concept
            words.add((cid if cid != "None" else "", lang, wid, lemma))

    rows = set()
    for cid, lang, wid, lemma in words:
        tag = TUFS_TAGS.get(lang, lang)
        for form in forms_of(lemma, lang):
            auto = sorted(by_tag.get((tag, normalize(form)), ()))
            rows.add(
                (
                    cid,
                    TUFS_CONCEPTS.get(cid, ""),
                    lang,
                    wid,
                    tag,
                    form,
                    ";".join(map(build.slug, auto)),
                )
            )
    with (build.HERE / "tufs-candidates.tsv").open("w", encoding="utf8") as out:
        out.write("tufs_cid\ttufs_gloss\ttufs_lang\ttufs_wid\ttag\tform\tauto\n")
        for row in sorted(rows):
            out.write("\t".join(row) + "\n")


if __name__ == "__main__":
    main()
