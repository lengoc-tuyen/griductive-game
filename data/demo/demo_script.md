# Kịch bản Quay Video Demo Sản phẩm — Mục 4.7 (10 điểm)

> **Lưu ý**: Tài liệu này dùng cho **Video Demo nộp bài chính thức (Mục 4.7)** sau khi nhánh Web GUI của Phần D (`origin/leekiet`) merge vào `main` và Phần C nối xong 2 API/nút `/api/hint` và `/api/auto_solve`.

---

## 1. Điều kiện tiên quyết trước khi bấm quay

1. **Code tích hợp trên nhánh nộp bài (`main`)**:
   - Đã có Web GUI mới nhất của Phần D (`frontend/gui/app.py`, `frontend/assets/`) cùng `main.py`.
   - Phần C đã gắn xong endpoint `POST /api/hint` và `POST /api/auto_solve` (hoặc `/api/step`) và nút tương ứng trên giao diện.
   - Chạy kiểm tra nhanh bộ dữ liệu trước khi quay:
     ```powershell
     python -m data.scripts.verify_puzzles
     python main.py
     ```
2. **Danh sách màn chơi gợi ý cho buổi quay**:
   - **Màn 1 (Chơi thủ công + Luật No-Guess)**: `data/puzzles/3x3/puzzle_3x3_ext_06.json` (gọn, đủ nhanh để giải tay hết bàn và có extension/advanced region).
   - **Màn 2 (Hint + Auto Solve + Extension)**: `data/puzzles/4x4/puzzle_4x4_ext_06.json` (hiển thị rõ `PARITY`, `COMPARE`, vùng nâng cao và nút Hint/Auto Solve).
   - **Màn 3 (Stress case 5×5)**: `data/puzzles/5x5/puzzle_5x5_ext_04.json` (chạy Auto Solve cho bảng 25 ô với biến phụ và nhiều mệnh đề).

---

## 2. Kịch bản quay chi tiết (Thời lượng mục tiêu: 6–8 phút | Quy định: 5–10 phút)

### Phân đoạn 1 — Giới thiệu & Giao diện Đồ họa (0:00 – 1:30 | 5 điểm)
- **Thao tác màn hình**:
  - Mở terminal chạy `python main.py`, cửa sổ trình duyệt tự mở giao diện Griductive.
  - Rê chuột giới thiệu bố cục: Logo/tiêu đề, đồng hồ đếm giờ, **nút chọn màn chơi (Select Puzzle)** liệt kê đủ $3\times 3$, $4\times 4$, $5\times 5$, nút **Load Custom JSON**, nút **Restart**, khu vực luật chơi, nút **Hint** và **Auto Solve**.
  - Chỉ vào lưới tọa độ cột chữ (`A, B, C...`) và hàng số (`1, 2, 3...`), thẻ mặt úp (tên theo alphabet, nghề nghiệp) và thẻ mặt ngửa ban đầu kèm clue.
- **Lời thuyết minh gợi ý**:
  - *"Xin chào thầy/cô và các bạn, đây là video demo đồ án Griductive Solver môn Nhập môn Trí tuệ Nhân tạo. Chương trình chạy giao diện Web kết nối Game Engine phía backend và Logic Agent dùng DPLL SAT Solver tự cài đặt..."*

### Phân đoạn 2 — Chơi thủ công & Kiểm chứng luật Không Đoán (1:30 – 4:00 | 2.5 điểm)
- **Thao tác màn hình**:
  1. Chọn màn `puzzle_3x3_ext_06`.
  2. Click vào **thẻ đã lật sẵn** $\rightarrow$ cho thấy tính năng **Highlight vùng tham chiếu của Clue** (ví dụ `corners`, `edges`, `between` hoặc `common_neighbors`).
  3. **Test `NOT_PROVABLE`**: Chọn 1 ô chưa có dữ kiện suy ra (đoán mò `CRIMINAL`/`INNOCENT`) $\rightarrow$ chỉ rõ thông báo từ chối **`NOT_PROVABLE`** (thẻ **không bị lật**, không lộ clue ẩn).
  4. **Test `CONTRADICTED`**: Chọn 1 ô đang bị ép `INNOCENT` (hoặc `CRIMINAL`) nhưng cố tình bấm ngược lại $\rightarrow$ chỉ rõ thông báo **`CONTRADICTED`** (thẻ vẫn giữ nguyên).
  5. **Test `ACCEPTED`**: Phán quyết đúng cho ô bị ép $\rightarrow$ xem hiệu ứng lật thẻ, đổi màu `INNOCENT`/`CRIMINAL`, và mở ra clue mới.
  6. Chơi tiếp các bước hoặc dùng chức năng **Restart** để chứng minh trạng thái quay về ban đầu.

### Phân đoạn 3 — Hint, Auto Solve & Stress Case 5×5 (4:00 – 6:30 | 2.5 điểm)
- **Thao tác màn hình**:
  1. Mở màn `puzzle_4x4_ext_06` ($4\times 4$ có `PARITY`, `COMPARE`, region nâng cao).
  2. Bấm **Hint** $\rightarrow$ chỉ rõ ô mà Agent tìm ra từ tri thức công khai + tập clue tối thiểu chứng minh cho ô đó được highlight.
  3. Bấm **Auto Solve** $\rightarrow$ để Agent tự động suy luận tuần tự từng bước không đoán đến khi giải xong toàn bộ bàn $4\times 4$ và hiển thị modal chiến thắng / trace.
  4. Chuyển sang màn `puzzle_5x5_ext_04` ($5\times 5$ — stress case 25 ô), bấm **Auto Solve** để chứng minh solver chạy nhanh và tìm đúng nghiệm duy nhất.
  5. *(Tùy chọn, ~30s)* Mở file `puzzle_4x4_ext_06.json` trong mục **Load Custom JSON** để demo tải file JSON từ ngoài vào.

### Phân đoạn 4 — Tổng kết (6:30 – 7:00)
- Tóm tắt lại các điểm đạt được: tách biệt `GameEngine` vs `LogicAgent`, mã hóa CNF tự động kèm extension, DPLL tự viết và bộ kiểm chứng/thực nghiệm đầy đủ. Cảm ơn thầy/cô.

---

## 3. Checklist Hậu kỳ & Nộp bài (Bắt buộc kiểm tra)

- [ ] Video dài đúng trong khoảng **5 đến 10 phút**.
- [ ] Có **thuyết minh giọng nói** hoặc **phụ đề** (tiếng Việt hoặc tiếng Anh) rõ ràng, dễ theo dõi.
- [ ] Upload lên **Google Drive** (**KHÔNG nộp link YouTube** theo quy định Mục 4.7).
- [ ] Bật chia sẻ **"Anyone with the link" $\rightarrow$ "Viewer"**.
- [ ] Mở link Google Drive trong **cửa sổ ẩn danh (Incognito)** chưa đăng nhập tài khoản Google để xác nhận xem được bình thường.
- [ ] Gắn link video demo vào file **`Report.pdf`** theo cấu trúc nộp bài Mục 5.
- [ ] **Quan trọng (Mục 5)**: Nếu trong `data/demo/` có file `.mp4` nặng, hãy xóa/di chuyển file `.mp4` tạm ra ngoài trước khi đóng gói `.zip` để giữ file nộp `StudentID1_StudentID2_...zip` gọn (dưới 20 MB nếu nộp trực tiếp).
