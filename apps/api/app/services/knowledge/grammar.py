import re

from app.services.knowledge.layout import SourceBlock
from app.services.knowledge.types import GrammarRecord, SentenceRecord, SourceRef
from app.services.normalization import normalize_korean_key

_GRAMMAR = re.compile(r"^\s*GRAMMAR\s*:\s*(?P<pattern>[^|]+?)(?:\s*\|\|\s*(?P<explanation>.*))?$", re.I)
_EXAMPLE = re.compile(r"^\s*EXAMPLE\s*:\s*(?P<ko>[^|]+?)(?:\s*\|\|\s*(?P<vi>.*))?$", re.I)
_KOREAN = re.compile(r"[\uac00-\ud7a3]")
_LATIN = re.compile(r"[A-Za-zÀ-ỹ]")


def _real_pattern_candidate(text: str) -> bool:
    normalized = " ".join(text.split())
    return (
        len(normalized) <= 60
        and _KOREAN.search(normalized) is not None
        and (normalized.startswith("-") or normalized == "에 따라")
    )


def normalize_pattern(text: str) -> str:
    return normalize_korean_key(text)


def extract_grammar(blocks: list[SourceBlock]) -> tuple[list[GrammarRecord], list[SentenceRecord]]:
    grammar: list[GrammarRecord] = []
    examples: list[SentenceRecord] = []
    active_index: int | None = None
    for block in blocks:
        match = _GRAMMAR.match(block.text)
        if match:
            pattern = match.group("pattern").strip()
            if not pattern:
                active_index = None
                continue
            grammar.append(GrammarRecord(
                source=SourceRef(block.page_number, block.printed_page_number, block.block_index),
                pattern=pattern,
                normalized_pattern=normalize_pattern(pattern),
                explanation_vi=(match.group("explanation") or "").strip() or None,
            ))
            active_index = len(grammar) - 1
            continue
        example = _EXAMPLE.match(block.text)
        if example and active_index is not None:
            local_id = f"sentence-{len(examples) + 1}"
            examples.append(SentenceRecord(
                source=SourceRef(block.page_number, block.printed_page_number, block.block_index),
                local_id=local_id,
                text_ko=example.group("ko").strip(),
                text_vi=(example.group("vi") or "").strip() or None,
                grammar_patterns=[grammar[active_index].normalized_pattern],
            ))
            grammar[active_index] = GrammarRecord(
                **{
                    **grammar[active_index].__dict__,
                    "example_ids": [*grammar[active_index].example_ids, local_id],
                }
            )
    if grammar:
        return grammar, examples

    candidates = [
        index for index, block in enumerate(blocks)
        if _real_pattern_candidate(block.text)
        and block.bbox[0] < block.page_width * 0.18
        and block.bbox[2] - block.bbox[0] < block.page_width * 0.45
    ]
    for candidate_index, block_index in enumerate(candidates):
        block = blocks[block_index]
        next_index = candidates[candidate_index + 1] if candidate_index + 1 < len(candidates) else len(blocks)
        window = [
            item for item in blocks[block_index + 1:next_index]
            if item.page_number == block.page_number
        ]
        explanation_parts: list[str] = []
        example_ids: list[str] = []
        for item in window:
            text = " ".join(item.text.split())
            korean_count = len(_KOREAN.findall(text))
            latin_count = len(_LATIN.findall(text))
            if latin_count > korean_count and len(text) >= 20 and not explanation_parts:
                explanation_parts.append(text)
                continue
            if (
                korean_count >= 4
                and text.endswith((".", "?", "요", "요."))
                and len(text) <= 180
                and not text.startswith(("현재", "동사", "형용사", "이다"))
            ):
                sentence_text = re.sub(r"^[AB]\s+", "", text)
                local_id = f"sentence-{len(examples) + 1}"
                examples.append(SentenceRecord(
                    source=SourceRef(item.page_number, item.printed_page_number, item.block_index),
                    local_id=local_id,
                    text_ko=sentence_text,
                    grammar_patterns=[normalize_pattern(block.text)],
                ))
                example_ids.append(local_id)
        grammar.append(GrammarRecord(
            source=SourceRef(block.page_number, block.printed_page_number, block.block_index),
            pattern=" ".join(block.text.split()),
            normalized_pattern=normalize_pattern(block.text),
            explanation_vi=" ".join(explanation_parts) or None,
            example_ids=example_ids,
        ))
    return grammar, examples
