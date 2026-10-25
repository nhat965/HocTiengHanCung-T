# Six-volume source lesson index

This index is a metadata audit of the six private PDFs in `docs/`. It is not a
published copy of the textbooks and does not replace page-level human review.
The TOC was read directly from the local PDFs; the deterministic title regex
was used only as a candidate detector and its false positives around appendices
were excluded from this index.

| Volume | PDF pages | TOC pages | Lessons in TOC | TOC lesson-start pages (printed) | Appendix markers |
|---|---:|---:|---:|---|---|
| Sơ cấp 1 | 380 | 14–15 | 15 | 19, 31, 51, 71, 91, 111, 131, 151, 171, 191, 211, 231, 251, 271, 291 | Phụ lục / audio 311; answers 332; new words 346 |
| Sơ cấp 2 | 362 | 13–14 | 15 | 13, 33, 53, 73, 93, 113, 133, 153, 173, 193, 213, 233, 253, 273, 293 | Audio 297; answers 318; new words 332 |
| Trung cấp 3 | 338 | 13–14 | 15 | 17, 35, 53, 71, 89, 107, 125, 143, 161, 179, 197, 215, 233, 251, 269 | Audio 288; answers 302; culture 316; new words 324 |
| Trung cấp 4 | 338 | 13–14 | 15 | 17, 35, 53, 71, 89, 107, 125, 143, 161, 179, 197, 215, 233, 251, 269 | Audio 288; answers 303; culture 317; new words 324 |
| Cao cấp 5 | 354 | 13–16 | 15 | 13, 35, 53, 71, 89, 107, 125, 143, 161, 179, 198, 216, 234, 252, 270 | Contents/appendix pages require visual boundary review |
| Cao cấp 6 | 366 | 13–16 | 15 | 17, 35, 53, 71, 89, 107, 125, 143, 161, 179, 198, 216, 234, 252, 270 | Contents/appendix pages require visual boundary review |

## Boundary notes

- The TOC is reliable for lesson ordering and titles, but its printed page
  numbers do not always equal the PDF page number. Sơ cấp 1, for example, has
  a long Hangeul introduction before the first lesson. A production import must
  use the PDF page number recorded in `SourcePage`, not the printed TOC number.
- The intermediate-4 pilot is the only lesson boundary currently validated at
  page level: lesson 01 starts at PDF page 18 and ends at PDF page 35 (printed
  pages 17–34).
- Appendix pages are deliberately excluded from lesson segmentation. Answers,
  transcripts and audio metadata must be matched by source span; a keyword hit
  is not evidence that a match succeeded.
- The supplied six files contain extractable text. The source audit records
  pages without text, image counts, table candidates and SHA-256 values in
  [`SOURCE_PDF_AUDIT.md`](SOURCE_PDF_AUDIT.md). OCR remains unresolved for any
  image-only region.

## Import status

Only Trung cấp 4, Bài 01 is imported into the private pilot database. The other
books remain metadata-only until the pilot review, rights boundary and a real
PostgreSQL run are accepted. No PDF, raw page transcript or bulk textbook data
is committed to the repository.
