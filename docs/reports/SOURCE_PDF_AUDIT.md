# Source PDF audit

Audit performed locally on 2026-10-23 with PyMuPDF. The six PDFs below exist in
the workspace under `docs/`; Git reports them as untracked, so their presence
on GitHub is **not verified**. No source PDF was modified or added to a commit.

## File inventory and measurable checks

| Volume / level | Filename | Size (bytes) | SHA-256 | PDF pages | Pages with text | Pages without text | Korean characters | Vietnamese characters | Pages with images | Pages with detected tables |
|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 1 / sơ cấp | `[Tailieuvui.com]_giao-trinh-tieng-han-tong-hop-so-cap-1-pdf.pdf` | 120177785 | `3f7fde096c95612fa37d9c1f61fe0ba840d04de0b6494785ea97b0071846b57e` | 380 | 376 | 4 | 60474 | 1404 | 223 | 121 |
| 2 / sơ cấp | `[Tailieuvui.com]_giao-trinh-tieng-han-tong-hop-so-cap-2-pdf.pdf` | 19569983 | `fec23447c0d0dd3be37c27d689d4886a4349bfd1423a12a42841437dcb76ca1c` | 362 | 361 | 1 | 77580 | 1419 | 210 | 105 |
| 3 / trung cấp | `[Tailieuvui.com]_giao-trinh-tieng-han-tong-hop-trung-cap-3-pdf.pdf` | 70277512 | `fecf2ca5e3177cd4569755053b25f900c4cfbe26980b7890e1d18c0794e26a97` | 338 | 334 | 4 | 109920 | 1082 | 244 | 97 |
| 4 / trung cấp | `[Tailieuvui.com]_giao-trinh-tieng-han-tong-hop-trung-cap-4-pdf.pdf` | 68078922 | `82d68eb2e2c45b0b3dbaefa09092e14466584bc48d60970a92c679b9c82f05fc` | 338 | 337 | 1 | 122670 | 939 | 242 | 106 |
| 5 / cao cấp | `[Tailieuvui.com]_giao-trinh-tieng-han-tong-hop-cao-cap-5.pdf` | 63996963 | `4bee039d9aa47eea9d8a6041b62f93f7c0c4250429f3a5807c1bd398e8a142ab` | 354 | 353 | 1 | 177320 | 743 | 354 | 129 |
| 6 / cao cấp | `[Tailieuvui.com]_giao-trinh-tieng-han-tong-hop-cao-cap-6.pdf` | 59622486 | `a323eb9dadccccec24059b7e970299bf6c39cc9e0908aad5e61400df92092203` | 366 | 365 | 1 | 208979 | 674 | 366 | 92 |

All six files open as unencrypted PDFs. They contain extractable Korean and
Vietnamese text; language-character counts above are literal Unicode counts,
not an assessment of OCR or translation accuracy. PDF metadata identifies
Adobe InDesign as the creator for all six. The source metadata titles are:

| Volume | PDF metadata title |
|---:|---|
| 1 | `한국어(베트남)_1권_본책(3쇄).indb` |
| 2 | `베트남인을위한종합한국어 2_표지(본책).indd` |
| 3 | `베트남인을위한종합한국어_3권_내지(본책).indb` |
| 4 | `베트남인을 위한 종합한국어 4_내지(본책)2쇄.indb` |
| 5 | `베트남_5권_(본책)_내지.indb` |
| 6 | `베트남_6권_(본책)_내지.indb` |

## Interpretation and limitations

- `Pages with text` means PyMuPDF returned non-whitespace text. The remaining
  pages may be blank, image-only, or otherwise lack extractable text; they have
  not been visually classified.
- `Pages with detected tables` is PyMuPDF `Page.find_tables()` output. This is
  a structural candidate count, not a verified count of semantic textbook
  tables or correctly aligned cells.
- Image-page counts are based on PDF image resources. They do not mean those
  pages are scans; the PDFs also contain ordinary illustrations and page
  artwork.
- Transcript/answer search is only a keyword scan and is not evidence of
  presence, absence, or successful matching. Lesson counts and section
  completeness have not yet been audited.
- Tesseract is not installed in this environment. No OCR was run. The pipeline
  must flag uncertain/image-only regions rather than fabricate text.
- The source files were audited and one volume-4 lesson range was extracted
  locally. No complete-book or six-book structured extraction is claimed.

## Volume 4 pilot

The contents page identifies lesson 01, `유행`, at printed page 17. In the
source PDF this corresponds to PDF page 18. The bounded pilot extracted PDF
pages 18–35 (printed pages 17–34) to the local, Git-ignored file
`data/extracted/book-4/lesson-01-raw.json` and its adjacent image-assets folder.

Measured output: 18 pages, 419 text blocks, 3,735 spans, 14 detected table
candidates, 54 extracted images, and 0 pages flagged by the current OCR
heuristic. The JSON is about 1.5 MB. This pilot validates that the raw pipeline
runs on a real source range; table alignment, layout order, and content
accuracy still require visual/human review.
