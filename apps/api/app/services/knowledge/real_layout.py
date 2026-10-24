"""Conservative extraction rules for visually structured Korean textbooks.

These rules emit review candidates only. They never infer missing answers or
translations and keep every record tied to the exact source block.
"""
from __future__ import annotations

import re

from app.services.knowledge.layout import SourceBlock
from app.services.knowledge.types import (
    DialogueTurnRecord, ExerciseOptionRecord, ExerciseRecord, PassageRecord,
    SourceRef,
)
from app.services.normalization import normalize_identifier, normalize_track_id

_KOREAN = re.compile(r"[\uac00-\ud7a3]")
_TRACK = re.compile(r"\bCD\s*(\d+)\s*TRACK\s*(\d+)\b", re.I)
_QUESTION = re.compile(r"^\s*(?:\((?P<child>\d+)\)|(?P<group>\d+)\s+)(?P<text>.+)$", re.S)
_OPTION = re.compile(r"[ⓐⓑⓒⓓ]\s*([^ⓐⓑⓒⓓ]+)")
_SPEAKER = re.compile(r"^\s*(?P<speaker>A|B)\s*(?P<text>.*)$")
_SECTION_LABELS = {
    "기본 어휘": "vocabulary",
    "기본 문법": "grammar",
    "말하기": "speaking",
    "듣기": "listening",
    "읽기": "reading",
    "쓰기": "writing",
    "문화": "culture",
}


def _source(block: SourceBlock) -> SourceRef:
    return SourceRef(block.page_number, block.printed_page_number, block.block_index)


def extract_real_layout(
    blocks: list[SourceBlock],
) -> tuple[list[DialogueTurnRecord], list[PassageRecord], list[ExerciseRecord]]:
    dialogues: list[DialogueTurnRecord] = []
    passages: list[PassageRecord] = []
    exercises: list[ExerciseRecord] = []
    active_section: str | None = None
    active_group: str | None = None
    active_track: str | None = None
    passage_blocks: dict[tuple[str, int], list[SourceBlock]] = {}
    dialogue_group: str | None = None
    dialogue_turn_index = 0
    pending_speaker: tuple[str, SourceBlock] | None = None

    for block in blocks:
        text = " ".join(block.text.replace("\x07", " ").split())
        if text in _SECTION_LABELS:
            active_section = _SECTION_LABELS[text]
            active_group = None
            active_track = None
            dialogue_group = None
            pending_speaker = None
            continue

        if active_section in {"reading", "culture"}:
            korean_count = len(_KOREAN.findall(text))
            if korean_count >= 30 and len(text) >= 90 and not _QUESTION.match(text):
                passage_blocks.setdefault((active_section, block.page_number), []).append(block)

        speaker = _SPEAKER.match(text)
        if active_section in {"grammar", "speaking"} and speaker:
            speaker_name = speaker.group("speaker")
            turn_text = speaker.group("text").strip()
            if not turn_text:
                pending_speaker = (speaker_name, block)
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
        match = _QUESTION.match(text)
        if not match:
            continue
        prompt = match.group("text").strip()
        if len(prompt) < 5 or len(_KOREAN.findall(prompt)) < 2:
            continue
        track_match = _TRACK.search(text)
        if track_match:
            active_track = normalize_track_id(f"CD{track_match.group(1)}TRACK{track_match.group(2)}")
        options = [
            ExerciseOptionRecord(
                source=_source(block), option_index=index + 1, text=value.strip(),
            )
            for index, value in enumerate(_OPTION.findall(prompt))
            if value.strip()
        ]
        clean_prompt = _OPTION.sub("", prompt).strip()
        if match.group("group"):
            active_group = normalize_identifier(f"{active_section}-p{block.page_number}-g{match.group('group')}")
            local_id = active_group
            parent_id = None
        else:
            active_group = active_group or normalize_identifier(f"{active_section}-p{block.page_number}")
            local_id = f"{active_group}.q{match.group('child')}"
            parent_id = active_group
        if "○" in prompt and "×" in prompt:
            exercise_type = "true_false"
        elif options:
            exercise_type = "multiple_choice"
        elif active_section == "writing":
            exercise_type = "writing_prompt"
        elif active_section == "speaking":
            exercise_type = "speaking_prompt"
        else:
            exercise_type = "short_answer"
        exercises.append(ExerciseRecord(
            source=_source(block), local_id=local_id, group_id=active_group,
            parent_id=parent_id, exercise_type=exercise_type,
            prompt=clean_prompt, options=options,
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
