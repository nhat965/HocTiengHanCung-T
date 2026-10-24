import { describe, expect, it } from "vitest";
import { canApproveReview, emptyReviewChecks, reviewCriteria } from "../app/review/reviewChecks";

describe("review confirmation", () => {
  it("starts every independent criterion unchecked", () => {
    expect(emptyReviewChecks()).toEqual({
      source_text: false,
      source_page: false,
      source_position: false,
      semantic_alignment: false,
      structure: false,
    });
    expect(reviewCriteria).toHaveLength(5);
  });

  it("only enables approval after evidence and every check are confirmed", () => {
    const checks = emptyReviewChecks();
    expect(canApproveReview(10, "사과 quả táo", checks)).toBe(false);
    checks.source_text = true;
    checks.source_page = true;
    checks.source_position = true;
    checks.semantic_alignment = true;
    expect(canApproveReview(10, "사과 quả táo", checks)).toBe(false);
    checks.structure = true;
    expect(canApproveReview(10, "사과 quả táo", checks)).toBe(true);
    expect(canApproveReview(null, "사과 quả táo", checks)).toBe(false);
    expect(canApproveReview(10, "", checks)).toBe(false);
  });
});
