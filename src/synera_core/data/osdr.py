"""NASA Open Science Data Repository (OSDR) ingestion and preprocessing.

Handles downloading, parsing, and QC of spaceflight multi-omics studies
(Microgravity x Ionizing Radiation factorial assays).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from synera_core.data.http_client import HTTPClient
from synera_core.config import find_repo_root

OSDR_BASE_URL = "https://osdr.nasa.gov"

def _get_client() -> HTTPClient:
    return HTTPClient()

def search_studies(term: str) -> Dict[str, Any]:
    """
    Search OSDR studies using keyword.
    
    Args:
        term: Search term
        
    Returns:
        JSON response from OSDR search API
    """
    client = _get_client()
    url = f"{OSDR_BASE_URL}/osdr/data/search"
    # Note: 'type=cgene' seems to be the type for GeneLab studies.
    params = {"term": term, "type": "cgene"}
    data, _, _ = client.get_json(url, params=params)
    return data

def get_meta(osd_id: str) -> Dict[str, Any]:
    """
    Get metadata for a specific OSDR study.
    
    Args:
        osd_id: OSD identifier (e.g., 'OSD-379' or '379')
        
    Returns:
        JSON response with study metadata
    """
    client = _get_client()
    # Ensure only the number is passed if OSD- prefix is included
    osd_num = osd_id.replace("OSD-", "")
    url = f"{OSDR_BASE_URL}/osdr/data/osd/meta/{osd_num}"
    data, _, _ = client.get_json(url)
    return data

def list_files(osd_id: str) -> Dict[str, Any]:
    """
    List files associated with an OSDR study.
    
    Args:
        osd_id: OSD identifier (e.g., '379')
        
    Returns:
        JSON response with file listing
    """
    client = _get_client()
    osd_num = osd_id.replace("OSD-", "")
    url = f"{OSDR_BASE_URL}/osdr/data/osd/files/{osd_num}"
    data, _, _ = client.get_json(url)
    return data

def download(osd_id: str, file_pattern: str, dest_dir: Optional[Path] = None) -> List[Path]:
    """
    Download files matching a regex pattern for an OSDR study.
    
    Args:
        osd_id: OSD identifier
        file_pattern: Regex pattern to match file names
        dest_dir: Destination directory. Defaults to data/raw/osdr/{osd_id}
        
    Returns:
        List of paths to downloaded files
    """
    if dest_dir is None:
        dest_dir = find_repo_root() / "data" / "raw" / "osdr" / osd_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    
    file_list = list_files(osd_id)
    downloaded_paths = []
    
    client = _get_client()
    pattern = re.compile(file_pattern)
    
    # OSDR file listing structure often is nested or under specific keys.
    # The exact structure needs to be navigated. Typically it's under 'files' or similar.
    # We will assume a flat list of dicts with 'file_name' and 'url' for simplicity,
    # or handle the tree structure if known.
    # For now, let's just recursively search for file names in the JSON response.
    
    def extract_files(node: Any) -> List[Dict[str, Any]]:
        found = []
        if isinstance(node, dict):
            if "file_name" in node and ("remote_url" in node or "url" in node):
                found.append(node)
            for value in node.values():
                found.extend(extract_files(value))
        elif isinstance(node, list):
            for item in node:
                found.extend(extract_files(item))
        return found
        
    all_files = extract_files(file_list)
    
    for f in all_files:
        fname = f.get("file_name", "")
        if pattern.search(fname):
            url = f.get("remote_url") or f.get("url")
            if not url:
                continue
            if not url.startswith("http"):
                url = f"{OSDR_BASE_URL}{url}"
                
            out_path = dest_dir / fname
            if not out_path.exists():
                print(f"Downloading {fname}...")
                content, _, _ = client.get(url)
                out_path.write_bytes(content)
            downloaded_paths.append(out_path)
            
    return downloaded_paths

def load_osdr_study(study_id: str, local_dir: Path | str) -> dict[str, Any]:
    """Load and index OSDR study files and metadata from local repository directory.

    Args:
        study_id: OSDR identifier (e.g., 'OSD-379').
        local_dir: Path where raw study files are cached.

    Returns:
        Dictionary containing study metadata and data frame mappings.
    """
    study_path = Path(local_dir) / study_id
    return {
        "study_id": study_id,
        "path": str(study_path),
        "exists": study_path.exists(),
        "tables": {},
    }
