"""Conservative reconstruction for textbook layouts without fixture markers.

The extractor represents an exercise group as a parent ``Exercise`` row and
questions as children. A numbered instruction is not a question by itself;
only a child marker or a sufficiently explicit standalone prompt becomes a
question. Every emitted row and option keeps the source block that produced it.
"""
from __future__ import annotations

import re

from app.services.knowledge.activities import (
    normalize_exercise_type,
    option_index,
    parse_inline_options,
)
from app.services.knowledge.layout import SourceBlock
from app.services.knowledge.types import (
    DialogueTurnRecord,
    ExerciseOptionRecord,
    ExerciseRecord,
    PassageRecord,
    SourceRef,
)
from app.services.normalization import normalize_identifier, normalize_track_id

_KOREAN = re.compile(r"[\uac00-\ud7a3]")
_TRACK = re.compile(r"\bCD\s*(\d+)\s*TRACK\s*(\d+)\b", re.I)
_GROUP_OR_QUESTION = re.compile(r"^\s*(?P<number>\d{1,2})[.)]?\s+(?P<text>.+)$", re.S)
_CHILD = re.compile(r"^\s*[\(\[](?P<number>\d{1,2})[\)\]]\s*(?P<text>.+)$", re.S)
_OPTION = re.compile(
    r"^\s*(?:OPTION\s*[:：]\s*|(?:\((?P<paren>[A-Da-d]|[①②③④⑤⑥⑦⑧⑨⑩]|[ⓐⓑⓒⓓ])\)|"
    r"(?P<bare>[A-Da-d]|[①②③④⑤⑥⑦⑧⑨⑩]|[ⓐⓑⓒⓓ])[.)。：：]?\s+))(?P<text>.+)$",
    re.I,
)
_SPEAKER = re.compile(
    r"^\s*(?P<speaker>A|B)(?:\s*[:：]\s*|\s+)(?P<text>[\uac00-\ud7a3].*)$"
)
_SECTION_LABELS = {
    "기본 어휘": "vocabulary",
    "기본 문법": "grammar",
    "말하기": "speaking",
    "듣기": "listening",
    "읽기": "reading",
    "쓰기": "writing",
    "문화": "culture",
}
_INSTRUCTION_HINTS = (
    "고르", "답하", "보십시오", "보세요", "쓰", "연결", "순서", "빈칸",
    "읽고", "듣고", "말해", "완성", "알맞", "선택", "choose", "fill",
    "match", "order", "write", "answer",
)


def _source(block: SourceBlock) -> SourceRef:
    return SourceRef(block.page_number, block.printed_page_number, block.block_index)


def _looks_like_prompt(text: str) -> bool:
    return len(text) >= 8 and len(_KOREAN.findall(text)) >= 2


def _looks_like_instruction(text: str) -> bool:
    folded = text.casefold()
    return _looks_like_prompt(text) and any(token in folded for token in _INSTRUCTION_HINTS)


def _append_option(
    exercises: list[ExerciseRecord],
    index: int,
    block: SourceBlock,
    label: str | None,
    text: str,
) -> None:
    current = exercises[index]
    option = ExerciseOptionRecord(
        source=_source(block),
        option_index=option_index(label, len(current.options) + 1),
        text=text.strip(),
    )
    exercises[index] = ExerciseRecord(**{
        **current.__dict__,
        "options": [*current.options, option],
        "exercise_type": normalize_exercise_type(
            current.exercise_type, instruction=current.instruction, options=True,
        ),
    })


def extract_real_layout(
    blocks: list[SourceBlock],
) -> tuple[list[DialogueTurnRecord], list[PassageRecord], list[ExerciseRecord]]:
    dialogues: list[DialogueTurnRecord] = []
    passages: list[PassageRecord] = []
    exercises: list[ExerciseRecord] = []
    active_section: str | None = None
    active_group: str | None = None
    active_question_index: int | None = None
    active_track: str | None = None
    passage_blocks: dict[tuple[str, int], list[SourceBlock]] = {}
    dialogue_group: str | None = None
    dialogue_turn_index = 0
    pending_speaker: tuple[str, SourceBlock] | None = None

    for block in blocks:
        text = " ".join(block.text.replace("\x07", " ").split())
        if not text:
            continue
        if text in _SECTION_LABELS:
            active_section = _SECTION_LABELS[text]
            active_group = None
            active_question_index = None
            active_track = None
            dialogue_group = None
            pending_speaker = None
            continue

        if active_section in {"reading", "culture"}:
            korean_count = len(_KOREAN.findall(text))
            if korean_count >= 30 and len(text) >= 90 and not _CHILD.match(text):
                passage_blocks.setdefault((active_section, block.page_number), []).append(block)

        speaker = _SPEAKER.match(text)
        if active_section in {"grammar", "speaking"} and speaker:
            speaker_name = speaker.group("speaker")
            turn_text = speaker.group("text").strip()
            if not turn_text or not _KOREAN.search(turn_text):
                pending_speaker = None
                continue
            if dialogue_group is None or (speaker_name == "A" and dialogue_turn_index >= 2):
                dialogue_group = f"{active_section}-p{block.page_number}-d{len(dialogues) + 1}"
                dialogue_turn_index = 0
            dialogues.append(DialogueTurnRecord(
                source=_source(block), local_id=f"turn-{len(dialogues) + 1}",
                group_id=dialogue_group, turn_index=dialogue_turn_index,
                speaker=speaker_name, text_ko=turn_text,
            ))
            dialogue_turn_index += 1
            pending_speaker = None
            continue
        if pending_speaker and _KOREAN.search(text):
            speaker_name, speaker_block = pending_speaker
            if dialogue_group is None or (speaker_name == "A" and dialogue_turn_index >= 2):
                dialogue_group = f"{active_section}-p{block.page_number}-d{len(dialogues) + 1}"
                dialogue_turn_index = 0
            dialogues.append(DialogueTurnRecord(
                source=_source(speaker_block), local_id=f"turn-{len(dialogues) + 1}",
                group_id=dialogue_group, turn_index=dialogue_turn_index,
                speaker=speaker_name, text_ko=text,
            ))
            dialogue_turn_index += 1
            pending_speaker = None
            continue

        if active_section not in {"speaking", "listening", "reading", "writing", "culture"}:
            continue
        track_match = _TRACK.search(text)
        if track_match:
            active_track = normalize_track_id(f"CD{track_match.group(1)}TRACK{track_match.group(2)}")

        option = _OPTION.match(text)
        if option and active_question_index is not None:
            _append_option(
                exercises,
                active_question_index,
                block,
                option.group("paren") or option.group("bare"),
                option.group("text"),
            )
            continue

        child = _CHILD.match(text)
        numbered = _GROUP_OR_QUESTION.match(text)
        if child and _looks_like_prompt(child.group("text")):
            number = child.group("number")
            prompt = child.group("text").strip()
            if active_group is None:
                active_group = normalize_identifier(f"{active_section}-p{block.page_number}-g{number}")
                exercises.append(ExerciseRecord(
                    source=_source(block), local_id=active_group, group_id=active_group,
                    exercise_type="unknown", prompt="",
                ))
            prompt, inline_options = parse_inline_options(prompt, _source(block))
            active_question_index = len(exercises)
            exercises.append(ExerciseRecord(
                source=_source(block), local_id=f"{active_group}.q{number}",
                group_id=active_group, parent_id=active_group,
                exercise_type=normalize_exercise_type(
                    None, section=active_section, options=bool(inline_options),
                    listening_track=active_track,
                ),
                prompt=prompt, options=inline_options,
                listening_track_id=active_track,
            ))
            continue

        if not numbered or not _looks_like_prompt(numbered.group("text")):
            continue
        number = numbered.group("number")
        prompt = numbered.group("text").strip()
        prompt, inline_options = parse_inline_options(prompt, _source(block))
        if _looks_like_instruction(prompt) and not inline_options:
            active_group = normalize_identifier(f"{active_section}-p{block.page_number}-g{number}")
            active_question_index = None
            exercises.append(ExerciseRecord(
                source=_source(block), local_id=active_group, group_id=active_group,
                exercise_type=normalize_exercise_type(
                    None, instruction=prompt, section=active_section,
                    listening_track=active_track,
                ),
                instruction=prompt, prompt=prompt,
            ))
            continue

        if active_group is not None:
            parent_id = active_group
            local_id = f"{active_group}.q{number}"
        else:
            active_group = normalize_identifier(f"{active_section}-p{block.page_number}-q{number}")
            parent_id = None
            local_id = active_group
        active_question_index = len(exercises)
        exercises.append(ExerciseRecord(
            source=_source(block), local_id=local_id, group_id=active_group,
            parent_id=parent_id,
            exercise_type=normalize_exercise_type(
                None, section=active_section, options=bool(inline_options),
                listening_track=active_track,
            ),
            prompt=prompt, options=inline_options,
            listening_track_id=active_track,
        ))

    for (section, page_number), items in passage_blocks.items():
        first = items[0]
        passages.append(PassageRecord(
            source=_source(first),
            local_id=f"{section}-p{page_number}",
            title=None,
            paragraphs=[" ".join(item.text.split()) for item in items],
        ))
    return dialogues, passages, exercises
