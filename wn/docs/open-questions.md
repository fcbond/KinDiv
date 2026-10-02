# Open questions

Design points that are not settled. Each says what the build does now.

## 1. Which ILI for *brother* and *sister*?

**Now.** `concept-ili.tsv` links `Br` and `Ss` to Princeton's *male sibling* and
*female sibling*. The existing wordnets put the words *brother* and *sister* one
level down, in their hyponyms:

| concept | KinDiv links to | the wordnets' *brother* / *sister* (a hyponym of it) |
|---|---|---|
| `Br` | `i91174` *male sibling* "a sibling who is male" | `i88708` *brother, blood brother* "a male with the same parents as someone else" |
| `Ss` | `i89922` *female sibling* "a person's sister" | `i93018` *sister, sis* "a female person who has the same parents as another person" |

In OEWN, *male sibling* and *female sibling* are under *kinsman* and
*kinswoman*, not under *sibling* (`i92980`, our `Sb`). Which Cygnet wordnets have
each ILI (from the review files' `existing_by_ili`):

- `i91174` *male sibling*: OEWN, omw-ja, and TUFS (en, zh, ja, id).
- `i88708` *brother*: OEWN, omw-cmn, omw-ja, omw-id, omw-pl, CantoWN, and TUFS
  (en, zh, ja, id).
- `i89922` *female sibling*: OEWN and omw-ja only.
- `i93018` *sister*: OEWN, omw-cmn, omw-ja, omw-id and omw-pl.

These are the only two of the 35 ILI links where our English lemma's sense in
OEWN differs from our link.

**The difference in meaning.** "Same parents" makes `i88708`/`i93018` full
siblings, which leaves out half-siblings. KinDiv's `Br` is the kin type
"brother", which does not separate full from half siblings; that fits
`i91174`/`i89922`. But the wordnets' words *brother*, *brat* and 兄弟 are linked to
the narrower synset, though they are used for half-brothers too.

**Options.**
- (a) Keep `i91174`/`i89922`: their definitions fit the kin type. Words that
  other wordnets link to `i88708` reach KinDiv only through the hypernym.
- (b) Relink to `i88708`/`i93018`, where the words are. `Br` then claims "same
  parents", which is narrower than the kin type.
- (c) Keep (a), and propose to CILI that the definitions of `i88708`/`i93018`
  say what the words mean (a brother or sister, including half-siblings), or
  that they be merged with their hypernyms.
- In any case, should *male sibling* and *female sibling* be under *sibling*?
  KinDiv's hierarchy puts `Br` under `Sb`; OEWN does not (see question 3).

**Evidence from OEWN's own hierarchy.** OEWN puts *half sister* (`i93019`, "a
sister who has only one parent in common with you") under *sister* (`i93018`,
"a female person who has the **same parents** as another person"), and *half
brother* (`i93307`) under *brother* (`i88708`). A half-sister cannot have the
same parents, so either the definitions of `i88708`/`i93018` are too narrow or
the hierarchy is wrong. The hyponymy says the words mean any brother or sister,
full or half, which is what KinDiv's `Br` and `Ss` mean. This favours (b) or
(c): link to `i88708`/`i93018` and ask CILI to widen their definitions to
"a male/female sibling", or merge each with its hypernym, since nothing then
separates them from *male sibling*/*female sibling*.

## 2. Half, step, adoptive and foster relatives

**Now.** None of these is a concept. KinDiv's codes are chains of genealogical
links (`Fa`, `Br`, `So`, ...) with no way to say how a link was made, so `Br` is
any brother: full, half, step or adoptive. Our extension (parents, spouses,
in-laws, Kinbank's recurring types) adds none either. `kinbank_words.py` reads
only positions whose links are capital letters with optional `e`/`y` for age,
so Kinbank's half-sibling positions (`mhB`, `fehZ`) and step positions
(`mFWS_notBorhB`) fall outside the atom space: they are neither matched nor
used as neighbours.

**What the sources have.**

- *Kinbank* records half siblings in 8 + 8 positions (by ego sex and sibling
  sex, some by relative age: `mehB` "male ego's older half brother", some by
  the shared parent: `mhB_FS` "paternal half brother") and step siblings
  indirectly (`mFWS_notBorhB` "father's wife's son that is not a brother or
  half brother"). Only 13 languages fill any of them, all from the VariKin
  sample:

  | language | family | what it distinguishes |
  |---|---|---|
  | Ama | Nyimang | *abakeri* any half sibling; *abakɛriŋ kaʃɛl*/*kar* half brother/sister |
  | Dilling | Nubian | *anenta*, *ambagan-dwano* any half sibling |
  | Karko | Nubian | *áfá-n-t̪ɔ́ɔ́d̪ʊ̀* any half sibling |
  | Moro | Heibanic | *leleŋnu*, *orba* any half sibling |
  | Ngile | Narrow Talodi | *anobede* any half sibling |
  | Nuer | Nilotic | *Gat gwa* half brother, *Nya gwa* half sister |
  | Southeastern Dinka | Nilotic | *Wenawa* half brother, *Nyanawa* half sister |
  | Hausa | Afro-Asiatic | paternal (*ɗan'ùbā*, *ùbā*) vs maternal (*uwarmù ɗaya*) half sibling |
  | Halia | Austronesian | by relative sex: same-sex *hahatoulana*, cross-sex *hahahinana* |
  | Hunza | isolate | *tcho*, *lus*, *yas*, partly shared with step siblings |
  | Hamtai | Nuclear Trans New Guinea | step siblings only: *taso*, *nukwe* |
  | Nunamiut | Eskimo-Aleut | half siblings by age and sex (*apiaqerak*, *nukaqerak*); step sister *kataq* |
  | Ottawa Ojibwa | Algic | half siblings by age and sex (*nissaye*, *nimisse*, *nishime*) |

  A general "half sibling" word occurs in 4 families (Nyimang, Nubian,
  Heibanic, Talodi), all in the Nuba Mountains, so one macroarea; sex-specific
  half brother/sister in 3 families (Nilotic, Afro-Asiatic, Austronesian) in 2
  macroareas. Neither meets the admission rule (5 families, 3 macroareas).
  Absence elsewhere means "not asked", not "no word": the other datasets did
  not elicit these positions.
- *KinDiv* records no gaps for them.
- *TUFS* has no half, step or adoptive kin words among its kin headings.
- *OEWN* has *half blood* (`i90390`, under *sibling*), *half brother*/*half
  sister* (`i93307`/`i93019`, under *brother*/*sister*), *stepparent*
  (`i93312`), *stepchild* (`i93308`), *adoptive parent* (`i88091`), *foster
  parent*/*child*/*brother*/*sister* (`i90060`, `i90055`, `i90054`, `i90061`),
  but no *stepbrother*/*stepsister* synset of their own (question 3).

**What adding them would take.**

- A new feature in the code for how a link is made, on the link it qualifies:
  half (one shared parent), step (through a parent's spouse or a spouse's
  parent), adoptive, foster. For example `hBr` or `Br(h)`, with the shared
  parent where it matters (`Fa.hBr` paternal half brother). A step brother
  is *not* simply `Fa;Wi;So`: a father's wife's son is usually one's own
  brother, so the chain needs the same qualifier (a step link) to exclude him.
- A decision on what plain `Br` means. Now it is any brother. With half
  brothers as concepts, `Br` stays the broader concept and `hBr` and a new
  full-brother concept (`fBr`, the "same parents" of `i88708`) sit under it.
- Parsing Kinbank's `h` positions, and admitting by the usual rule. On the
  current data nothing would be admitted; the main source would have to be
  dictionaries, as for the attestations of unattested concepts.
- Kinbank's step positions are negative ("father's wife's son that is not a
  brother or half brother"), which the extension matcher cannot read as a
  set of atoms.

## 3. OEWN problems found while linking

To report to OEWN (github.com/globalwordnet/english-wordnet), and to keep in mind
when linking:

- **Step and half siblings merged.** `i93019` has the lemmas *half sister*,
  *half-sister* and *stepsister*, and `i93307` has *stepbrother*,
  *half-brother* and *half brother*, both defined as "only one parent in
  common". A step sibling shares no parent; *stepbrother* and *stepsister*
  need synsets of their own (child of one's stepparent), beside *stepparent*
  and *stepchild*, which OEWN has.
- **Half siblings under full siblings.** As in question 1: *half sister* is
  under *sister* "same parents", *half brother* under *brother*.
- **Male and female sibling not under sibling.** *male sibling* (`i91174`)
  is under *kinsman*, *female sibling* (`i89922`) under *kinswoman*, while
  *sibling* (`i92980`) is under *relative*. Each should also be a hyponym of
  *sibling* (multiple inheritance, as for *brother*: male and sibling).
- **Foster siblings outside kinship.** *foster brother* (`i90054`) is under
  *male*, and *foster sister* (`i90061`) under *female*, not under any
  relative; *foster parent* (`i90060`) is under *defender*. *adoptive parent*
  and *stepparent* are under *parent*, so the treatment is inconsistent.

## 4. Speaker sex, register and politeness on kin terms

**Anchor sex is not speaker register.** KinDiv's `x`/`o` ("male/female
speaking", after Murdock's *m.s.*/*w.s.*) is the sex of the *anchor* (ego), the
person the relation is traced from: `x;El;Br` is "an elder brother of a man", and it changes what the
word denotes (Burmese *nyi* is a man's younger brother whoever is speaking). The
pronoun wordnet's `Men`/`Wom` ("men's/women's speech", from NTUMC) is a
restriction on the *speaker*, a register: *boku* "I" is predominantly men's
speech but denotes whoever says it. The two coincide only when the speaker is
the anchor (first-person pronouns, kin terms of address), which is why "male speaking"
looks like the same thing. They should stay distinct features, but:

- the labels now say "(male anchor)" rather than "(male speaking)" (done:
  `relabel` in `build.py`);
- `Men`/`Wom` could apply to kin terms too, but we have no checked example:
  Wiktionary marks Japanese *oyaji* 親父 "father" and *ofukuro* 御袋 "mother"
  only as informal, not as men's speech.

**Politeness and formality are missing.** Kin terms vary on the same axes as
pronouns:

- politeness: Japanese *ani* 兄 "elder brother" (plain) vs *oniisan* お兄さん
  (honorific);
- formality: English *father* vs *dad* vs *old man*; Japanese *chichiue* 父上
  (archaic, honorific) vs *oyaji* 親父 (informal).

The pronoun features `Fml`/`Infml`, `Pol`/`Hon`/`NHon` and `Men`/`Wom` would apply
unchanged (`El;Br;Hon` for *oniisan*). No source we use records them for kin
terms:

- KinDiv, Kinbank and TUFS give one word per kin type, or list alternatives
  without saying how they differ.
- NTUMC puts Japanese *兄*, *兄さん* and *兄貴* in one synset ("an older brother"),
  and *父*, *お父さん*, *親父*, *父上* in another ("a male parent"); none of its 32
  links from non-pronoun synsets to feature synsets is from a kin synset.
- OEWN does separate register for English parents, as concepts of their own:
  *dad, daddy, pa, papa* (`i89370`, "an informal term for a father") and
  *old man* (`i91724`, "an informal term for your father") are hyponyms of
  *father* (`i89901`, our `Fa`); *old man* is also a hyponym of *dysphemism*;
  *ma, mama, mom, mommy* (`i91123`, "informal terms for a mother") is under
  *mother* (`i91462`, our `Mo`). The register is stated only in the
  definition (and, for *old man*, the second hypernym), not by a feature.
  NTUMC's Japanese mixes them: formal *母* is in the informal-mother synset,
  and *お母さん* in both.

**How to add them.** OEWN's practice answers the design question: a register
variant is a concept of its own, a hyponym of the plain kin type, as in the
pronoun wordnet, where `1;Sg;Fml` is under `1;Sg`. Kin codes would take the
pronoun features: `Fa;Infml` for *dad* (= `i89370`), `El;Br;Hon` for
*oniisan*, with `exemplifies` links to the same feature synsets. *old man*
(`i91724`) is also `Fa;Infml`; OEWN separates it from *dad* only as a
dysphemism, so the codes would need a value for that (a pejorative register)
or the two would fall together. Admission needs evidence that languages lexicalize
the register distinction for a kin type, which none of our sources records.

**Future work:** add register features to kin concepts, starting from English
(OEWN's *dad*, *old man*, *mom*, which would link to existing ILIs) and
Japanese (where the distinctions are grammaticalized), and from
pronoun-substitute data (question 2 of omw-pronoun's list: kin terms used in
address).

## 5. Beyond genealogy: adoption, death, divorce and more (future work)

KinDiv's kin types are chains of birth and marriage links between living people.
Languages also lexicalize how a link was made, whether it still holds, and
relations that run through a third party. None of these is a concept yet (half
and step siblings are question 2). Examples to start from:

| area | examples |
|---|---|
| adoption, fostering | Japanese *mukoyōshi* 婿養子, "an adult man who is adopted into a Japanese family as a daughter's husband, and who takes the family's surname" (son-in-law and adopted son at once); *yōshi* 養子 "adopted child", *yōfu* 養父 "adoptive father"; Hawaiian *hānai* "foster child, adopted child"; English *foster brother* |
| death | English *widow*, *widower*, *orphan*; Japanese *mibōjin* 未亡人 and *goke* 後家 "widow"; Mandarin *xiānfù* 先父 "one's deceased father" (respectful, literary) and *xiānbǐ* 先妣 "one's deceased mother"; Japanese *bōfu* 亡父 "deceased father"; English *levir* "a husband's brother", the term of levirate marriage, in which a widow marries her late husband's brother |
| divorce, remarriage | English *ex-wife*, *ex-husband*; Mandarin *qiánqī* 前妻 "ex-wife or late wife"; English *stepmother*, Japanese *keibo*/*mamahaha* 継母; Japanese *harachigai* 腹違い "a paternal half sibling" (same father, different mother) |
| plural marriage | Hindi *saut*, *sautan* "co-wife"; Hebrew *tsará* צָרָה and Swahili *mke mwenza* "co-wife" |
| affines of affines | Spanish *consuegro*/*consuegra* "co-father/mother-in-law", the parent of one's child's spouse; Yiddish *mekhutn* מחותּן "male relative by marriage, especially son-in-law's or daughter-in-law's father"; Hindi *samdhī* "co-father-in-law"; Korean *sadon* 사돈 "co-parent-in-law"; Hindi *sāṛhū* "husband of sister of wife" |
| ritual and fictive kin | Spanish *compadre*, "godfather of one's child; parent of one's godchild"; Mandarin *gāndiē* 干爹 (乾爹) "godfather; (nominally) adoptive father"; milk kinship: English *milk sibling*, Turkish *süt kardeşi* |
| birth order | Japanese *chōnan* 長男 "the eldest of a family's sons", *suekko* 末っ子 "youngest child" |

Every example was checked against English Wiktionary (October 2026); glosses in
quotation marks are Wiktionary's. Not confirmed there, so left out: Hebrew
*shakul* "bereaved of a child", an Arabic term for "milk brother", and Japanese
*ibo kyōdai* 異母兄弟 (Wiktionary has it only as Chinese).

**What the codes would need.**

- *Link qualifiers*, saying how a link was made: adoptive, foster, step, half,
  milk, ritual (godparenthood). *mukoyōshi* is `Da;Hu` that is also an
  adoptive `So`.
- *Link status*: former (divorce), late (death). *qiánqī* is a former `Wi`;
  *xiānfù* a late `Fa` (with politeness: question 4).
- *Relations through a missing link*: a widow is a `Wi` whose `Hu` is dead; an
  orphan a `Ch` whose `Pa` are dead.
- *Co-relations*, shared position rather than a chain: co-wife (`Hu;Wi` of a
  `Wi`), *consuegro* (`Ch;Sp;Pa`, already a chain), *sāṛhū* (`Wi;Ss;Hu`, already a
  chain).
- *Birth order* beyond elder/younger: eldest, youngest, second.

Some of these are already chains in the current notation (*consuegro*,
*sāṛhū*) and could be admitted now if a source records them; the rest need new
features. Kinbank elicits few of them (13 languages for half siblings, step
siblings only negatively); dictionaries and OEWN (*widow*, *widower*, *orphan*,
*stepmother*, *foster brother*) are the likely sources.
