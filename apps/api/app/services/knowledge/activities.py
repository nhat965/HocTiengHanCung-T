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
_OPTION = re.compile(r"^\s*(?:OPTION\s*:|\([A-D1-9]\)\s*)(?P<text>.*)$", re.I)
_ANSWER = re.compile(r"^\s*ANSWER\[(?P<id>[\w.-]+)\]\s*:\s*(?P<answer>.*)$", re.I)
_TRACK = re.compile(r"\bCD\s*(?P<disc>\d+)\s*TRACK\s*(?P<track>\d+)\b", re.I)
_TRANSCRIPT = re.compile(r"^\s*TRANSCRIPT\[(?P<track>[^\]]+)\]\s*:\s*(?P<text>.*)$", re.I)


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
            exercises.append(ExerciseRecord(
                source=source,
                local_id=group,
                group_id=group,
                exercise_type=exercise.group("kind").lower(),
                instruction=(exercise.group("instruction") or "").strip() or None,
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
            exercises.append(ExerciseRecord(
                source=source,
                local_id=question_id,
                group_id=group,
                parent_id=group,
                exercise_type=exercises[active_exercise].exercise_type,
                prompt=question.group("prompt").strip(),
                passage_id=passages[active_passage].local_id if active_passage is not None else None,
            ))
            active_exercise = len(exercises) - 1
            continue
        option = _OPTION.match(text)
        if option and active_exercise is not None:
            current = exercises[active_exercise]
            choice = ExerciseOptionRecord(
                source=source,
                option_index=len(current.options) + 1,
                text=option.group("text").strip(),
            )
            exercises[active_exercise] = ExerciseRecord(
                **{**current.__dict__, "options": [*current.options, choice]}
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

    linked: list[ExerciseRecord] = []
    answers_by_key = {key.casefold(): value for key, value in answers.items()}
    for record in exercises:
        candidate = answers_by_key.get(record.local_id.casefold())
        if candidate is None:
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
    return turns, passages, linked, tracks, transcripts
