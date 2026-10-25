# Task 08.1E — Exercise Extraction & Answer Linking

## Root cause

The prior marker extractor only recognized synthetic `Q...`/`OPTION` lines,
while the real-layout extractor treated nearly every numbered line in an
exercise section as a question. It also accepted a short answer key such as
`q1` without checking whether multiple groups contained a question with that
number. The pilot's 67 exercise rows therefore represented extraction records,
not 67 learner-ready questions; options and sourced answer keys were absent
because the real layout did not reconstruct them.

## Implementation

- Reconstructed real-layout exercises as `group → instruction → question → option`.
- Added conservative question/instruction heuristics and ignored page/heading
  numbers that lack question evidence.
- Added supported type normalization: `multiple_choice`, `fill_blank`,
  `matching`, `ordering`, `short_answer`, `writing`, `listening_question`, and
  `unknown`.
- Recognized explicit `OPTION:`/A–D/①–⑩/ⓐ–ⓓ labels and inline options while
  preserving source references.
- Linked answer keys only from explicit source markers. Short keys are accepted
  only when unambiguous; ambiguous keys remain unresolved.
- Preserved approved options and answer keys during re-import and updated only
  pending extracted rows.
- Learner APIs hide approved multiple-choice records without at least two
  approved options and never return `correct` or reveal an answer without an
  approved answer key.

## Files changed

- `apps/api/app/services/knowledge/activities.py`
- `apps/api/app/services/knowledge/real_layout.py`
- `apps/api/app/services/knowledge/pipeline.py`
- `apps/api/app/services/knowledge/persistence.py`
- `apps/api/app/routers/study.py`
- `apps/api/app/routers/textbooks.py`
- `apps/api/tests/test_knowledge_extractors.py`

No schema or migration was required.

## Golden fixture and expected counts

The public synthetic fixture contains six groups (multiple choice, fill blank,
matching, ordering, short answer, and a group with two child questions), seven
questions, four options on the multiple-choice question, and two unambiguous
answer keys. It also includes an ambiguous `q1` key that must remain
unresolved. A second fixture verifies that numbered group instructions are not
counted as questions and that inline/standalone options keep their order and
source block.

## Verification

- Local API tests: unavailable in this checkout because Python/PostgreSQL are
  not installed.
- Local web tests/build: `npm test -- --run` and `npm run build` passed.
- PostgreSQL 16 GitHub Actions: 37 tests passed, 1 skipped in [run 40109242474](https://github.com/nhat965/HocTiengHanCung-T/actions/runs/40109242474).
- Implementation commits: `adc87ecebbc4da74cc5b0157aa0dc04a006897c0`,
  `87adcda39f66127f6dd4abd357952a7a9179d555`,
  `0a4d9abcafd05b824eacca4a5f8fc1c3e8a891a2`,
  `2aa3714818816f601cba50ae9cf86195455a45ab`.
- Pull request: [#8](https://github.com/nhat965/HocTiengHanCung-T/pull/8)

The private Trung cấp 4 PDF is not present in this workspace. Consequently no
new real-PDF pilot counts are claimed. The previous pilot's 67 records must not
be interpreted as 67 learner-ready questions; a rerun requires the privately
authorized PDF and manual source review.

## Remaining risks

Answer-key layouts that contain only implicit ordinal lists, image-only options,
or no explicit group/question reference remain unresolved by design. They need
source-backed review or OCR in a later task; no answer is inferred.
