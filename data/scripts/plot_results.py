"""[E] Generate tables and charts from experiment benchmark results (for report section 4.5 & 4.6)."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False


def generate_plots_and_tables(csv_path: Path, figures_dir: Path, tables_dir: Path) -> None:
    if not csv_path.exists():
        print(f"CSV file not found: {csv_path}")
        return

    figures_dir.mkdir(parents=True, exist_ok=True)
    tables_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)

    if not rows:
        print("No data rows found in CSV.")
        return

    # 1. Generate Markdown & LaTeX tables
    md_table_path = tables_dir / "experiments_table.md"
    tex_table_path = tables_dir / "experiments_table.tex"

    # Markdown Table
    md_lines = [
        "| Puzzle ID | Size | Diff | Steps | Vars (Pri/Aux) | Clauses | SAT Calls | Decisions | Backtracks | DPLL (s) | PySAT (s) | Z3 (s) |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        vars_str = f"{r['primary_vars']}/{r['aux_vars']}"
        md_lines.append(
            f"| `{r['puzzle_id']}` | {r['size']}x{r['size']} | {r['difficulty']} | {r['steps']} | "
            f"{vars_str} | {r['clauses']} | {r['sat_calls']} | {r['decisions']} | {r['backtracks']} | "
            f"{float(r['dpll_total_runtime_s']):.4f} | {r['pysat_runtime_s']} | {r['z3_runtime_s']} |"
        )
    with open(md_table_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines) + "\n")
    print(f"Saved Markdown report table to: {md_table_path}")

    # LaTeX Table
    tex_lines = [
        r"\begin{table}[h!]",
        r"\centering",
        r"\small",
        r"\begin{tabular}{|l|c|c|r|r|r|r|r|r|r|}",
        r"\hline",
        r"\textbf{Puzzle} & \textbf{Size} & \textbf{Steps} & \textbf{Vars} & \textbf{Clauses} & \textbf{SAT Calls} & \textbf{Dec.} & \textbf{Back.} & \textbf{DPLL (s)} & \textbf{PySAT (s)} \\ \hline",
    ]
    for r in rows:
        tex_lines.append(
            f"{r['puzzle_id'].replace('_', r'\_')} & {r['size']}x{r['size']} & {r['steps']} & "
            f"{r['total_vars']} & {r['clauses']} & {r['sat_calls']} & {r['decisions']} & {r['backtracks']} & "
            f"{float(r['dpll_total_runtime_s']):.4f} & {r['pysat_runtime_s']} \\\\ \\hline"
        )
    tex_lines.extend([
        r"\end{tabular}",
        r"\caption{Experimental evaluation results across Griductive benchmark puzzles.}",
        r"\label{tab:experiments}",
        r"\end{table}",
    ])
    with open(tex_table_path, "w", encoding="utf-8") as f:
        f.write("\n".join(tex_lines) + "\n")
    print(f"Saved LaTeX report table to: {tex_table_path}")

    if not MATPLOTLIB_AVAILABLE:
        print("matplotlib is not available; skipping figure plots.")
        return

    # 2. Plot 1: Runtime Comparison by Puzzle
    puzzle_ids = [r["puzzle_id"].replace("puzzle_", "") for r in rows]
    dpll_times = [float(r["dpll_total_runtime_s"]) for r in rows]
    pysat_times = [float(r["pysat_runtime_s"]) if r["pysat_runtime_s"] != "N/A" else 0.0 for r in rows]
    z3_times = [float(r["z3_runtime_s"]) if r["z3_runtime_s"] != "N/A" else 0.0 for r in rows]

    x = range(len(puzzle_ids))
    width = 0.25

    plt.figure(figsize=(10, 5))
    plt.bar([p - width for p in x], dpll_times, width=width, label="DPLL (Custom)", color="#1f77b4")
    plt.bar(x, pysat_times, width=width, label="PySAT (Glucose4)", color="#2ca02c")
    plt.bar([p + width for p in x], z3_times, width=width, label="Z3 Solver", color="#ff7f0e")

    plt.xlabel("Puzzle")
    plt.ylabel("Total Runtime (seconds)")
    plt.title("Runtime Comparison: DPLL vs PySAT vs Z3")
    plt.xticks(x, puzzle_ids, rotation=35, ha="right")
    plt.legend()
    plt.tight_layout()
    plot1_path = figures_dir / "solver_runtime_comparison.png"
    plt.savefig(plot1_path, dpi=200)
    plt.close()
    print(f"Saved figure: {plot1_path}")

    # 3. Plot 2: Clauses and Variables scaling by Size
    sizes = [f"{r['size']}x{r['size']}" for r in rows]
    clauses = [int(r["clauses"]) for r in rows]
    vars_total = [int(r["total_vars"]) for r in rows]

    plt.figure(figsize=(9, 4.5))
    plt.plot(puzzle_ids, clauses, marker="o", color="#d62728", label="CNF Clauses")
    plt.plot(puzzle_ids, vars_total, marker="s", color="#9467bd", label="Total Variables")
    plt.xlabel("Puzzle")
    plt.ylabel("Count")
    plt.title("CNF Clauses and Variables across Puzzles")
    plt.xticks(range(len(puzzle_ids)), puzzle_ids, rotation=35, ha="right")
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.legend()
    plt.tight_layout()
    plot2_path = figures_dir / "clauses_and_vars_growth.png"
    plt.savefig(plot2_path, dpi=200)
    plt.close()
    print(f"Saved figure: {plot2_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate plots and tables from benchmark results")
    parser.add_argument("--csv", type=str, default="data/results/experiments_benchmark.csv",
                        help="Input CSV file")
    parser.add_argument("--figures-dir", type=str, default="data/figures",
                        help="Output directory for plots")
    parser.add_argument("--tables-dir", type=str, default="data/results",
                        help="Output directory for generated tables")
    args = parser.parse_args()

    generate_plots_and_tables(Path(args.csv), Path(args.figures_dir), Path(args.tables_dir))


if __name__ == "__main__":
    main()
