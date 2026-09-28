#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Turn tufs-candidates.tsv into the checked mapping tufs-kindiv.tsv.

This file *is* the curation: every TUFS word that KinDiv does not already have is
mapped here by hand, with a confidence and, where useful, a note. A word is
mapped by its own meaning, not by the TUFS concept it was listed under.

Each candidate gets, in order:

1. ``kindiv`` rows: concepts the same form already has in KinDiv;
2. the broad uncle/aunt node for European-style words (``BROAD``);
3. ``curated`` rows from ``CURATED``; a row with no concept records why a word is
   left out (a title, an adjective, ...);
4. failing all of those, the default concept for its TUFS concept id.

Usage: uv run wn/tufs_curation.py
"""

from __future__ import annotations

import logging

import build

logger = logging.getLogger(__name__)

H, M, L = "high", "medium", "low"
UNC = "affinal as well as consanguineal: matches OEWN uncle"
AUN = "affinal as well as consanguineal: matches OEWN aunt"

#: (TUFS language, form) -> [(KinDiv concept, confidence, note)]
CURATED: dict[tuple[str, str], list[tuple[str, str, str]]] = {
    ("ja", "おじさん"): [("Unc", H, UNC)],
    ("ja", "おばさん"): [("Aun", H, AUN)],
    ("ms", "pak cik"): [("Unc", M, "also an older man")],
    ("ms", "ibu saudara"): [("Aun", H, "")],
    ("my", "ဦးလေး"): [("Pa;Yn;Br", M, "also a younger aunt's husband")],
    ("my", "ဦးဦး"): [("Unc", L, "familiar term of address")],
    ("my", "အဒေါ်"): [("Aun", M, "")],
    ("my", "ဒေါ်ဒေါ်"): [("Aun", L, "familiar term of address")],
    ("as", "جدّ"): [("Gr;Fa", H, "Syrian Arabic")],
    ("as", "ستّ"): [("Gr;Mo", H, "Syrian Arabic")],
    ("lo", "ພໍ່ເຖົ້າ"): [("Gr;Fa", L, "literally 'old father'; also father-in-law")],
    ("lo", "ແມ່ເຖົ້າ"): [("Gr;Mo", L, "literally 'old mother'; also mother-in-law")],
    ("mn", "өвгөн"): [("Gr;Fa", L, "primarily 'old man'")],
    ("mn", "эмгэн"): [("Gr;Mo", L, "primarily 'old woman'")],
    ("my", "အဖိုး"): [("Gr;Fa", H, "")],
    ("my", "ဖိုးဖိုး"): [("Gr;Fa", H, "familiar")],
    ("my", "အဖွား"): [("Gr;Mo", H, "")],
    ("my", "ဖွားဖွား"): [("Gr;Mo", H, "familiar")],
    ("ru", "дедушка"): [("Gr;Fa", H, "")],
    ("ru", "бабушка"): [("Gr;Mo", H, "")],
    ("ur", "دادا"): [("Fa;Fa", H, "")],
    ("ur", "دادی"): [("Fa;Mo", H, "")],
    ("vi", "ông ngoại"): [("Mo;Fa", H, "")],
    ("vi", "ông nội"): [("Fa;Fa", H, "")],
    ("vi", "bà ngoại"): [("Mo;Mo", H, "")],
    ("vi", "bà nội"): [("Fa;Mo", H, "")],
    ("zh", "爷爷"): [("Fa;Fa", H, "")],
    ("ja", "おばあさん"): [("Gr;Mo", H, "")],
    ("tr", "baba anne"): [("Fa;Mo", H, "usually written babaanne")],
    ("ms", "nénék"): [("Gr;Mo", H, "")],
    ("as", "أخّ"): [("Br", H, "Syrian Arabic")],
    ("de", "Geschwister"): [("Sb", H, "")],
    ("id", "saudara"): [("Sb", M, "also 'relative'")],
    ("ja", "兄弟"): [("Sb", H, "")],
    ("km", "បងប្អូនប្រុស"): [("Br", H, "")],
    ("ko", "형제"): [("Br", M, "brothers; also siblings")],
    ("lo", "ອ້າຍນ້ອງ"): [("Sb", M, "also 'relatives'")],
    ("mn", "ах дүү"): [("Sb", M, "also 'brothers'")],
    ("ms", "adik-beradik"): [("Sb", H, "")],
    ("my", "ညီအစ်ကိုမောင်နှမ"): [("Sb", H, "")],
    ("pb", "irmãos"): [("Sb", H, "plural form")],
    ("th", "พี่น้อง"): [("Sb", H, "")],
    ("tl", "kapatid"): [("Sb", H, "")],
    ("tr", "kardeş"): [("Sb", H, "")],
    ("vi", "anh em"): [("Sb", M, "also 'brothers'")],
    ("id", "kakak laki-laki"): [("El;Br", H, "")],
    ("ja", "兄"): [("El;Br", H, "")],
    ("lo", "ອ້າຍ"): [("El;Br", H, "")],
    ("my", "ကိုကို"): [("El;Br", H, "familiar")],
    ("my", "အစ်ကို"): [("El;Br", H, "")],
    ("pt", "irmão mais velho"): [("El;Br", H, "")],
    ("ru", "старший брат"): [("El;Br", H, "")],
    ("th", "พี่ชาย"): [("El;Br", H, "")],
    ("tl", "kuya"): [("El;Br", H, "")],
    ("tr", "ağabey"): [("El;Br", H, "")],
    ("tr", "abi"): [("El;Br", H, "colloquial")],
    ("ur", "بڑا بھائی"): [("El;Br", H, "")],
    ("ur", "بڑے بھائی صاحب"): [("El;Br", M, "honorific")],
    ("id", "kakak"): [("El;Sb", H, "")],
    ("as", "إخت"): [("Ss", H, "Syrian Arabic")],
    ("id", "kakak perempuan"): [("El;Ss", H, "")],
    ("ja", "姉"): [("El;Ss", H, "")],
    ("ja", "お姉さん"): [("El;Ss", H, "")],
    ("km", "បងប្អូនស្រី"): [("Ss", H, "")],
    ("ko", "자매"): [("Ss", H, "sisters")],
    ("lo", "ເອື້ອຍ"): [("El;Ss", H, "")],
    ("lo", "ເອື້ອຍນ້ອງ"): [("Ss", M, "sisters")],
    ("mn", "эгч дүүс"): [("Ss", M, "sisters")],
    ("my", "မမ"): [("El;Ss", H, "familiar")],
    ("my", "အစ်မ"): [("El;Ss", H, "")],
    ("pb", "irmãs"): [("Ss", H, "plural form")],
    ("pt", "irmã mais velha"): [("El;Ss", H, "")],
    ("ru", "старшая сестра"): [("El;Ss", H, "")],
    ("ru", "сестра"): [("Ss", H, "")],
    ("th", "พี่สาว"): [("El;Ss", H, "")],
    ("tl", "ate"): [("El;Ss", H, "")],
    ("tl", "kapatid na babae"): [("Ss", H, "")],
    ("tr", "abla"): [("El;Ss", H, "")],
    ("tr", "kız kardeş"): [("Ss", H, "")],
    ("ur", "بڑی بہن"): [("El;Ss", H, "")],
    ("ur", "آپا"): [("El;Ss", M, "")],
    ("vi", "chị em"): [("Ss", M, "sisters")],
    ("zh", "姐妹"): [("Ss", H, "sisters")],
    ("ja", "弟"): [("Yn;Br", H, "")],
    ("ja", "弟さん"): [("Yn;Br", H, "")],
    ("ms", "adik lelaki"): [("Yn;Br", H, "")],
    ("my", "ညီလေး"): [("x;Yn;Br", H, "ညီ: a man's younger brother")],
    ("my", "မောင်လေး"): [("o;Yn;Br", H, "မောင်: a woman's younger brother")],
    ("ur", "چھوٹا بھائی"): [("Yn;Br", H, "")],
    ("ja", "妹"): [("Yn;Ss", H, "")],
    ("ja", "妹さん"): [("Yn;Ss", H, "")],
    ("ms", "adik perempuan"): [("Yn;Ss", H, "")],
    ("my", "ညီမလေး"): [("o;Yn;Ss", H, "ညီမ: a woman's younger sister")],
    ("my", "ညီမ"): [("o;Yn;Ss", H, "")],
    ("my", "နှမလေး"): [("x;Yn;Ss", M, "နှမ: a man's (younger) sister")],
    ("my", "နှမ"): [("x;Yn;Ss", M, "")],
    ("ur", "چھوٹی بہن"): [("Yn;Ss", H, "")],
    ("as", "عمّ"): [("Fa;Br", H, "Syrian Arabic")],
    ("as", "عمّة"): [("Fa;Ss", H, "Syrian Arabic; an aunt, filed under TUFS uncle")],
    ("km", "ពូ"): [("Pa;Yn;Br", M, "")],
    ("lo", "ລຸງ"): [("Pa;El;Br", H, "")],
    ("ru", "дядя"): [("Unc", H, UNC)],
    ("ur", "تایا"): [("Fa;El;Br", H, "")],
    ("zh", "伯父"): [("Fa;El;Br", H, "")],
    ("zh", "叔父"): [("Fa;Yn;Br", H, "")],
    ("zh", "舅父"): [("Mo;Br", H, "")],
    ("zh", "姑夫"): [("Fa;Ss;Hu", H, "")],
    ("zh", "姨夫"): [("Mo;Ss;Hu", H, "")],
    ("km", "មីង"): [("Pa;Yn;Ss", M, "")],
    ("lo", "ປ້າ"): [("Pa;El;Ss", H, "")],
    ("ur", "پھوپھی"): [("Fa;Ss", H, "")],
    ("zh", "婶母"): [("Fa;Yn;Br;Wi", H, "")],
    ("zh", "姨母"): [("Mo;Ss", H, "")],
    ("ru", "тётя"): [("Aun", H, AUN)],
    ("id", "saudara sepupu"): [("Pa;Sb;Ch", H, "")],
    ("km", "បងប្អូនជីដូនមួយ"): [("Pa;Sb;Ch", H, "")],
    ("ko", "사촌"): [("Pa;Sb;Ch", H, "")],
    ("lo", "ລູກເອື້ອຍລູກນ້ອງ"): [("Pa;Sb;Ch", H, "")],
    ("ru", "двоюродный брат"): [("Pa;Sb;So", H, "")],
    ("th", "ลูกพี่ลูกน้อง"): [("Pa;Sb;Ch", H, "")],
    ("tl", "pinsan"): [("Pa;Sb;Ch", H, "")],
    ("tr", "kuzen"): [("Pa;Sb;Ch", H, "")],
    ("ur", "چچازاد بھائی"): [("Fa;Br;So", H, "")],
    ("vi", "chị ho"): [("El;Pa;Sb;Da", H, "TUFS typo for chị họ")],
    ("zh", "姑姑"): [("Fa;Ss", H, "")],
    ("tr", "anneanne"): [("Mo;Mo", H, "")],
    ("zh", "老爷"): [("Mo;Fa", M, "regional (northern); also 'master'")],
    ("as", "خال"): [("Mo;Br", H, "Syrian Arabic")],
    ("as", "خالة"): [("Mo;Ss", H, "Syrian Arabic")],
    ("zh", "伯母"): [
        ("Fa;El;Br;Wi", H, "also a polite 'auntie' for a friend's mother")
    ],
    ("mn", "ах"): [
        ("", M, "elder brother (El;Br); listed under TUFS uncle as a term of address")
    ],
    ("mn", "эгч"): [
        ("", M, "elder sister (El;Ss); listed under TUFS aunt as a term of address")
    ],
    # parents, children, spouses, in-laws
    ("tl", "asawa"): [("Sp", H, "spouse: not gendered")],
    ("tr", "eş"): [("Sp", H, "spouse: not gendered")],
    ("ar", "زوح"): [("Hu", H, "corrected from the TUFS typo زوح")],
    ("as", "زوج"): [("Hu", H, "Syrian Arabic")],
    ("as", "جوز"): [("Hu", H, "Syrian Arabic")],
    ("de", "Mann"): [("Hu", M, "primarily 'man'")],
    ("my", "ယောက်ျား"): [("Hu", M, "also 'man'")],
    ("my", "အမျိုးသား"): [("Hu", M, "polite; also 'man'")],
    ("de", "Frau"): [("Wi", M, "primarily 'woman'")],
    ("es", "mujer"): [("Wi", M, "primarily 'woman'")],
    ("fr", "femme"): [("Wi", M, "primarily 'woman'")],
    ("as", "مرة"): [("Wi", M, "Syrian Arabic; primarily 'woman'")],
    ("my", "မိန်းမ"): [("Wi", M, "primarily 'woman'")],
    ("my", "အမျိုးသမီး"): [("Wi", M, "polite; also 'woman'")],
    ("ur", "بیگم"): [("Wi", M, "also 'lady'")],
    ("fr", "madame"): [("", H, "'Mrs, madam': a title, not a kin term")],
    ("id", "nyonya"): [("", H, "'Mrs, madam': a title, not a kin term")],
    ("pt", "meus pais"): [("Pa", M, "'my parents': the form is a phrase")],
    ("tr", "anne babası"): [
        ("", H, "possessive form of anne baba ('his/her parents')")
    ],
    ("ar", "أَبَوِيٌّ"): [("", H, "adjective 'paternal, parental'")],
    ("ar", "حَمٌ"): [
        ("Sp;Fa", M, "classically the husband's father, or any of the husband's kin")
    ],
}

#: Words that also cover relatives by marriage: add the broad node alongside KinDiv's
BROAD = {
    ("en", "uncle"),
    ("de", "Onkel"),
    ("fr", "oncle"),
    ("es", "tío"),
    ("pt", "tio"),
    ("pb", "tio"),
    ("id", "paman"),
    ("tl", "tito"),
    ("en", "aunt"),
    ("de", "Tante"),
    ("fr", "tante"),
    ("es", "tía"),
    ("pt", "tia"),
    ("pb", "tia"),
    ("id", "bibi"),
    ("tl", "tita"),
}
AUNT_CIDS = {"16869", "16192"}

#: TUFS misspellings: (TUFS language, form) -> corrected form
CORRECTIONS = {("ar", "زوح"): "زوج"}

#: The kin type every word under these TUFS concepts expresses, unless curated
CID_DEFAULT = {
    "16343": "Hu",
    "16351": "Hu",
    "16364": "Wi",
    "16402": "Wi",
    "16495": "Fa",
    "16500": "Fa",
    "16496": "Mo",
    "16507": "Mo",
    "16647": "So",
    "16488": "Pa",
}
DEFAULT_NOTE = {"16488": "plural 'parents'"}


def mappings(row: dict[str, str]) -> list[tuple[str, str, str, str]]:
    """Return (concept, method, confidence, note) rows for one candidate."""
    key = (row["tufs_lang"], row["form"])
    found = [
        (code.replace("-", ";"), "kindiv", H, "")
        for code in row["auto"].split(";")
        if code
    ]
    if key in BROAD:
        aunt = row["tufs_cid"] in AUNT_CIDS
        found.append(("Aun" if aunt else "Unc", "curated", H, AUN if aunt else UNC))
    have = {concept for concept, *_ in found}
    for concept, confidence, note in CURATED.get(key, []):
        if concept not in have and (concept or not found):
            found.append((concept, "curated", confidence, note))
    if not found and row["tufs_cid"] in CID_DEFAULT:
        cid = row["tufs_cid"]
        found.append((CID_DEFAULT[cid], "default", H, DEFAULT_NOTE.get(cid, "")))
    return found


def main() -> None:
    """Write tufs-kindiv.tsv and log candidates left unmapped."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    columns = ["tufs_cid", "tufs_gloss", "tufs_lang", "tufs_wid", "tag", "form"]
    used = set()
    with (build.HERE / "tufs-kindiv.tsv").open("w", encoding="utf8") as out:
        out.write("\t".join(columns) + "\tconcept\tmethod\tconfidence\tnote\n")
        for row in build.read_tsv(build.HERE / "tufs-candidates.tsv"):
            used.add((row["tufs_lang"], row["form"]))
            found = mappings(row)
            if not found:
                logger.warning("unmapped: %s %s", row["tufs_lang"], row["form"])
            for mapping in found:
                form = CORRECTIONS.get((row["tufs_lang"], row["form"]), row["form"])
                fixed = dict(row, form=form)
                out.write("\t".join([fixed[c] for c in columns] + list(mapping)) + "\n")
    for key in sorted(CURATED.keys() - used):
        logger.warning("curated but not a candidate: %s", key)


if __name__ == "__main__":
    main()
