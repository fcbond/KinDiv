"""Tests for the KinDiv wordnet builder.

Run with: uv run --with pytest pytest wn
"""

from __future__ import annotations

import pytest

import build


@pytest.mark.parametrize(
    ("code", "subdomain", "expected"),
    [
        ("Gr;Fa", "grandparents", "the father of one's parent (a grandparent)"),
        ("Gr;Ch", "grandchildren", "a child of one's child (a grandchild)"),
        ("Pb", "uncles and aunts", "a sibling of one's parent (an uncle or aunt)"),
        ("x;Fa;Br;So", "cousins", "a son of a man's father's brother (a cousin)"),
        (
            "Pa;El;Br",
            "uncles and aunts",
            "an elder brother of one's parent (an uncle or aunt)",
        ),
        (
            "El;Br;Ch",
            "nephews and nieces",
            "a child of one's elder brother (a nephew or niece)",
        ),
        ("o;Yn;Ss", "siblings", "a younger sister of a woman (a sibling)"),
        (
            "El;Fa;Br;So",
            "cousins",
            "a son of one's father's brother, who is older than oneself (a cousin)",
        ),
        (
            "x;El;Pa;Sb;So",
            "cousins",
            "a son of a man's parent's sibling, who is older than him (a cousin)",
        ),
    ],
)
def test_define(code: str, subdomain: str, expected: str) -> None:
    assert build.define(code, subdomain) == expected


def test_definitions_are_long_enough_for_cili() -> None:
    # CILI rejects ILI definitions shorter than 20 characters
    concepts = build.read_concepts()
    assert all(len(c.definition) >= 20 for c in concepts.values())


def test_definitions_are_unique() -> None:
    concepts = build.read_concepts()
    definitions = [c.definition for c in concepts.values()]
    assert len(definitions) == len(set(definitions))


def test_paternal_cousins_sit_between_their_kin_types() -> None:
    # Fa;Sb;So was used in relations but missing from upstream concepts
    ancestry = build.read_hierarchy(build.read_concepts())
    assert {"Fa;Sb;So", "Pa;Sb;So", "Fa;Sb;Ch"} <= ancestry["Fa;Br;So"]
    assert {"Fa;Sb;Da", "Pa;Sb;Da"} <= ancestry["Fa;Ss;Da"]


def test_nearest_skips_ancestors_of_included_ancestors() -> None:
    ancestry = {"a": set(), "b": {"a"}, "c": {"a", "b"}}
    assert build.nearest({"a", "b", "c"}, ancestry) == {
        "a": set(),
        "b": {"a"},
        "c": {"b"},
    }
    assert build.nearest({"a", "c"}, ancestry) == {"a": set(), "c": {"a"}}


def test_every_language_has_a_tag() -> None:
    concepts = build.read_concepts()
    languages = build.read_languages(concepts)
    assert all(language.tag for language in languages.values())


def test_invisible_characters_are_stripped() -> None:
    languages = build.read_languages(build.read_concepts())
    forms = {form for language in languages.values() for form in language.words}
    assert not any(ch in form for form in forms for ch in "\u200b\u200e\n")
    assert "いとこ" in languages["Japanese"].words


def test_broad_uncle_and_aunt_are_linked_and_above_kindiv_nodes() -> None:
    concepts = build.read_concepts()
    ancestry = build.read_hierarchy(concepts)
    assert concepts["Unc"].ili == "i93825"
    assert concepts["Aun"].ili == "i88357"
    assert "Unc" in ancestry["Fa;El;Br"]
    assert "Aun" in ancestry["Mo;Ss"]


def test_tufs_rows_name_known_concepts_and_languages() -> None:
    concepts = build.read_concepts()
    tags = set(build.LANGUAGE_TAGS.values())
    for row in build.read_tsv(build.HERE / "tufs-kindiv.tsv"):
        assert row["tag"] in tags
        assert not row["concept"] or row["concept"] in concepts
        # a row without a concept must say why
        assert row["concept"] or row["note"]


def test_tufs_words_are_added_but_low_confidence_ones_are_not() -> None:
    concepts = build.read_concepts()
    languages = build.read_languages(concepts)
    build.add_tufs(languages, concepts)
    assert "Unc" in {c for c, _ in languages["Russian"].words["дядя"]}
    assert "خال" in languages["Syrian Arabic"].words
    assert "өвгөн" not in languages["Mongolian"].words


def test_affinal_uncles_and_aunts_are_uncles_and_in_laws() -> None:
    ancestry = build.read_hierarchy(build.read_concepts())
    assert {"Pa;Ss;Hu", "Unc", "InL", "Rel"} <= ancestry["Fa;Ss;Hu"]
    assert {"Fa;Br;Wi", "Pa;Br;Wi", "Aun", "InL"} <= ancestry["Fa;El;Br;Wi"]
    assert "Pa;Br" not in ancestry["Fa;Ss;Hu"]


def test_every_concept_is_a_relative() -> None:
    concepts = build.read_concepts()
    ancestry = build.read_hierarchy(concepts)
    assert all("Rel" in ancestry[code] for code in concepts if code != "Rel")


@pytest.fixture(scope="module")
def data() -> tuple[dict, dict, dict]:
    concepts = build.read_concepts()
    languages = build.read_languages(concepts)
    build.add_tufs(languages, concepts)
    build.add_attestations(languages, concepts)
    build.add_kinbank(languages, concepts)
    build.add_gaps(languages, concepts)
    return concepts, build.read_hierarchy(concepts), languages


def test_shared_lexicon_is_unlexicalized_and_proposes_each_ili_once(data) -> None:
    concepts, ancestry, _ = data
    lines: list[str] = []
    build.write_base(lines, concepts, ancestry)
    synsets = [line for line in lines if "<Synset " in line]
    assert len(synsets) == len(concepts)
    assert all('lexicalized="false"' in line for line in synsets)
    proposed = sum(bool(c.languages) and not c.ili for c in concepts.values())
    assert sum("<ILIDefinition>" in line for line in lines) == proposed


def test_language_lexicon_has_no_relations_or_proposals(data) -> None:
    concepts, _, languages = data
    lines: list[str] = []
    counts = build.write_language(lines, languages["Mandarin"], concepts)
    text = "\n".join(lines)
    assert "<SynsetRelation" not in text
    assert 'ili="in"' not in text
    assert "<ILIDefinition>" not in text
    assert 'id="kindiv-cmn-Fa-Ss-Hu" ili=""' in text
    assert text.count('lexicalized="false"') == counts["gaps"]


def test_english_covers_every_concept_with_a_word_or_a_phrase(data) -> None:
    concepts, _, languages = data
    english = languages["English"]
    build.add_phrases(english, concepts)
    words = {code for senses in english.words.values() for code, _ in senses}
    assert words | set(english.phrases.values()) == set(concepts)
    assert not words & set(english.phrases.values())
    assert english.phrases["father's sister's husband"] == "Fa;Ss;Hu"


def test_phrases_are_unlexicalized_senses_on_unlexicalized_synsets(data) -> None:
    concepts, _, languages = data
    lines: list[str] = []
    build.write_language(lines, languages["English"], concepts)
    text = "\n".join(lines)
    assert 'synset="kindiv-en-Fa-Ss-Hu" lexicalized="false"/>' in text
    synset = next(line for line in lines if '<Synset id="kindiv-en-Fa-Ss-Hu"' in line)
    assert 'ili=""' in synset
    assert 'lexicalized="false"' in synset
    assert 'lexfile="noun.kin"' in synset


def test_languages_from_later_sources_keep_their_kindiv_gaps(data) -> None:
    # Arikara has no word in KinDiv's `words`, only gaps; its words come from Kinbank
    _, _, languages = data
    assert languages["Arikara"].words
    assert languages["Arikara"].gaps
