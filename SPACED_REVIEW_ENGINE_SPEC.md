# Spaced Review Engine Spec

This spec defines the first version of a smart review system for `Block 01` and `Block 02`.

The goal is not to replace the existing review blocks.
The goal is to make them smarter.

## 1. Core Idea

For each class lesson, the platform should choose review content from two sources:

- `due review`
  - patterns that should return because of spacing
- `class weakness review`
  - patterns that should return because the class is still shaky on them

So the review blocks become:

- structurally fixed
- instructionally adaptive

## 2. What We Are Building

We are building a class-aware review engine, not a fully individualized live lesson engine.

That means:

- the main class lesson still runs as one shared lesson
- `Block 01` and `Block 02` are chosen for the class
- individual learners can still be flagged for extra intervention

## 3. Review Levels

### Level A: Core Class Review

Always include:

- `1` recent review target
- `1` spaced older review target

Purpose:

- maintain continuity
- support spacing even when no visible failure happened today

### Level B: Class-Risk Review

Conditionally include:

- `1` class-risk target when enough students are shaky or missed it

Purpose:

- respond to real class weakness

### Level C: Individual Follow-Up

Do not put this into the whole-class live block unless it is also a class-risk issue.

Instead:

- recommend `KI` lesson
- small-group reteach
- extra practice
- repeat lesson / partial repeat

## 4. Simple Selection Rule

For a class about to teach lesson `L`, choose:

1. `recent target`
   - from the immediately previous lesson
2. `due spaced target`
   - from roughly `3 to 5` lessons back, or the oldest overdue target
3. `class-risk target`
   - if the class threshold is crossed
4. optional `high-utility maintenance target`
   - a frequently used early pattern that should stay automatic

That gives `2 to 4` review targets for the class.

## 5. One Target Is Not One Item

A review target should appear in multiple touches.

Recommended depth:

- `light target`
  - `1 to 2` touches
- `standard target`
  - `2` touches
- `priority target`
  - `3 to 4` touches

Recommended mapping:

- `Block 01`
  - oral or flashcard review
- `Block 02`
  - encoding, discrimination, or application review

Example:

- Target `r`
  - Block 01: identify and say `/r/`
  - Block 02: write or discriminate a word with `r`

## 6. Class Thresholds

Mark a target as `class-risk` when either threshold is met:

- at least `30%` of marked learners are `shaky` or `missed`
- at least `3` learners in the class are `shaky` or `missed`

Escalate priority when:

- the same target is weak across `2 consecutive lessons`
- or Korean transfer flags recur on the same target

## 7. Data Sources

Use three existing data sources first:

- `LessonAttemptRecord`
- `SlideResultRecord`
- `StudentMarkRecord`

Use current lesson metadata:

- lesson order
- `target_pattern`
- `new_units`
- `korean_interference_active`

No new lesson JSON schema is required for phase 1.

## 8. New Data Model

Add a new review-tracking table.

Suggested model:

`ClassPatternReviewRecord`

Fields:

- `id`
- `class_id`
- `pattern_key`
- `source_lesson_id`
- `first_taught_lesson_id`
- `last_seen_lesson_id`
- `last_reviewed_lesson_id`
- `mastery_state`
  - `secure`
  - `shaky`
  - `missed`
- `times_secure`
- `times_shaky`
- `times_missed`
- `consecutive_weak_lessons`
- `korean_transfer_count`
- `next_due_lesson_number`
- `priority_score`
- `notes` optional

Purpose:

- hold class-level review state by pattern

## 9. Pattern Key

Use a normalized `pattern_key`.

Phase 1 rule:

- derive from lesson `target_pattern`

Examples:

- `r`
- `l`
- `c_k`
- `l_clusters`
- `prefixes_un_re_pre_dis`

Later versions can also track sub-patterns and confusion pairs.

## 10. Scheduling Rules

When a pattern is first taught:

- schedule it for immediate light review in the next lesson

If class mastery is:

- `secure`
  - next due in `4 to 6` lessons
- `shaky`
  - next due in `1 to 2` lessons
- `missed`
  - next due in the next lesson and flag for reteach

If Korean transfer is present:

- boost priority
- shorten spacing window

## 11. Block Mapping

### Block 01

Use for:

- flashcard recall
- oral production
- quick contrast or discrimination

### Block 02

Use for:

- encoding
- listening and write
- one stronger application item

Recommended distribution:

- recent target: Block 01
- spaced target: Block 01 or 02
- class-risk target: Block 02

## 12. Review Selection Algorithm

For class `C` and next lesson `L`:

1. Load all review records for `C`
2. Mark any pattern with `next_due_lesson_number <= current_lesson_number` as due
3. Rank due patterns by:
   - overdue amount
   - weak mastery
   - repeated weakness
   - Korean transfer count
4. Always include:
   - previous lesson target
   - top due target not equal to previous lesson target
5. If a class-risk pattern exists:
   - include it
6. Limit whole-class review to `2 to 4` targets

## 13. Output Structure

The engine should return:

- `recent_review_target`
- `due_review_targets`
- `class_risk_targets`
- `individual_follow_up_flags`

Each target should include:

- `pattern_key`
- `source_lesson_id`
- `reason`
- `priority`
- `recommended_touch_count`

## 14. Teacher Experience

The teacher should be able to see:

- why a target is in review today
- whether it is due or weak
- whether it is a Korean transfer issue

Short labels:

- `Recent review`
- `Due review`
- `Class-risk review`

## 15. Phase 1 Implementation

Phase 1 will not rewrite lesson JSON dynamically.

Instead it will:

- compute review recommendations
- show them in the platform
- let the teacher preview what should be reviewed in `Block 01/02`

Deliverables:

1. `review_scheduler_service.py`
2. `ClassPatternReviewRecord` model
3. pattern update logic after lesson completion
4. class-level review recommendation panel

## 16. Phase 2 Implementation

Phase 2 can make review content partially dynamic.

Options:

- choose from a review bank
- inject alternate review cards into `Block 01/02`
- generate class-specific review packets

## 17. Why This Design

This fits the reality of class teaching:

- whole-class live instruction stays coherent
- review becomes smarter
- individual needs are still surfaced
- the system uses existing marking data instead of inventing a separate workflow
