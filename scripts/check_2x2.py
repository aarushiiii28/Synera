import json
from synera_core.data.osdr import get_meta

def analyze_study(osd_id):
    meta = get_meta(osd_id)
    study_node = meta['study'].get(osd_id)
    if not study_node:
        study_node = list(meta['study'].values())[0]
        
    study = study_node['studies'][0]
    
    factors = study.get('factors', [])
    factor_map = {f.get('@id'): f.get('factorName', '') for f in factors}
    print(f"\n--- {osd_id} Factors ---")
    for fn in factor_map.values():
        print(f"  - {fn}")
        
    samples = study.get('materials', {}).get('samples', [])
    
    cells = {}
    sample_names = set()
    animal_ids = set()
    
    for s in samples:
        name = s.get('name', '')
        sample_names.add(name)
        chars = s.get('characteristics', [])
        for c in chars:
            val = c.get('value', '')
            if isinstance(val, dict):
                val = val.get('annotationValue', '')
            # simple heuristic for animal number
            if name.split('_')[-1].startswith('M'):
                animal_ids.add(name.split('_')[-1])
                
        factor_values = s.get('factorValues', [])
        # determine rad and grav
        rad = 0
        grav = 0
        for fv in factor_values:
            cat_id = fv.get('category', {}).get('@id', '')
            cat = factor_map.get(cat_id, '').lower()
            val = fv.get('value', '')
            if isinstance(val, dict):
                val = val.get('annotationValue', '')
            val = str(val).lower()
            
            if 'radiation' in cat or 'dose' in cat or 'ionizing' in cat:
                if val and val not in ['0 gy', '0', 'none', 'sham', 'control', '0 cgy', '0gy', 'non-irradiated']:
                    rad = 1
            if 'spaceflight' in cat or 'microgravity' in cat or 'unloading' in cat or 'suspension' in cat or 'gravity' in cat:
                if val and val not in ['none', 'control', 'sham', '1g', 'normally loaded control']:
                    grav = 1
                    
        cell = (rad, grav)
        cells[cell] = cells.get(cell, 0) + 1
        
    print(f"n per cell:")
    print(f"  Control (Rad=0, Grav=0): {cells.get((0,0), 0)}")
    print(f"  Radiation (Rad=1, Grav=0): {cells.get((1,0), 0)}")
    print(f"  HLU (Rad=0, Grav=1): {cells.get((0,1), 0)}")
    print(f"  Both (Rad=1, Grav=1): {cells.get((1,1), 0)}")
    
    # Validation check
    for cell in [(0,0), (1,0), (0,1), (1,1)]:
        if cells.get(cell, 0) < 2:
            print(f"ERROR: Cell {cell} has fewer than 2 samples!")
            
    return sample_names, animal_ids

s1, a1 = analyze_study("OSD-211")
s2, a2 = analyze_study("OSD-237")

overlap_s = s1.intersection(s2)
overlap_a = a1.intersection(a2)

print("\n--- Overlap Check ---")
print(f"Sample name overlap: {len(overlap_s)}")
print(f"Animal ID overlap: {len(overlap_a)}")

if overlap_a:
    print(f"Animals overlap between OSD-211 and OSD-237. These tissues come from the SAME COHORT.")
    print("Evidence level: CROSS_TISSUE_SAME_COHORT")
else:
    print("No animal overlap. Independent replication.")
