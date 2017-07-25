import json
from arclimb.core import Graph, Node, Correspondence


def from_json(graph_fn: str) -> Graph:
    with open(graph_fn, 'r') as graph_file:
        graph_dict = json.load(graph_file)

    return Graph.from_dict(graph_dict)


def to_json(graph: Graph, filename: str) -> None:
    with open(filename, 'w') as file:
        json.dump(graph.to_dict(), file)
