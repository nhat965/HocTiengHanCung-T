import re

from app.services.knowledge.layout import SourceBlock
from app.services.knowledge.types import GrammarRecord, SentenceRecord, SourceRef
from app.services.normalization import normalize_korean_key

_GRAMMAR = re.compile(r"^\s*GRAMMAR\s*:\s*(?P<pattern>[^|]+?)(?:\s*\|\|\s*(?P<explanation>.*))?$", re.I)
_EXAMPLE = re.compile(r"^\s*EXAMPLE\s*:\s*(?P<ko>[^|]+?)(?:\s*\|\|\s*(?P<vi>.*))?$", re.I)


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
    return grammar, examples
