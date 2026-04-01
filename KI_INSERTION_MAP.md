# Korean Intervention Insertion Map

This map places the standalone `KI` lessons into the main `G` sequence as intervention lessons, not as replacements for core phonics lessons.

Policy:
- `Required when flagged`
- `Skippable when stable`

## Recommended Order

1. `G2-L7`
2. `KI-L1`
3. `G2-L8`
4. `G2-L9`
5. `G2-L10`
6. `G2-L11`
7. `KI-L4`
8. `G3-L12`
9. `G3-L13`
10. `G3-L14`
11. `G3-L15`
12. `KI-L2`
13. `G3-L16`
14. `... core sequence continues ...`
15. `G6-L39`
16. `KI-L5`
17. `G7-L40`
18. `... core sequence continues ...`
19. `G7-L43`
20. `KI-L3`
21. `G8-L44`

## Placement Rationale

- [KI-L1.json](/Users/tanioramotu/luminos-engine/app/content/lessons/KI-L1.json)
  - Insert after `G2-L7`.
  - Purpose: establish `/r/` vs `/l/` auditory discrimination before the first sustained `/r/` decoding load.
  - Assign when: the learner confuses `/r/` and `/l/` in listening, oral response, or word repetition.
  - Skip or shorten when: the learner can discriminate `/r/` and `/l/` accurately across minimal pairs.

- [KI-L4.json](/Users/tanioramotu/luminos-engine/app/content/lessons/KI-L4.json)
  - Insert after `G2-L11`.
  - Purpose: stabilize final coda production once simple codas are available and before denser final-cluster pressure builds.
  - Assign when: the learner drops or weakens final consonants in `CVC` words or simple codas during reading or repetition.
  - Skip or shorten when: final stops and nasals are preserved consistently in connected speech.

- [KI-L2.json](/Users/tanioramotu/luminos-engine/app/content/lessons/KI-L2.json)
  - Insert after `G3-L15`.
  - Purpose: move from liquid discrimination into print and production practice after the first explicit liquid instruction.
  - Assign when: the learner can hear the contrast but still reads or says `r/l` words inaccurately from print.
  - Skip or shorten when: print-to-speech production is already stable in words and short sentences.

- [KI-L5.json](/Users/tanioramotu/luminos-engine/app/content/lessons/KI-L5.json)
  - Insert after `G6-L39`.
  - Purpose: reduce high-risk vowel contrast collapse before the later vowel-heavy sequence.
  - Assign when: the learner collapses high-risk vowel contrasts such as `ship/sheep` or `pen/pan` in reading or dictation.
  - Skip or shorten when: those vowel contrasts are already stable in listening, reading, and encoding.

- [KI-L3.json](/Users/tanioramotu/luminos-engine/app/content/lessons/KI-L3.json)
  - Insert after `G7-L43`.
  - Purpose: front-load cluster production practice before the cluster-heavy band in `G8`.
  - Assign when: the learner inserts a vowel in clusters like `/st/`, `/bl/`, `/tr/`, or breaks the cluster apart.
  - Skip or shorten when: clusters are produced cleanly without epenthesis in words and sentences.

## Use Rule

- Use `KI` lessons as targeted intervention lessons, not as optional enrichment.
- A `KI` lesson is required when the learner shows the trigger pattern.
- A `KI` lesson is skippable when the target is already stable.
- Keep the main `G` lesson order intact.
- Do not count a `KI` lesson as the student’s only exposure to the corresponding phonics pattern in the core sequence.
- If a learner is stable on the target contrast, the teacher can shorten the `KI` lesson to Blocks `03`, `06`, `07`, `08`, and `09`.

## Quick Assignment Rules

- Assign `KI-L1` before `KI-L2` if the issue is primarily auditory discrimination.
- Assign `KI-L2` when the issue is mainly print-to-speech transfer for liquids.
- Assign `KI-L4` early if coda deletion is already visible in `G2`.
- Assign `KI-L5` only when the learner is actually collapsing vowel categories; do not use it as a default detour.
- Assign `KI-L3` just before the dense cluster band or earlier if epenthesis is already showing up.
