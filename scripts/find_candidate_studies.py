import json
import pandas as pd

from synera_core.data.osdr import search_studies, get_meta, list_files
from synera_core.config import find_repo_root

def main():
    terms = [
        "spaceflight", "microgravity", "hindlimb unloading", "clinostat", 
        "ionizing radiation", "heavy ion", "HZE", "gamma", "proton", "Rodent Research"
    ]
    
    print("Searching for candidate studies...")
    studies = {}
    for term in terms:
        try:
            res = search_studies(term)
            hits = res.get("hits", {}).get("hits", [])
            for hit in hits:
                source = hit.get("_source", {})
                study_id = source.get("Study Identifier")
                if not study_id:
                    continue
                    
                assay_type = source.get("Study Assay Measurement Type", "").lower()
                # Filter for transcriptomics
                if not any(x in assay_type for x in ["rna", "transcription", "microarray", "seq"]):
                    continue
                    
                if study_id not in studies:
                    studies[study_id] = source
        except Exception as e:
            print(f"Error searching {term}: {e}")

    print(f"Found {len(studies)} potential transcriptomics studies.")
    
    candidates = []
    
    for idx, (study_id, source) in enumerate(studies.items()):
        # Limit to first 50 to avoid hours of API calls, if necessary, but we need the best ones.
        # So we process all.
        print(f"[{idx+1}/{len(studies)}] Analyzing {study_id}...")
        try:
            meta = get_meta(study_id)
        except Exception as e:
            print(f"Failed to fetch meta for {study_id}: {e}")
            continue
            
        meta_str = json.dumps(meta).lower()
        source_str = json.dumps(source).lower()
        combined_str = meta_str + source_str
        
        # Extract factors from meta
        study = meta.get("study", {})
        factors = study.get("study_factors", [])
        factors_str = json.dumps(factors).lower()
        
        has_gravity = any(x in combined_str for x in ["spaceflight", "microgravity", "hindlimb unloading", "clinostat"])
        
        # Radiation must be a factor, not just mentioned in spaceflight text
        rad_terms = ["dose", "irradiated", "gamma", "ionizing", "proton", "hze", "radiation"]
        has_rad = any(x in factors_str for x in rad_terms)
        
        score = 0
        is_2x2 = False
        if has_gravity and has_rad:
            score += 3
            is_2x2 = True
            
        organism = source.get("organism", "").lower()
        if "mouse" in organism or "mus musculus" in organism or "human" in organism or "homo sapiens" in organism:
            score += 1
            
        # Replicates - crude heuristic
        if combined_str.count("sample name") >= 12 or combined_str.count("source name") >= 12:
            score += 1
            
        try:
            files = list_files(study_id)
            files_str = json.dumps(files).lower()
            if "processed" in files_str or "normalized" in files_str or "counts" in files_str:
                score += 1
        except Exception:
            pass
            
        candidates.append({
            "study_id": study_id,
            "title": source.get("Study Title", ""),
            "organism": organism,
            "has_gravity": has_gravity,
            "has_rad": has_rad,
            "is_2x2": is_2x2,
            "score": score
        })
        
    df = pd.DataFrame(candidates)
    if not df.empty:
        df = df.sort_values("score", ascending=False)
        
        out_dir = find_repo_root() / "data" / "interim"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "osdr_candidates.csv"
        df.to_csv(out_path, index=False)
        
        print("\nTop 15 candidates:")
        print(df.head(15)[["study_id", "score", "is_2x2", "organism", "title"]])
    else:
        print("No candidates found.")
        
if __name__ == "__main__":
    main()
