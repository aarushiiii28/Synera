import json
from pathlib import Path
from synera_core.benchmark.evaluate import evaluate_benchmark
import nbformat as nbf
from synera_core.config import find_repo_root

def generate_notebook(title, cells_content, out_path):
    nb = nbf.v4.new_notebook()
    cells = []
    for cell_type, content in cells_content:
        if cell_type == "markdown":
            cells.append(nbf.v4.new_markdown_cell(content))
        else:
            cells.append(nbf.v4.new_code_cell(content))
    nb.cells = cells
    with open(out_path, 'w') as f:
        nbf.write(nb, f)
        
def main():
    repo_root = find_repo_root()
    # 1. Run Benchmark
    print("Evaluating benchmark...")
    evaluate_benchmark(seeds=2, snrs=[1.0, 5.0], out_dir=repo_root / "artifacts" / "results")
    
    # 2. Generate Notebooks
    print("Generating Notebooks...")
    nb_dir = repo_root / "notebooks"
    nb_dir.mkdir(exist_ok=True)
    
    nb3_cells = [
        ("markdown", "# 03 - Synthetic Benchmark\\nEngine Report Card (Track B)"),
        ("code", "import json\nimport pandas as pd\nwith open('../artifacts/results/benchmark.json') as f:\n    res = json.load(f)\nprint(pd.DataFrame(res['benchmark_summary']).T)")
    ]
    generate_notebook("03_synthetic_benchmark", nb3_cells, nb_dir / "03_synthetic_benchmark.ipynb")
    
    nb7_cells = [
        ("markdown", "# 07 - Security Poisoning Lab\\nCybersecurity layer with realistic attack simulations."),
        ("code", "from synera_core.benchmark.generator import generate_benchmark\nfrom synera_core.security.tamper_sim import simulate_attack\np, _ = generate_benchmark(seed=999, n_per_city=50)\nprint('Running drift_units attack...')\nres = simulate_attack('drift_units', p)\nprint(res)")
    ]
    generate_notebook("07_security_poisoning_lab", nb7_cells, nb_dir / "07_security_poisoning_lab.ipynb")
    
if __name__ == "__main__":
    main()
