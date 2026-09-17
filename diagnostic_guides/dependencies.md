# Python and optional dependency preparation

This bot needs Linux, Python 3.11+ and SQLite FTS5 for installation and indexing.
Text/Markdown retrieval requires no pip dependencies. Missing pdftotext affects
PDF indexing only; Poppler must be prepared separately before going offline.

A missing module may indicate an absent optional dependency or a different selected
Python environment. Compare the exact message with START_HERE and the interpreter
the owner selected. Do not install packages or change PATH based on a log alone.
