# Task 08.1B — Data preservation

## Lỗi tái hiện và nguyên nhân

Regression fixture đã import, approve vocabulary/grammar/exercise, sửa một
WordSense, lưu GrammarNote, đánh dấu vocabulary đã học, hoàn thành lesson và
lưu StudyAttempt trước khi chạy lại cùng ImportJob.

Hai lỗi được tái hiện:

1. Lesson không đổi nội dung vẫn bị tăng `version` sau re-import.
2. Exercise parent/child bị tạo bản ghi mới vì lần tạo dùng prompt fallback
   (`instruction`/`local_id`) nhưng lần lookup chỉ dùng `item.prompt`, thường là
   `None`.

## Cách sửa

- Persistence chỉ cập nhật Lesson và tăng version khi các trường thật sự thay
  đổi; bản ghi approved/reviewed tiếp tục được bảo vệ.
- Exercise chuẩn hóa prompt một lần rồi dùng cùng giá trị cho lookup và insert,
  giữ ổn định ID parent/child.
- Không có migration mới: các trường progress, review, provenance và ghi chú
  hiện có đã đủ để bảo toàn dữ liệu.

## File thay đổi

- `apps/api/app/services/knowledge/persistence.py`
- `apps/api/tests/test_extraction_worker.py`
- `docs/reports/TASK_08_1B_DATA_PRESERVATION.md`

## Test bổ sung

`test_reimport_preserves_approved_knowledge_and_learning_state` kiểm tra nội
dung, ID, version, review history, provenance, progress, note, StudyAttempt và
số lượng entity trước/sau re-import; đồng thời xác nhận không tạo duplicate
exercise.

Existing transaction rollback, idempotency và approved-record tests vẫn được
chạy cùng suite.

## Kết quả

- Local API suite: **29 passed**.
- PostgreSQL 16 CI: passed in run [40096399990](https://github.com/nhat965/HocTiengHanCung-T/actions/runs/40096399990) trên commit `ae991ad799a221358be821c23d895ca2afe310a1`.
- Không sử dụng dữ liệu giáo trình riêng tư trong fixture.

## Git handoff

- Branch: `codex/task-08-real-pdf-import`
- Commit: `ae991ad799a221358be821c23d895ca2afe310a1`.
- CI: [GitHub Actions run 40096399990](https://github.com/nhat965/HocTiengHanCung-T/actions/runs/40096399990).

## Rủi ro còn lại

- Re-import với extractor thay đổi thật sự vẫn tạo phiên bản pending mới theo
  logic entity hiện có; việc review khác biệt thuộc phạm vi review workflow.
- Task này chưa kiểm thử concurrent workers, OCR, parser mới hoặc import toàn bộ
  sáu quyển.
