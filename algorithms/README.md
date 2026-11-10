# `algorithms/` — Hướng dẫn cách làm & triển khai

Tài liệu này giải thích **toàn bộ** phần lõi thuật toán của Griductive Solver: ý tưởng, luồng dữ liệu, và cách từng hàm được cài đặt. Đọc theo thứ tự từ trên xuống là nắm được cả hệ thống.

> Phạm vi: bản **cơ bản** đủ để game chơi được (4.2 lõi, 4.3, 4.4 lõi). Phần nâng cao (extensions, evaluator, uniqueness, trace đầy đủ, …) liệt kê ở [mục 8](#8-những-gì-còn-để-lại).

---

## Mục lục

1. [Bức tranh tổng thể](#1-bức-tranh-tổng-thể)
2. [Phase 0 — Hợp đồng dữ liệu (`models.py`, `public_state.py`)](#2-phase-0--hợp-đồng-dữ-liệu)
3. [Phase 1 — Logic & CNF (`logic/`)](#3-phase-1--logic--cnf-logic)
4. [Phase 2 — DPLL SAT solver (`sat/`)](#4-phase-2--dpll-sat-solver-sat)
5. [Phase 3 — Agent suy luận (`agent/`)](#5-phase-3--agent-suy-luận-agent)
6. [Ví dụ chạy tay trên puzzle 3×3](#6-ví-dụ-chạy-tay-trên-puzzle-33)
7. [Test (`tests/`)](#7-test-tests)
8. [Những gì còn để lại](#8-những-gì-còn-để-lại)
9. [Câu hỏi vấn đáp hay gặp](#9-câu-hỏi-vấn-đáp-hay-gặp)

---

## 1. Bức tranh tổng thể

### Ý tưởng cốt lõi

Mỗi người `i` ứng với **một biến mệnh đề** `C_i` (True = Criminal, False = Innocent). Mỗi clue đã lộ là một công thức logic về các biến đó. Gom lại thành knowledge base `KB_t`.

Một verdict chỉ được chấp nhận khi nó **đúng trong mọi model** của `KB_t` (logical consequence), không phải chỉ đúng trong *một* model. Kiểm tra bằng **phản chứng**:

```
KB ⊨ C_i    ⇔  KB ∧ ¬C_i  là UNSAT   → CRIMINAL
KB ⊨ ¬C_i   ⇔  KB ∧ C_i   là UNSAT   → INNOCENT
cả hai SAT                            → UNKNOWN
KB tự nó UNSAT                        → INCONSISTENT
```

Vậy chỉ cần một **SAT solver** (DPLL) + một bộ **chuyển clue → CNF** là đủ suy luận.

### Luồng dữ liệu

```
          ┌──────────────── GameEngine (D, frontend/) ────────────────┐
          │  giữ: lời giải ẩn + clue chưa lộ                           │
          │  public_state() ──► PublicState  (board, clue đã lộ, verdict đã chứng minh)
          │  submit(cell, status) ◄── verdict                          │
          └───────────────────────────────┬───────────────────────────┘
                                          │ PublicState (chỉ thông tin công khai)
                                          ▼
 agent/knowledge_base.build_kb ──► logic/encoder.CNFEncoder ──► list[list[int]]  (CNF)
          │                               │
          │                               ├─ logic/clues.validate     (kiểm tham số)
          │                               ├─ logic/regions.resolve    (vùng → danh sách ô)
          │                               ├─ logic/variable_map       (ô → số biến)
          │                               └─ logic/cardinality        (đếm → mệnh đề)
          ▼
 agent/entailment.classify ──► sat/dpll.solve(KB, assumptions=[±v])  ──► SAT / UNSAT
          │
          ▼
 agent/deduction_agent (Auto Solve) · agent/hint (Hint) · entailment.check_verdict (Engine phán verdict)
```

### Quy ước chung

| Khái niệm | Quy ước |
|---|---|
| Ô (cell) | chuỗi `"C2"` = cột C, hàng 2. Cột đánh chữ từ trái, hàng đánh số từ trên |
| Row-major | A1, B1, C1, A2, B2, … (đi hết hàng 1 rồi tới hàng 2) |
| Biến | số nguyên dương. Ô thứ `i` theo row-major ↦ biến `i` (bắt đầu từ 1) |
| Literal | `+v` = ô của `v` là CRIMINAL, `-v` = INNOCENT (giống DIMACS) |
| Clause | `list[int]` — OR của các literal. Ví dụ `[1, -3]` = `C_1 ∨ ¬C_3` |
| CNF | `list[list[int]]` — AND của các clause |

Toàn bộ dùng thư viện chuẩn Python 3, không phụ thuộc gì thêm.

---

## 2. Phase 0 — Hợp đồng dữ liệu

### 2.1 `logic/models.py`

File được **mọi phần** import, nên chốt đầu tiên.

| Thành phần | Vai trò |
|---|---|
| `Status` (enum `CRIMINAL`/`INNOCENT`) | trạng thái của một người. `.opposite` cho trạng thái ngược lại. Kế thừa `str` nên so sánh/serialize JSON dễ |
| `ClueType` (enum 6 loại) | `FACT, SAME, DIFFERENT, EXACTLY, AT_LEAST, AT_MOST`. `COUNTING_TYPES` = 3 loại đếm |
| `parse_cell("C2") → (2, 1)` | dùng regex `^([A-Z])([1-9][0-9]*)$`; trả chỉ số **0-based** (cột, hàng) |
| `make_cell(2, 1) → "C2"` | hàm ngược |
| `Character(name, profession, cell)` | một nhân vật |
| `Board(size, characters)` | thông tin **tĩnh, công khai**: kích thước + ai ngồi đâu. **Không** chứa status hay clue → đưa cho agent an toàn |
| `Clue(id, owner, type, params)` | một clue có cấu trúc; `owner` = ô của lá bài mang clue |

**`Board.__post_init__`** kiểm tra ngay khi tạo: size trong [1, 26]; mỗi ô nằm trong lưới; không trùng ô, không trùng tên; đủ `size²` nhân vật. Đồng thời dựng 2 dict tra cứu `_by_cell`, `_by_name` để các hàm sau chạy O(1):

- `cells()` – mọi ô theo row-major.
- `cell_of(name)` – tên → ô.
- `ref_to_cell(ref)` – nhận **ô hoặc tên** đều được (clue có thể ghi `"of": "Hank"` hay `"of": "C2"`).
- `row_major_key(cell)` – khoá sắp xếp `(hàng, cột)`.

**Format `params` của clue** (cũng ghi trong docstring file):

| type | params |
|---|---|
| FACT | `{"person": "Abel", "status": "CRIMINAL"}` |
| SAME / DIFFERENT | `{"a": "Abel", "b": "Bea"}` |
| EXACTLY / AT_LEAST / AT_MOST | `{"region": <Region>, "k": 2}` |

Region: `{"kind":"row","row":2}`, `{"kind":"col","col":"B"}`, `{"kind":"neighbors","of":"C2"}`, `{"kind":"cells","cells":["A1","B3"]}`.

`from_dict` / `to_dict` để E đọc/ghi JSON.

### 2.2 `agent/public_state.py` — ranh giới Engine ↔ Agent

Đề yêu cầu tách 2 vai: **Game Engine** giữ lời giải; **Logic Agent** chỉ thấy thông tin công khai. File này hiện thực ranh giới đó.

- **`PublicState(board, revealed_clues, proved)`** – frozen dataclass. `proved` là `dict[cell, Status]`.
  - `unresolved_cells()` – ô chưa có verdict, row-major (đây là thứ tự agent quét → "chọn xác định").
  - `is_solved()` – đã có đủ `size²` verdict.
- **`VerdictResult`** – `ACCEPTED / NOT_PROVABLE / CONTRADICTED`.
- **`EngineProtocol`** – interface (`typing.Protocol`) mà D cài:
  - `public_state() -> PublicState`
  - `submit(cell, status) -> (VerdictResult, Clue | None)` — nếu ACCEPTED thì lật bài và trả clue mới.

Agent **chỉ** nhận object có 2 method này → về mặt cấu trúc code, nó không thể đọc lời giải ẩn.

---

## 3. Phase 1 — Logic & CNF (`logic/`)

### 3.1 `regions.py` — vùng → danh sách ô

`resolve(region, board) -> list[cell]` tra bảng `_RESOLVERS[kind]` rồi gọi hàm tương ứng. Kết quả luôn **sắp row-major, không trùng**.

| kind | Cách làm |
|---|---|
| `row` | kiểm `1 ≤ row ≤ size`; sinh `make_cell(c, row-1)` cho mọi cột |
| `col` | kiểm chữ cái trong `A..`; sinh mọi hàng của cột đó |
| `neighbors` | `neighbors_of(cell)`: duyệt `dr, dc ∈ {-1,0,1}`, **bỏ (0,0)** (không tính chính ô đó), bỏ ô ra ngoài lưới → ô giữa có 8, ô biên 5, ô góc 3 |
| `cells` | đổi từng phần tử qua `ref_to_cell`; báo lỗi nếu trùng hoặc rỗng |

Lỗi → `RegionError`. `register_region(kind, fn)` là "móc" để extension thêm vùng mới (góc, biên, giữa hai người, …) mà không sửa code cũ.

### 3.2 `clues.py` — kiểm tra tham số

`referenced_cells(clue, board)` vừa **validate** vừa trả các ô mà clue nhắc tới (GUI của D dùng để highlight khi người chơi chọn clue). `validate()` chỉ gọi nó và bỏ kết quả.

- Kiểm `owner` có trên lưới.
- FACT: tên tồn tại, `status` hợp lệ.
- SAME/DIFFERENT: hai tên tồn tại **và khác nhau**.
- Đếm: region resolve được; `k` là `int` (không phải `bool` — vì trong Python `True` là `int`!) và `0 ≤ k ≤ |R|`.

Lỗi → `ClueValidationError` có kèm `clue.id` để dễ dò.

### 3.3 `variable_map.py` — ô ↔ biến

`VariableMap(board)` duyệt `board.cells()` (row-major), gán biến `1, 2, …, n²`. Với 3×3: A1=1, B1=2, C1=3, A2=4, B2=5, C2=6, A3=7, B3=8, C3=9.

- `var(cell)`, `var_of_name(name)`, `cell(var)`.
- **Biến phụ** (cho encoding nâng cao sau này) cấp bằng `new_aux()` bắt đầu từ `n²+1` → luôn tách khỏi biến chính như đề yêu cầu. `num_primary`, `num_aux`, `num_vars` để báo cáo số liệu.

Ánh xạ **xác định**: cùng board → luôn cùng số biến.

### 3.4 `cardinality.py` — ràng buộc đếm → CNF

Dùng **mã hoá tổ hợp trực tiếp** (direct/binomial encoding), không cần biến phụ. Với các literal `x_1..x_n`:

**At most k** — "không có k+1 người nào cùng là criminal":
```
với mọi tập con S, |S| = k+1:   ∨_{x∈S} ¬x
```
**At least k** — "trong mọi nhóm n−k+1 người, có ít nhất một criminal" (nếu không thì số criminal ≤ k−1):
```
với mọi tập con S, |S| = n−k+1:  ∨_{x∈S} x
```
**Exactly k** = at_most(k) ∧ at_least(k).

Cài bằng `itertools.combinations`. Trường hợp biên: `at_most` với `k ≥ n` → `[]` (luôn đúng); `at_least` với `k ≤ 0` → `[]`; `k` không thể đạt → `[[]]` (clause rỗng = luôn sai).

**Ví dụ dẫn xuất (dùng cho report)** — `EXACTLY(1, row 1)` trên 3×3, biến A1=1, B1=2, C1=3:
```
at_most(1):  tập con cỡ 2 → (¬1 ∨ ¬2) (¬1 ∨ ¬3) (¬2 ∨ ¬3)
at_least(1): tập con cỡ 3 → (1 ∨ 2 ∨ 3)
⇒ 4 clause, 0 biến phụ
```
Số clause: `at_most` = C(n, k+1), `at_least` = C(n, n−k+1). Với region bắt buộc (hàng/cột ≤ 5, hàng xóm ≤ 8) tối đa C(8,4) = 70 → chấp nhận được.

### 3.5 `encoder.py` — clue → CNF

`CNFEncoder(board)` giữ một `VariableMap` và bảng `_handlers[ClueType]`:

| Clue | CNF | Lý do |
|---|---|---|
| FACT(p, CRIMINAL) | `[C_p]` | unit literal |
| FACT(p, INNOCENT) | `[¬C_p]` | |
| SAME(a, b) | `(¬a ∨ b) ∧ (a ∨ ¬b)` | `a ↔ b` = `(a→b) ∧ (b→a)` |
| DIFFERENT(a, b) | `(a ∨ b) ∧ (¬a ∨ ¬b)` | `a ⊕ b`: ít nhất một đúng, không cả hai |
| EXACTLY / AT_LEAST / AT_MOST(R, k) | `cardinality.*(vars(R), k)` | |

**Dẫn xuất SAME (cho report):** `a ↔ b ≡ (a → b) ∧ (b → a) ≡ (¬a ∨ b) ∧ (¬b ∨ a)`.
**Dẫn xuất DIFFERENT:** `a ⊕ b ≡ (a ∨ b) ∧ ¬(a ∧ b) ≡ (a ∨ b) ∧ (¬a ∨ ¬b)`.

Hàm public:
- `encode_clue(clue)` – **validate trước** rồi mới encode.
- `encode_verdict(cell, status)` – verdict đã chứng minh → unit clause `[v]` / `[-v]`.
- `encode(clues, proved)` → `EncodedCNF(clauses, num_primary, num_aux, clause_origin)`. `clause_origin[i]` ghi clause `i` sinh từ clue nào (hoặc `"verdict:B2"`) — sau này dùng cho trace/hint giải thích.

Không có CNF nào viết tay cho từng puzzle: mọi thứ sinh tự động từ clue (đúng yêu cầu 3.3).

---

## 4. Phase 2 — DPLL SAT solver (`sat/`)

### 4.1 `cnf.py`

- `normalize(clauses)` – bỏ literal trùng trong clause, **bỏ clause tautology** (chứa cả `x` và `¬x`, luôn đúng), phát hiện clause rỗng (→ UNSAT ngay). Từ chối literal `0`.
- `max_var`, `to_dimacs`, `from_dimacs` – xuất/nhập định dạng DIMACS chuẩn (`p cnf <vars> <clauses>`, mỗi clause kết thúc bằng `0`) để debug hoặc so với solver khác.

### 4.2 `stats.py`

`SolverStats`: `decisions`, `propagations`, `backtracks`, `conflicts`, `runtime`; `merge()` cộng dồn qua nhiều lần gọi (agent cần tổng).

### 4.3 `heuristics.py`

`lowest_index(clauses, assignment)` – biến **chưa gán có chỉ số nhỏ nhất** xuất hiện trong một clause **chưa thoả**. Xác định (cùng input → cùng lựa chọn), đúng yêu cầu "deterministic variable selection". Bỏ qua biến chỉ nằm trong clause đã thoả → không rẽ nhánh vô ích.

### 4.4 `dpll.py` — thuật toán chính

```
DPLL(assignment):
    UNIT-PROPAGATE(assignment)          # có thể phát hiện xung đột
    if conflict: return FAIL
    v ← biến chọn theo heuristic
    if không còn biến (mọi clause đã thoả): return assignment
    for value in (True, False):          # decision
        r ← DPLL(assignment ∪ {v = value})
        if r ≠ FAIL: return r
        backtracks += 1
    return FAIL
```

**Unit propagation (`_propagate`)** — lặp tới khi không còn thay đổi; mỗi vòng quét mọi clause và với mỗi clause đếm:
- có literal đúng → clause thoả, bỏ qua;
- **0** literal chưa gán (và không có literal đúng) → mọi literal sai → **xung đột** (`conflicts += 1`, ném `_Conflict`);
- **đúng 1** literal chưa gán → literal đó **bắt buộc** đúng → gán, `propagations += 1`.

**Backtracking** cài bằng cách **copy assignment** cho mỗi nhánh (`dict(assignment)`): nhánh thất bại thì bản copy bị bỏ, assignment của tầng trên còn nguyên → không cần undo-trail. Đơn giản, đúng, đủ nhanh cho ≤ 25 biến.

**`solve(assumptions)`**:
1. Clause rỗng sẵn → UNSAT.
2. Gán trước các literal trong `assumptions` (vd. `[-v]` để hỏi `KB ∧ ¬C_v`); nếu assumptions tự mâu thuẫn (`3` và `-3`) → UNSAT.
3. Gọi `_search`, đo `time.perf_counter()`.
4. SAT → trả **model đầy đủ** trên `1..num_vars` (biến không xuất hiện/không cần gán → `False`).

Trả `SolveResult(status, model, stats)`. Dùng assumptions thay vì sửa CNF → **một** solver dùng lại cho nhiều câu hỏi trên cùng KB.

Đếm số liệu theo định nghĩa:
- *decision* = mỗi lần gán thử một giá trị cho biến rẽ nhánh (kể cả nhánh thứ hai);
- *propagation* = mỗi literal được unit propagation ép;
- *backtrack* = mỗi nhánh bị huỷ do dẫn tới xung đột.

---

## 5. Phase 3 — Agent suy luận (`agent/`)

### 5.1 `knowledge_base.py`

`build_kb(state)`:
```
KB_t = encode(state.revealed_clues, state.proved)
     = CNF(clue đã lộ) ∧ unit clause cho mọi verdict đã chứng minh
```
Chỉ đọc từ `PublicState` → lời giải ẩn & clue chưa lộ **không thể** lọt vào.

`KnowledgeBase`:
- `query(assumptions)` – **mọi** lời gọi SAT đi qua đây → đếm `sat_calls`, cộng dồn `stats`, lưu `queries` (assumptions, kết quả). Solver được tạo **lười** một lần và tái sử dụng.
- `is_consistent()` – `query()` không assumption, **cache** kết quả (chỉ hỏi 1 lần mỗi KB).
- `num_primary`, `num_aux`, `num_clauses` – số liệu cho thực nghiệm 4.5.

### 5.2 `entailment.py`

**`classify(kb, cell)`**:
```python
if not kb.is_consistent():  return INCONSISTENT     # KB UNSAT
v = var(cell)
if not kb.query([-v]).is_sat: return CRIMINAL       # KB ∧ ¬C UNSAT
if not kb.query([ v]).is_sat: return INNOCENT       # KB ∧ C UNSAT
return UNKNOWN
```
Tối đa 2 lời gọi SAT / ô (+1 kiểm consistency dùng chung cho cả KB). Nếu KB nhất quán thì không thể cả hai cùng UNSAT, nên thứ tự kiểm không ảnh hưởng.

`Classification.status` đổi CRIMINAL/INNOCENT → `Status`, còn lại → `None`.

**`classify_all(kb)`** – phân loại mọi ô chưa giải (row-major).

**`check_verdict(state, cell, status)`** — hàm **Engine của D gọi** khi người chơi bấm verdict:
- ô đã có verdict → so trực tiếp;
- ngược lại `forced = classify(build_kb(state), cell).status`:
  - `None` (UNKNOWN / INCONSISTENT) → `NOT_PROVABLE`
  - trùng `status` → `ACCEPTED`
  - ngược → `CONTRADICTED`

Lưu ý: Engine phán verdict dựa trên **suy diễn từ thông tin công khai**, không so với lời giải. Vì puzzle hợp lệ có nghiệm duy nhất, verdict đã suy ra được thì chắc chắn trùng lời giải.

### 5.3 `deduction_agent.py` — vòng lặp suy luận (Auto Solve)

**`find_forced(kb)`** – quét `unresolved_cells()` theo row-major, trả `ForcedVerdict(cell, status)` **đầu tiên** bị ép; không có → `None`; KB mâu thuẫn → `ValueError`. Đây là "chọn xác định, không bao giờ đoán".

**`next_forced(state)`** = `find_forced(build_kb(state))`.

**`DeductionAgent.run(engine)`**:
```
loop:
    state ← engine.public_state()
    if state.is_solved():                → SOLVED
    if đạt max_steps:                    → STEP_LIMIT
    kb ← build_kb(state)                 # ghi max số biến / clause
    forced ← find_forced(kb)             # KB UNSAT → INCONSISTENT
    if forced is None:                   → STUCK   (không đoán!)
    result, clue ← engine.submit(forced) # engine lật bài, trả clue mới
    if result ≠ ACCEPTED:                → REJECTED (chỉ xảy ra khi có bug / puzzle sai)
    ghi Step(index, cell, verdict, active_clue_ids, sat_calls, revealed_clue_id)
```
Mỗi bước **dựng lại KB** từ public state mới (đơn giản, chắc chắn không lẫn trạng thái cũ). Kết quả `AgentRun` chứa outcome, danh sách `Step` (trace cơ bản), tổng `sat_calls`, `stats` cộng dồn, max số biến chính/phụ/clause → đủ cột cho bảng thực nghiệm 4.5.

### 5.4 `hint.py`

`hint(state)` = `next_forced(state)`: trả ô + verdict có thể chứng minh ngay; không có → `None`; KB mâu thuẫn → `ValueError`. Chỉ dùng public state, không đọc lời giải (đúng 4.4).

---

## 6. Ví dụ chạy tay trên puzzle 3×3

Fixture: [`tests/fixtures/puzzle_3x3_basic.json`](tests/fixtures/puzzle_3x3_basic.json)

```
      A          B          C
1  Alice(I)   Dan(C)     Gina(I)
2  Bob(I)     Eve(I)*    Hank(C)
3  Cara(C)    Finn(I)    Ivy(I)        * = lật sẵn từ đầu
```

| Ô | Clue |
|---|---|
| B2 | AT_MOST(0, {A1, A2}) — A1, A2 đều vô tội |
| A1 | EXACTLY(1, row 1) |
| A2 | FACT(Gina, INNOCENT) |
| B1 | EXACTLY(1, row 2) |
| C1 | EXACTLY(1, col C) |
| C2 | SAME(Finn, Ivy) |
| B3 | AT_LEAST(1, col A) |
| A3 | AT_MOST(1, col A) |
| C3 | AT_MOST(2, neighbors of C3) |

Agent chạy (`DeductionAgent().run`) — 8 bước:

| Bước | KB có (ngoài verdict) | Ô bị ép đầu tiên (row-major) | Lý do | Clue lật ra |
|---|---|---|---|---|
| 1 | B2 | **A1 = I** | AT_MOST(0,{A1,A2}) | EXACTLY(1,row1) |
| 2 | B2, A1 | **A2 = I** | cùng clue B2 (B1 vẫn UNKNOWN: B1 hay C1?) | FACT(Gina=I) |
| 3 | + A2 | **B1 = C** | row1 đúng 1 criminal, A1=I, C1=I | EXACTLY(1,row2) |
| 4 | + B1 | **C1 = I** | FACT | EXACTLY(1,col C) |
| 5 | + C1 | **C2 = C** | row2: A2=I, B2=I ⇒ C2 | SAME(Finn,Ivy) |
| 6 | + C2 | **B3 = I** | col C đúng 1 = C2 ⇒ C3=I; SAME ⇒ B3=I (A3 vẫn UNKNOWN) | AT_LEAST(1,col A) |
| 7 | + B3 | **A3 = C** | col A ≥ 1, A1=A2=I | AT_MOST(1,col A) |
| 8 | + A3 | **C3 = I** | col C | — |

→ `SOLVED`, khớp lời giải. Bước 2 minh hoạ "không đoán": B1 chưa được chứng minh nên agent bỏ qua, chọn A2.

Ví dụ một truy vấn (bước 3, ô B1 = biến 2): `KB ∧ ¬C_2` → unit propagation: A1=I, C1=I (từ verdict/FACT), `(1∨2∨3)` còn 1 literal… đều sai → **xung đột** → UNSAT ⇒ B1 CRIMINAL.

---

## 7. Test (`tests/`)

Chạy (dùng `unittest` có sẵn, không cần cài pytest):

```bash
python -m unittest discover -s algorithms/tests -t .
```

| File | Kiểm gì |
|---|---|
| `helpers.py` | `load_fixture`; **`FakeEngine`** cài `EngineProtocol` tối giản (dùng `check_verdict` + assert verdict đúng lời giải) — mẫu tham khảo cho D; `brute_force_models` liệt kê mọi model (công thức nhỏ) |
| `test_regions.py` | parse/make cell, row-major, row/col/neighbors (ô giữa 8, góc 3, theo tên), cells; region & clue sai đều báo lỗi |
| `test_encoder.py` | **cardinality so với vét cạn** (n = 0..5, mọi k, mọi assignment); CNF của SAME/DIFFERENT/FACT/verdict; toàn bộ clue + ô lật sẵn có **đúng 1 model** = lời giải |
| `test_dpll.py` | công thức rỗng, clause rỗng, `x ∧ ¬x`, ví dụ mục 3.4 của đề, đếm propagation, assumptions mâu thuẫn, pigeonhole 3→2 (UNSAT, có backtrack), tính xác định, **300 công thức ngẫu nhiên so với vét cạn** (kèm kiểm model thật sự thoả), DIMACS round-trip |
| `test_agent.py` | phân loại ban đầu, `check_verdict` ra đủ 3 kết quả, verdict bị từ chối không đổi state, INCONSISTENT (SAME + DIFFERENT cùng cặp), hint, KB rỗng không ép gì, Auto Solve giải đúng 8 bước, STUCK khi bỏ clue then chốt, STEP_LIMIT |

Lưu ý khi làm fixture: **status của ô lật sẵn là một phần của KB**. Bỏ nó đi thì bộ clue trên có 2 nghiệm (test từng bắt được lỗi này).

---

## 8. Những gì còn để lại

| Hạng mục | Mục đề | Ghi chú |
|---|---|---|
| ≥ 2 extension (`logic/extensions.py`) | 3.2 | thêm handler vào `CNFEncoder._handlers` và/hoặc `regions.register_region` |
| Evaluator ngữ nghĩa (`logic/evaluator.py`) + test chéo | 4.2 | **bắt buộc** — cho assignment đầy đủ, tính clue đúng/sai trực tiếp, so với CNF |
| Uniqueness check (`agent/uniqueness.py`) | 4.4 | giải toàn bộ clue → có model M → thêm clause chặn M → giải lại phải UNSAT |
| Trace đầy đủ (`agent/trace.py`) | 4.4 | đã có `KnowledgeBase.queries` + `clause_origin` làm nguyên liệu |
| Hint kèm clue liên quan | 4.1 | vd. bỏ dần từng clue xem verdict còn được ép không |
| Encoding có biến phụ (sequential counter) | 3.3 | cho region lớn; dùng `VariableMap.new_aux()` |
| Watched literals / heuristic khác / pure literal | 4.3 | tối ưu, không bắt buộc |

---

## 9. Câu hỏi vấn đáp hay gặp

**Vì sao không lấy luôn model SAT tìm được làm đáp án?** Một model chỉ là *một* khả năng. Verdict phải đúng trong *mọi* model ⇒ phải chứng minh phủ định là UNSAT.

**Vì sao cần kiểm `KB` UNSAT riêng?** KB mâu thuẫn thì `KB ∧ ¬C` và `KB ∧ C` đều UNSAT ⇒ "chứng minh" được mọi thứ. Phải bắt trường hợp này trước, trả INCONSISTENT.

**Agent có "nhìn trộm" lời giải không?** Không. Nó chỉ nhận object có `public_state()` / `submit()`; KB dựng từ `PublicState`, mà `PublicState` không chứa lời giải hay clue chưa lộ.

**Tại sao chọn mã hoá tổ hợp trực tiếp?** Region bắt buộc nhỏ (≤ 8 ô), không sinh biến phụ, dễ dẫn xuất trong report. Nhược điểm: số clause tăng theo tổ hợp với region lớn.

**DPLL backtrack thế nào?** Mỗi nhánh làm trên bản copy của assignment; nhánh thất bại thì bỏ bản copy và thử giá trị còn lại; cả hai thất bại thì trả FAIL lên tầng trên.

**Sao chọn row-major?** Đề cho phép chọn xác định bất kỳ (gợi ý row-major); trùng với thứ tự đánh số biến nên trace dễ đọc.
