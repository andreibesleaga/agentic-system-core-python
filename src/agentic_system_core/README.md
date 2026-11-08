# `agentic_system_core/` — the package

**Summary.** The Python package: a discovery-file checker, a conformance-vector checker
and runner for seven areas, a small reading API, and the `agsc` command that runs those
and hands every other verb to the Node engine. Standard library only.

**Read after:** the repository [README](../../README.md). **Read next:**
[docs/MAINTAINING.md](../../docs/MAINTAINING.md).

| Module | What it does |
|---|---|
| `cli.py` | the `agsc` command: the three checker verbs here, every other verb forwarded to Node |
| `wellknown.py` | the discovery-file checker, the Python twin of the engine's `validate-wellknown` |
| `vectors.py` | the conformance-vector checker, the runner, and the specification index |
| `areas/` | one handler per vector area this package runs natively, and `build_tree.py`, which checks the files a whole build wrote against `build-0020` to `build-0028` |
| `reader.py` | the reading API: a discovery document, its links, digests, chunks and graph |
| `diagnostics.py` | the diagnostics envelope and its findings |
| `jcs.py` | canonical JSON (RFC 8785) and the strict I-JSON reader |
| `yamlsubset.py`, `frontmatter.py` | the closed YAML subset, item checks and adoption |
| `slug.py`, `links.py`, `markdown.py` | slugs, the fourteen Link keys, a small CommonMark scanner |
| `graph.py`, `rdf.py`, `context.py` | the RDF dataset, canonical N-Quads and Turtle, `graph.jsonld` and the per-item files, the JSON-LD context |
| `discovery.py`, `site.py` | `llms.txt`, the link set, the search index, headers, `security.txt`, the content version |
| `urls.py`, `net.py` | URL handling, and the guarded HTTP reader used only with `--allow-network` |
| `data/spec-index.json` | the rule identifiers, error codes and version this package ships |
| `data/context.jsonld` | the published JSON-LD context, as the engine's `tools/gen-ns` derives it; `graph.jsonld` is compacted with it |
