export const reviewCriteria = [
  { id: "source_text", label: "Nội dung ứng viên phù hợp với nguồn" },
  { id: "source_page", label: "Đúng trang PDF" },
  { id: "source_position", label: "Đúng vị trí nguồn" },
  { id: "semantic_alignment", label: "Đúng nghĩa Hàn – Việt" },
  { id: "structure", label: "Đúng cấu trúc bài học" },
] as const;

export type ReviewCheckId = (typeof reviewCriteria)[number]["id"];
export type ReviewCheckState = Record<ReviewCheckId, boolean>;

export function emptyReviewChecks(): ReviewCheckState {
  return Object.fromEntries(reviewCriteria.map(({ id }) => [id, false])) as ReviewCheckState;
}

export function canApproveReview(
  sourceSpanId: number | null,
  sourceText: string | null,
  checks: ReviewCheckState,
): boolean {
  return Boolean(
    sourceSpanId &&
      sourceText?.trim() &&
      reviewCriteria.every(({ id }) => checks[id]),
  );
}
