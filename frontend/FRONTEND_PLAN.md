# Kế hoạch Phân công & Đặc tả Kỹ thuật Phần Frontend (Phân hệ D)

Tài liệu này quy định kiến trúc, phân chia công việc và hợp đồng giao tiếp (API & JSON Contract) cho 2 thành viên phụ trách **Phân hệ D – Game Engine & Web GUI (Mục 4.1)**.

---

## 1. Tổng quan Kiến trúc & Phân vai

Dự án sử dụng kiến trúc **Python Web Application** (chạy local qua `python main.py`, tự động mở trình duyệt):
* **Người D1 – Lead & Python Web API / Game Engine (Bạn đảm nhận)**:
  * Chịu trách nhiệm đưa ra các quyết định thống nhất về dữ liệu và luồng hoạt động của game.
  * Xây dựng `GameEngine` (giữ lời giải ẩn & clue ẩn, kiểm tra phán quyết của người chơi), bộ chuyển đổi manh mối sang ngôn ngữ tự nhiên (`clue_renderer`), và cung cấp **RESTful JSON API** qua Web Server (`app.py`, `main.py`).
* **Người D2 – Giao diện Web Griductive (HTML / CSS / JS)**:
  * Xây dựng toàn bộ giao diện người dùng trên trình duyệt mô phỏng theo bản gốc **Knotwise Griductive** (https://knotwise.games/games/griductive), gọi các API JSON do D1 cung cấp để hiển thị bàn cờ, lật thẻ 3D, phán quyết `Innocent`/`Criminal` và highlight vùng manh mối.

*(Lưu ý: Phần Deduction Agent, Hint và Auto-Solve thuộc trách nhiệm của thành viên phụ trách **Phân hệ C (`algorithms/agent/`)** — xem hướng dẫn tích hợp ở Mục 6).*

---

## 2. Cấu trúc Thư mục & Quyền sở hữu File (Không đụng độ Git)

Hai thành viên D1 và D2 làm việc trên 2 tập file hoàn toàn độc lập:

```text
griductive-game/
├── main.py                          # [D1] Điểm khởi chạy chính -> bật Web Server & mở trình duyệt
└── frontend/
    ├── FRONTEND_PLAN.md             # Tài liệu đặc tả thống nhất này
    ├── engine/                      # [D1 Sở hữu 100%]
    │   ├── __init__.py
    │   ├── verdict.py               # [D1] Kiểu kết quả trả về cho Verdict (ACCEPTED / NOT_PROVABLE / CONTRADICTED)
    │   └── game_engine.py           # [D1] Quản lý puzzle, giữ lời giải ẩn, kiểm tra verdict
    ├── gui/                         # [D1 Sở hữu phần Python Server & Renderer]
    │   ├── __init__.py
    │   ├── clue_renderer.py         # [D1] Chuyển Clue -> câu tiếng Anh tự nhiên + danh sách ô highlight
    │   └── app.py                   # [D1] Web Server cung cấp API JSON & phục vụ file tĩnh
    └── assets/                      # [D2 Sở hữu 100% - Giao diện Web Knotwise]
        ├── index.html               # [D2] Khung trang chính, Modal phán quyết, Sidebar luật chơi
        ├── css/
        │   └── styles.css           # [D2] Bảng màu giấy ấm, 3D Flip Card, Highlight, Responsive Grid
        └── js/
            ├── api.js               # [D2] Các hàm fetch() gọi sang API của D1
            ├── avatars.js           # [D2] Bộ sinh Avatar SVG minh họa nhân vật
            ├── board.js             # [D2] Render lưới N×N, lật thẻ 3D, kính lúp highlight vùng clue
            └── main.js              # [D2] Xử lý nút Load, Restart, Mark, đồng hồ bấm giờ
```

---

## 3. Chi tiết Công việc của Người D1 (Python Engine, Clue Renderer & Web API)

Công việc của **D1** gồm 3 hạng mục chính:

### 3.1. `frontend/gui/clue_renderer.py` — Dịch Clue & Xác định vùng Highlight
Sử dụng các hàm có sẵn trong `algorithms/logic/models.py`, `algorithms/logic/clues.py`, và `algorithms/logic/regions.py`:
1. **`render_clue_text(clue: Clue, board: Board) -> str`**:
   * Chuyển cấu trúc `Clue` thành câu tiếng Anh tự nhiên để hiển thị trên mặt thẻ đã lật:
     * `FACT`: `"{person} is a criminal."` hoặc `"{person} is innocent."`.
     * `SAME`: `"{a} and {b} have the same status."`.
     * `DIFFERENT`: `"{a} and {b} have different statuses."`.
     * `EXACTLY` / `AT_LEAST` / `AT_MOST`:
       * Nếu `k == 0` (với `EXACTLY` hoặc `AT_MOST`): `"There are no criminals in {region_text}."`.
       * Ngược lại: `"Exactly {k} criminal(s) in {region_text}."`, `"At least {k} ..."`, `"At most {k} ..."`.
2. **`get_highlight_cells(clue: Clue, board: Board) -> list[str]`**:
   * Gọi trực tiếp `algorithms.logic.clues.referenced_cells(clue, board)` để lấy danh sách tọa độ các ô mà manh mối đó tham chiếu tới (sắp xếp theo thứ tự row-major).

### 3.2. `frontend/engine/verdict.py` & `frontend/engine/game_engine.py` — Bộ máy Game Engine
`GameEngine` là nơi **duy nhất** giữ lời giải ẩn (`solution`) và các manh mối chưa lật, đồng thời tuân thủ `EngineProtocol` trong `algorithms/agent/public_state.py`:

1. **Khởi tạo & Quản lý trạng thái**:
   * Đọc file JSON màn chơi (`id`, `size`, `characters`, `solution`, `initially_revealed`, `clues`).
   * Khởi tạo `self.board = Board.from_dict(puzzle)`.
   * Validate toàn bộ clue ngay khi nạp bằng `clues.validate(clue, self.board)`.
   * Giữ kín `self._solution: dict[str, Status]` và `self._clues_by_owner: dict[str, Clue]`.
2. **`restart() -> None`**:
   * Reset `self._proved` chỉ gồm các ô trong `initially_revealed` và `self._revealed_clues` chỉ gồm clue của các ô đó.
3. **`public_state() -> PublicState`**:
   * Trả về `PublicState(board=self.board, revealed_clues=tuple(self._revealed_clues), proved=dict(self._proved))`.
4. **`submit(cell: str, status: Status) -> tuple[VerdictResult, Optional[Clue]]`** và **`submit_verdict(cell, status) -> VerdictOutcome`**:
   * Gọi `check_verdict(self.public_state(), cell, status)` từ `algorithms.agent.entailment`. **Tuyệt đối không** dùng `self._solution` để cho phép đoán mò!
   * Nếu kết quả là `VerdictResult.ACCEPTED` (suy diễn được từ `PublicState` hiện tại):
     * Cập nhật `self._proved[cell] = status`, mở clue tại `cell` (nếu có) đưa vào `self._revealed_clues` và trả về clue vừa mở.
   * Nếu kết quả là `VerdictResult.NOT_PROVABLE` hoặc `VerdictResult.CONTRADICTED`:
     * Giữ nguyên trạng thái bàn cờ, trả về thông báo từ chối tương ứng.
5. **`serialize_state() -> dict`**:
   * Đóng gói dữ liệu bàn cờ và thẻ bài công khai hiện tại thành đúng chuẩn JSON ở Mục 4 để trả về cho Web UI.

### 3.3. `frontend/gui/app.py` & `main.py` — Web Server & REST API
* Dùng `ThreadingHTTPServer` chuẩn của Python phục vụ thư mục tĩnh `frontend/assets/` tại đường dẫn gốc `/` và mở các endpoint `/api/...`.
* Khi chạy `python main.py`:
  * Tự động nạp màn chơi mặc định.
  * Khởi chạy server tại `http://127.0.0.1:5000` và tự động mở trình duyệt.
  * Cung cấp trang `/dev` (D1 Test Console) để test trực tiếp API khi D2 chưa tạo `frontend/assets/index.html`.

---

## 4. Hợp đồng Giao tiếp JSON (API Contract Thống nhất giữa D1 và D2)

Mọi giao tiếp giữa giao diện Web (D2) và Server Python (D1) đều dùng JSON qua 5 endpoint cơ bản dưới đây:

### 4.1. Cấu trúc đối tượng `GameState` chuẩn (trả về trong mọi API)

```json
{
  "puzzle_id": "test_3x3_basic",
  "size": 3,
  "is_solved": false,
  "proved_count": 1,
  "total_cells": 9,
  "cards": [
    {
      "cell": "A1",
      "row": 1,
      "col": "A",
      "name": "Alice",
      "profession": "Cook",
      "is_revealed": false,
      "status": null,
      "clue_id": null,
      "clue_text": null,
      "highlight_cells": []
    },
    {
      "cell": "B2",
      "row": 2,
      "col": "B",
      "name": "Eve",
      "profession": "Clerk",
      "is_revealed": true,
      "status": "INNOCENT",
      "clue_id": "clue_B2",
      "clue_text": "There are no criminals in {A1, A2}.",
      "highlight_cells": ["A1", "A2"]
    }
  ]
}
```

### 4.2. Danh sách các Endpoint API của D1

| Method & URL | Dữ liệu gửi lên (Request Body) | Dữ liệu trả về (Response JSON) | Mô tả hành vi |
| :--- | :--- | :--- | :--- |
| **`GET /api/puzzles`** | *(Không có)* | `{"ok": true, "puzzles": [{"id": "test_3x3_basic", "name": "test_3x3_basic (3x3)", "size": 3, "path": "..."}]}` | Lấy danh sách các màn chơi có sẵn trong `data/puzzles/` và `fixtures/` để hiển thị trên thanh chọn màn chơi. |
| **`GET /api/state`** | *(Không có)* | `{"ok": true, "state": <GameState>}` | Lấy trạng thái bàn cờ hiện tại khi vừa mở trang web. |
| **`POST /api/load`** | `{"path": "..."}` hoặc `{"puzzle": {...}}` | `{"ok": true, "message": "...", "state": <GameState>}` | Nạp một màn chơi mới theo đường dẫn hoặc nội dung file JSON upload. |
| **`POST /api/restart`** | *(Không có)* | `{"ok": true, "message": "...", "state": <GameState>}` | Đưa màn chơi hiện tại về trạng thái ban đầu. |
| **`POST /api/verdict`** | `{"cell": "A1", "status": "INNOCENT"}` | `{"ok": true, "result": "ACCEPTED" \| "NOT_PROVABLE" \| "CONTRADICTED", "cell": "A1", "status": "INNOCENT", "message": "...", "revealed_clue": {...}, "state": <GameState>}` | Người chơi phán quyết 1 ô. Chỉ khi `result == "ACCEPTED"` thì thẻ mới lật trong `state`. |

---

## 5. Chi tiết Công việc của Người D2 (Giao diện Web chuẩn Knotwise Griductive)

Người D2 làm việc hoàn toàn trong thư mục `frontend/assets/`, sử dụng HTML5, CSS3 và Vanilla JavaScript để tái tạo trải nghiệm của https://knotwise.games/games/griductive:

### 5.1. Bố cục & Bảng màu chuẩn Knotwise (`styles.css` & `index.html`)
* **Bảng màu (CSS Variables)**:
  * Nền trang (`--bg-page`): `#F4F0E8` (màu giấy ấm)
  * Viền & chữ chính (`--ink`): `#262420`
  * Nền thẻ úp (`--card-down`): `#FAF7F2`
  * Thẻ Innocent (`--innocent-bg` / `--innocent-border`): nền `#EAF5EE`, viền `#22C55E`, nút `#38A169`
  * Thẻ Criminal (`--criminal-bg` / `--criminal-border`): nền `#FDE8E7`, viền `#E0564B`, nút `#E53E3E`
  * Viền Highlight vùng Clue (`--highlight-ring`): `#F59E0B` (vàng hổ phách) / `#3B82F6` (xanh dương)
* **Bố cục 3 phần**:
  1. **Header Bar**: Logo chữ có chân `Griductive`, Dropdown chọn màn chơi ($3\times 3, 4\times 4, 5\times 5$) + nút Upload file JSON (`Load`), đồng hồ bấm giờ `00:00`, nút `Restart`.
  2. **Sidebar Trái**: Tiêu đề game, thông tin màn chơi hiện tại và hướng dẫn ngắn **HOW TO PLAY**.
  3. **Khu vực Bàn cờ Trung tâm**: Lưới thẻ $N \times N$ tự co giãn theo `size` ($3, 4, 5$) và hàng nút bấm dạng viên thuốc có đổ bóng cứng (`box-shadow: 2px 2px 0 #262420`) nằm ngay dưới bàn cờ.

### 5.2. Thiết kế Thẻ 3D & Avatar (`board.js` & `avatars.js`)
* **Mặt trước (Khi thẻ đang úp - `is_revealed: false`)**:
  * Góc trên trái: Tọa độ `A1`, `B2`...
  * Góc trên phải: Ô màu ghi chú nhỏ (nếu người chơi dùng tính năng `Mark`).
  * Chính giữa: Avatar SVG tròn (tự sinh màu tóc/áo/da nhất quán theo tên nhân vật), bên dưới là **Tên nhân vật** in đậm và **Nghề nghiệp** (font monospace).
* **Mặt sau (Khi thẻ đã mở - `is_revealed: true`)**:
  * Hiệu ứng lật thẻ 3D mượt mà (`transform: rotateY(180deg)`).
  * Đổi màu nền và viền theo `status` (`INNOCENT` xanh mint / `CRIMINAL` đỏ coral).
  * Header thu gọn (avatar nhỏ + Tên + Nghề), phần thân giữa thẻ hiển thị `clue_text`.

### 5.3. Các luồng tương tác của D2 (`main.js` & `board.js`)
1. **Click vào thẻ đang úp $\rightarrow$ Mở Modal Phán quyết**:
   * Hiển thị Popup chính giữa màn hình với Avatar nhân vật, tọa độ, nghề nghiệp và câu hỏi *"Innocent or criminal?"*.
   * Khi bấm nút **Innocent** hoặc **Criminal**, gọi `POST /api/verdict`:
     * Nếu `result === "ACCEPTED"`: Đóng modal, chạy hiệu ứng lật thẻ 3D và hiển thị clue mới.
     * Nếu `result === "NOT_PROVABLE"`: Hiện thông báo từ chối *"NOT PROVABLE: Neither status is logically forced by current clues. Do not guess!"*.
     * Nếu `result === "CONTRADICTED"`: Báo lỗi đỏ *"CONTRADICTED: The opposite status is logically forced!"*.
2. **Click vào thẻ đã mở $\rightarrow$ Highlight vùng tham chiếu của Clue**:
   * Hiện icon kính lúp `🔍` trên thẻ đang chọn.
   * Lấy mảng `card.highlight_cells` để tô viền sáng nổi bật các ô nằm trong vùng của clue đó, đồng thời giảm độ mờ (`opacity: 0.45`) của các ô không liên quan. Click lại lần nữa để tắt highlight.
3. **Nút `Mark` (Ghi chú nháp)**:
   * Bật/tắt chế độ ghi chú nháp (click vào thẻ úp sẽ đổi màu chấm vuông góc thẻ qua 4 màu: Đỏ, Xanh lá, Vàng, Xanh dương).

---

## 6. Hướng dẫn dành cho Thành viên làm Agent / Hint / Auto-Solve (Phân hệ C)

`GameEngine` của D1 đã tuân thủ đầy đủ giao thức `EngineProtocol` (`public_state()`, `submit(cell, status)`, `restart()`). Khi thành viên phụ trách **Phân hệ C (`algorithms/agent/`)** muốn gắn chức năng `Hint` và `Auto Solve` lên Web:
1. Mở `frontend/gui/app.py` tại vị trí đánh dấu `# TODO [For C - Deduction Agent owner]`.
2. Thêm 2 hàm vào `GriductiveWebService`:
   * **Hint**: Gọi `algorithms.agent.hint.hint(self.engine.public_state())` để lấy `ForcedVerdict(cell, status)` và trả về qua route `POST /api/hint`.
   * **Auto-Solve / Step**: Truyền trực tiếp `self.engine` vào `DeductionAgent().run(self.engine)` (hoặc `next_forced(self.engine.public_state())` + `self.engine.submit(...)`) và trả về qua route `POST /api/auto_solve` (hoặc `POST /api/step`).
