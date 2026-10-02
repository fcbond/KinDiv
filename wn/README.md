# KinDiv as a multilingual wordnet

`build.py` turns the KinDiv tables, plus the TUFS Basic Vocabulary kinship words,
into a [`wn`](https://wn.readthedocs.io) collection of WN-LMF 1.4 packages,
`release/kindiv-0.1/` and `release/kindiv-0.1.tar.xz` (gitignored: attach them to a
GitHub release). Collection-level README, LICENSE and `citation.bib` are copied
from `collection/`.

```
uv run wn/tufs_words.py              # TUFS words -> tufs-candidates.tsv
uv run wn/tufs_curation.py           # candidates -> tufs-kindiv.tsv
uv run wn/build.py                   # collection, lexicons.tsv, ili-proposals.tsv
uv run --with pytest --with langcodes --with language_data --with unidecode pytest wn  # tests
```

## Model

- **`kindiv`** (language `mul`) is the interlingual concept layer, like KinDiv's
  own. It has one synset per concept (310), all `lexicalized="false"`, with the
  definition, the ILI or an ILI proposal (`ili="in"` + `ILIDefinition`, written
  only here), and the whole hypernym hierarchy. WN-LMF requires entries, so each
  concept's lemma is its kin-type code (`Fa;Br;So`), as an unlexicalized sense.
- **`kindiv-<tag>`** (1,028 lexicons: 171 from KinDiv, TUFS and hmong-ontology, the rest from Kinbank) are
  standalone lexicons of words: one synset per concept the language lexicalizes,
  carrying the concept's ILI where it has one (empty otherwise), and
  `dc:identifier="KinDiv:Fa;Br;So"`. They have **no relations**. The hierarchy
  is in the shared lexicon; join a language synset to its concept on
  `dc:identifier`:

  ```python
  base = wn.Wordnet("kindiv")
  concept = {s.metadata()["identifier"]: s for s in base.synsets()}
  pl = wn.Wordnet("kindiv-pl")
  wujek = pl.synsets("wujek")[0]
  concept[wujek.metadata()["identifier"]].hypernyms()
  # KinDiv:Mo;Sb, KinDiv:Pa;Br, KinDiv:Mo;Br|Mo;Br;So, KinDiv:Mo;Br|x;Ss;Ch
  ```

  Wn's `expand="kindiv"` does **not** give the hierarchy yet. It matches
  synsets by ILI, and a proposed concept (`ili="in"`) has none until CILI
  assigns one, so only the 35 ILI-linked concepts are reached, and even their
  paths skip proposed ancestors (*dziadek* "grandfather" reaches *grandparent*
  but not the merger above it). Expansion also returns only synsets present in
  the language's own lexicon. Once CILI assigns ILIs to the proposals,
  `expand` will work for every concept.
- **Words** become entries, with one sense per concept they express. The sense's
  `dc:source` is the provenance (KinDiv, TUFS, OEWN or Wiktionary).
- **English phrases**: every concept English has no word for (197 of 236) gets
  its compositional phrase in `kindiv-en`, e.g. "father's sister's husband",
  "man's parent's father", "father's brother's son (older than self)". The phrase
  is an unlexicalized sense (`lexicalized="false"`) on an unlexicalized synset
  marked `dc:type="phrase"`, so `kindiv-en` names every concept.
- **Gaps** become `lexicalized="false"` synsets, written only for languages that also
  have words. When a word and a gap are both recorded for the same concept, the word
  wins; `build.py` logs these cases.
- **Hypernymy** comes from `relations` plus `extra-relations.tsv`. Upstream KinDiv uses
  `Fa;Sb;So` and `Fa;Sb;Da` (son/daughter of father's sibling) in `relations` and
  `gaps` but never listed them in `concepts`, apparently by accident; this fork
  adds them to `concepts`. `build.py` still bridges any code missing from
  `concepts`.
- **Definitions** are generated from the kin-type code, e.g. "a son of a man's
  father's brother, who is older than him (a cousin)".

A LexiconExtension design (languages extending `kindiv`) was tried and dropped:
wn 1.1 checks every extension's base before adding anything, so extensions shipped
with their base in one file or collection are silently skipped.

## Labels: anchor, not speaker

KinDiv's `x`/`o` (Murdock's "male/female speaking") is the sex of the **anchor**,
the person a relation is traced from: `x;El;Br` is a man's elder brother, whoever
is speaking. The build labels these concepts "(male anchor)"/"(female anchor)"
(`relabel` in `build.py`), so they are not confused with a restriction on the
speaker, such as the pronoun wordnet's *men's speech* (`docs/open-questions.md`,
question 4).

## ILI links

`concept-ili.tsv` is the hand-curated mapping to the CILI, checked against OEWN 2025.
Only `exact` rows become `ili=`. A `broader` row (OEWN *uncle*/*aunt* also cover
relatives by marriage) is kept only as `dc:relation` plus a note. Which ILI
*brother* and *sister* should link to is open: see `docs/open-questions.md`.

## Beyond KinDiv

KinDiv covers only consanguineal kin outside the nuclear family.
`extra-concepts.tsv` and `extra-relations.tsv` add 32 more nodes, all under a
single root, `Rel` (*relative*):

- **parents, children, spouses**: `Pa Fa Mo`, `Ch So Da`, `Sp Hu Wi`;
- **in-laws**: `InL` above parents-in-law (`Sp;Pa Sp;Fa Sp;Mo`), children-in-law
  (`Ch;Sp Da;Hu So;Wi`), and siblings-in-law (`BrL` = `Sp;Br` or `Ss;Hu`; `SsL` =
  `Sp;Ss` or `Br;Wi`);
- **uncle and aunt by blood or marriage**: `Unc` and `Aun` (English *uncle* and
  *aunt*), with KinDiv's `Pa;Br`/`Pa;Ss` beneath them;
- **affinal uncles and aunts**: `Pa;Ss;Hu` > `Fa;Ss;Hu`, `Mo;Ss;Hu`, and
  `Pa;Br;Wi` > `Fa;Br;Wi` > `Fa;El;Br;Wi`, `Fa;Yn;Br;Wi`. These sit under both
  `Unc`/`Aun` and `InL`.

English words for these come from OEWN, and for the in-law nodes OEWN lacks
(*parent-in-law*, *child-in-law*, and the specific senses of *brother-in-law* and
*sister-in-law*) from Wiktionary (`extra-words.tsv`). OEWN defines
*sister-in-law* (i93022) narrowly as "the sister of your spouse", so that ILI
goes on `Sp;Ss`; the broad `SsL` is a new-ILI candidate.

| status | concepts |
|---|--:|
| linked to an existing ILI | 35 |
| attested, new-ILI candidate (`ili="in"` + `ILIDefinition`) | 144 |
| unattested: occurs only as a gap, or a structural node no source attests | 51 |

`ili-proposals.tsv` lists every concept with its status, the number of languages
that lexicalize it, the number with a gap, and the proposed ILI definition. Of the
139 candidates, 47 are attested in only one language.

The 43 unattested concepts are mostly speaker-sex variants (grandparents,
grandchildren, uncles and aunts), plus *maternal grandparent*, the
elder/younger-sibling's-child set, and four cousin types. They should not be
proposed to CILI unless an attestation is found.

## TUFS

`tufs_words.py` collects TUFS kinship words from `../tufs`, from both
`tufs-vocab.tsv` (36 kinship concept ids) and the raw SQL dumps (Bunrui Goihyō
family headings). The raw dumps matter because `munge.py` drops some words, e.g.
zh 姑姑 and 表妹, and ar عم. Each form is then matched against KinDiv words in the
same language, giving `tufs-candidates.tsv`.

`tufs_curation.py` turns the candidates into `tufs-kindiv.tsv`; the script
holds every hand decision, so it is the place to review or change them.
`tufs-kindiv.tsv` is the checked mapping: one row per (TUFS word, KinDiv concept).
`method` is `kindiv` (the form already has that concept in KinDiv), `curated`,
or `default` (the one kin type of its TUFS concept, e.g. every word under TUFS
"father" is `Fa`),
and each row has a `confidence`. Each word is mapped by its own meaning, not by
its TUFS concept: TUFS "uncle" holds tr *amca* (Fa;Br) and *dayı* (Mo;Br). Rows
with `low` confidence, or with no concept, are kept for review but not built; the
rows with no concept are titles (fr *madame*, id *nyonya*), an adjective and a
possessive form. TUFS 子ども is "child" in the sense of a young person, not
offspring, so it is not used. TUFS forms are NFC-normalized (TUFS writes Arabic
shadda before tanwīn), and one typo (ar زوح for زوج) is corrected.

TUFS `as` is Syrian Arabic (`apc`), not Assamese; `pb` is merged into `pt`.

## Hmong

`attested-words.tsv` holds words from sources other than KinDiv and TUFS, each
with its source URL and quoted evidence; only `exact` rows are built. It includes
the 28 White Hmong / Green Mong kin terms mapped in
`../hmong-ontology/kinship-kindiv.tsv` (White 2021, Table 29, p. 288).

Four concepts come from `../hmong-ontology/kindiv-proposals.tsv`, motivated by
Hmong *nus*, *muam*, *tij laug* and *kwv*: `o;Fa;Sb;So`, `x;Fa;Sb;Da`,
`x;El;Fa;Sb;So`, `x;Yn;Fa;Sb;So`. They rest on those terms covering the child of
a father's sister as well as a father's brother, which Nathan White has still to
confirm. If he does not, they collapse to the existing `Fa;Br;*` concepts.

## Kinbank

[Kinbank](https://github.com/kinbank/kinbank) (Passmore et al. 2023, CC BY 4.0)
records the term used at each genealogical position in 1,314 languages.
`kinbank_words.py` reads a clone at `../kinbank` and writes
`kinbank-candidates.tsv`: the terms whose set of positions equals a KinDiv
concept's, where the language was also asked about every neighbouring position
(other ego sex, other sex or side of each link, other relative age), so the term
is known not to extend there. A general position (sibling, child, parent, spouse)
holding several words is read as a list of alternatives, not one broad term.

`build.py` adds the 12,767 matches (925 languages) that carry no
`broader_synonym` flag. A flag means another word covers the term's positions
*and* a neighbour it lacks, so its absence there may only mean Kinbank recorded
one word per slot (German *Opa* vs *Großvater*); those 3,730 stay in the table.

Checked against KinDiv where both have the word, the matches agree 95%. The
remaining disagreements are mostly Kinbank data errors (Danish *sønnedatter* also
listed under DD; Welsh *cefnder* under female cousins), with a few genuine
differences (Polish *wujek*, Hungarian *unokanővér*). Notes:

- Kinbank's `parameters.csv` calls `mG` "Grandparent", but its forms (English
  *sibling*, Swedish *syskon*) show `G` is a sibling.
- ISO 639-3 codes map to the tags `languages.tsv` already uses, including
  macrolanguages (`pes` -> `fa`, `hbs` -> `sh`, `tgl` -> `tl`). 217 Kinbank
  languages have no ISO code and are skipped.
- Two Kinbank varieties transcribe languages with an orthography of their own
  (`p_englishstan1293`, `p_germanstan1295`: *ˈbɹʌðə*, *ŭngʹkəl*, *ˈtɔχtɐ*). Their
  forms become `<Pronunciation>`s of the written word for the same concept
  (`notation="IPA"`, or `respelling` for dictionary respelling), not words. Where
  that written word was held back for a broader synonym (German *Tochter*,
  *Sohn*), the transcription's exact match attests it and it is added.
- Most Kinbank forms for languages written in another script are
  romanizations (Mandarin *xiong di*, Hindi *bhāī*, Russian *brat*): 3,000
  forms in 65 languages. `kinbank_words.py` marks them in the `transcription`
  column, by comparing the form's letters with the language's likely script
  (CLDR via langcodes; Old Norse and Old Irish count as Latin-written). Where
  the language has a word in its own script for the concept, the romanization
  becomes its `<Pronunciation notation="romanization">`: the only such word,
  or the one whose Unidecode transliteration matches best (*tang jie* goes to
  *堂姐*, not *堂姊*). Otherwise it stays a lemma, the only record of the word,
  with `<Pronunciation notation="source-transcription">`. 325 romanizations are
  pronunciations; 1,902 lemmas are transcriptions. Every lemma records its
  script (`script="Hani"`).

## Attestations

Research for the concepts no source attested found words in `attested-words.tsv`
(with source URLs and quoted definitions): e.g. Serbo-Croatian *tetak* and
*strina*, Ukrainian *дядина*, Swedish *morförälder*, Comanche and Gunwinggu
speaker-sex grandchild terms. With Kinbank, only 7 concepts remain unattested:
grandparent/grandfather/grandmother (female anchor), paternal grandfather (male
anchor), and uncle (both) and aunt (female anchor) by anchor sex.

## Concepts from Kinbank

`kinbank_concepts.py` looks for meanings (sets of positions) that recur in
Kinbank but match no concept, and writes them to `kinbank-new-concepts.tsv`; with
`--write` it adds those that pass the admission rule:

- **a kin type** (one code, e.g. `x;Ss;Da` "a man's sister's daughter", `Hu;Fa`
  "husband's father") needs **>= 5 language families in >= 3 macroareas**: it is
  already a node of the genealogical grid KinDiv enumerates, so recurrence is
  justification enough;
- **a merger** of kin types (a union, written `Fa|Fa;Br` "father or father's
  brother") needs **>= 8 families and at most two parts**: it claims languages merge
  positions, so it needs more evidence.

Families count isolates separately; macroareas guard against areal spread. 74
concepts were admitted (38 kin types, 36 mergers), including cross cousin
(`Fa;Ss;Ch|Mo;Br;Ch`), opposite-sex sibling (`o;Br|x;Ss`), the reciprocal
grandparent/grandchild (`Ch;Ch|Pa;Pa`) and Omaha-type `Mo;Br|Mo;Br;So`. Their
hierarchy is computed from the positions they cover: a concept's hypernyms are
the smallest concepts containing it, so *father* sits under both *parent* and
*father or father's brother*; a concept nothing contains goes under `InL` or `Rel`.
Kinbank counts are inflated for Bantu and Algonquian (Morgan 1871), which is why
the thresholds use families, not languages. The 48 unions that failed (5-7
families, or three parts) stay in the table for review.
