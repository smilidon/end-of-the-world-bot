# Recovery and offline preparation

1. While online, save the source, license notices, OS packages/Python wheels,
   compatible optional tools, chosen model weights and their licenses/checksums.
   Use official upstream instructions; do not assume dependencies are preinstalled.
2. Keep documents and runtime outputs outside git. Back up the dedicated library
   and tools separately; this source repository is not a dataset/model backup.
3. After a move or restore, select the new --root and --nav paths. Re-run synthetic
   tests, a known reference query and a PDF citation. Test optional tools separately.
4. If the index is stale, stop your own CLI/server activity, move
   library/local-qa/guides.sqlite to a backup location, then run the index command.
   Indexing refuses overwrite; do not edit or reuse a live app database.
5. If PDFs yield no text, check pdftotext and whether the PDF is scanned. There is
   no bundled OCR. If no result is found, use the original PDF or Kiwix manually.
6. If Ollama or WebUI fails, search still works without AI. Read the reported
   source locations directly. If routing/native rendering fails, no missing
   road geometry or coordinates should be invented.

A complete air-gap restore and reboot of a clean device have not been tested.
Keep these instructions and useful original reference documents accessible without
the agent, cloud, model or chat UI.
