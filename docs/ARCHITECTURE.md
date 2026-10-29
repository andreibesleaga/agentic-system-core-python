# Architecture of the Python package

**Summary.** What the package talks to, and how its modules call each other. The
diagrams use the module names of `src/agentic_system_core/`; the one-line purpose of each
module is in [src/agentic_system_core/README.md](../src/agentic_system_core/README.md).

**Read after:** the [README](../README.md). **Read next:** [MAINTAINING.md](MAINTAINING.md).

## The package and its surroundings

The package reads a discovery document and a vector set, writes a diagnostics envelope
and an exit code, and hands every verb it does not run itself to the Node engine. It opens
a network connection only when `--allow-network` is on the command line.

```mermaid
flowchart LR
    user["Person or CI job"] -->|"agsc verb, or Python import"| pkg["agentic-system-core<br/>(this package)"]
    pkg -->|"reads"| doc["Discovery document<br/>(file, or URL with --allow-network)"]
    pkg -->|"reads"| vec["Conformance-vector set<br/>(engine repo or npm package)"]
    pkg -->|"diagnostics envelope, exit code"| user
    pkg -->|"the sixteen engine verbs, as typed"| node["Node engine<br/>(npm agentic-system-core, agsc)"]
```

The engine is a separate program: the package never imports it. The tests run it beside
this repository to prove the two agree (see [MAINTAINING.md](MAINTAINING.md)).

## Modules and calls

An arrow means "imports". `cli.py` is the only entry point; the rest is a library.
`jcs.py`, `diagnostics.py` and `urls.py` are used from several places and are left out of
the picture to keep it readable: `jcs.py` (canonical JSON) is imported by many
modules, `diagnostics.py` (the envelope and the exit code) by `cli.py`, `wellknown.py`
and `vectors.py`, and `urls.py` by `net.py`, `reader.py` and `wellknown.py`.

```mermaid
flowchart TD
    cli["cli.py<br/>agsc command"] --> wellknown["wellknown.py<br/>discovery-file checker"]
    cli --> vectors["vectors.py<br/>vector checker and runner"]
    cli -->|"passes fetch in"| net
    cli -->|"subprocess, no shell"| node["Node engine agsc"]
    wellknown --> net["net.py<br/>guarded HTTP reader"]
    vectors --> areas["areas/<br/>one handler per area"]
    vectors --> index[("data/spec-index.json")]

    areas --> frontmatter["frontmatter.py"]
    areas --> slug["slug.py"]
    areas --> links["links.py"]
    areas --> graphmod["graph.py"]
    areas --> context["context.py"]
    areas --> discovery["discovery.py"]
    areas --> site["site.py"]
    areas --> wellknown
    areas --> rdf

    frontmatter --> yamlsubset["yamlsubset.py"]
    frontmatter --> slug
    frontmatter --> links
    links --> markdown["markdown.py"]
    graphmod --> links
    graphmod --> rdf["rdf.py"]
    context --> rdf
    discovery --> graphmod
    discovery --> links

    reader["reader.py<br/>reading API"]
```

`reader.py` stands apart: no other module imports it, and it imports only the package
constants, `urls.py` and `jcs.py`. It never opens a connection; a fetcher is passed in by
the caller.

## One run of `agsc validate-wellknown`

```mermaid
sequenceDiagram
    participant U as Person or CI job
    participant C as cli.py
    participant W as wellknown.py
    participant N as net.py
    participant D as diagnostics.py
    U->>C: agsc validate-wellknown FILE, level 2
    C->>W: validate(target, level, peer, dev, allow_network, fetcher=net.fetch)
    W->>W: load(target): read the file
    opt target is a URL and network reads are allowed
        W->>N: fetch(url): classify, pin, follow at most three redirects
        N-->>W: final URL, headers, bytes
    end
    W->>W: check(source, level, findings)
    W->>D: envelope(findings, verb)
    D-->>W: envelope
    W-->>C: envelope, number of files read
    C->>D: exit_code(envelope)
    C-->>U: report, exit code 0, 1 or 2
```
