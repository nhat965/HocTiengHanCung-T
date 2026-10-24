"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "../../lib/api";

type Book = {
  id: number;
  title: string;
  level: string;
  volume_number: number;
  data_status: string;
  lesson_count: number;
  completed_lessons: number;
  progress_percent: number;
};
type Lesson = {
  id: number;
  ordinal: number | null;
  title: string;
  start_pdf_page: number | null;
  end_pdf_page: number | null;
  vocabulary_count: number;
  grammar_count: number;
  progress_status: string;
};

const statusLabels: Record<string, string> = {
  empty: "Chưa có dữ liệu",
  processing: "Đang xử lý",
  failed: "Import lỗi",
  needs_review: "Cần kiểm duyệt",
  ready: "Sẵn sàng học",
  completed: "Đã hoàn thành",
  in_progress: "Đang học",
  not_started: "Chưa bắt đầu",
};

export default function LessonsPage({ params }: { params: Promise<{ bookId: string }> }) {
  const [bookId, setBookId] = useState<number | null>(null);
  const [book, setBook] = useState<Book | null>(null);
  const [lessons, setLessons] = useState<Lesson[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    params.then(({ bookId: id }) => {
      const parsed = Number(id);
      if (!Number.isInteger(parsed) || parsed < 1) {
        setError("Quyển sách không hợp lệ.");
        setLoading(false);
        return;
      }
      setBookId(parsed);
      Promise.all([
        api<Book>(`textbooks/${parsed}`),
        api<Lesson[]>(`textbooks/${parsed}/lessons`),
      ]).then(([bookRow, lessonRows]) => {
        if (!active) return;
        setBook(bookRow);
        setLessons(lessonRows);
      }).catch((reason: Error) => {
        if (active) setError(reason.message);
      }).finally(() => {
        if (active) setLoading(false);
      });
    });
    return () => { active = false; };
  }, [params]);

  return (
    <main className="learning-workspace page-shell">
      <p className="eyebrow">Thư viện cá nhân</p>
      <h1>{book ? book.title : "Các bài học"}</h1>
      {book && <p className="page-lede">{book.level} · Quyển {book.volume_number} · {book.completed_lessons}/{book.lesson_count} bài hoàn thành</p>}
      {error && <p className="alert" role="alert">{error}</p>}
      {loading ? <p>Đang tải bài học…</p> : !error && lessons.length === 0 ? (
        <div className="empty-state"><strong>Chưa có bài học khả dụng.</strong><p>{book?.data_status === "needs_review" ? "Dữ liệu đang chờ kiểm duyệt, nên chưa hiển thị trong chế độ học." : "Hãy đăng ký và xử lý tài liệu trước khi học."}</p></div>
      ) : (
        <section className="lesson-cards" aria-label="Danh sách bài học">
          {lessons.map((lesson) => (
            <Link className="lesson-card" href={`/lessons/${lesson.id}`} key={lesson.id}>
              <span className="eyebrow">Bài {String(lesson.ordinal ?? "—").padStart(2, "0")}</span>
              <h2>{lesson.title}</h2>
              <p>Trang PDF {lesson.start_pdf_page ?? "?"}–{lesson.end_pdf_page ?? "?"}</p>
              <div className="lesson-card-meta">
                <span>{lesson.vocabulary_count} từ vựng</span>
                <span>{lesson.grammar_count} ngữ pháp</span>
                <span>{statusLabels[lesson.progress_status] ?? lesson.progress_status}</span>
              </div>
              <strong>{lesson.progress_status === "in_progress" ? "Tiếp tục học →" : "Mở bài học →"}</strong>
            </Link>
          ))}
        </section>
      )}
      {bookId && <Link className="back-link" href="/">← Quay lại các quyển sách</Link>}
    </main>
  );
}
