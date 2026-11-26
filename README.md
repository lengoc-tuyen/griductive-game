# griductive-game

Griductive Solver (CSC14003 – Project 2): game suy luận lưới, giải bằng logic mệnh đề + CNF + DPLL tự cài.

## Cấu trúc thư mục & phân công

```
griductive-game/
├── main.py                      # entry point → chạy web server + mở GUI trên trình duyệt
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
│   │   ├── evaluator.py         #   evaluator ngữ nghĩa (test chéo, không dùng CNF)
│   │   └── errors.py            #   lỗi validate clue / region
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
│       ├── fixtures/                     # puzzle mẫu cho test (puzzle_3x3_basic cũng là màn mặc định của game)
│       ├── helpers.py                    # tiện ích dùng chung cho test
│       ├── test_regions.py               # [A] region + validate clue
│       ├── test_encoder.py               # [A] cardinality + encoder
│       ├── test_encoder_vs_evaluator.py  # [A] encoder ↔ evaluator test chéo
│       ├── test_extensions.py            # [A] extension clue + region nâng cao
│       ├── test_dpll.py                  # [B]
│       ├── test_agent.py                 # [C]
│       ├── test_frontend_d1.py           # [D] GameEngine, clue_renderer, Web API
│       └── test_generator.py             # [E] loader, cross-check, generator, benchmark
│
├── frontend/                    # [D] Game & GUI (4.1)
│   ├── engine/
│   │   ├── game_engine.py       #   giữ lời giải + clue ẩn, xử lý verdict
│   │   └── verdict.py           #   ACCEPTED / NOT_PROVABLE / CONTRADICTED
│   ├── gui/
│   │   ├── app.py               #   web server + REST API (load / restart / verdict / hint / step / auto solve)
│   │   └── clue_renderer.py     #   clue → câu tự nhiên + ô cần highlight
│   └── assets/                  #   giao diện web
│       ├── index.html
│       ├── css/styles.css
│       ├── img/
│       └── js/                  #   api.js (gọi server), board.js (vẽ lưới), main.js (điều khiển), avatars.js
│
└── data/                        # [E] Dữ liệu & thực nghiệm (4.5)
    ├── schema.md                #   định dạng JSON của puzzle
    ├── puzzle_loader.py         #   đọc/ghi JSON → Puzzle
    ├── puzzles/{3x3,4x4,5x5}/   #   bộ puzzle nghiệm duy nhất
    ├── edge_cases/              #   case STUCK / INCONSISTENT / stress 5x5
    ├── scripts/
    │   ├── generate_puzzles.py  #   sinh puzzle nghiệm duy nhất
    │   ├── names_pool.py        #   tên + nghề cho nhân vật
    │   ├── create_edge_cases.py #   sinh các edge case
    │   ├── cross_checker.py     #   kiểm tra chéo bằng brute force / PySAT / Z3
    │   ├── verify_puzzles.py    #   kiểm tra duy nhất nghiệm + giải được không đoán
    │   ├── run_experiments.py   #   đo số liệu, ghi cả failure/timeout
    │   └── plot_results.py      #   bảng / biểu đồ
    ├── results/                 #   CSV kết quả
    └── figures/                 #   biểu đồ cho report
```

## Ranh giới giữa các phần

- **A → mọi người**: `algorithms/logic/models.py` (Cell, Status, Clue) là hợp đồng chung — chốt sớm nhất.
- **A ↔ E**: format clue trong `data/schema.md` phải khớp `models.py`.
- **B**: chỉ nhận/trả CNF dạng `list[list[int]]`, không biết gì về game.
- **C**: chỉ nhận `PublicState` từ Engine, **không** được đọc lời giải ẩn hay clue chưa lộ.
- **D**: `GameEngine` là nơi duy nhất giữ lời giải; GUI gọi agent cho Hint / Auto Solve và để kiểm tra verdict.

## Cài đặt & chạy

Yêu cầu Python ≥ 3.9. Game và solver chỉ dùng thư viện chuẩn (GUI là web app chạy bằng `http.server`),
không cần cài thêm gì. Mọi lệnh đều chạy **từ thư mục gốc** của project.

### Chơi game

```bash
python main.py                                    # mở game trên trình duyệt (http://127.0.0.1:5000)
python main.py data/puzzles/4x4/puzzle_4x4_easy_01.json  # mở sẵn một màn chơi
python main.py --port 8000 --no-browser           # đổi cổng / không tự mở trình duyệt
```

### Chạy test

```bash
python -m unittest discover -s algorithms/tests -t .
```

### Thực nghiệm (mục 4.5)

Cần cài thêm thư viện tùy chọn: `pip install matplotlib python-sat z3-solver`
(`python-sat` / `z3-solver` chỉ dùng để kiểm tra chéo; thiếu thì script bỏ qua phần đó).

```bash
python -m data.scripts.verify_puzzles             # kiểm tra mỗi puzzle có đúng 1 nghiệm
python -m data.scripts.run_experiments            # đo số liệu → data/results/*.csv
python -m data.scripts.plot_results               # vẽ biểu đồ → data/figures/
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
