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
| `wellknown_facts.py` | the checker's 1.1 checks of what the document links: the chunk count, set commitment and digest (AGSC-06-44), the ledger length, the agent card on the node's own origin (AGSC-11-16), the `describedby` link in the `Link` header of `/` (AGSC-06-40) |
| `signposting.py` | the Signposting links of `/` (AGSC-06-40), the licence URL (AGSC-06-44) and the home page's Dataset block (AGSC-06-41), as data |
| `catalogue.py`, `agentcard.py` | the opt-in `/.well-known/ard.json` and `ai-catalog.json` (AGSC-06-42) and the A2A agent card (AGSC-06-34), as bytes |
| `vectors.py` | the conformance-vector checker, the runner, and the specification index |
| `areas/` | one handler per vector area this package runs natively (`discovery_web.py` holds the web-connection cases disc-0026 to disc-0031, disc-0033 and disc-0035 to disc-0038, by vector id), `build_tree.py`, which checks the files a whole build wrote against `build-0020` to `build-0028`, and `_expected_reads.py`, the guard that fails a pass which left a member of `expected` unread, as the engine's handlers are guarded |
| `reader.py` | the reading API: a discovery document, its links, digests, chunks and graph |
| `diagnostics.py` | the diagnostics envelope and its findings |
| `jcs.py` | canonical JSON (RFC 8785) and the strict I-JSON reader |
| `yamlsubset.py`, `frontmatter.py` | the closed YAML subset, item checks and adoption |
| `slug.py`, `links.py`, `markdown.py` | slugs, the fourteen Link keys with the four Link warnings of AGSC-03-23 to 03-26, a small CommonMark scanner |
| `relations.py` | the relation table of AGSC-03-01 (keys, inverses, RDF properties, self-link readings, expected target kinds), read from `data/relations.json`; `links.py` and `graph.py` take theirs from it |
| `derive.py`, `questions.py` | the readings of the Link graph with their reasons (AGSC-05-33) and the ten questions (AGSC-05-34) |
| `graph.py`, `rdf.py`, `context.py`, `skos.py` | the RDF dataset, canonical N-Quads and Turtle, `graph.jsonld` and the per-item files, the JSON-LD context, the SKOS view of `export --skos` (AGSC-05-36) |
| `discovery.py`, `site.py` | `llms.txt`, the link set, the search index, headers, `security.txt`, the content version |
| `urls.py`, `net.py` | URL handling, and the guarded HTTP reader used only with `--allow-network`, with the run's request budget (AGSC-11-10(c)); the only module that opens a connection |
| `data/spec-index.json` | the rule identifiers, error codes and version this package ships |
| `data/context.jsonld` | the published JSON-LD context, as the engine's `tools/gen-ns` derives it; `graph.jsonld` is compacted with it |
| `data/relations.json` | the relation table, as the engine's `src/knowledge/relations.js` holds it (written out by the command in docs/MAINTAINING.md) |
