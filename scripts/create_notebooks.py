import json

notebook_01 = {
 "cells": [
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "# 01. Data Acquisition and Provenance\n",
    "\n",
    "This notebook demonstrates fetching real data (NASA OSDR and Environmental metrics), caching raw responses, and registering them securely to the SYNERA provenance ledger."
   ]
  },
  {
   "cell_type": "code",
   "execution_count": None,
   "metadata": {},
   "outputs": [],
   "source": [
    "from synera_core.data.http_client import HTTPClient\n",
    "from synera_core.provenance.ledger import Ledger\n",
    "from synera_core.config import find_repo_root\n",
    "\n",
    "repo_root = find_repo_root()\n",
    "db_path = repo_root / 'artifacts' / 'synera.db'\n",
    "key_path = repo_root / 'configs' / 'signer.key'\n",
    "ledger = Ledger(db_path, key_path) if db_path.exists() and key_path.exists() else None\n",
    "\n",
    "client = HTTPClient(ledger=ledger)\n",
    "url = 'https://osdr.nasa.gov/osdr/data/search'\n",
    "params = {'term': 'spaceflight', 'type': 'cgene'}\n",
    "\n",
    "print(\"Fetching OSDR Search...\")\n",
    "content, path, cached = client.get(url, params)\n",
    "print(f\"Cached: {cached}\")\n",
    "print(f\"Saved to: {path}\")"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": None,
   "metadata": {},
   "outputs": [],
   "source": [
    "if ledger:\n",
    "    print(\"\\nLatest Ledger Block:\")\n",
    "    head = ledger.head()\n",
    "    print(f\"Block #{head.index}: {head.block_type}\")\n",
    "    print(f\"Hash: {head.block_hash}\")\n",
    "    import json\n",
    "    print(f\"Payload: {json.dumps(head.payload, indent=2)}\")"
   ]
  }
 ],
 "metadata": {
  "language_info": {
   "name": "python"
  }
 },
 "nbformat": 4,
 "nbformat_minor": 2
}

with open(r'd:\synera1.0\synera\notebooks\01_data_acquisition.ipynb', 'w') as f:
    json.dump(notebook_01, f, indent=2)

notebook_02 = {
 "cells": [
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "# 02. Exploratory Data Analysis and QC\n",
    "\n",
    "Review processed OSDR transcripts (Radiation x Microgravity) and Environmental Panel."
   ]
  },
  {
   "cell_type": "code",
   "execution_count": None,
   "metadata": {},
   "outputs": [],
   "source": [
    "import pandas as pd\n",
    "import seaborn as sns\n",
    "import matplotlib.pyplot as plt\n",
    "from synera_core.config import find_repo_root\n",
    "\n",
    "repo_root = find_repo_root()\n",
    "env_path = repo_root / 'data' / 'processed' / 'env_panel.parquet'\n",
    "\n",
    "if env_path.exists():\n",
    "    df = pd.read_parquet(env_path)\n",
    "    print(f\"Env Panel Shape: {df.shape}\")\n",
    "    display(df.head())\n",
    "else:\n",
    "    print(\"Env panel not found.\")"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": None,
   "metadata": {},
   "outputs": [],
   "source": [
    "if env_path.exists():\n",
    "    plt.figure(figsize=(10, 8))\n",
    "    sns.heatmap(df[['tmax', 'tmean', 'rh', 'heat_index', 'precip', 'drought_index', 'pm25', 'o3']].corr(), annot=True, cmap='coolwarm', vmin=-1, vmax=1)\n",
    "    plt.title('Environmental Stressor Correlation Matrix')\n",
    "    plt.show()\n",
    "\n",
    "    plt.figure(figsize=(12, 6))\n",
    "    sns.scatterplot(data=df, x='pm25', y='heat_index', hue='city', alpha=0.6)\n",
    "    plt.title('Heat Index vs PM2.5 by City')\n",
    "    plt.show()"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## QC Notes & Confounding\n",
    "- Strong seasonal cycles in Delhi and Beijing for temperature and PM2.5.\n",
    "- Missing data primarily in specific periods for certain Open-Meteo AQ metrics (flagged, not filled).\n",
    "- Batch effects in OSDR data typically correlate with sequencing runs."
   ]
  }
 ],
 "metadata": {
  "language_info": {
   "name": "python"
  }
 },
 "nbformat": 4,
 "nbformat_minor": 2
}

with open(r'd:\synera1.0\synera\notebooks\02_eda_and_qc.ipynb', 'w') as f:
    json.dump(notebook_02, f, indent=2)
