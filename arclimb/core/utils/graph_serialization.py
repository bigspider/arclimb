import networkx as nw
import json


def from_json(graph_fn: str, node_fields: dict, ) -> nw.Graph:
    with open(graph_fn, 'r') as graph_file:
        graph_dict = json.load(graph_file)

    g = nw.Graph()

    for node_dict in graph_dict['nodes']:
        g.add_node()
    pass

def to_json(graph: nw.Graph, filename: str, fields_to_include: dict) -> None:

    pass
