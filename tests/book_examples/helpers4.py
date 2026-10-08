"""Portable source paths for chapter 4's offline book-example tests."""
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[2]
EXAMPLES = REPOSITORY / "docs" / "book-examples" / "chapters-02-04"
CHAPTER04 = REPOSITORY / "core" / "book_examples" / "chapter04"
