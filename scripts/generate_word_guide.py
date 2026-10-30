import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn

doc = docx.Document()

# Page Margins
for section in doc.sections:
    section.top_margin = Inches(1.0)
    section.bottom_margin = Inches(1.0)
    section.left_margin = Inches(1.0)
    section.right_margin = Inches(1.0)

# Colors
C_NAVY = RGBColor(24, 43, 73)
C_DARK = RGBColor(33, 37, 41)
C_TEAL = RGBColor(16, 124, 65)
C_BLUE = RGBColor(31, 78, 121)
C_MUTED = RGBColor(108, 117, 125)

def set_cell_background(cell, hex_color):
    shading_elm = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{hex_color}"/>')
    cell._tc.get_or_add_tcPr().append(shading_elm)

def set_cell_margins(cell, top=100, bottom=100, left=150, right=150):
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = OxmlElement('w:tcMar')
    for m, val in [('top', top), ('bottom', bottom), ('left', left), ('right', right)]:
        node = OxmlElement(f'w:{m}')
        node.set(qn('w:w'), str(val))
        node.set(qn('w:type'), 'dxa')
        tcMar.append(node)
    tcPr.append(tcMar)

# Title
p_title = doc.add_paragraph()
r_kicker = p_title.add_run('SYNERA PLATFORM · SYSTEM ARCHITECTURE\n')
r_kicker.font.size = Pt(10)
r_kicker.font.bold = True
r_kicker.font.color.rgb = C_BLUE

r_title = p_title.add_run('Trust Center — Beginner\'s Study Guide')
r_title.font.size = Pt(24)
r_title.font.bold = True
r_title.font.color.rgb = C_NAVY

p_sub = doc.add_paragraph()
r_sub = p_sub.add_run('How SYNERA uses cybersecurity, SHA-256 cryptography, and an immutable evidence ledger to guarantee tamper-proof scientific results.')
r_sub.font.size = Pt(11)
r_sub.font.italic = True
r_sub.font.color.rgb = C_MUTED

doc.add_paragraph() # Spacing

# Callout Box: What is the Trust Center?
tbl_box = doc.add_table(rows=1, cols=1)
tbl_box.alignment = WD_TABLE_ALIGNMENT.CENTER
c_box = tbl_box.cell(0, 0)
set_cell_background(c_box, 'F0F4F8')
set_cell_margins(c_box, top=160, bottom=160, left=200, right=200)

p_box = c_box.paragraphs[0]
r_box_h = p_box.add_run('THE CORE PURPOSE OF THE TRUST CENTER\n')
r_box_h.bold = True
r_box_h.font.size = Pt(10.5)
r_box_h.font.color.rgb = C_BLUE

r_box_b = p_box.add_run(
    'In modern AI and scientific research, it is easy for someone to quietly alter a data file, drop inconvenient rows, or secretly tweak model weights to produce a desired result. '
    'The Trust Center is SYNERA\'s automated "lie detector and security vault"—proving mathematically that nobody cheated, no data was doctored, and every single result is 100% genuine and reproducible.'
)
r_box_b.font.size = Pt(10.5)
r_box_b.font.color.rgb = C_DARK

doc.add_paragraph()

# Heading 1: The 3 Core Pillars
h1 = doc.add_heading(level=1)
r_h1 = h1.add_run('1. The 3 Core Pillars of Trust')
r_h1.font.color.rgb = C_NAVY

p_p1 = doc.add_paragraph(style='List Bullet')
r = p_p1.add_run('Pillar 1: Cybersecurity (Anomaly Detection): ')
r.bold = True
p_p1.add_run('Detects poisoned records, suspicious outliers, unit drift, and model tampering before and during execution.')

p_p2 = doc.add_paragraph(style='List Bullet')
r = p_p2.add_run('Pillar 2: Cryptographic Provenance (SHA-256 Hashes): ')
r.bold = True
p_p2.add_run('Every dataset, every Python file, every AI model, and every result gets a 64-character digital fingerprint. If even one single bit or character changes, the fingerprint changes completely.')

p_p3 = doc.add_paragraph(style='List Bullet')
r = p_p3.add_run('Pillar 3: Evidence Ledger (Blockchain Chain of Custody): ')
r.bold = True
p_p3.add_run('All fingerprints are chained together chronologically into an immutable, signed ledger. You cannot alter past records without breaking the entire chain.')

doc.add_paragraph()

# Heading 2: Guided Tour
h2 = doc.add_heading(level=1)
r_h2 = h2.add_run('2. Step-by-Step Guided Tour of the Trust Center')
r_h2.font.color.rgb = C_NAVY

# Section Top Bar
p_top = doc.add_paragraph()
r = p_top.add_run('Top Bar Status: LEDGER VALID\n')
r.bold = True
r.font.size = Pt(12)
r.font.color.rgb = C_TEAL
p_top.add_run('At the top right of the page, a green indicator displays whether the entire cryptographic ledger chain is intact. It displays the chain height (the total number of blocks recorded, e.g., 28 blocks) and the head hash (the cryptographic fingerprint of the latest block).')

# Section A
p_secA = doc.add_paragraph()
r = p_secA.add_run('Section A: A Vulnerable Path to Scientific Results\n')
r.bold = True
r.font.size = Pt(12)
r.font.color.rgb = C_BLUE
p_secA.add_run(
    'Think of a scientific result as a parcel passed through 6 different hands:\n'
    '  1. DATA -> 2. MODEL -> 3. CODE -> 4. PIPELINE -> 5. VERSION -> 6. REPRODUCIBILITY\n\n'
    'The red points in the diagram represent potential attack vectors where someone could tamper with the result:\n'
    '• Data Tampering: Caught by the SHA-256 dataset hash (change one bit, hash breaks).\n'
    '• Data Poisoning: Flagged by advisory anomaly detectors (Isolation Forest, Autoencoders, MCD).\n'
    '• Model Manipulation: Caught by model weights hash and hold-out probe prediction tests.\n'
    '• Code Alteration: Caught by source-tree git hash (any code change changes the hash).\n'
    '• Version Mismatch: Caught by the sequential blockchain ledger chain.\n'
    '• Reproducibility Failure: Caught by automated Replay (re-running the exact pipeline from recorded parameters to ensure identical outputs).'
)

# Section B
p_secB = doc.add_paragraph()
r = p_secB.add_run('Section B: The Trust Layer Philosophy\n')
r.bold = True
r.font.size = Pt(12)
r.font.color.rgb = C_BLUE
p_secB.add_run(
    'Key Maxim: "The ledger does not prove the science. It makes the computational provenance tamper-evident."\n'
    'In other words, the ledger cannot tell if a physical theory is true, but it provides mathematical proof of exactly how the experiment was conducted, what data was input, and that the result was not forged.'
)

# Section C
p_secC = doc.add_paragraph()
r = p_secC.add_run('Section C: The Tamper Simulator (Live Attack Playground)\n')
r.bold = True
r.font.size = Pt(12)
r.font.color.rgb = C_BLUE
p_secC.add_run(
    'This is an interactive security testing tool:\n'
    '1. You pick a dataset (e.g., India Grid or US Mortality) and an attack mode:\n'
    '   - Bit flip: Changes a single byte in the raw file.\n'
    '   - Row edit: Modifies numbers in data rows.\n'
    '   - Subtle edit: Adds a tiny +0.3 shift to values (trying to evade detection).\n'
    '   - Poison labels: Inverts health/event labels.\n'
    '   - Ledger tamper: Directly alters an entry in the ledger.\n'
    '2. When you click "LAUNCH ATTACK", SYNERA creates a temporary copy of the dataset in memory, applies the damage, and re-calculates the SHA-256 fingerprint.\n'
    '3. Result: The new hash does not match the registered hash, and the finding is immediately BLOCKED from VERIFIED status. (The live real data is never touched).'
)

# Section D
p_secD = doc.add_paragraph()
r = p_secD.add_run('Section D: How Reliable Are the Alarms?\n')
r.bold = True
r.font.size = Pt(12)
r.font.color.rgb = C_BLUE
p_secD.add_run(
    'This section highlights a vital truth in AI security:\n'
    '• AI Anomaly Detectors (Isolation Forest, Autoencoders) are statistical guesses. They can have a 3% to 5% false alarm rate on clean data, and often miss sneaky, subtle edits completely.\n'
    '• Cryptographic Hashes (SHA-256) are mathematical certainties. They catch 100.0% of attacks, with exactly 0.0% false alarms.\n'
    '• Golden Rule: Statistical detectors only advise and warn, but cryptographic hashes are what actually block.'
)

# Section E, F, G
p_secEFG = doc.add_paragraph()
r = p_secEFG.add_run('Sections E, F, and G: Ledger Explorer, Merkle Proof, and Live Integrity\n')
r.bold = True
r.font.size = Pt(12)
r.font.color.rgb = C_BLUE
p_secEFG.add_run(
    '• Ledger Explorer (Section E): Allows you to browse the ledger block-by-block, reading timestamps, data sources, code commits, and parent block hashes.\n'
    '• Merkle Proof (Section F): Generates a mathematical proof showing that a specific result or file is included in the ledger without requiring you to download the entire chain.\n'
    '• Live Integrity Check (Section G): Scans the real files currently on the server\'s disk right now, recalculating their SHA-256 hashes to guarantee they haven\'t suffered bit-rot or accidental modification.'
)

doc.add_paragraph()

# Table Summary
h3 = doc.add_heading(level=1)
r_h3 = h3.add_run('3. Quick Reference Summary for Beginners')
r_h3.font.color.rgb = C_NAVY

table = doc.add_table(rows=5, cols=3)
table.alignment = WD_TABLE_ALIGNMENT.CENTER

headers = ['Mechanism', 'What It Does', 'Why It Matters']
col_widths = [Inches(1.8), Inches(2.7), Inches(2.0)]

hdr_cells = table.rows[0].cells
for i, h_text in enumerate(headers):
    hdr_cells[i].text = h_text
    set_cell_background(hdr_cells[i], '1F4E79')
    set_cell_margins(hdr_cells[i], top=120, bottom=120, left=140, right=140)
    p = hdr_cells[i].paragraphs[0]
    p.runs[0].font.bold = True
    p.runs[0].font.color.rgb = RGBColor(255, 255, 255)
    p.runs[0].font.size = Pt(10)

data = [
    ('SHA-256 Hashes', 'Generates unique 64-character digital fingerprints of data, code, and models.', 'Any change, even 1 single bit, is caught instantly.'),
    ('Evidence Ledger', 'Chains fingerprint blocks together chronologically using cryptography.', 'Past results cannot be deleted, replaced, or rewritten.'),
    ('Tamper Simulator', 'Interactive live sandbox to simulate 5 attack modes on cloned data.', 'Demonstrates and proves that the defenses actually work.'),
    ('Replay Verification', 'Reruns the entire statistical pipeline from recorded parameters.', 'Proves that results are deterministic, reproducible science.')
]

for row_idx, (m, w, y) in enumerate(data, start=1):
    row_cells = table.rows[row_idx].cells
    row_cells[0].text = m
    row_cells[1].text = w
    row_cells[2].text = y
    bg_color = 'F9FAFC' if row_idx % 2 == 1 else 'FFFFFF'
    for c_idx, cell in enumerate(row_cells):
        set_cell_background(cell, bg_color)
        set_cell_margins(cell, top=100, bottom=100, left=140, right=140)
        p = cell.paragraphs[0]
        p.runs[0].font.size = Pt(9.5)
        p.runs[0].font.color.rgb = C_DARK
        if c_idx == 0:
            p.runs[0].font.bold = True

for row in table.rows:
    for i, w in enumerate(col_widths):
        row.cells[i].width = w

out_path = 'd:/synera1.0/synera/SYNERA_Trust_Center_Beginner_Guide.docx'
doc.save(out_path)
print('Successfully saved to:', out_path)
