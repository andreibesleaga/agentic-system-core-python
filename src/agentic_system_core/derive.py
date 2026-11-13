"""The readings of the Link graph, each with its reasons (AGSC-05-33).

What: from the edges ``links.edges`` returns, the relations the graph holds without
anyone having authored them. A reading is ``{source, key, target, because}``;
``because`` is a list of steps ``{rule, from}``, ``from`` being the edges
``[source, key, target]`` the step used:

* ``inverse`` — the computed inverse of an authored edge (a);
* ``symmetric`` — the other direction of ``related``, ``excludes``, ``contradicts`` (b);
* ``transitive`` — a chain of two or more edges of one transitive key (c);
* ``closure`` — the same chain for ``requires`` and ``required-by`` (d).

Why: the engine's ``check``, ``explain`` and composition brief read these readings, and
``graph-0029`` pins them; a port that answers "why is this so" must give the same
reasons. Nothing here is written to a graph file: readings are computed on demand.
The engine's ``src/knowledge/derive.js`` is the reference; the transitive column and
the inverse names come from the relation table (``relations.py``).

Standard library only.
"""

from .relations import INVERSE, RELATIONS, SYMMETRIC

#: Every name an edge can carry -> the name of the edge it was computed from.
PARTNER = dict(pair for row in RELATIONS
               for pair in ((row["key"], row["inverse"]), (row["inverse"], row["key"])))

#: AGSC-05-33 (c): each transitive key and its computed inverse, in code-point order.
CHAIN_KEYS = tuple(sorted(set(name for row in RELATIONS if row["transitive"]
                              for name in (row["key"], row["inverse"]))))
#: AGSC-05-33 (d): the chains read as a closure.
CLOSURE_KEYS = ("requires", INVERSE["requires"])


def _direct(edges):
    """(a) and (b): each computed edge that is the inverse or the swap of an authored one."""
    out = []
    for edge in edges:
        if not edge["computed"] or edge["key"] not in PARTNER:
            continue
        out.append({
            "because": [{
                "from": [[edge["target"], PARTNER[edge["key"]], edge["source"]]],
                "rule": "symmetric" if edge["key"] in SYMMETRIC else "inverse",
            }],
            "key": edge["key"], "source": edge["source"], "target": edge["target"]})
    return out


def _walk(adjacency, start):
    """Breadth first from ``start``, each frontier in code-point order: every item reached,
    with the item it was first reached from and its depth (the shortest chain)."""
    reached = {start: (None, 0)}
    frontier = [start]
    depth = 0
    while frontier:
        depth += 1
        following = []
        for node in frontier:
            for target in sorted(adjacency.get(node, ())):
                if target not in reached:
                    reached[target] = (node, depth)
                    following.append(target)
        frontier = sorted(following)
    return reached


def _chain_to(reached, key, target):
    chain = []
    node = target
    while reached[node][0] is not None:
        chain.insert(0, [reached[node][0], key, node])
        node = reached[node][0]
    return chain


def _chains(edges):
    """(c) and (d): one reading for each pair joined by a chain of two or more edges."""
    out = []
    for key in CHAIN_KEYS:
        adjacency = {}
        for edge in edges:
            if edge["key"] == key:
                adjacency.setdefault(edge["source"], set()).add(edge["target"])
        for source in adjacency:
            reached = _walk(adjacency, source)
            for target, (_, depth) in reached.items():
                if depth < 2:
                    continue
                rule = "closure" if key in CLOSURE_KEYS else "transitive"
                out.append({"because": [{"from": _chain_to(reached, key, target), "rule": rule}],
                            "key": key, "source": source, "target": target})
    return out


def readings(edges):
    """AGSC-05-33: the readings of a Link graph, ordered by source, key, target.

    ``edges`` are the edges of ``links.edges``, authored and computed, in any order.
    """
    return sorted(_direct(edges) + _chains(edges),
                  key=lambda one: (one["source"], one["key"], one["target"]))
