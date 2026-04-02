# Strict Validator Spec

## Purpose

Define a strict, machine-enforceable validator for lesson content so that:

- no decodable word appears before all of its grapheme units are taught
- no "sight word" is silently treated as decodable
- every student-facing word can be audited from JSON alone
- lessons can fail fast during `load_lesson()` instead of being reviewed manually after the fact

This spec is designed to fit the current repo structure:

- structural validation already exists in [app/services/block_validator.py](/Users/tanioramotu/luminos-engine/app/services/block_validator.py)
- payload-shape validation already exists in [app/services/slide_payload_validator.py](/Users/tanioramotu/luminos-engine/app/services/slide_payload_validator.py)
- lesson loading already passes through [app/services/lesson_service.py](/Users/tanioramotu/luminos-engine/app/services/lesson_service.py)
- there is already a loose reader-vocabulary audit script in [scripts/audit_reader_vocab.py](/Users/tanioramotu/luminos-engine/scripts/audit_reader_vocab.py)

## Non-Negotiable Rule

For every student-facing token in Blocks `04`, `05`, `06`, `07`, `08`, `09`, and `10`:

- if the token is marked `decodable`, every grapheme unit in that token must already be taught, or be introduced earlier in the same lesson before the token appears
- if the token is marked `sight`, it must be explicitly declared as an approved sight word
- if a token is neither fully decodable nor explicitly sight, validation fails

This is stricter than the current heuristic scripts. That is intentional.

## Validation Layers

### Layer 1: Existing Structural Validation

Keep the existing checks:

- block order
- block labels
- allowed `view_type` by block
- payload schema validity

No changes needed here except composing the new validator into the same path.

### Layer 2: Required Metadata Validation

The following lesson-level fields must be present and valid:

- `lesson_id`
- `unit_id`
- `target_pattern`
- `title`
- `korean_interference_active`
- `content_pack_status`

Strict additions:

- `new_units`: list of grapheme units explicitly taught for the first time in this lesson
- `new_sight_words`: list of sight words explicitly introduced for the first time in this lesson

Rules:

- `target_pattern` must not be blank
- `new_units` must not be empty unless the lesson is explicitly marked as `review_only`
- `new_sight_words` can be empty
- every entry in `new_units` must be canonicalized to the same token format used by the validator

Example:

```json
{
  "lesson_id": "G2-L5",
  "target_pattern": "c_k",
  "new_units": ["c", "k"],
  "new_sight_words": []
}
```

For a chunk lesson:

```json
{
  "lesson_id": "G4-L21",
  "target_pattern": "sh",
  "new_units": ["sh"],
  "new_sight_words": []
}
```

For a morphology lesson:

```json
{
  "lesson_id": "G9-L58",
  "target_pattern": "prefixes_un_re_pre_dis",
  "new_units": ["un-", "re-", "pre-", "dis-"],
  "new_sight_words": []
}
```

## Canonical Unit Rules

The validator must operate on canonical units, not raw letters.

Examples of canonical units:

- single graphemes: `s`, `a`, `t`
- digraphs / trigraphs: `sh`, `th`, `ch`, `ng`, `igh`, `tion`
- vowel teams: `ai`, `ay`, `ee`, `ea`, `oa`, `ow`
- r-controlled units: `ar`, `er`, `ir`, `ur`, `or`, `air`, `ear`, `eer`
- endings and morphology chunks when taught as units: `-ed`, `-ing`, `-er`, `-est`, `-tion`, `un-`, `re-`
- silent-letter patterns when taught as units: `kn`, `wr`, `gn`

Important:

- `ck` must be represented as `ck`, not `c` + `k`, once it is treated as a single orthographic unit
- cluster lessons do not create new vowel units; they license specific consonant adjacency patterns
- a word can only be validated strictly if its student-facing representation includes machine-readable unit segmentation

## Required Student-Facing Token Inventory

Every student-facing word must be recoverable from JSON in a machine-readable way.

### For `flashcard` slides that introduce or practice words

If the word is student-facing and decodable, the slide must include one of:

- `blend_units`
- `grapheme_units`

Required:

- every displayed decodable word in Block `04`
- every `Reader Prep` word

### For `drag_letter` and `writing_encoding`

Required:

- `target_word`
- `expected_answer`
- `grapheme_units`

### For `read_respond`

Required:

- `text_content`
- `word_types`
- `token_units`

`token_units` is a new required field for strict mode.

Example:

```json
{
  "text_content": "I sat.",
  "word_types": {
    "I": "sight",
    "sat": "decodable"
  },
  "token_units": {
    "I": ["I"],
    "sat": ["s", "a", "t"]
  }
}
```

For later lessons:

```json
{
  "text_content": "The action is in this section.",
  "word_types": {
    "The": "sight",
    "action": "decodable",
    "is": "sight",
    "in": "sight",
    "this": "sight",
    "section": "decodable"
  },
  "token_units": {
    "The": ["The"],
    "action": ["act", "tion"],
    "is": ["is"],
    "in": ["in"],
    "this": ["this"],
    "section": ["sect", "ion"]
  }
}
```

Without `token_units`, strict validation is not possible for running text.

## Allowed Token Classes

Each student-facing token must be one of:

- `decodable`
- `sight`
- `teacher_only`

Rules:

- `teacher_only` tokens cannot appear in student-facing reading text
- punctuation is ignored for validation
- case is normalized for matching, except reporting should preserve original case

## Cumulative Teaching Inventory

The validator must compute a cumulative inventory in lesson order.

For lesson `L`:

- `allowed_units_before_lesson` = all `new_units` from prior lessons
- `allowed_sight_before_lesson` = all `new_sight_words` from prior lessons

Within a lesson:

- Blocks `01` and `02` can only use prior inventory
- Block `03` introduces `new_units`
- Blocks `04` to `10` can use prior inventory + current lesson `new_units` + current lesson `new_sight_words`

This matches the intended teaching flow more closely than the current loose audit.

## Block-Specific Strictness

### Blocks `01` and `02`

Strict review-only:

- no current lesson `new_units`
- no future units

### Block `03`

Introduction-only:

- may contain current lesson `new_units`
- must not silently introduce extra units beyond `new_units`

### Block `04`

Vocabulary gate:

- every student-facing decodable word must validate against allowed units
- no hidden future patterns

### Block `05`

Word-building gate:

- every `target_word` must validate
- every draggable or slot sequence must match the canonical units for that word

### Blocks `06` and `07`

Sentence / reader gate:

- every token must be either validated decodable or explicitly sight
- `word_types` and `token_units` must cover all lexical tokens in `text_content`
- no unknown tokens

### Block `08`

Encoding gate:

- dictated targets must validate against allowed units
- `grapheme_units` must exactly match the target tokenization

### Blocks `09` and `10`

Meaning / transfer gate:

- if student-facing word strings are shown, they must also validate
- prompts can contain teacher-facing language, but displayed student text must stay controlled unless explicitly marked `teacher_only`

## Sight Word Rules

Strict sight-word behavior:

- if a word is introduced as sight, it must appear in `new_sight_words`
- if a word is tagged `sight` in any slide, it must exist in the cumulative sight-word inventory
- a word cannot be tagged `decodable` in one slide and `sight` in another unless an override file explicitly authorizes the transition

This would catch the current `I` inconsistency in `G1-L1`.

## Error Codes

Implement stable validator codes.

- `DC001`: blank or missing `target_pattern`
- `DC002`: missing `new_units`
- `DC003`: missing `new_sight_words`
- `DC010`: student-facing token missing from `word_types`
- `DC011`: student-facing token missing from `token_units`
- `DC012`: token marked `decodable` but contains untaught unit
- `DC013`: token marked `sight` but not declared in cumulative sight inventory
- `DC014`: token classified inconsistently across slides
- `DC015`: slide introduces unit not declared in `new_units`
- `DC016`: review block uses current or future unit
- `DC017`: canonical unit split incorrectly, e.g. `ck` treated as `c` + `k` after `ck` is supposed to be atomic
- `DC018`: displayed word in running text cannot be reconstructed from machine-readable token metadata

## Output Contract

The strict validator should produce machine-readable failures.

Example shape:

```json
{
  "lesson_id": "G2-L8",
  "errors": [
    {
      "code": "DC012",
      "block_id": "04",
      "slide_id": "04-05",
      "token": "trek",
      "message": "Token uses untaught onset cluster 'tr' before explicit cluster instruction."
    }
  ],
  "warnings": []
}
```

## First Implementation

This is the first practical implementation order. Do not jump straight to perfect automated parsing; make the data model strict first.

### Phase 1: Add the missing machine-readable fields

Add to every lesson:

- `new_units`
- `new_sight_words`

Add to every `read_respond` slide:

- `token_units`

Backfill the highest-priority lessons first:

- `G1-L1`
- `G2-L5`
- `G2-L6`
- `G2-L8`
- `G2-L10`
- `G2-L11`
- `G3-L14`
- `G3-L15`
- `G3-L16`
- `G8-L51`

### Phase 2: Implement strict validator service

Add:

- `app/services/controlled_text_validator.py`

Responsibilities:

- compute cumulative unit inventory
- validate lesson-level metadata
- validate student-facing token inventories
- emit stable error codes

### Phase 3: Wire into lesson loading

Extend [app/services/lesson_service.py](/Users/tanioramotu/luminos-engine/app/services/lesson_service.py):

- after `validate_slide_payloads(lesson)`
- call `validate_controlled_text(lesson, prior_lessons_context)`

Because strict validation depends on prior lessons, add a corpus-level loader path for validation, not just single-lesson parsing.

### Phase 4: Add CLI audit

Add:

- `scripts/validate_lessons_strict.py`

Output:

- per-lesson pass/fail
- grouped error counts by code
- nonzero exit on any strict failure

This becomes the content gate for CI or release checks.

## First Implementation Constraints

The first version should not try to infer units from prose.

Do not rely on:

- `teacher_cue`
- `observation_note`
- free-text `back_text`
- `target_pattern` parsing alone

Strict validation should only trust explicit machine-readable fields.

## Recommended First Pass Success Criteria

Phase 1 is successful when:

- `G1-L1` no longer misclassifies `I`
- `G8-L51` no longer has blank metadata
- the validator correctly fails `G2-L5`, `G2-L6`, `G2-L8`, `G2-L10`, `G2-L11`, `G3-L14`, `G3-L15`, `G3-L16`
- the validator can produce clean pass/fail output across the whole corpus

## Practical Note

The current repo can support strict validation, but not with the current lesson JSON alone. The missing piece is explicit token metadata for running text. Until that exists, all "double-control" checks in readers and sentences will stay heuristic.

