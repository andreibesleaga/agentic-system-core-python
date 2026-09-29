# Agentic System Core — Python

Two checkers and a small reading API for AgenticSystemCore knowledge nodes, in
pure Python, plus one `agsc` command that runs those and hands every other verb
to the Node engine.

**This is not a second implementation of the engine.** Building a Bundle,
emitting a site, composing, importing, exporting and governing all stay with the
Node package `agentic-system-core`. What this package gives you is the part a
consumer needs when there is no Node on the machine: checking a published node's
discovery file, checking and running a conformance-vector set, and reading a
node's links, digests, chunks and graph. A full Python implementation of the
engine may come later; when it does, this text will change.

Standard library only. No runtime dependency, and none is planned: everything
here is either a rule of the specification or something Python already ships.

**What the specification is, and what is different about it.** AgenticSystemCore turns
a folder of Markdown files into a knowledge node that people and agents can find,
verify and cite. Other systems have some of these properties; to the author's knowledge none has
them together: a knowledge base a machine can find through registered web mechanisms,
a digest on everything it points at, a typed graph with a published vocabulary, bytes
pinned by conformance vectors, a person on every merge — directly, or by a standing
rule that person recorded — and a runnable harness out of the same files, with no
server. This package is the Python reader and checker of such nodes; maintainers read
[docs/MAINTAINING.md](docs/MAINTAINING.md).

## Install

```
pip install --pre agentic-system-core
```

Until `1.0.0` is released, every version of this package is a release candidate
(`1.0.0rc6` today), and pip installs a release candidate only when asked: use
`--pre`, or name the version, `pip install "agentic-system-core==1.0.0rc6"`. The
two `0.0.x` versions on PyPI only reserved the name, contain no code and are
yanked, so a plain `pip install agentic-system-core` finds nothing to install.

Python 3.9 or newer. To forward the other verbs you also need Node 22.13 or
newer and the npm package:

```
npm install -g agentic-system-core
```

**Two commands named `agsc`.** The npm package installs an `agsc` too, and it is
the engine's command line: its verbs are exactly the sixteen of the specification
(AGSC-09-07), so `validate-wellknown`, `validate-vectors` and `run-vectors` are not
among them, and it refuses them with `AGSC-E001`. The `agsc` here is a checker
distribution (the AGSC-09-90 contracts) that runs those three itself and hands
every other verb to the engine. With both installed, whichever directory comes
first on your `PATH` decides which `agsc` you get; `python -m agentic_system_core.cli`
always reaches this one.

## What runs here

### `agsc validate-wellknown <file>`

Checks one discovery document — the file a node serves at
`/.well-known/knowledge-linkset` — against the rules that govern it: the media
type and profile, the link-set shape, the anchor, the member and target
ordering, the relation names, the target attributes, the digest form, the
surface declarations, and, with `--peer`, the mutual check between two nodes.

```
agsc validate-wellknown www/.well-known/knowledge-linkset --level 2 --json
agsc validate-wellknown www/.well-known/knowledge-linkset \
     --peer ../other/www/.well-known/knowledge-linkset
```

Levels 0 to 3 mean what the specification says they mean. At Level 0 and 1 the
shape, the names, the ordering and the digest form are checked. At Level 2 and
above the document must also be canonical bytes, every artefact link must carry
a digest, the graph link must carry its five bundle facts, and the ledger must be
linked with its head. A node that declares itself `restricted` must instead omit
its content facts, its ledger link and the digest of every target it does not
serve openly (AGSC-11-20). A document that declares a newer MINOR of the same
MAJOR may use relations and attributes this version does not define: they are
ignored with the warning `AGSC-E506`, never reported as errors; a document of
another MAJOR gets no such tolerance (AGSC-00-21, AGSC-09-93).

When the document is a file inside a `.well-known/` directory, every
same-origin target is resolved on disk and its digest is verified against the
real bytes — so a build output is checked completely with no network at all.

Output is the same diagnostics envelope the engine emits (`--json`), and the
exit code is the same: 0 pass, 1 fail, 2 usage fault.

**Reading a URL needs `--allow-network`.** This is the one deliberate difference
from the Node tool, which reads a URL argument without asking. Nothing in this
package opens a connection unless that flag is on the command line. With it, the
same protections apply: https only (plain http to loopback under `--dev`), every
resolved address classified and refused if it is private, link-local, loopback
or reserved, the connection pinned to the address that was classified, at most
three redirects, ten seconds, one mebibyte.

### `agsc validate-vectors <dir>` and `agsc run-vectors <dir>`

`validate-vectors` checks a conformance-vector set against the file-format
rules: the required members, the closed area and level lists, the identifier
grammars, the file encoding, the canonical member order, and the resolution of
every rule identifier and every error code against the specification. An empty
set is a failure, not a clean run.

Resolving identifiers needs the specification. This package ships a small index
of it — the rule identifiers, the registered error codes and the declared
version — derived from `spec/` by command; `--spec <dir>` derives the same index
from a live `spec/` directory instead.

`run-vectors` executes the vectors. **It runs seven areas natively — `build`,
`discovery`, `frontmatter`, `graph`, `jcs`, `links` and `slug` — and names every
other area as not run, with the reason.** Each of the seven is derived from the
rule text of the specification alone, in the standard library:

| Area | What this package implements for it |
|---|---|
| `frontmatter` | a reader for the closed YAML subset of AGSC-02-02 (failsafe scalars, each rejected construct under its own code, line numbers), the item checks of spec/02, and the drop-in adoption of AGSC-02-90…93 |
| `slug` | the slug grammar and uniqueness |
| `jcs` | RFC 8785 canonical JSON with NFC before sorting |
| `links` | the fourteen Link keys and their inverses, the cycle and cluster-tree checks, heading anchors, and inline-link resolution over a small CommonMark 0.31.2 scanner (headings and inline links only, outside code; its subset is written down in `agentic_system_core/markdown.py`) |
| `graph` | the RDF dataset of spec/05, canonical `graph.nq` (every line a quad named by the Bundle IRI, AGSC-04-15), the byte-pinned `graph.ttl` profile of AGSC-05-10, and the JSON-LD context of AGSC-06-32 with the compaction it round-trips |
| `build` | the `search.json` tokenizer and index, static query fragments, the served header set, `security.txt`, the content version and the staleness comparison; the two `build` vectors that need a whole Bundle build are reported as not run, by name |
| `discovery` | `/llms.txt` and `/llms-full.txt` byte for byte, reachability, the sitemap and robots facts, the link-set writer, and the discovery-document checks including the restricted-node rule of AGSC-11-20 |

The other areas need a Bundle build, the engine's composition or governance
modules, or its command-line surface. Nothing is ever counted as a pass that
was not executed, and nothing is silently skipped.

The pending list is the engine's: a file `{"pending": [ids], "reason": {…}}`,
found beside the vectors or named with `--pending`.

### `agentic_system_core.reader`

```python
from agentic_system_core.reader import DiscoveryDocument, read_chunks, read_graph

node = DiscoveryDocument.from_path("www/.well-known/knowledge-linkset")
node.anchor                      # 'https://example.org/'
node.links("graph")              # the rel#graph targets
node.peers()                     # the nodes it federates with
node.surfaces()["chunks"].href   # where the chunk export is

link = node.links("alternate")[0]
link.verify(open("www/llms.txt", "rb").read())   # digest against bytes you hold
link.fetch(my_fetcher)                            # nothing fetches by itself
```

`read_chunks` reads `chunks.jsonl` into a list of records, or returns the shard
manifest as it stands when the file is one. `read_graph` reads `graph.jsonld` as
plain JSON — no RDF library, no triples; turning it into a graph is a job for a
library you choose.

A member the reader does not know — in a chunk line, a chunk manifest, the graph or
a discovery document of a later version of the specification — is neither refused
nor rewritten: it is kept as it stands, and the calls above simply do not read it
(AGSC-00-21).

A digest is an RFC 9530 dictionary member, whose value RFC 9530 defines as "a
Byte Sequence (Section 3.3.5 of [STRUCTURED-FIELDS]) that conveys an encoded
version of the byte output produced by the digest calculation" — base64 between
two colons, which is why it reads `sha-256=:<base64>:`.

## What forwards to Node

Every other verb: `init`, `lint`, `build`, `verify`, `ci`, `export`, `import`,
`compose`, `propose`, `review`, `refresh`, `skills`, `mcp`, `run`, `trace`,
`conform`. If the npm package's `agsc` is on the PATH, the call is handed to it
exactly as typed and its exit code comes back. If it is not, the command stops
with one sentence saying what to install. The call is made with a list of
arguments and never through a shell.

## Version

The specification version is `1.0.0-rc.6`, a SemVer pre-release. Python packages
use PEP 440, which spells the same pre-release `1.0.0rc6`, and that is the
version on PyPI. `agsc --version` prints both.

## The vector copies in this repository

`tests/fixtures/vectors/` holds byte-identical copies of the vectors of the
seven areas this package runs, so that the test suite proves the promise
without needing the engine checkout. When the engine is beside this
repository, one test compares the copies with the originals byte for byte and
fails if they have drifted, and another runs the engine's own vector runner
over the engine's live set and requires the two runners to agree on every
vector of those seven areas.

## Equivalence with the engine's checker

The discovery-file checker is meant to give the same verdict as the engine's
`tools/validate-wellknown` on the same input. The test suite proves it: both
tools are run over the same documents — the fixture set, a document taken from
the engine's own conformance vectors, the built discovery files of two live
sites and a set of deliberately broken files — at every Level, with and without
a peer, and the status, the counts and the position and code of every finding
are compared. Message text is not compared: the specification leaves a message
unspecified so it can be translated, and pins the code. That test is skipped,
with a message saying so, when Node or the engine checkout is not present.

## Tests

```
python -m venv .venv && .venv/bin/pip install -e ".[test]"
.venv/bin/python -m pytest
.venv/bin/python -m coverage run -m pytest && .venv/bin/python -m coverage report
```

Deterministic, fixed data, no clock, no network. The only subprocess in the
suite is the Node tool in the equivalence test.

## Licence

Apache-2.0. See `LICENSE`.

The conformance vectors copied under `tests/fixtures/vectors/` and the rule index in
`src/agentic_system_core/data/` come from the specification's distribution and keep the
licences stated there (the engine repository's README and `LICENSE-CONTENT`).

## How this is made

This work is written and maintained by Andrei N. Besleaga with the help of AI
assistants. A person decides what is written, an assistant drafts and checks it, and a
person reads, edits and approves everything that is published and answers for it. Every
published item records how its text was made and names the person accountable for it.
Written with AI assistance, reviewed and published by a person.
The assistance covered text and code alike. This package calls no AI model. What an
assistant or agent writes from this work is its own output, not a statement by the author.

## What this does not claim

This is the independent work of one person, published as it is, with no warranty of any
kind and no liability for anything that follows from using it. Nothing in it is legal or
professional advice. No standards body, foundation, company or institution named in this
repository has reviewed, approved or is connected with this work, and it is not a document
of the IETF, of the W3C or of any other body. Other product and organisation names are the
marks of their owners and are used only to say what is being talked about.
Every right not expressly granted by the licences is reserved, and nothing here promises
that the work or its addresses will stay available.

## Notice

AgenticSystemCore™ is a trademark of Andrei N. Besleaga. Other names belong to their owners.

© 2026 Andrei N. Besleaga. Code: Apache-2.0. Schemas, ontology, identifiers and the
discovery document: CC0-1.0.
