"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, ApiError } from "../lib/api";
import { canApproveReview, emptyReviewChecks, reviewCriteria, type ReviewCheckId, type ReviewCheckState } from "./reviewChecks";

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

type AnswerResolution = {
  id: number;
  status: string;
  compound_key: string | null;
  lesson_number: number | null;
  skill_section: string | null;
  exercise_group: string | null;
  question_number: string | null;
  question_context_id: number | null;
  exercise_id: number | null;
  question_prompt: string | null;
  question_page_number: number | null;
  question_source_span_id: number | null;
  answer_text: string;
  answer_page_number: number | null;
  answer_source_span_id: number | null;
  match_reason: string | null;
  reviewer_note: string | null;
  version: number;
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

const correctionFields: Record<string, Array<{ field: string; label: string }>> = {
  vocabulary: [{ field: "headword", label: "Từ vựng" }],
  word_sense: [{ field: "meaning_vi", label: "Nghĩa tiếng Việt" }],
  grammar: [
    { field: "pattern", label: "Mẫu ngữ pháp" },
    { field: "explanation_vi", label: "Giải thích tiếng Việt" },
  ],
  sentence: [
    { field: "text_ko", label: "Câu tiếng Hàn" },
    { field: "text_vi", label: "Câu tiếng Việt" },
  ],
  exercise: [{ field: "prompt", label: "Đề bài" }],
};

export default function ReviewPage() {
  const [records, setRecords] = useState<ReviewRecord[]>([]);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [checks, setChecks] = useState<Record<string, ReviewCheckState>>({});
  const [editing, setEditing] = useState<string | null>(null);
  const [correctionField, setCorrectionField] = useState("");
  const [correctionValue, setCorrectionValue] = useState("");
  const [answerCandidates, setAnswerCandidates] = useState<AnswerResolution[]>([]);
  const [contextSelection, setContextSelection] = useState<Record<number, string>>({});
  const [contextNotes, setContextNotes] = useState<Record<number, string>>({});
  const [answerChecks, setAnswerChecks] = useState<Record<number, ReviewCheckState>>({});

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

  async function loadAnswerCandidates() {
    try {
      const rows = await api<AnswerResolution[]>("answer-resolution?status=matched_candidate,needs_review,unresolved,verified&limit=50");
      setAnswerCandidates(rows);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Không thể tải candidate đáp án.");
    }
  }

  useEffect(() => { void loadAnswerCandidates(); }, []);

  async function reviewAnswerCandidate(candidate: AnswerResolution, action: "confirm" | "reject" | "select") {
    setError("");
    const selected = Number(contextSelection[candidate.id]);
    try {
      await api(`answer-resolution/${candidate.id}/review`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action,
          expected_version: candidate.version,
          ...(action === "select" && Number.isInteger(selected) && selected > 0 ? { question_context_id: selected } : {}),
          ...(action === "select" ? { note: contextNotes[candidate.id] ?? "" } : {}),
        }),
      });
      setMessage(action === "reject" ? "Đã từ chối cặp ghép; candidate vẫn được lưu để audit." : "Đã xác nhận cặp nguồn; cần approve riêng sau checklist.");
      await loadAnswerCandidates();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Không thể cập nhật candidate đáp án.");
    }
  }

  async function approveAnswerCandidate(candidate: AnswerResolution) {
    setError("");
    try {
      await api(`answer-resolution/${candidate.id}/approve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          expected_version: candidate.version,
          checks: reviewCriteria.filter(({ id }) => (answerChecks[candidate.id] ?? emptyReviewChecks())[id]).map(({ id }) => id),
          note: "Reviewer đã đối chiếu câu hỏi và phụ lục đáp án có nguồn.",
        }),
      });
      setMessage("Đã tạo AnswerKey đã duyệt với provenance phụ lục.");
      await loadAnswerCandidates();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Không thể approve đáp án.");
    }
  }

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
          checks: reviewCriteria.filter(({ id }) => checks[recordKey(record)]?.[id]).map(({ id }) => id),
          note: "Đã đối chiếu candidate với đoạn nguồn hiển thị trong hàng đợi riêng tư.",
        } : {
          status,
          expected_version: record.version,
          source_span_id: record.source_span_id,
          reviewer_action: "flagged",
          checks: [],
          note: "Chưa đủ bằng chứng để duyệt; cần kiểm tra lại nguồn.",
        }),
      });
      setRecords((current) => current.filter((item) => item !== record));
      setMessage(status === "approved" ? "Đã duyệt và ghi lịch sử đối chiếu." : "Đã đánh dấu unresolved.");
    } catch (reason) {
      if (reason instanceof ApiError && reason.status === 409) {
        await load(offset);
      }
      setError(reason instanceof Error ? reason.message : "Không thể cập nhật review.");
    }
  }

  function recordKey(record: ReviewRecord): string {
    return `${record.entity_type}-${record.entity_id}`;
  }

  function recordChecks(record: ReviewRecord): ReviewCheckState {
    return checks[recordKey(record)] ?? emptyReviewChecks();
  }

  function activeCorrectionField(record: ReviewRecord) {
    const fields = correctionFields[record.entity_type] ?? [];
    return fields.find((field) => field.field === correctionField) ?? fields[0];
  }

  function toggleCheck(record: ReviewRecord, id: ReviewCheckId) {
    const key = recordKey(record);
    const next = { ...recordChecks(record), [id]: !recordChecks(record)[id] };
    setChecks((current) => ({ ...current, [key]: next }));
  }

  async function correct(record: ReviewRecord) {
    const correction = correctionFields[record.entity_type];
    const selectedField = correctionField || correction?.[0]?.field;
    if (!correction || !selectedField || !correctionValue.trim()) return;
    setError("");
    try {
      await api(`review/${record.entity_type}/${record.entity_id}/correction`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ expected_version: record.version, field: selectedField, value: correctionValue.trim() }),
      });
      setEditing(null);
      setCorrectionValue("");
      await load(offset);
      setMessage("Đã lưu chỉnh sửa thủ công; bản ghi vẫn chờ duyệt.");
    } catch (reason) {
      if (reason instanceof ApiError && reason.status === 409) await load(offset);
      setError(reason instanceof Error ? reason.message : "Không thể lưu chỉnh sửa.");
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
              <fieldset className="review-checks">
                <legend>Checklist đối chiếu — tự xác nhận từng tiêu chí</legend>
                {reviewCriteria.map(({ id, label }) => (
                  <label key={id}>
                    <input type="checkbox" checked={recordChecks(record)[id]} onChange={() => toggleCheck(record, id)} />
                    {label}
                  </label>
                ))}
              </fieldset>
              {correctionFields[record.entity_type] && (
                <div className="review-correction">
                  {editing === recordKey(record) ? (
                    <>
                      {correctionFields[record.entity_type].length > 1 && (
                        <label>Trường cần sửa
                          <select value={correctionField} onChange={(event) => setCorrectionField(event.target.value)}>
                            {correctionFields[record.entity_type].map((field) => <option key={field.field} value={field.field}>{field.label}</option>)}
                          </select>
                        </label>
                      )}
                      <label>{activeCorrectionField(record)?.label}
                        <input value={correctionValue} onChange={(event) => setCorrectionValue(event.target.value)} />
                      </label>
                      <button className="secondary-button" type="button" onClick={() => void correct(record)}>Lưu chỉnh sửa</button>
                      <button className="secondary-button" type="button" onClick={() => setEditing(null)}>Hủy</button>
                    </>
                  ) : (
                    <button className="secondary-button" type="button" onClick={() => { setEditing(recordKey(record)); setCorrectionField(correctionFields[record.entity_type][0].field); setCorrectionValue(record.preview); }}>
                      Sửa candidate trước khi duyệt
                    </button>
                  )}
                </div>
              )}
              <div className="review-actions">
                <button className="primary-button" type="button" disabled={!canApproveReview(record.source_span_id, record.source_text, recordChecks(record))} onClick={() => void update(record, "approved")}>Approve sau đối chiếu</button>
                <button className="secondary-button" type="button" onClick={() => void update(record, "unresolved")}>Đánh dấu unresolved</button>
              </div>
            </article>
          ))}
        </section>
      ) : (
        <div className="empty-state"><strong>Không còn bản ghi pending trong trang này.</strong><p>Các bản ghi chưa có bằng chứng vẫn được giữ ngoài learner view.</p></div>
      )}
      <section className="review-list" aria-label="Đối chiếu đáp án phụ lục">
        <p className="eyebrow">Answer resolution</p>
        <h2>Đáp án phụ lục cần đối chiếu</h2>
        <p className="page-lede">Candidate không phải đáp án học viên cho đến khi reviewer xác nhận và approve cả hai nguồn.</p>
        {answerCandidates.length ? answerCandidates.map((candidate) => (
          <article className="review-card" key={`answer-${candidate.id}`}>
            <div className="review-card-head">
              <span className="eyebrow">Bài {candidate.lesson_number ?? "?"} · {candidate.skill_section ?? "chưa rõ"} · nhóm {candidate.exercise_group ?? "?"} · câu {candidate.question_number ?? "?"}</span>
              <span className="source-tag">{candidate.status} · v{candidate.version}</span>
            </div>
            <p className="source-tag">{candidate.compound_key ?? "Thiếu compound key - không thể tự ghép"}</p>
            <div className="review-evidence">
              <div><strong>Câu hỏi</strong><p>{candidate.question_prompt ?? "Chưa có question context; chọn lại một context có nguồn."}</p><p>PDF {candidate.question_page_number ?? "?"} · span {candidate.question_source_span_id ?? "?"}</p></div>
              <div><strong>Đáp án phụ lục</strong><p>{candidate.answer_text}</p><p>PDF {candidate.answer_page_number ?? "?"} · span {candidate.answer_source_span_id ?? "?"}</p></div>
            </div>
            <p className="source-tag">{candidate.match_reason ?? "Chưa có lý do ghép."}</p>
            {candidate.status === "needs_review" || candidate.status === "unresolved" ? <label>Question context ID thay thế
              <input inputMode="numeric" value={contextSelection[candidate.id] ?? ""} onChange={(event) => setContextSelection((current) => ({ ...current, [candidate.id]: event.target.value }))} />
              <span>Lý do đối chiếu</span>
              <input value={contextNotes[candidate.id] ?? ""} onChange={(event) => setContextNotes((current) => ({ ...current, [candidate.id]: event.target.value }))} />
            </label> : null}
            {candidate.status === "verified" ? <fieldset className="review-checklist">
              <legend>Checklist bắt buộc trước khi approve</legend>
              {reviewCriteria.map(({ id, label }) => <label key={`${candidate.id}-${id}`}>
                <input type="checkbox" checked={(answerChecks[candidate.id] ?? emptyReviewChecks())[id]} onChange={() => setAnswerChecks((current) => ({
                  ...current,
                  [candidate.id]: { ...(current[candidate.id] ?? emptyReviewChecks()), [id]: !(current[candidate.id] ?? emptyReviewChecks())[id] },
                }))} />
                {label}
              </label>)}
            </fieldset> : null}
            <div className="review-actions">
              {candidate.status === "matched_candidate" && <button className="primary-button" type="button" onClick={() => void reviewAnswerCandidate(candidate, "confirm")}>Xác nhận cặp</button>}
              {(candidate.status === "needs_review" || candidate.status === "unresolved") && <button className="secondary-button" type="button" disabled={!contextNotes[candidate.id]?.trim()} onClick={() => void reviewAnswerCandidate(candidate, "select")}>Chọn lại context</button>}
              {candidate.status !== "approved" && <button className="secondary-button" type="button" onClick={() => void reviewAnswerCandidate(candidate, "reject")}>Từ chối cặp</button>}
              {candidate.status === "verified" && <button className="primary-button" type="button" disabled={!reviewCriteria.every(({ id }) => (answerChecks[candidate.id] ?? emptyReviewChecks())[id])} onClick={() => void approveAnswerCandidate(candidate)}>Approve đáp án</button>}
            </div>
          </article>
        )) : <div className="empty-state"><strong>Không có candidate answer đang chờ.</strong><p>Không có đáp án nào được tạo tự động cho learner.</p></div>}
      </section>
      <div className="review-pagination">
        <button className="secondary-button" type="button" disabled={offset === 0 || loading} onClick={() => void load(Math.max(0, offset - 50))}>Trang trước</button>
        <span>Offset {offset}</span>
        <button className="secondary-button" type="button" disabled={records.length < 50 || loading} onClick={() => void load(offset + 50)}>Trang sau</button>
      </div>
      <Link className="back-link" href="/books">← Thư viện sách</Link>
    </main>
  );
}
