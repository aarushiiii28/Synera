import nbformat as nbf
import os

# Palettes
COLORS = 'bg="#081B2E", cyan="#16B5FF", green="#6FD65B", amber="#FFB547", red="#FF4D5E"'

def create_notebook(path, cells_content):
    nb = nbf.v4.new_notebook()
    cells = []
    for ctype, content in cells_content:
        if ctype == 'md':
            cells.append(nbf.v4.new_markdown_cell(content))
        else:
            cells.append(nbf.v4.new_code_cell(content))
    nb.cells = cells
    with open(path, 'w', encoding='utf-8') as f:
        nbf.write(nb, f)

# Notebook 04
cells_04 = [
    ('md', '# SYNERA Discovery (04)'),
    ('code', f'''
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from synera_core.discovery.interactions import factorial_interaction
from synera_core.validation.multitest import bh_fdr

plt.style.use('dark_background')
# {COLORS}

# Factorial Discovery on Track A (OSD-211)
expr = pd.read_parquet('../data/processed/osdr_OSD-211_expr.parquet')
meta = pd.read_parquet('../data/processed/osdr_OSD-211_meta.parquet')
meta = meta.set_index('sample_id').loc[expr.columns].reset_index()

res = factorial_interaction(expr.T, meta, 'radiation', 'microgravity')
res['q_AB'] = bh_fdr(res['p_AB'].values)

# Volcano plot
plt.figure(figsize=(6,4), facecolor="#081B2E")
plt.scatter(res['b_AB'], -np.log10(res['p_AB']), c="#16B5FF", alpha=0.5, s=10)
plt.xlabel("Interaction Effect (b_AB)")
plt.ylabel("-log10(p)")
plt.title("Volcano Plot (OSD-211)")
plt.show()

# Output head
res.head()
    ''')
]
create_notebook('notebooks/04_discovery.ipynb', cells_04)

# Notebook 05
cells_05 = [
    ('md', '# SYNERA Validation (05)'),
    ('code', f'''
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from synera_core.discovery.interactions import factorial_interaction
from synera_core.validation.multitest import bh_fdr
import scipy.stats as stats

plt.style.use('dark_background')
# {COLORS}

expr = pd.read_parquet('../data/processed/osdr_OSD-211_expr.parquet')
meta = pd.read_parquet('../data/processed/osdr_OSD-211_meta.parquet')
meta = meta.set_index('sample_id').loc[expr.columns].reset_index()

# Null calibration
np.random.seed(42)
meta['r_perm'] = np.random.permutation(meta['radiation'])
meta['g_perm'] = np.random.permutation(meta['microgravity'])
res_null = factorial_interaction(expr.T, meta, 'r_perm', 'g_perm')
p_null = res_null['p_AB'].dropna().values

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10,4), facecolor="#081B2E")
ax1.hist(p_null, bins=50, color="#FFB547")
ax1.set_title("Null p-value Histogram")

stats.probplot(p_null, dist="uniform", plot=ax2)
ax2.get_lines()[0].set_color('#6FD65B')
ax2.set_title("QQ Plot (Uniform)")
plt.show()
    ''')
]
create_notebook('notebooks/05_validation.ipynb', cells_05)

# Notebook 06
cells_06 = [
    ('md', '# SYNERA Replication (06)'),
    ('code', f'''
import pandas as pd
import os
from synera_core.discovery.interactions import factorial_interaction
from synera_core.validation.multitest import bh_fdr
from synera_core.validation.replication import replicate
from synera_core.provenance.ledger import Ledger
from synera_core.provenance.manifest import register_file
from synera_core.config import find_repo_root

repo_root = find_repo_root()
db_path = repo_root / "artifacts" / "synera.db"
key_path = repo_root / "configs" / "signer.key"
ledger = Ledger(db_path, key_path)

# Discovery (OSD-211)
expr_d = pd.read_parquet('../data/processed/osdr_OSD-211_expr.parquet')
meta_d = pd.read_parquet('../data/processed/osdr_OSD-211_meta.parquet')
meta_d = meta_d.set_index('sample_id').loc[expr_d.columns].reset_index()
res_d = factorial_interaction(expr_d.T, meta_d, 'radiation', 'microgravity')
res_d['q_AB_d'] = bh_fdr(res_d['p_AB'].values)
res_d = res_d.rename(columns={{c: c+"_d" for c in res_d.columns if c != "q_AB_d"}})

# Replication (OSD-237)
expr_r = pd.read_parquet('../data/processed/osdr_OSD-237_expr.parquet')
meta_r = pd.read_parquet('../data/processed/osdr_OSD-237_meta.parquet')
meta_r = meta_r.set_index('sample_id').loc[expr_r.columns].reset_index()
res_r = factorial_interaction(expr_r.T, meta_r, 'radiation', 'microgravity')
res_r = res_r.rename(columns={{c: c+"_r" for c in res_r.columns}})

# Replicate
rep_res = replicate(res_d, res_r, evidence_level="CROSS_TISSUE_SAME_COHORT")
print(rep_res)

# Save and register
out_path = repo_root / "artifacts" / "results"
out_path.mkdir(parents=True, exist_ok=True)
pd.DataFrame([rep_res]).drop(columns=['flags']).to_json(out_path / "track_a_replication.json")
register_file(ledger, out_path / "track_a_replication.json", "finding_verification", {{"track": "A"}})
    ''')
]
create_notebook('notebooks/06_replication.ipynb', cells_06)

print("Created notebooks 04, 05, 06.")
