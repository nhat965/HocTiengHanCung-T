import re

from app.services.knowledge.layout import SourceBlock
from app.services.knowledge.types import (
    DialogueTurnRecord,
    ExerciseOptionRecord,
    ExerciseRecord,
    ListeningTrackRecord,
    PassageRecord,
    SourceRef,
    TranscriptRecord,
)
from app.services.normalization import normalize_track_id

_DIALOGUE = re.compile(r"^\s*DIALOGUE(?:\[(?P<id>[\w.-]+)\])?\s*:\s*(?P<topic>.*)$", re.I)
_TURN = re.compile(r"^\s*(?P<speaker>[^:|]+)\s*:\s*(?P<ko>[^|]+?)(?:\s*\|\|\s*(?P<vi>.*))?$")
_READING = re.compile(r"^\s*READING(?:\[(?P<id>[\w.-]+)\])?\s*:\s*(?P<title>.*)$", re.I)
_PARAGRAPH = re.compile(r"^\s*PARAGRAPH\s*:\s*(?P<text>.*)$", re.I)
_EXERCISE = re.compile(r"^\s*EXERCISE\[(?P<id>[\w.-]+)\]\s*:\s*(?P<kind>[\w-]+)(?:\s*\|\|\s*(?P<instruction>.*))?$", re.I)
_QUESTION = re.compile(r"^\s*Q(?P<id>[\w.-]+)\s*:\s*(?P<prompt>.*)$", re.I)
_OPTION = re.compile(
    r"^\s*(?:OPTION\s*[:：]\s*|(?:\((?P<paren>[A-Da-d1-9]|[①②③④⑤⑥⑦⑧⑨⑩]|[ⓐⓑⓒⓓ])\)|"
    r"(?P<bare>[A-Da-d]|[①②③④⑤⑥⑦⑧⑨⑩]|[ⓐⓑⓒⓓ])[.)。：：]?\s+))(?P<text>.+)$",
    re.I,
)
_ANSWER = re.compile(r"^\s*ANSWER\[(?P<id>[\w.-]+)\]\s*:\s*(?P<answer>.*)$", re.I)
_TRACK = re.compile(r"\bCD\s*(?P<disc>\d+)\s*TRACK\s*(?P<track>\d+)\b", re.I)
_TRANSCRIPT = re.compile(r"^\s*TRANSCRIPT\[(?P<track>[^\]]+)\]\s*:\s*(?P<text>.*)$", re.I)

_TYPE_ALIASES = {
    "multiplechoice": "multiple_choice",
    "multiple-choice": "multiple_choice",
    "mcq": "multiple_choice",
    "single_choice": "multiple_choice",
    "fill": "fill_blank",
    "fill-in": "fill_blank",
    "fill_in": "fill_blank",
    "matching": "matching",
    "match": "matching",
    "ordering": "ordering",
    "order": "ordering",
    "short-answer": "short_answer",
    "free_response": "short_answer",
    "writing_prompt": "writing",
    "listening": "listening_question",
}
_SUPPORTED_TYPES = {
    "multiple_choice", "fill_blank", "matching", "ordering", "short_answer",
    "writing", "listening_question", "unknown",
}


def normalize_exercise_type(
    kind: str | None,
    *,
    instruction: str | None = None,
    options: bool = False,
    section: str | None = None,
    listening_track: str | None = None,
) -> str:
    """Return only a supported type when the source provides enough evidence."""
    raw = re.sub(r"\s+", "_", (kind or "").strip().casefold())
    normalized = _TYPE_ALIASES.get(raw, raw)
    if normalized in _SUPPORTED_TYPES and normalized != "unknown":
        return normalized
    instruction_text = (instruction or "").casefold()
    if listening_track or section == "listening":
        return "listening_question"
    if options:
        return "multiple_choice"
    if any(token in instruction_text for token in ("빈칸", "fill", "điền")):
        return "fill_blank"
    if any(token in instruction_text for token in ("연결", "matching", "nối")):
        return "matching"
    if any(token in instruction_text for token in ("순서", "ordering", "sắp xếp")):
        return "ordering"
    if section == "writing":
        return "writing"
    if normalized in _SUPPORTED_TYPES:
        return normalized
    return "unknown"


_CIRCLED_DIGITS = "①②③④⑤⑥⑦⑧⑨⑩"
_CIRCLED_LETTERS = "ⓐⓑⓒⓓ"


def option_index(label: str | None, fallback: int) -> int:
    if not label:
        return fallback
    normalized = label.casefold()
    if normalized in _CIRCLED_DIGITS:
        return _CIRCLED_DIGITS.index(normalized) + 1
    if normalized in _CIRCLED_LETTERS:
        return _CIRCLED_LETTERS.index(normalized) + 1
    if normalized.isdigit():
        return int(normalized)
    if normalized.isalpha() and "a" <= normalized <= "z":
        return ord(normalized) - ord("a") + 1
    return fallback


def parse_inline_options(text: str, source: SourceRef) -> tuple[str, list[ExerciseOptionRecord]]:
    """Split explicit option labels from a question prompt without guessing."""
    pattern = re.compile(
        rf"(?P<label>[A-Da-d]|[{_CIRCLED_DIGITS}{_CIRCLED_LETTERS}])\s*[.)。：：]?\s*"
        rf"(?P<text>[^A-Da-d{_CIRCLED_DIGITS}{_CIRCLED_LETTERS}]+?)(?=(?:[A-Da-d]|[{_CIRCLED_DIGITS}{_CIRCLED_LETTERS}])\s*[.)。：：]?\s|$)",
    )
    matches = list(pattern.finditer(text))
    if len(matches) < 2:
        return text, []
    options = [
        ExerciseOptionRecord(
            source=source,
            option_index=option_index(match.group("label"), index + 1),
            text=match.group("text").strip(),
        )
        for index, match in enumerate(matches)
        if match.group("text").strip()
    ]
    prompt = text[:matches[0].start()].strip()
    return prompt, options


def extract_activities(
    blocks: list[SourceBlock],
) -> tuple[
    list[DialogueTurnRecord],
    list[PassageRecord],
    list[ExerciseRecord],
    list[ListeningTrackRecord],
    list[TranscriptRecord],
]:
    turns: list[DialogueTurnRecord] = []
    passages: list[PassageRecord] = []
    exercises: list[ExerciseRecord] = []
    tracks: list[ListeningTrackRecord] = []
    transcripts: list[TranscriptRecord] = []
    active_dialogue: str | None = None
    active_passage: int | None = None
    active_exercise: int | None = None
    question_index_by_group: dict[str, int] = {}
    exercise_index_by_id: dict[str, int] = {}
    answers: dict[str, tuple[str, SourceRef]] = {}
    track_ids: set[str] = set()

    for block in blocks:
        text = block.text.strip()
        source = SourceRef(block.page_number, block.printed_page_number, block.block_index)
        reading = _READING.match(text)
        if reading:
            active_passage = len(passages)
            passages.append(PassageRecord(
                source=source,
                local_id=reading.group("id") or f"passage-{active_passage + 1}",
                title=reading.group("title").strip() or None,
            ))
            active_dialogue = None
            active_exercise = None
            continue
        if _EXERCISE.match(text):
            active_dialogue = None
            active_passage = None
        elif re.match(r"^(?:PARAGRAPH|GRAMMAR|EXAMPLE|ANSWER|TRANSCRIPT|CD\s*\d+\s+TRACK)\b", text, re.I):
            active_dialogue = None

        dialogue = _DIALOGUE.match(text)
        if dialogue:
            active_dialogue = dialogue.group("id") or f"dialogue-{len(turns) + 1}"
            active_exercise = None
            active_passage = None
            continue
        turn = _TURN.match(text)
        if active_dialogue and turn and not text.startswith(("DIALOGUE", "EXERCISE")):
            turns.append(DialogueTurnRecord(
                source=source,
                local_id=f"turn-{len(turns) + 1}",
                group_id=active_dialogue,
                turn_index=sum(item.group_id == active_dialogue for item in turns),
                speaker=turn.group("speaker").strip(),
                text_ko=turn.group("ko").strip(),
                text_vi=(turn.group("vi") or "").strip() or None,
            ))
            continue

        paragraph = _PARAGRAPH.match(text)
        if paragraph and active_passage is not None:
            current = passages[active_passage]
            passages[active_passage] = PassageRecord(
                **{**current.__dict__, "paragraphs": [*current.paragraphs, paragraph.group("text").strip()]}
            )
            continue

        exercise = _EXERCISE.match(text)
        if exercise:
            active_exercise = len(exercises)
            group = exercise.group("id")
            exercise_index_by_id[group] = active_exercise
            question_index_by_group[group] = 0
            instruction = (exercise.group("instruction") or "").strip() or None
            exercises.append(ExerciseRecord(
                source=source,
                local_id=group,
                group_id=group,
                exercise_type=normalize_exercise_type(
                    exercise.group("kind"), instruction=instruction,
                ),
                instruction=instruction,
                prompt=instruction or "",
                passage_id=passages[active_passage].local_id if active_passage is not None else None,
            ))
            active_dialogue = None
            continue
        question = _QUESTION.match(text)
        if question and active_exercise is not None:
            group = exercises[active_exercise].group_id
            question_index_by_group[group] += 1
            question_id = f"{group}.q{question.group('id')}"
            exercise_index_by_id[question_id] = len(exercises)
            prompt, inline_options = parse_inline_options(question.group("prompt").strip(), source)
            parent = exercises[active_exercise]
            exercises.append(ExerciseRecord(
                source=source,
                local_id=question_id,
                group_id=group,
                parent_id=group,
                exercise_type=normalize_exercise_type(
                    parent.exercise_type,
                    instruction=parent.instruction,
                    options=bool(inline_options),
                ),
                prompt=prompt,
                options=inline_options,
                passage_id=passages[active_passage].local_id if active_passage is not None else None,
            ))
            active_exercise = len(exercises) - 1
            continue
        option = _OPTION.match(text)
        if option and active_exercise is not None:
            current = exercises[active_exercise]
            choice = ExerciseOptionRecord(
                source=source,
                option_index=option_index(option.group("paren") or option.group("bare"), len(current.options) + 1),
                text=option.group("text").strip(),
            )
            exercises[active_exercise] = ExerciseRecord(
                **{
                    **current.__dict__,
                    "options": [*current.options, choice],
                    "exercise_type": normalize_exercise_type(
                        current.exercise_type,
                        instruction=current.instruction,
                        options=True,
                    ),
                }
            )
            continue
        answer = _ANSWER.match(text)
        if answer:
            answers[answer.group("id")] = (answer.group("answer").strip(), source)
            continue
        track = _TRACK.search(text)
        if track:
            track_id = normalize_track_id(f"CD{track.group('disc')}TRACK{track.group('track')}")
            if track_id not in track_ids:
                track_ids.add(track_id)
                tracks.append(ListeningTrackRecord(
                    source=source,
                    local_id=track_id,
                    track_identifier=track_id,
                    audio_status="missing",
                ))
        transcript = _TRANSCRIPT.match(text)
        if transcript:
            track_id = normalize_track_id(transcript.group("track"))
            transcripts.append(TranscriptRecord(
                source=source,
                track_identifier=track_id,
                text=transcript.group("text").strip(),
            ))

    return turns, passages, _link_answer_records(exercises, answers), tracks, transcripts


def _link_answer_records(
    exercises: list[ExerciseRecord],
    answers: dict[str, tuple[str, SourceRef]],
) -> list[ExerciseRecord]:
    linked: list[ExerciseRecord] = []
    answers_by_key = {key.casefold(): value for key, value in answers.items()}
    question_records = [record for record in exercises if record.parent_id is not None]
    aliases: dict[str, list[ExerciseRecord]] = {}
    for record in question_records:
        aliases.setdefault(record.local_id.split(".")[-1].casefold(), []).append(record)
    for record in exercises:
        candidate = (
            answers_by_key.get(record.local_id.casefold())
            if record.parent_id is not None else None
        )
        if candidate is None:
            matching = aliases.get(record.local_id.split(".")[-1].casefold(), [])
            if record.parent_id is not None and len(matching) == 1:
                candidate = answers_by_key.get(record.local_id.split(".")[-1].casefold())
        if candidate is None:
            linked.append(record)
            continue
        answer_text, answer_source = candidate
        linked.append(ExerciseRecord(**{
            **record.__dict__,
            "answer": answer_text,
            "answer_source": answer_source,
        }))
    return linked


def link_answer_keys(
    exercises: list[ExerciseRecord],
    blocks: list[SourceBlock],
) -> list[ExerciseRecord]:
    """Link only explicit source answer markers to question records.

    A short key such as ``q1`` is accepted only when it identifies exactly one
    question in the extracted set. When several groups contain ``q1`` the key
    remains unresolved instead of being attached to the wrong exercise.
    """
    answers: dict[str, tuple[str, SourceRef]] = {}
    for block in blocks:
        match = _ANSWER.match(block.text.strip())
        if match:
            answers[match.group("id")] = (
                match.group("answer").strip(),
                SourceRef(block.page_number, block.printed_page_number, block.block_index),
            )
    return _link_answer_records(exercises, answers)
