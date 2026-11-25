"""[E] Generate Markdown/LaTeX tables and publication charts from experiment CSVs."""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path
from typing import Optional

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _short_id(puzzle_id: str) -> str:
    return puzzle_id.replace("puzzle_", "")


def _build_main_tables(rows: list[dict[str, str]], tables_dir: Path) -> None:
    md_path = tables_dir / "experiments_table.md"
    tex_path = tables_dir / "experiments_table.tex"

    md_lines = [
        "| Puzzle ID | Size | Diff | Outcome | Steps | Vars (Pri/Aux) | Clauses | SAT Calls | Dec | Prop | Back | Agent (s) | DPLL Uniq (s) | PySAT Uniq (s) | Z3 Uniq (s) |",
        "|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in rows:
        agent_s = r.get("dpll_agent_total_runtime_s") or r.get("dpll_total_runtime_s", "0")
        dpll_u = r.get("dpll_unique_s", "N/A")
        pysat_u = r.get("pysat_unique_s") or r.get("pysat_runtime_s", "N/A")
        z3_u = r.get("z3_unique_s") or r.get("z3_runtime_s", "N/A")
        md_lines.append(
            f"| `{r['puzzle_id']}` | {r['size']}x{r['size']} | {r['difficulty']} | {r['outcome']} | "
            f"{r['steps']} | {r['primary_vars']}/{r['aux_vars']} | {r['clauses']} | "
            f"{r['sat_calls']} | {r['decisions']} | {r['propagations']} | {r['backtracks']} | "
            f"{float(agent_s):.5f} | {dpll_u} | {pysat_u} | {z3_u} |"
        )
    md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    print(f"Saved Markdown report table -> {md_path}")

    tex_lines = [
        r"\begin{table}[h!]",
        r"\centering",
        r"\scriptsize",
        r"\begin{tabular}{|l|c|c|r|r|r|r|r|r|r|r|r|}",
        r"\hline",
        r"\textbf{Puzzle} & \textbf{Size} & \textbf{Steps} & \textbf{Pri/Aux} & \textbf{Clauses} & \textbf{Calls} & \textbf{Dec} & \textbf{Prop} & \textbf{Back} & \textbf{Agent (s)} & \textbf{DPLL Uniq (s)} & \textbf{PySAT (s)} \\ \hline",
    ]
    for r in rows:
        agent_s = r.get("dpll_agent_total_runtime_s") or r.get("dpll_total_runtime_s", "0")
        dpll_u = r.get("dpll_unique_s", "N/A")
        pysat_u = r.get("pysat_unique_s") or r.get("pysat_runtime_s", "N/A")
        tex_lines.append(
            f"{r['puzzle_id'].replace('_', r'\_')} & {r['size']}x{r['size']} & {r['steps']} & "
            f"{r['primary_vars']}/{r['aux_vars']} & {r['clauses']} & {r['sat_calls']} & "
            f"{r['decisions']} & {r['propagations']} & {r['backtracks']} & "
            f"{float(agent_s):.5f} & {dpll_u} & {pysat_u} \\\\ \\hline"
        )
    tex_lines.extend([
        r"\end{tabular}",
        r"\caption{Benchmark evaluation across Griductive puzzles (Deduction Loop metrics and Complete-KB Uniqueness comparison).}",
        r"\label{tab:experiments}",
        r"\end{table}",
    ])
    tex_path.write_text("\n".join(tex_lines) + "\n", encoding="utf-8")
    print(f"Saved LaTeX report table -> {tex_path}")


def _build_heuristics_tables(rows: list[dict[str, str]], tables_dir: Path) -> None:
    if not rows:
        return
    md_path = tables_dir / "heuristics_table.md"
    tex_path = tables_dir / "heuristics_table.tex"

    by_puzzle: dict[str, dict[str, dict[str, str]]] = defaultdict(dict)
    order: list[str] = []
    for r in rows:
        pid = r["puzzle_id"]
        if pid not in by_puzzle:
            order.append(pid)
        by_puzzle[pid][r["heuristic"]] = r

    md_lines = [
        "| Puzzle ID | Size | lowest_index (Dec / Calls / Time ms) | most_occurrences (Dec / Calls / Time ms) | jeroslow_wang (Dec / Calls / Time ms) |",
        "|---|---|---|---|---|",
    ]
    totals = {h: {"dec": 0, "calls": 0, "ms": 0.0, "bt": 0} for h in ("lowest_index", "most_occurrences", "jeroslow_wang")}
    for pid in order:
        hmap = by_puzzle[pid]
        size = next(iter(hmap.values()))["size"]
        cells = []
        for h in ("lowest_index", "most_occurrences", "jeroslow_wang"):
            r = hmap[h]
            ms = float(r["total_runtime_s"]) * 1000.0
            totals[h]["dec"] += int(r["decisions"])
            totals[h]["calls"] += int(r["sat_calls"])
            totals[h]["bt"] += int(r["backtracks"])
            totals[h]["ms"] += ms
            cells.append(f"{r['decisions']} / {r['sat_calls']} / {ms:.2f}")
        md_lines.append(f"| `{pid}` | {size}x{size} | {cells[0]} | {cells[1]} | {cells[2]} |")

    md_lines.append(
        f"| **TOTAL ({len(order)} puzzles)** | — | "
        + " | ".join(
            f"**{totals[h]['dec']} / {totals[h]['calls']} / {totals[h]['ms']:.2f}**"
            for h in ("lowest_index", "most_occurrences", "jeroslow_wang")
        )
        + " |"
    )
    md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    print(f"Saved Heuristics Markdown table -> {md_path}")

    tex_lines = [
        r"\begin{table}[h!]",
        r"\centering",
        r"\small",
        r"\begin{tabular}{|l|r|r|r|r|}",
        r"\hline",
        r"\textbf{Heuristic} & \textbf{Total Decisions} & \textbf{Total Backtracks} & \textbf{Total SAT Calls} & \textbf{Total Time (ms)} \\ \hline",
    ]
    for h in ("lowest_index", "most_occurrences", "jeroslow_wang"):
        t = totals[h]
        tex_lines.append(
            f"\\texttt{{{h.replace('_', r'\_')}}} & {t['dec']} & {t['bt']} & {t['calls']} & {t['ms']:.2f} \\\\ \\hline"
        )
    tex_lines.extend([
        r"\end{tabular}",
        r"\caption{Comparison of the three deterministic DPLL heuristics on the same puzzle set.}",
        r"\label{tab:heuristics}",
        r"\end{table}",
    ])
    tex_path.write_text("\n".join(tex_lines) + "\n", encoding="utf-8")
    print(f"Saved Heuristics LaTeX table -> {tex_path}")


def _build_edge_cases_tables(rows: list[dict[str, str]], tables_dir: Path) -> None:
    if not rows:
        return
    md_path = tables_dir / "edge_cases_table.md"
    tex_path = tables_dir / "edge_cases_table.tex"

    md_lines = [
        "| Case ID | Size | Scenario | Expected | Actual | Uniqueness | Steps | Vars (Pri/Aux) | Clauses | SAT Calls | Dec | Back | Runtime (s) | Notes |",
        "|---|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for r in rows:
        md_lines.append(
            f"| `{r['case_id']}` | {r['size']}x{r['size']} | {r['scenario']} | {r['expected_outcome']} | "
            f"**{r['actual_outcome']}** | {r['uniqueness_status']} | {r['steps']} | "
            f"{r['primary_vars']}/{r['aux_vars']} | {r['clauses']} | {r['sat_calls']} | "
            f"{r['decisions']} | {r['backtracks']} | {float(r['runtime_s']):.5f} | {r['notes']} |"
        )
    md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    print(f"Saved Edge-Cases Markdown table -> {md_path}")

    tex_lines = [
        r"\begin{table}[h!]",
        r"\centering",
        r"\scriptsize",
        r"\begin{tabular}{|l|c|l|l|l|r|r|r|r|}",
        r"\hline",
        r"\textbf{Case ID} & \textbf{Size} & \textbf{Scenario} & \textbf{Outcome} & \textbf{Uniqueness} & \textbf{Steps} & \textbf{Calls} & \textbf{Dec} & \textbf{Time (s)} \\ \hline",
    ]
    for r in rows:
        tex_lines.append(
            f"{r['case_id'].replace('_', r'\_')} & {r['size']}x{r['size']} & "
            f"{r['scenario'].replace('_', r'\_')} & {r['actual_outcome']} & {r['uniqueness_status']} & "
            f"{r['steps']} & {r['sat_calls']} & {r['decisions']} & {float(r['runtime_s']):.5f} \\\\ \\hline"
        )
    tex_lines.extend([
        r"\end{tabular}",
        r"\caption{Failure, ambiguity, inconsistency, and timeout stress cases (reported without omission).}",
        r"\label{tab:edge_cases}",
        r"\end{table}",
    ])
    tex_path.write_text("\n".join(tex_lines) + "\n", encoding="utf-8")
    print(f"Saved Edge-Cases LaTeX table -> {tex_path}")


def _plot_runtime_same_task(
    main_rows: list[dict[str, str]],
    heur_rows: list[dict[str, str]],
    figures_dir: Path,
) -> None:
    puzzle_ids = [_short_id(r["puzzle_id"]) for r in main_rows]
    series: list[tuple[str, list[float], str]] = []

    if heur_rows:
        by_pid_h: dict[str, dict[str, float]] = defaultdict(dict)
        for hr in heur_rows:
            by_pid_h[hr["puzzle_id"]][hr["heuristic"]] = float(hr["unique_runtime_s"]) * 1000.0
        palette = {
            "lowest_index": "#1f77b4",
            "most_occurrences": "#9467bd",
            "jeroslow_wang": "#17becf",
        }
        for h in ("lowest_index", "most_occurrences", "jeroslow_wang"):
            vals = [by_pid_h.get(r["puzzle_id"], {}).get(h, 0.0) for r in main_rows]
            series.append((f"DPLL ({h})", vals, palette[h]))
    else:
        col = "dpll_unique_s" if "dpll_unique_s" in main_rows[0] else "dpll_total_runtime_s"
        series.append(("DPLL (Custom)", [float(r[col]) * 1000.0 for r in main_rows], "#1f77b4"))

    pysat_col = "pysat_unique_s" if "pysat_unique_s" in main_rows[0] else "pysat_runtime_s"
    z3_col = "z3_unique_s" if "z3_unique_s" in main_rows[0] else "z3_runtime_s"
    if any(r.get(pysat_col, "N/A") != "N/A" for r in main_rows):
        series.append((
            "PySAT (Glucose4)",
            [float(r[pysat_col]) * 1000.0 if r.get(pysat_col, "N/A") != "N/A" else 0.0 for r in main_rows],
            "#2ca02c",
        ))
    if any(r.get(z3_col, "N/A") != "N/A" for r in main_rows):
        series.append((
            "Z3 Solver",
            [float(r[z3_col]) * 1000.0 if r.get(z3_col, "N/A") != "N/A" else 0.0 for r in main_rows],
            "#ff7f0e",
        ))

    n_series = len(series)
    width = min(0.24, 0.80 / max(1, n_series))
    x = list(range(len(puzzle_ids)))

    fig_w = max(12.0, len(puzzle_ids) * 0.55)
    plt.figure(figsize=(fig_w, 5.4))
    for idx, (label, vals, color) in enumerate(series):
        offset = (idx - (n_series - 1) / 2.0) * width
        plt.bar([xi + offset for xi in x], vals, width=width, label=label, color=color)

    plt.xlabel("Puzzle")
    plt.ylabel("Runtime (ms)")
    plt.title("Same-Task Comparison: Complete-KB Uniqueness Check")
    plt.xticks(x, puzzle_ids, rotation=38, ha="right")
    plt.grid(axis="y", linestyle="--", alpha=0.4)
    plt.legend()
    plt.tight_layout()
    out_path = figures_dir / "solver_runtime_comparison.png"
    plt.savefig(out_path, dpi=200)
    plt.close()
    print(f"Saved figure -> {out_path}")


def _plot_heuristics_comparison(
    main_rows: list[dict[str, str]],
    heur_rows: list[dict[str, str]],
    figures_dir: Path,
) -> None:
    if not heur_rows:
        return
    puzzle_ids = [_short_id(r["puzzle_id"]) for r in main_rows]
    by_pid_h: dict[str, dict[str, dict[str, str]]] = defaultdict(dict)
    for hr in heur_rows:
        by_pid_h[hr["puzzle_id"]][hr["heuristic"]] = hr

    heur_meta = [
        ("lowest_index", "lowest_index", "#1f77b4"),
        ("most_occurrences", "most_occurrences", "#9467bd"),
        ("jeroslow_wang", "jeroslow_wang", "#17becf"),
    ]
    x = list(range(len(puzzle_ids)))
    width = 0.25

    fig_w = max(12.0, len(puzzle_ids) * 0.55)
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(fig_w, 7.8), sharex=True)
    for idx, (h, label, color) in enumerate(heur_meta):
        offset = (idx - 1) * width
        decs = [int(by_pid_h[r["puzzle_id"]][h]["decisions"]) for r in main_rows]
        times = [float(by_pid_h[r["puzzle_id"]][h]["total_runtime_s"]) * 1000.0 for r in main_rows]
        ax1.bar([xi + offset for xi in x], decs, width=width, label=label, color=color)
        ax2.bar([xi + offset for xi in x], times, width=width, label=label, color=color)

    ax1.set_ylabel("DPLL Decisions (Sum)")
    ax1.set_title("Deduction Agent Loop Across Heuristics (Same Puzzle Set)")
    ax1.grid(axis="y", linestyle="--", alpha=0.4)
    ax1.legend()

    ax2.set_ylabel("Total Agent Runtime (ms)")
    ax2.set_xlabel("Puzzle")
    ax2.set_xticks(x)
    ax2.set_xticklabels(puzzle_ids, rotation=38, ha="right")
    ax2.grid(axis="y", linestyle="--", alpha=0.4)

    plt.tight_layout()
    out_path = figures_dir / "heuristics_comparison.png"
    plt.savefig(out_path, dpi=200)
    plt.close()
    print(f"Saved figure -> {out_path}")


def _plot_clauses_and_vars(main_rows: list[dict[str, str]], figures_dir: Path) -> None:
    puzzle_ids = [_short_id(r["puzzle_id"]) for r in main_rows]
    pri = [int(r["primary_vars"]) for r in main_rows]
    aux = [int(r["aux_vars"]) for r in main_rows]
    clauses = [int(r["clauses"]) for r in main_rows]
    x = list(range(len(puzzle_ids)))

    fig_w = max(12.0, len(puzzle_ids) * 0.55)
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(fig_w, 7.6), sharex=True)
    ax1.bar(x, pri, label="Primary Vars (N^2)", color="#3b82f6")
    ax1.bar(x, aux, bottom=pri, label="Auxiliary Vars (Extensions)", color="#f59e0b")
    ax1.set_ylabel("Variables")
    ax1.set_title("CNF Variables (Primary + Auxiliary) and Clauses Growth Across Puzzles")
    ax1.grid(axis="y", linestyle="--", alpha=0.4)
    ax1.legend()

    ax2.plot(x, clauses, marker="o", linewidth=2.2, color="#dc2626", label="CNF Clauses")
    for xi, cl in zip(x, clauses):
        ax2.annotate(str(cl), (xi, cl), textcoords="offset points", xytext=(0, 6), ha="center", fontsize=8)
    ax2.set_ylim(0, max(clauses) * 1.16)
    ax2.set_ylabel("CNF Clauses")
    ax2.set_xlabel("Puzzle")
    ax2.set_xticks(x)
    ax2.set_xticklabels(puzzle_ids, rotation=38, ha="right")
    ax2.grid(True, linestyle="--", alpha=0.4)
    ax2.legend()

    plt.tight_layout()
    out_path = figures_dir / "clauses_and_vars_growth.png"
    plt.savefig(out_path, dpi=200)
    plt.close()
    print(f"Saved figure -> {out_path}")


def generate_plots_and_tables(
    csv_path: Path,
    figures_dir: Path,
    tables_dir: Path,
    heuristics_csv: Optional[Path] = None,
    edge_cases_csv: Optional[Path] = None,
) -> None:
    main_rows = _read_csv(csv_path)
    if not main_rows:
        print(f"CSV file not found or empty: {csv_path}")
        return

    figures_dir.mkdir(parents=True, exist_ok=True)
    tables_dir.mkdir(parents=True, exist_ok=True)

    heur_rows = _read_csv(heuristics_csv) if heuristics_csv else []
    edge_rows = _read_csv(edge_cases_csv) if edge_cases_csv else []

    _build_main_tables(main_rows, tables_dir)
    _build_heuristics_tables(heur_rows, tables_dir)
    _build_edge_cases_tables(edge_rows, tables_dir)

    if not MATPLOTLIB_AVAILABLE:
        print("matplotlib is not available; skipping figure plots.")
        return

    _plot_runtime_same_task(main_rows, heur_rows, figures_dir)
    _plot_heuristics_comparison(main_rows, heur_rows, figures_dir)
    _plot_clauses_and_vars(main_rows, figures_dir)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate plots and tables from benchmark results")
    parser.add_argument("--results-dir", type=str, default="data/results",
                        help="Directory containing benchmark CSV files")
    parser.add_argument("--csv", type=str, default=None,
                        help="Explicit path to main benchmark CSV (defaults to <results-dir>/experiments_benchmark.csv)")
    parser.add_argument("--figures-dir", type=str, default="data/figures",
                        help="Output directory for plots")
    parser.add_argument("--tables-dir", type=str, default="data/results",
                        help="Output directory for generated Markdown/LaTeX tables")
    args = parser.parse_args()

    res_dir = Path(args.results_dir)
    main_csv = Path(args.csv) if args.csv else res_dir / "experiments_benchmark.csv"
    heur_csv = res_dir / "experiments_heuristics.csv"
    edge_csv = res_dir / "experiments_edge_cases.csv"

    generate_plots_and_tables(
        csv_path=main_csv,
        figures_dir=Path(args.figures_dir),
        tables_dir=Path(args.tables_dir),
        heuristics_csv=heur_csv if heur_csv.exists() else None,
        edge_cases_csv=edge_csv if edge_csv.exists() else None,
    )


if __name__ == "__main__":
    main()
