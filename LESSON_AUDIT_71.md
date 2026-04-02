# Lesson Audit: 71-Lesson Corpus

## Scope

This audit reviews all 71 lessons in `app/content/lessons/` against the following criteria:

- controlled-text / "double-control" compliance
- lesson substance and practice density
- Korean phonological interference coverage
- likely next remediation action

## Rubric

- `Control pass`: no obvious controlled-text breach detected by audit heuristics
- `Control at risk`: metadata inconsistency or one likely controlled-text breach
- `Control fail`: multiple likely breaches, usually untaught clusters / split units appearing before the explicit cluster strand
- `Very thin`: 20-32 total slides
- `Thin`: 33-38 total slides
- `Moderate`: 39-44 total slides
- `Stronger`: 45+ total slides
- `Korean support embedded only`: interference is flagged in cues/notes, but there is no dedicated learner contrast work
- `Some contrast`: at least some `minimal_pair` work exists

## Cross-Corpus Findings

- Every lesson has only 1 slide in Block `07`, Block `09`, and Block `10`. This is structurally thin even in later, larger lessons.
- The early sequence repeatedly breaks strict double-control through untaught clusters or split units before the explicit cluster strand.
- Korean support is mostly embedded in teacher notes. Dedicated learner contrast practice is sparse.
- Metadata is not fully reliable enough to enforce rules automatically without cleanup.

## Audit

### Group 1

- `G1-L1` (`s · a · t`): Control at risk; very thin; Korean support none; Priority high. Fix sight-word metadata for `I`, which is introduced as sight but later tagged decodable; add more sentence bridge, reread, and oral generation work.
- `G1-L2` (`i`): Control at risk; very thin; Korean support embedded only; Priority high. Remove or postpone `its`-style coda complexity; expand Blocks `07`, `09`, `10`.
- `G1-L3` (`p`): Control pass; very thin; Korean support embedded only; Priority high. Add more cumulative sentence reading and encoding volume.
- `G1-L4` (`n`): Control pass; very thin; Korean support embedded only; Priority high. Add reread and simple generative sentence work.

### Group 2

- `G2-L5` (`c_k`): Control fail; very thin; Korean support embedded only; Priority critical. `tick` and `pick` introduce `ck` too early and treat it as split letters; either teach `ck` explicitly or replace with simpler forms.
- `G2-L6` (`e`): Control fail; very thin; Korean support embedded only; Priority critical. `step` introduces `st` before the cluster strand; replace with non-cluster items.
- `G2-L7` (`h`): Control fail; very thin; Korean support embedded only; Priority high. `hint` adds coda complexity too early; simplify word pool.
- `G2-L8` (`r`): Control fail; very thin; Korean support embedded only; Priority critical. Strong `/r/` teacher guidance, but no learner contrast tasks; `rack`, `trek`, `trap` add `ck` and `tr` too early. Add a dedicated `/r/` contrast mini-lesson or full lesson before cluster loading.
- `G2-L9` (`m`): Control at risk; very thin; Korean support embedded only; Priority high. `mask` adds `sk` too early; add `/m/` cumulative practice and defer clusters.
- `G2-L10` (`d`): Control fail; thin; Korean support embedded only; Priority critical. `drip`, `end`, `and`, `ink` add cluster/coda pressure too early; split `d` learning from cluster work.
- `G2-L11` (`w`): Control fail; thin; Korean support embedded only; Priority critical. `swim`, `swam`, `swept`, `twin` overload cluster complexity; reserve these for later and add simpler `w` practice first.

### Group 3

- `G3-L12` (`g`): Control at risk; very thin; Korean support embedded only; Priority high. `twig` adds `tw`; simplify vocabulary and reader pool.
- `G3-L13` (`o`): Control fail; moderate; Korean support embedded only; Priority high. `stop` and `rock` introduce cluster/`ck` complexity; tighten controlled-text pool.
- `G3-L14` (`u`): Control fail; thin; Korean support embedded only; Priority critical. `drum`, `truck`, `duck`, `stuck` overload onset/coda complexity; this lesson needs a simpler word pool.
- `G3-L15` (`l`): Control fail; thin; Korean support embedded only; Priority critical. High `r_l` load with no dedicated discrimination work; add a dedicated `/l/` contrast lesson or mini-sequence before loading `sl/gl`.
- `G3-L16` (`f`): Control fail; thin; Korean support embedded only; Priority critical. Heavy `f_p` load plus `fr/fl/st/lt`; split phoneme establishment from cluster work.
- `G3-L17` (`b`): Control at risk; thin; Korean support embedded only; Priority high. `grub` adds onset cluster too early; add clearer `/b/` vs `/v/` groundwork later.
- `G3-L18` (`j`): Control at risk; thin; Korean support embedded only; Priority high. `just` adds `st` coda pressure; also light on explicit learner discrimination.
- `G3-L19` (`v`): Control at risk; thin; Korean support embedded only; Priority high. `v_b` coverage is almost entirely embedded; add dedicated `/v/` vs `/b/` minimal-pair work.
- `G3-L20` (`y` consonant): Control at risk; thin; Korean support embedded only; Priority high. `yell` and `yelp` add coda complexity; add simpler `y` onset practice.

### Group 4

- `G4-L21` (`sh`): Control at risk; moderate; Korean support embedded only; Priority medium-high. `fresh` and `brush` add clusters not yet formalized; otherwise sequence direction is sound.
- `G4-L22` (`th_voiceless`): Control fail; thin; Korean support embedded only; Priority high. `thick`, `think`, `broth` add `ck`, `nk`, `br`; add more dedicated voiceless `th` contrast work before complex codas/onsets.
- `G4-L23` (`th_voiced`): Control pass; thin; Korean support some contrast; Priority medium. This is one of the few lessons with actual minimal-pair work; still needs more Block `07/09/10` volume.
- `G4-L24` (`ch`): Control at risk; moderate; Korean support embedded only; Priority medium. `chest` adds coda cluster load; add a small `ch` vs `sh` contrast band.
- `G4-L25` (`qu`): Control fail; thin; Korean support embedded only; Priority medium-high. `quick` and `quest` introduce extra coda complexity; separate `qu` establishment from harder codas.
- `G4-L26` (`ng`): Control at risk; moderate; Korean support embedded only; Priority medium-high. `strong` and `bring` add onset cluster work beyond the target; simplify if strict control is required.

### Group 5

- `G5-L27` (`ai_ay`): Control at risk; moderate; Korean support embedded only; Priority medium. `train`, `play`, `stay` rely on onset clusters; okay for a looser sequence, not okay for strict double-control.
- `G5-L28` (`ee_ea`): Control at risk; moderate; Korean support embedded only; Priority medium. `tree` introduces `tr`; add simpler non-cluster exemplars first.
- `G5-L29` (`oa_ow`): Control fail; moderate; Korean support embedded only; Priority medium-high. `float`, `snow`, `grow`, `slow` assume cluster readiness; tighten entry words.
- `G5-L30` (`oo_long`): Control at risk; moderate; Korean support embedded only; Priority medium-high. `spoon` and `smooth` assume cluster control; also metadata around `with` needs cleanup.
- `G5-L31` (`oo_short`): Control at risk; thin; Korean support some contrast; Priority medium. One of the better vowel-contrast lessons because it includes minimal-pair work; still needs more reader and close practice.
- `G5-L32` (`CVCe`): Control pass; stronger; Korean support embedded only; Priority medium. Stronger volume than most lessons, but still thin in fluency, morpheme noticing, and close.
- `G5-L33` (`oi_oy`): Control pass; moderate; Korean support embedded only; Priority medium. Add more oral sentence generation and contrastive spelling practice.
- `G5-L34` (`y_long_i`): Control fail; thin; Korean support embedded only; Priority medium-high. Many words (`fly`, `sky`, `try`, `dry`, `cry`) assume cluster readiness; okay later in a cluster-ready pathway, not strict control.
- `G5-L35` (`z`): Control pass; moderate; Korean support embedded only; Priority medium. Add explicit `z` vs `s` voicing discrimination and more sentence generation.

### Group 6

- `G6-L36` (`ar`): Control at risk; stronger; Korean support embedded only; Priority medium. `star` assumes cluster readiness; otherwise content is reasonably substantial.
- `G6-L37` (`er_ir_ur`): Control pass; stronger; Korean support embedded only; Priority medium. High `r_l` burden needs dedicated learner contrast, not just flagged cues.
- `G6-L38` (`or`): Control at risk; stronger; Korean support embedded only; Priority medium. `sport` and `storm` assume onset-cluster readiness.
- `G6-L39` (`air_ear_eer`): Control pass; stronger; Korean support embedded only; Priority medium. Good volume, but still only one reader slide and one close slide.

### Group 7

- `G7-L40` (`wh`): Control pass; moderate; Korean support embedded only; Priority medium. Add explicit meaning transfer and more fluency repetition.
- `G7-L41` (`soft_c_soft_g`): Control at risk; thin; Korean support some contrast; Priority medium. Minimal-pair work helps, but `stage` assumes onset-cluster readiness and later blocks are still thin.
- `G7-L42` (`ou_ow_aʊ`): Control at risk; stronger; Korean support embedded only; Priority medium. `found` assumes coda cluster readiness; otherwise sequence is workable.
- `G7-L43` (`tion`): Control pass; stronger; Korean support embedded only; Priority medium-high. Morphophonemic instruction is good, but it needs more sentence construction and explicit word-family transfer.

### Group 8

- `G8-L44` (`l_clusters`): Control pass; very thin; Korean support embedded only; Priority high. This is exactly where dedicated Korean cluster intervention should exist, but it does not.
- `G8-L45` (`r_clusters`): Control pass; thin; Korean support embedded only; Priority critical. Very high `r_l` load with no minimal-pair learner work; add explicit `/r/` vs `/l/` plus epenthesis drills.
- `G8-L46` (`s_clusters`): Control pass; stronger; Korean support embedded only; Priority high. Add cluster reduction / vowel epenthesis contrast tasks.
- `G8-L47` (`final_nasal_clusters`): Control pass; very thin; Korean support embedded only; Priority high. Needs more final-coda preservation practice.
- `G8-L48` (`final_sf_clusters`): Control pass; stronger; Korean support embedded only; Priority high. Good volume, but still missing dedicated Korean coda support.
- `G8-L49` (`final_l_clusters`): Control pass; stronger; Korean support embedded only; Priority high. Strong `r_l` risk; needs learner discrimination and production work.
- `G8-L50` (`triple_clusters`): Control pass; stronger; Korean support embedded only; Priority critical. High-risk cluster lesson with no dedicated learner contrast layer.
- `G8-L51` (`missing target pattern`): Control at risk; stronger; Korean support embedded only; Priority critical. Metadata is defective and the lesson duplicates triple-cluster style work; fix naming, pattern, and instructional purpose.
- `G8-L52` (`silent_kn_wr_gn`): Control pass; very thin; Korean support embedded only; Priority medium-high. Add explicit silent-letter analysis and contrast work.
- `G8-L53` (`final_le`): Control pass; stronger; Korean support embedded only; Priority medium. Add more encoding and sentence generation.
- `G8-L54` (`nge_nce`): Control pass; stronger; Korean support embedded only; Priority medium. Add more contrast between endings and more dictation.
- `G8-L55` (`age_ice_ace_idge`): Control pass; very thin; Korean support embedded only; Priority medium-high. Too little practice for the pattern load.
- `G8-L56` (`ph_gh_igh`): Control pass; stronger; Korean support embedded only; Priority medium-high. Strong `f_p` potential, but no learner contrast work.

### Group 9

- `G9-L57` (`open_closed_syllable`): Control pass; stronger; Korean support embedded only; Priority medium. Good concept strand; add more sentence-level transfer and syllable marking tasks.
- `G9-L58` (`prefixes_un_re_pre_dis`): Control pass; very thin; Korean support embedded only; Priority medium-high. Morphology idea is good, but practice volume is too low for durable transfer.
- `G9-L59` (`suffix_ed`): Control pass; stronger; Korean support some contrast; Priority medium. One of the better later lessons; still needs more independent generation and dictation.
- `G9-L60` (`suffix_ing_er_est`): Control pass; stronger; Korean support embedded only; Priority medium. Add spelling-change sorting and sentence-combining work.
- `G9-L61` (`suffix_ful_less_ness_ment`): Control pass; very thin; Korean support embedded only; Priority medium-high. Too much concept load for too little practice.
- `G9-L62` (`compound_words`): Control pass; stronger; Korean support embedded only; Priority medium. Add word-splitting and generation tasks.
- `G9-L63` (`y_ee_multisyllable`): Control pass; thin; Korean support some contrast; Priority medium. Better than many because it includes some contrast work; still thin in reader/close.
- `G9-L64` (`y_ee_multisyllable`): Control pass; thin; Korean support some contrast; Priority medium. Similar to `G9-L63`; expand transfer and dictation.
- `G9-L65` (`ou_ough_variants`): Control pass; very thin; Korean support embedded only; Priority medium-high. Pattern complexity is high, but practice density is low.
- `G9-L66` (`ou_ough_variants`): Control pass; thin; Korean support some contrast; Priority medium. Keep the contrast work, but increase reader and generation volume.
- `G9-L67` (`schwa`): Control pass; stronger; Korean support embedded only; Priority medium. Good target choice, but schwa needs more oral/written transfer.

### Group 10

- `G10-L68` (`latin_roots`): Control pass; very thin; Korean support embedded only; Priority medium-high. Important morphology content, but too little repetition and generative writing.
- `G10-L69` (`greek_roots`): Control pass; very thin; Korean support embedded only; Priority medium-high. Add explicit root sorting, semantic mapping, and sentence generation.
- `G10-L70` (`morphological_families`): Control pass; very thin; Korean support embedded only; Priority medium-high. Add word-building ladders and sentence-combining tasks.
- `G10-L71` (`y_ee_programme_review`): Control pass; very thin; Korean support embedded only; Priority medium-high. The final review needs more cumulative reading, dictation, and generative application.

## Highest-Priority Fix List

1. Metadata cleanup
   - `G1-L1`
   - `G8-L51`

2. Early double-control repairs
   - `G2-L5`
   - `G2-L6`
   - `G2-L8`
   - `G2-L10`
   - `G2-L11`
   - `G3-L14`
   - `G3-L15`
   - `G3-L16`

3. Dedicated Korean-interference lesson band
   - after `G2-L8`
   - around `G3-L15`
   - before `G8-L44` to `G8-L50`

4. Structural expansion targets
   - all lessons: expand Blocks `07`, `09`, `10`
   - especially `G1-L1` to `G2-L11`, `G8-L44` to `G8-L55`, `G9-L58`, `G9-L61`, `G9-L65`, `G10-L68` to `G10-L71`

## Recommended Minimum Structural Standard Per Lesson

- Block `06`: at least 3-4 sentence slides
- Block `07`: 1 reader slide plus 2 reread / fluency passes
- Block `08`: add phrase or sentence dictation by mid-program
- Block `09`: include explicit noticing, morpheme mapping, or sentence combining
- Block `10`: include one oral recall, one transfer response, and one generative sentence

