"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { api } from "../../lib/api";

type Lesson = {
  id: number;
  ordinal: number | null;
  title: string;
  start_pdf_page: number | null;
  end_pdf_page: number | null;
  progress_status: string;
};
type Vocabulary = { id: number; headword: string; meanings_vi: string[]; source_page_number: number | null };
type Flashcard = { vocabulary_id: number; headword: string; meanings_vi: string[]; examples: string[]; status: string };
type Grammar = { id: number; pattern: string; explanation_vi: string | null; source_page_number: number | null };
type Sentence = { id: number; text_ko: string; text_vi: string | null; source_page_number: number | null };
type Passage = { id: number; title: string | null; text: string; source_page_number: number | null };
type Dialogue = { id: number; topic: string | null; turns: { turn_index: number; speaker: string | null; text_ko: string; text_vi: string | null }[] };
type Listening = { id: number; track_identifier: string; audio_status: string; transcript_available: boolean; source_page_number: number | null };
type Option = { option_index: number; text: string };
type Exercise = { id: number; prompt: string; exercise_type: string; options: Option[]; source_page_number: number | null; has_children: boolean };
type Tab = "overview" | "vocabulary" | "grammar" | "examples" | "dialogue" | "reading" | "practice" | "listening";
type LessonContent = {
  lesson: Lesson;
  vocabulary: Vocabulary[];
  flashcards: Flashcard[];
  grammar: Grammar[];
  sentences: Sentence[];
  dialogues: Dialogue[];
  reading: Passage[];
  exercises: Exercise[];
  listening: Listening[];
};

const tabTitles: Record<Tab, string> = {
  overview: "Tổng quan",
  vocabulary: "Từ vựng",
  grammar: "Ngữ pháp",
  examples: "Ví dụ",
  dialogue: "Hội thoại",
  reading: "Đọc hiểu",
  practice: "Bài tập",
  listening: "Nghe",
};

export default function LessonDetailPage({ params }: { params: Promise<{ lessonId: string }> }) {
  const [content, setContent] = useState<LessonContent | null>(null);
  const [tab, setTab] = useState<Tab>("overview");
  const [cardIndex, setCardIndex] = useState(0);
  const [cardFlipped, setCardFlipped] = useState(false);
  const [activityMessage, setActivityMessage] = useState("");
  const [answers, setAnswers] = useState<Record<number, string>>({});
  const [results, setResults] = useState<Record<number, string>>({});
  const [completed, setCompleted] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    params.then(async ({ lessonId }) => {
      const id = Number(lessonId);
      if (!Number.isInteger(id) || id < 1) {
        setError("Bài học không hợp lệ.");
        setLoading(false);
        return;
      }
      try {
        await api(`study/lessons/${id}/open`, { method: "POST" });
        const [lesson, vocabulary, flashcards, grammar, sentences, dialogues, reading, exercises, listening] = await Promise.all([
          api<Lesson>(`lessons/${id}`),
          api<Vocabulary[]>(`lessons/${id}/vocabulary?review_status=approved`),
          api<Flashcard[]>(`study/lessons/${id}/flashcards`),
          api<Grammar[]>(`lessons/${id}/grammar?review_status=approved`),
          api<Sentence[]>(`lessons/${id}/sentences?review_status=approved`),
          api<Dialogue[]>(`lessons/${id}/dialogues?review_status=approved`),
          api<Passage[]>(`lessons/${id}/reading?review_status=approved`),
          api<Exercise[]>(`lessons/${id}/exercises?review_status=approved`),
          api<Listening[]>(`lessons/${id}/listening?review_status=approved`),
        ]);
        if (active) {
          setContent({
            lesson, vocabulary, flashcards, grammar, sentences, dialogues, reading,
            exercises: exercises.filter((item) => !item.has_children),
            listening,
          });
          setCompleted(lesson.progress_status === "completed");
        }
      } catch (reason) {
        if (active) setError(reason instanceof Error ? reason.message : "Không thể tải bài học.");
      } finally {
        if (active) setLoading(false);
      }
    });
    return () => { active = false; };
  }, [params]);

  const visibleTabs: Tab[] = content ? [
    "overview",
    ...(content.vocabulary.length ? ["vocabulary" as const] : []),
    ...(content.grammar.length ? ["grammar" as const] : []),
    ...(content.sentences.length ? ["examples" as const] : []),
    ...(content.dialogues.length ? ["dialogue" as const] : []),
    ...(content.reading.length ? ["reading" as const] : []),
    ...(content.exercises.length ? ["practice" as const] : []),
    ...(content.listening.length ? ["listening" as const] : []),
  ] : ["overview"];

  async function markLearned(vocabularyId: number) {
    try {
      await api(`study/vocabulary/${vocabularyId}/learned`, { method: "POST" });
      setContent((current) => current ? {
        ...current,
        flashcards: current.flashcards.map((card) =>
          card.vocabulary_id === vocabularyId ? { ...card, status: "learned" } : card,
        ),
      } : current);
      setActivityMessage("Đã lưu tiến độ học từ vựng.");
      setError("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Không thể lưu tiến độ từ vựng.");
    }
  }

  async function saveNote(grammarId: number, note: string) {
    try {
      await api(`study/grammar/${grammarId}/note`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ note }),
      });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Không thể lưu ghi chú.");
    }
  }

  async function submitExercise(event: FormEvent<HTMLFormElement>, exercise: Exercise) {
    event.preventDefault();
    try {
      const result = await api<{ correct: boolean | null; answer_revealed: string | null }>(
        `study/exercises/${exercise.id}/attempt`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ answer: answers[exercise.id] ?? "" }),
        },
      );
      setResults((current) => ({
        ...current,
        [exercise.id]: result.correct === null
          ? "Đã lưu câu trả lời; đáp án chưa được kiểm duyệt."
          : `${result.correct ? "Chính xác." : "Chưa chính xác."}${result.answer_revealed ? ` Đáp án: ${result.answer_revealed}` : ""}`,
      }));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Không thể lưu câu trả lời.");
    }
  }

  async function completeLesson() {
    if (!content) return;
    try {
      await api(`study/lessons/${content.lesson.id}/complete`, { method: "POST" });
      setCompleted(true);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Không thể lưu tiến độ bài học.");
    }
  }

  if (loading) return <main className="learning-workspace page-shell">Đang tải bài học…</main>;
  if (error && !content) return <main className="learning-workspace page-shell"><p className="alert" role="alert">{error}</p></main>;
  if (!content) return <main className="learning-workspace page-shell"><div className="empty-state"><strong>Không tìm thấy bài học.</strong><p>Hãy quay lại danh sách quyển sách.</p></div><Link className="back-link" href="/">← Thư viện</Link></main>;

  const currentCard = content.flashcards[cardIndex];
  return (
    <main className="learning-workspace page-shell">
      <p className="eyebrow">Bài {String(content.lesson.ordinal ?? "—").padStart(2, "0")} · PDF {content.lesson.start_pdf_page ?? "?"}–{content.lesson.end_pdf_page ?? "?"}</p>
      <h1>{content.lesson.title}</h1>
      <div className="tabs" role="tablist" aria-label="Các phần của bài học">
        {visibleTabs.map((item) => <button type="button" role="tab" aria-selected={tab === item} className={tab === item ? "active" : ""} key={item} onClick={() => setTab(item)}>{tabTitles[item]}</button>)}
      </div>
      {error && <p className="alert" role="alert">{error}</p>}

      {tab === "overview" && <section className="content-section"><h2>Tổng quan bài học</h2><p>{content.vocabulary.length} từ vựng · {content.grammar.length} mẫu ngữ pháp · {content.exercises.length} bài tập</p><p>Dữ liệu hiển thị tại đây đã qua kiểm duyệt và có thể truy xuất trang nguồn.</p><button className="primary-button" type="button" onClick={completeLesson}>{completed ? "Đã lưu hoàn thành" : "Đánh dấu bài học hoàn thành"}</button></section>}

      {tab === "vocabulary" && <section className="content-section"><h2>Thẻ từ vựng</h2>{currentCard ? <><button className={`flashcard${cardFlipped ? " flipped" : ""}`} type="button" onClick={() => setCardFlipped((value) => !value)} aria-label="Lật thẻ từ vựng"><span className="eyebrow">{cardFlipped ? "Tiếng Việt" : "Tiếng Hàn"}</span><strong>{cardFlipped ? currentCard.meanings_vi.join(" · ") : currentCard.headword}</strong><small>Nhấn để lật</small></button>{currentCard.examples.map((example) => <p className="example-line" key={example}>{example}</p>)}<div className="flashcard-actions"><button type="button" onClick={() => { setCardFlipped(false); setActivityMessage(""); setCardIndex((index) => (index + content.flashcards.length - 1) % content.flashcards.length); }}>Trước</button><span>{cardIndex + 1}/{content.flashcards.length}</span><button type="button" onClick={() => { setCardFlipped(false); setActivityMessage(""); setCardIndex((index) => (index + 1) % content.flashcards.length); }}>Tiếp</button><button type="button" onClick={() => markLearned(currentCard.vocabulary_id)}>Đánh dấu đã học</button></div>{activityMessage && <p className="feedback" role="status">{activityMessage}</p>}</> : <Empty message="Các từ vựng đã duyệt chưa có nghĩa đã duyệt để tạo thẻ học." />}</section>}

      {tab === "grammar" && <section className="content-section"><h2>Ngữ pháp</h2><div className="grammar-list">{content.grammar.map((item) => <article key={item.id}><div><h3>{item.pattern}</h3><p>{item.explanation_vi || "Chưa có giải thích được duyệt."}</p><span className="source-tag">Trang PDF {item.source_page_number ?? "?"}</span></div><GrammarNote grammar={item} onSave={(note) => saveNote(item.id, note)} /></article>)}</div></section>}

      {tab === "examples" && <section className="content-section"><h2>Ví dụ</h2>{content.sentences.map((item) => <article className="knowledge-card" key={item.id}><p lang="ko">{item.text_ko}</p>{item.text_vi && <p>{item.text_vi}</p>}<span className="source-tag">Trang PDF {item.source_page_number ?? "?"}</span></article>)}</section>}

      {tab === "dialogue" && <section className="content-section"><h2>Hội thoại</h2>{content.dialogues.map((item) => <article className="knowledge-card" key={item.id}><h3>{item.topic || "Hội thoại"}</h3>{item.turns.map((turn) => <p key={turn.turn_index}><strong>{turn.speaker || `Lượt ${turn.turn_index}`}:</strong> {turn.text_ko}{turn.text_vi && <small className="translation">{turn.text_vi}</small>}</p>)}</article>)}</section>}

      {tab === "reading" && <section className="content-section"><h2>Đọc hiểu</h2>{content.reading.map((item) => <article className="knowledge-card" key={item.id}><h3>{item.title || "Bài đọc"}</h3><p className="reading-text">{item.text}</p><span className="source-tag">Trang PDF {item.source_page_number ?? "?"}</span></article>)}</section>}

      {tab === "practice" && <section className="content-section"><h2>Luyện tập</h2>{content.exercises.map((exercise, index) => <form className="exercise-card" key={exercise.id} onSubmit={(event) => submitExercise(event, exercise)}><span className="eyebrow">Câu {index + 1} · {exercise.exercise_type}</span><h3>{exercise.prompt || "Chọn đáp án phù hợp"}</h3>{exercise.options.length ? <div className="exercise-options">{exercise.options.map((option) => <label key={option.option_index}><input type="radio" name={`exercise-${exercise.id}`} value={option.option_index} checked={answers[exercise.id] === String(option.option_index)} onChange={(event) => setAnswers((current) => ({ ...current, [exercise.id]: event.target.value }))} required /><span>{option.text}</span></label>)}</div> : <input className="exercise-answer" aria-label={`Câu trả lời ${index + 1}`} value={answers[exercise.id] ?? ""} onChange={(event) => setAnswers((current) => ({ ...current, [exercise.id]: event.target.value }))} required />}<button className="primary-button" type="submit">Nộp câu trả lời</button>{results[exercise.id] && <p className="feedback" role="status">{results[exercise.id]}</p>}</form>)}</section>}

      {tab === "listening" && <section className="content-section"><h2>Listening metadata</h2>{content.listening.map((item) => <article className="knowledge-card" key={item.id}><h3>Track {item.track_identifier}</h3><p>Âm thanh: {item.audio_status} · Transcript: {item.transcript_available ? "có nguồn" : "chưa có"}</p><span className="source-tag">Trang PDF {item.source_page_number ?? "?"}</span></article>)}</section>}
      <Link className="back-link" href="/">← Thư viện sách</Link>
    </main>
  );
}

function Empty({ message }: { message: string }) {
  return <div className="empty-state"><strong>Chưa có nội dung học.</strong><p>{message}</p></div>;
}

function GrammarNote({ grammar, onSave }: {
  grammar: Grammar;
  onSave: (note: string) => void;
}) {
  const [value, setValue] = useState("");
  const [loaded, setLoaded] = useState(false);
  const [loadError, setLoadError] = useState("");
  useEffect(() => {
    let active = true;
    api<{ note: string }>(`study/grammar/${grammar.id}/note`)
      .then((result) => { if (active) setValue(result.note); })
      .catch(() => { if (active) setLoadError("Ghi chú chưa thể tải. Kiểm tra kết nối rồi thử lại."); })
      .finally(() => { if (active) setLoaded(true); });
    return () => { active = false; };
  }, [grammar.id]);
  return <div className="grammar-note"><label htmlFor={`note-${grammar.id}`}>Ghi chú cá nhân</label>{loadError && <p className="auth-error" role="alert">{loadError}</p>}<textarea id={`note-${grammar.id}`} value={value} onChange={(event) => setValue(event.target.value)} disabled={!loaded || Boolean(loadError)} /><button type="button" onClick={() => onSave(value)} disabled={!loaded || Boolean(loadError)}>Lưu ghi chú</button></div>;
}
