## Context Navigation (Graphify + Obsidian)

1. Before scanning the entire codebase with grep or file searches, inspect `graphify-out/graph.json` or the Obsidian markdown notes in `graphify-out/obsidian/`.
2. Identify caller/callee links and affected submodules from the graph nodes first.
3. Only read raw source code for the specific files that need editing.
