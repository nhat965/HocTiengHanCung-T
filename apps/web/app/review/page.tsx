"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "../lib/api";

type ReviewRecord = {
  entity_type: string;
  entity_id: number;
  review_status: string;
  source_page_number: number | null;
  source_printed_page_number: string | null;
  source_text: string | null;
  preview: string;
  version: number;
  source_span_id: number | null;
};

const labels: Record<string, string> = {
  vocabulary: "Từ vựng",
  word_sense: "Nghĩa từ",
  grammar: "Ngữ pháp",
  sentence: "Câu ví dụ",
  dialogue_turn: "Lượt hội thoại",
  passage: "Bài đọc",
  exercise: "Bài tập",
  exercise_option: "Phương án",
  answer_key: "Đáp án",
  listening_track: "Track nghe",
  transcript: "Transcript",
  lesson: "Bài học",
};

export default function ReviewPage() {
  const [records, setRecords] = useState<ReviewRecord[]>([]);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  async function load(nextOffset = offset) {
    setLoading(true);
    setError("");
    try {
      const rows = await api<ReviewRecord[]>(`review?review_status=pending&offset=${nextOffset}&limit=50`);
      setRecords(rows);
      setOffset(nextOffset);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Không thể tải hàng đợi kiểm duyệt.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(0); }, []);

  async function update(record: ReviewRecord, status: "approved" | "unresolved") {
    setMessage("");
    setError("");
    try {
      await api(`review/${record.entity_type}/${record.entity_id}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(status === "approved" ? {
          status,
          expected_version: record.version,
          source_span_id: record.source_span_id,
          reviewer_action: "compared_to_source",
          checks: ["source_text", "source_position", "semantic_alignment", "structure"],
          note: "Đã đối chiếu candidate với đoạn nguồn hiển thị trong hàng đợi riêng tư.",
        } : {
          status,
          source_span_id: record.source_span_id,
          reviewer_action: "flagged",
          checks: [],
          note: "Chưa đủ bằng chứng để duyệt; cần kiểm tra lại nguồn.",
        }),
      });
      setRecords((current) => current.filter((item) => item !== record));
      setMessage(status === "approved" ? "Đã duyệt và ghi lịch sử đối chiếu." : "Đã đánh dấu unresolved.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Không thể cập nhật review.");
    }
  }

  return (
    <main className="learning-workspace page-shell review-page">
      <p className="eyebrow">Kiểm duyệt riêng tư</p>
      <h1>Đối chiếu nguồn</h1>
      <p className="page-lede">Chỉ approve sau khi so sánh candidate với trang và đoạn nguồn. Dữ liệu chưa duyệt không xuất hiện trong bài học.</p>
      {error && <p className="alert" role="alert">{error}</p>}
      {message && <p className="feedback" role="status">{message}</p>}
      {loading ? <p>Đang tải hàng đợi…</p> : records.length ? (
        <section className="review-list" aria-label="Hàng đợi kiểm duyệt">
          {records.map((record) => (
            <article className="review-card" key={`${record.entity_type}-${record.entity_id}`}>
              <div className="review-card-head">
                <span className="eyebrow">{labels[record.entity_type] ?? record.entity_type} · #{record.entity_id}</span>
                <span className="source-tag">Version {record.version}</span>
              </div>
              <h2>{record.preview}</h2>
              <div className="review-evidence">
                <div><strong>Candidate</strong><p>{record.preview}</p></div>
                <div><strong>Nguồn</strong><p>{record.source_text || "Chưa có source span; không được approve."}</p></div>
              </div>
              <p className="source-tag">PDF page {record.source_page_number ?? "?"}{record.source_printed_page_number ? ` · printed ${record.source_printed_page_number}` : ""} · span {record.source_span_id ?? "?"}</p>
              <div className="review-actions">
                <button className="primary-button" type="button" disabled={!record.source_span_id} onClick={() => void update(record, "approved")}>Approve sau đối chiếu</button>
                <button className="secondary-button" type="button" onClick={() => void update(record, "unresolved")}>Đánh dấu unresolved</button>
              </div>
            </article>
          ))}
        </section>
      ) : (
        <div className="empty-state"><strong>Không còn bản ghi pending trong trang này.</strong><p>Các bản ghi chưa có bằng chứng vẫn được giữ ngoài learner view.</p></div>
      )}
      <div className="review-pagination">
        <button className="secondary-button" type="button" disabled={offset === 0 || loading} onClick={() => void load(Math.max(0, offset - 50))}>Trang trước</button>
        <span>Offset {offset}</span>
        <button className="secondary-button" type="button" disabled={records.length < 50 || loading} onClick={() => void load(offset + 50)}>Trang sau</button>
      </div>
      <Link className="back-link" href="/books">← Thư viện sách</Link>
    </main>
  );
}
