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
    wellknown --> net["net.py<br/>guarded HTTP reader,<br/>request budget"]
    wellknown --> facts["wellknown_facts.py<br/>chunk, ledger, card, home-link checks"]
    facts --> net
    vectors --> areas["areas/<br/>one handler per area,<br/>each behind the expected-reads guard"]
    vectors --> index[("data/spec-index.json")]
    context --> published[("data/context.jsonld")]

    areas --> frontmatter["frontmatter.py"]
    areas --> slug["slug.py"]
    areas --> links["links.py"]
    areas --> graphmod["graph.py"]
    areas --> context["context.py"]
    areas --> discovery["discovery.py"]
    areas --> site["site.py"]
    areas --> wellknown
    areas --> rdf

    areas --> derive["derive.py<br/>readings"]
    areas --> questions["questions.py<br/>ten questions"]
    areas --> skos["skos.py<br/>SKOS view"]
    areas --> signposting["signposting.py<br/>Link of /, Dataset block"]
    areas --> catalogue["catalogue.py<br/>ard.json, ai-catalog.json"]
    areas --> agentcard["agentcard.py<br/>A2A agent card"]
    catalogue --> signposting

    frontmatter --> yamlsubset["yamlsubset.py"]
    frontmatter --> slug
    frontmatter --> links
    links --> markdown["markdown.py"]
    links --> relations["relations.py<br/>relation table"]
    relations --> table[("data/relations.json")]
    graphmod --> links
    graphmod --> relations
    graphmod --> rdf["rdf.py"]
    graphmod --> context
    context --> rdf
    derive --> relations
    questions --> links
    questions --> relations
    skos --> rdf
    discovery --> graphmod
    discovery --> links

    reader["reader.py<br/>reading API"]
```

The relation table of AGSC-03-01 has one source in the package: `relations.py` reads
`data/relations.json`, the engine's table written out by Node, and every module that
needs a key, an inverse or a property takes it from there (`tests/test_architecture.py`
fails when a module spells out a computed inverse name).

`areas/build_tree.py` checks the files a whole build wrote against the `build` cases
that need one (`build-0020` to `build-0028`, less `build-0024`, withdrawn in 1.1). It
builds nothing: the caller passes a function that runs a build, and the test suite
passes one that runs the engine's.

Every area handler runs behind `areas/_expected_reads.py`, the twin of the engine's
guard: a pass that left a member of a case's `expected` unread is turned into a fail,
so a vector cannot pass on an expectation no code compared.

`net.py` is the only module that opens a connection (`tests/test_architecture.py`
fails otherwise): every request of a run passes its address classification, its caps,
its deadline and one request budget for the run, redirects included (AGSC-11-10(c)).
`signposting.py`, `catalogue.py` and `agentcard.py` are pure writers of data: they give
what the home page, the two catalogue files and the agent card carry, so the vectors
that pin those bytes run here, though this package writes no site.

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
    opt the document links chunks, a ledger or an agent card
        W->>W: wellknown_facts: recompute count and set, ledger length, card served
    end
    opt target is a URL
        W->>N: fetch(/): the Link header of the home page (describedby, AGSC-06-40)
    end
    W->>D: envelope(findings, verb)
    D-->>W: envelope
    W-->>C: envelope, number of files read
    C->>D: exit_code(envelope)
    C-->>U: report, exit code 0, 1 or 2
```
