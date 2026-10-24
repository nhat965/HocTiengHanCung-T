# Task 08.1C — Review integrity

## Root cause đã xác nhận

- Review UI tự gửi sẵn toàn bộ checklist nên người dùng không thực sự xác nhận
  từng tiêu chí.
- API chỉ yêu cầu `source_text` và `source_position`, đồng thời chỉ kiểm tra
  source span thuộc owner; chưa kiểm tra span thuộc đúng textbook/lesson và
  chưa yêu cầu source text không rỗng.
- Chưa có API correction tối thiểu cho candidate trước khi approve.
- Review history chưa lưu cấu trúc thay đổi thủ công.

## Cách sửa

- Thêm năm checkbox độc lập trong `/review`, mặc định bỏ chọn; nút Approve chỉ
  bật khi đủ bằng chứng và đủ checklist.
- Backend bắt buộc toàn bộ checklist, `expected_version`, provenance hợp lệ,
  source text không rỗng, đúng owner, textbook và khoảng trang của lesson.
- Thêm `POST /review/{entity_type}/{entity_id}/correction` cho các trường
  vocabulary, WordSense, grammar, sentence và exercise. Correction tăng
  version, đánh dấu `content_origin=human_corrected`, không tự approve và không
  thay raw PDF.
- Thêm `content_reviews.change_set` để lưu before/after; re-import bảo toàn
  candidate đã sửa tay đang chờ duyệt.
- Conflict version trả HTTP 409; frontend tải lại queue sau conflict.

## File thay đổi

- `apps/api/app/routers/data.py`
- `apps/api/app/schemas.py`
- `apps/api/app/models.py`
- `apps/api/app/services/knowledge/persistence.py`
- `apps/api/migrations/versions/20261024_0009_review_correction_history.py`
- `apps/api/tests/test_data_api.py`
- `apps/api/tests/test_extraction_worker.py`
- `apps/web/app/review/page.tsx`
- `apps/web/app/review/reviewChecks.ts`
- `apps/web/app/lib/api.ts`
- `apps/web/app/globals.css`
- `apps/web/tests/review-checks.spec.ts`

## Regression tests

- Thiếu review confirmation không được approve.
- Source span sai lesson bị từ chối.
- Stale version trả 409 và không ghi review decision.
- Correct candidate → reload → approve.
- Correction history lưu before/after và vẫn còn sau re-import.
- Owner isolation hiện có vẫn được chạy.
- Frontend kiểm tra năm checkbox độc lập và gate Approve.

## Kết quả kiểm thử

- Frontend review checks: **2 passed**.
- Frontend production build: **passed**.
- API/PostgreSQL: chờ GitHub Actions sau khi push.
- Không sử dụng dữ liệu giáo trình riêng tư trong fixture.

## Git handoff

- Branch: `codex/task-08-real-pdf-import`
- Commit/CI: cập nhật sau khi GitHub Actions hoàn tất.
- Không tự merge; dừng sau Task 08.1C.

## Hạn chế còn lại

- Chưa thực hiện concurrent workers, exercise parser, OCR, AI Tutor hoặc
  authentication refactor.
- Checklist semantic/structure hiện được áp dụng thống nhất cho mọi entity;
  các entity không song ngữ vẫn cần reviewer xác nhận tiêu chí phù hợp.
