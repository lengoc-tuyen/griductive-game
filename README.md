# griductive-game

Griductive Solver (CSC14003 – Project 2): game suy luận lưới, giải bằng logic mệnh đề + CNF + DPLL tự cài.

## Cấu trúc thư mục & phân công

```
griductive-game/
├── main.py                      # entry point → mở GUI
├── requirements.txt
│
├── algorithms/                  # A + B + C
│   ├── logic/                   # [A] Logic & CNF (4.2)
│   │   ├── models.py            #   Cell, Status, Clue — kiểu dữ liệu dùng chung
│   │   ├── regions.py           #   row / column / neighbors / explicit (+ region nâng cao)
│   │   ├── clues.py             #   6 clue core + validate tham số/region
│   │   ├── extensions.py        #   ≥ 2 extension (parity, so sánh vùng, ...)
│   │   ├── variable_map.py      #   map nhân vật → C_i, biến phụ tách riêng
│   │   ├── cardinality.py       #   at_least / at_most / exactly → CNF
│   │   ├── encoder.py           #   clue → clauses, đếm biến/mệnh đề
│   │   └── evaluator.py         #   evaluator ngữ nghĩa (test chéo, không dùng CNF)
│   ├── sat/                     # [B] DPLL SAT solver (4.3)
│   │   ├── cnf.py               #   container CNF (+ DIMACS)
│   │   ├── dpll.py              #   unit propagation, conflict, branching, backtrack, assumptions
│   │   ├── heuristics.py        #   chọn biến xác định (+ pure literal tùy chọn)
│   │   └── stats.py             #   decisions / propagations / backtracks / runtime
│   ├── agent/                   # [C] Deduction agent (4.4) — tích hợp A + B
│   │   ├── public_state.py      #   view công khai Engine đưa cho agent
│   │   ├── knowledge_base.py    #   KB_t = CNF(clue đã lộ) ∧ unit clauses
│   │   ├── entailment.py        #   CRIMINAL / INNOCENT / UNKNOWN / INCONSISTENT
│   │   ├── deduction_agent.py   #   vòng lặp suy luận
│   │   ├── uniqueness.py        #   kiểm tra nghiệm duy nhất
│   │   ├── hint.py              #   Hint (không đọc lời giải ẩn)
│   │   └── trace.py             #   deduction trace
│   └── tests/
│       ├── test_regions.py               # [A]
│       ├── test_encoder_vs_evaluator.py  # [A]
│       ├── test_dpll.py                  # [B]
│       └── test_agent.py                 # [C]
│
├── frontend/                    # [D] Game & GUI (4.1)
│   ├── engine/
│   │   ├── game_engine.py       #   giữ lời giải + clue ẩn, xử lý verdict
│   │   └── verdict.py           #   ACCEPTED / NOT_PROVABLE / CONTRADICTED
│   ├── gui/
│   │   ├── app.py               #   cửa sổ chính
│   │   ├── board_view.py        #   lưới + tọa độ hàng/cột
│   │   ├── card_widget.py       #   1 thẻ: tên, nghề, status, clue, highlight
│   │   ├── controls.py          #   Load / Restart / Hint / Auto Solve / CRIMINAL / INNOCENT
│   │   ├── clue_renderer.py     #   clue → câu tiếng tự nhiên + ô cần highlight
│   │   └── messages.py          #   thông báo NOT_PROVABLE / CONTRADICTED, trace
│   └── assets/
│
└── data/                        # [E] Dữ liệu & thực nghiệm (4.5, 4.7)
    ├── schema.md                #   định dạng JSON của puzzle
    ├── puzzle_loader.py         #   đọc/ghi JSON → Puzzle
    ├── puzzles/{3x3,4x4,5x5}/   #   bộ puzzle nghiệm duy nhất
    ├── scripts/
    │   ├── verify_puzzles.py    #   kiểm tra duy nhất nghiệm + giải được không đoán
    │   ├── run_experiments.py   #   đo số liệu, ghi cả failure/timeout
    │   └── plot_results.py      #   bảng / biểu đồ
    ├── results/                 #   CSV kết quả
    ├── figures/                 #   biểu đồ cho report
    └── demo/                    #   tài liệu video demo
```

## Ranh giới giữa các phần

- **A → mọi người**: `algorithms/logic/models.py` (Cell, Status, Clue) là hợp đồng chung — chốt sớm nhất.
- **A ↔ E**: format clue trong `data/schema.md` phải khớp `models.py`.
- **B**: chỉ nhận/trả CNF dạng `list[list[int]]`, không biết gì về game.
- **C**: chỉ nhận `PublicState` từ Engine, **không** được đọc lời giải ẩn hay clue chưa lộ.
- **D**: `GameEngine` là nơi duy nhất giữ lời giải; GUI gọi agent cho Hint / Auto Solve và để kiểm tra verdict.

## Cài đặt & chạy

Chỉ dùng thư viện chuẩn của Python (≥ 3.9); GUI dùng `tkinter`
(macOS + Homebrew: `brew install python-tk`).

```bash
python -m unittest discover -s algorithms/tests -t .                 # toàn bộ test A + B + C
python -m algorithms.tools.manual_gui [path/to/puzzle.json]           # GUI dev để test thuật toán
```

## Phần thuật toán (A + B + C) — tóm tắt

- **Clue**: 6 loại core + 2 extension `PARITY` (chẵn/lẻ, XOR chain có biến phụ) và
  `COMPARE` (so sánh số criminal giữa 2 vùng, unary counter có biến phụ) + region nâng cao
  `corners`, `edges`, `between`, `common_neighbors`. Mọi clue đếm có thể đếm innocent bằng
  `"counts": "INNOCENT"`. `evaluator.py` kiểm tra ngữ nghĩa trực tiếp, test chéo với encoder
  trên mọi assignment 3×3.
- **DPLL**: two-watched-literals + trail (không copy assignment), chọn biến theo thứ tự tĩnh
  xác định (`lowest_index` / `most_occurrences` / `jeroslow_wang`), hỗ trợ assumptions,
  `add_clause`, giới hạn thời gian / số decision.
- **Agent**: phân loại CRIMINAL/INNOCENT/UNKNOWN/INCONSISTENT theo đúng định nghĩa entailment,
  dùng lại model đã tìm được để bỏ bớt truy vấn thừa; `DeductionTrace` ghi từng bước + mọi truy
  vấn SAT; `hint` trả về ô bị ép + tập clue tối thiểu chứng minh nó; `uniqueness` đếm nghiệm
  bằng blocking clause trên biến chính.
- **API cho D / E**: `GameEngine` gọi `entailment.check_verdict(public_state, cell, status)`;
  Hint / Auto Solve dùng `hint.hint(state)` và `DeductionAgent().run(engine)`;
  thí nghiệm dùng `AgentRun.summary()`; kiểm tra puzzle dùng `uniqueness.check_uniqueness`.
