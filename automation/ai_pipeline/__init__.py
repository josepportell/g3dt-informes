"""AI pipeline — LLM-first project processing.

Stage 1 (inventory) and Stage 2 (typology) coexist with the existing
deterministic stack (FileScanner, FileMiner, ConceptScout, auto_extractor).

Import symbols directly from their submodules to avoid load-order races
under concurrent requests (e.g. FastAPI threadpool):

    from automation.ai_pipeline.inventory import build_inventory, Inventory
    from automation.ai_pipeline.typology import classify_project, ProjectTypology

See docs/ARQUITECTURA-AI-PIPELINE.md.
"""
