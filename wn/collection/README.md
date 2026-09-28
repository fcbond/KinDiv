# KinDiv wordnets

Kinship terms in 1,028 languages, as WN-LMF wordnets for the
[`wn`](https://wn.readthedocs.io) library. Built from
[KinDiv](https://github.com/fcbond/KinDiv), the database of lexical diversity in
the kinship domain, extended with parents, children, spouses and in-laws, and with
kinship words from the TUFS Basic Vocabulary, Kinbank and White (2021) for Hmong.

- `kindiv` holds the concepts: one unlexicalized synset per kin type (310), with
  its definition, its ILI (or an ILI proposal) and the hypernym hierarchy. Its
  lemmas are kin-type codes such as `Fa;Br;So`; its language tag is `mul`.
- `kindiv-<lang>` is a standalone lexicon of one language's words, with no
  relations. A recorded lexical gap is an unlexicalized synset. `kindiv-en` also
  names every concept English has no word for, with an unlexicalized phrase
  ("father's sister's husband").

The hierarchy is reached through the ILI:

```python
import wn

wn.add("kindiv-0.1.tar.xz")
zh = wn.Wordnet("kindiv-cmn", expand="kindiv")
zh.synsets("哥哥")[0].hypernym_paths()
```

35 concepts have an ILI now; the other attested ones are proposed to the
Collaborative Interlingual Index. Until they are accepted, every synset's
`dc:identifier` (e.g. `KinDiv:Fa;Br;So`) links it to its concept in `kindiv`.

Sources: KinDiv (CC BY-SA 3.0); Kinbank (CC BY 4.0); TUFS Basic Vocabulary, Tokyo University of
Foreign Studies (CC BY 4.0); Open English WordNet (CC BY 4.0); Wiktionary
(CC BY-SA).
