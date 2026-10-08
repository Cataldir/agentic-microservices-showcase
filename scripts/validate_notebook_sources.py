"""Validate notebook JSON and Python cell syntax without executing cells."""
from pathlib import Path
import ast
import json

def main():
    root = Path(__file__).resolve().parents[1]
    notebooks = list((root / "notebooks").rglob("*.ipynb"))
    if not notebooks:
        raise ValueError("No notebooks found")
    code_cells = 0
    for path in notebooks:
        notebook = json.loads(path.read_text(encoding="utf-8"))
        for index, cell in enumerate(notebook.get("cells", [])):
            if cell.get("cell_type") == "code":
                source = cell.get("source", [])
                source = "".join(source) if isinstance(source, list) else source
                compile(source, f"{path.name}:cell{index}", "exec",
                        flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT)
                code_cells += 1
    print(json.dumps({"notebooks": len(notebooks), "code_cells_compiled": code_cells,
                      "cells_executed": 0, "cloud_calls": 0}))

if __name__ == "__main__":
    main()
