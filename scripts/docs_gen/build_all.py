"""
Master Documentation Build Orchestrator for OmniPost (20-Notification-Delivery-Platform).
Executes all generator modules in sequence.
"""

import os
import sys

# Add script directory to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from gen_overview_and_scan import generate_overview_and_scan
from gen_features import generate_features_docs
from gen_architecture_and_tech import generate_architecture_and_tech
from gen_interview_and_improvements import generate_interview_and_improvements
from gen_system_design import generate_system_design
from gen_checklist import generate_master_checklist
from gen_vitepress_config import generate_vitepress_config

def main():
    root_dir = os.path.dirname(os.path.dirname(current_dir))
    docs_dir = os.path.join(root_dir, "docs")
    print(f"🚀 Starting OmniPost documentation build in: {docs_dir}")

    # 1. Overview and Project Scan
    print("▶ Generating Step 0, Step 0.1, Step 1, and Pitches...")
    generate_overview_and_scan(docs_dir)

    # 2. Features and Say It Out Loud
    print("▶ Generating Step 2 Feature Inventory & Step 2.5 Say It Out Loud...")
    generate_features_docs(docs_dir)

    # 3. Architecture, Build Order, API Reference, Tech Comparisons, Security, AI, Ops
    print("▶ Generating Steps 3, 4, 5, 6, 7, 8, 9...")
    generate_architecture_and_tech(docs_dir)

    # 4. Interview Q&A, Gaps, Glossary, Confirm List
    print("▶ Generating Steps 10, 11, 12 Interview Q&A, Gaps, Glossary, Confirm List...")
    generate_interview_and_improvements(docs_dir)

    # 5. System Design Deep Dive (17 chapters + decisions)
    print("▶ Generating Step 14 System Design Deep Dive Suite...")
    generate_system_design(docs_dir)

    # 6. Master Checklist (All 275 items)
    print("▶ Generating Master Checklist (All 275 items)...")
    generate_master_checklist(docs_dir)

    # 7. VitePress Configuration & Themes
    print("▶ Generating Step 13 VitePress Config, Themes & Index...")
    generate_vitepress_config(docs_dir)

    print("✅ All documentation files successfully generated.")

if __name__ == "__main__":
    main()
