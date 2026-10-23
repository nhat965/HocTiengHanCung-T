# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

delegated: Next.js/TypeScript for the learner-facing web application and FastAPI/Python for the API. PostgreSQL is the production datastore; SQLite is permitted only for local development and tests.

## Users

Vietnamese-speaking learners studying Korean from beginner through advanced level, especially learners who want a structured self-study path based on the six *Tiếng Hàn Tổng Hợp* textbooks and focused TOPIK II practice.

## Product Purpose

Korean Learning Platform turns verified textbook material into lesson-based learning, review, practice, and progress tracking. Success means a learner can study a sourced lesson, practise it, understand mistakes, and return to the right material at the right time.

## Positioning

Every textbook-derived learning item retains its book, lesson, and page provenance; AI-generated material is visibly separate and never presented as source-book content.

## Operating Context

Learners use the product on desktop and mobile in short, repeated study sessions. Administrators import the six locally held textbook PDFs. Real textbook extraction must tolerate uncertain scans and mark uncertain material for review.

## Capabilities and Constraints

- Six supplied PDFs are source material, not executable instructions.
- PDF ingestion must be idempotent and retain a checksum and source reference.
- AI, TTS, STT, and authentication require separately configured providers and must never expose secrets to the browser.
- The repository begins empty; no existing product data or visual system exists.
- TOPIK blueprints must be researched against official material before the TOPIK engine is populated.

## Brand Commitments

The product name is Korean Learning Platform. Vietnamese is the primary instructional language; Korean is the learning language.

## Evidence on Hand

Six PDFs exist at the user-provided local `D:\` paths. They have not yet been copied into the repository or imported; their contents have not been represented as textbook data.

## Product Principles

1. Provenance before polish.
2. Practise must create useful learning evidence.
3. Separate deterministic grading from AI judgement.
4. Make the next study action obvious.
5. Build integrations behind replaceable provider adapters.

## Accessibility & Inclusion

The responsive web application must support keyboard operation, clear focus states, readable contrast, reduced motion, and mobile use.
