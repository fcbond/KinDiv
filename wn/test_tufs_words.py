"""Tests for the TUFS kinship-word extractor."""

from __future__ import annotations

import pytest

import tufs_words


@pytest.mark.parametrize(
    ("lemma", "lang", "expected"),
    [
        ("(သူတစ်ပါးရဲ့)အစ်ကို; ကိုကို", "my", ["အစ်ကို", "ကိုကို"]),
        ("伯母 bómǔ", "zh", ["伯母"]),
        ("哥哥 (orth:pīnyīn gēge)", "zh", ["哥哥"]),
        ("pak cik", "ms", ["pak cik"]),
        ("خال / خالة\u200f", "as", ["خال", "خالة"]),
    ],
)
def test_forms_of(lemma: str, lang: str, expected: list[str]) -> None:
    assert tufs_words.forms_of(lemma, lang) == expected


def test_normalize_ignores_arabic_vowel_marks() -> None:
    assert tufs_words.normalize("عَمٌّ") == tufs_words.normalize("عم")


def test_forms_are_in_canonical_order() -> None:
    # TUFS writes shadda (U+0651) before dammatan (U+064C)
    assert tufs_words.forms_of(
        "\u0623\u064e\u0628\u064e\u0648\u0650\u064a\u0651\u064c", "ar"
    ) == ["\u0623\u064e\u0628\u064e\u0648\u0650\u064a\u064c\u0651"]
