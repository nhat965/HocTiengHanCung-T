"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "../lib/api";

type Book = {
  id: number;
  title: string;
  level: string;
  volume_number: number;
  lesson_count: number;
  completed_lessons: number;
  progress_percent: number;
  data_status: string;
};
type Progress = { last_lesson_id: number | null; last_lesson_title: string | null };

const statusLabels: Record<string, string> = {
  empty: "Chưa có dữ liệu",
  processing: "Đang xử lý",
  failed: "Import lỗi",
  needs_review: "Cần kiểm duyệt",
  ready: "Sẵn sàng học",
};

export default function BooksPage() {
  const [books, setBooks] = useState<Book[]>([]);
  const [resume, setResume] = useState<Progress | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([api<Book[]>("textbooks"), api<Progress>("study/progress")])
      .then(([rows, progress]) => {
        setBooks(rows);
        setResume(progress);
      })
      .catch((reason: Error) => setError(reason.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <main className="learning-workspace page-shell">
      <p className="eyebrow">Thư viện cá nhân</p>
      <h1>Chọn quyển sách</h1>
      <p className="page-lede">Chỉ hiển thị tài liệu đã đăng ký trong kho dữ liệu riêng.</p>
      {error && <p className="alert" role="alert">{error}</p>}
      {resume?.last_lesson_id && <Link className="resume-card" href={`/lessons/${resume.last_lesson_id}`}>Tiếp tục bài gần nhất: <strong>{resume.last_lesson_title}</strong> →</Link>}
      {loading ? <p>Đang tải thư viện…</p> : books.length ? (
        <section className="book-cards" aria-label="Các quyển sách đã đăng ký">
          {books.map((book) => (
            <Link className="book-card" href={`/books/${book.id}`} key={book.id}>
              <span className="eyebrow">{book.level} · Quyển {book.volume_number}</span>
              <h2>{book.title}</h2>
              <p>{book.lesson_count} bài học · {book.completed_lessons} đã hoàn thành</p>
              <div className="progress-track" role="progressbar" aria-label="Tiến độ học" aria-valuenow={book.progress_percent} aria-valuemin={0} aria-valuemax={100}><span style={{ width: `${book.progress_percent}%` }} /></div>
              <div className="book-card-footer"><span>{statusLabels[book.data_status] ?? book.data_status}</span><strong>{book.progress_percent}%</strong></div>
            </Link>
          ))}
        </section>
      ) : !error && (
        <div className="empty-state"><strong>Chưa có quyển sách nào.</strong><p>Đăng ký tài liệu được phép sử dụng trong máy chủ riêng. Danh sách này không sử dụng dữ liệu giả định.</p></div>
      )}
    </main>
  );
}
