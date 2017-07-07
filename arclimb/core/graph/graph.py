import networkx as nw
from typing import NamedTuple, Dict, Set, Any, NewType

NodeId = NewType('NodeId', str)


class Point(NamedTuple):
    x: float
    y: float


class Correspondence(NamedTuple):
    point1: Point
    point2: Point


class Node(NamedTuple):
    id: NodeId
    attributes: Dict[str, Any] = {}

    def __hash__(self):
        return hash(self.id)


class Graph(object):
    def __init__(self):
        self.__graph = nw.Graph()

    def add_node(self, node: Node) -> None:
        self.__graph.add_node(node.id, node=node)

    def remove_node(self, node_id: NodeId) -> None:
        self.__graph.remove_node(node_id)

    def add_correspondence(self, node1_id: NodeId, node2_id: NodeId, correspondence: Correspondence) -> None:
        if not self.__graph.has_edge(node1_id, node2_id):
            self.__graph.add_edge(node1_id, node2_id, correspondences=set())

        self.__graph[node1_id][node2_id]['correspondences'].add(correspondence)

    def remove_correspondence(self, node1_id: NodeId, node2_id: NodeId, correspondence: Correspondence) -> None:
        if self.__graph.has_edge(node1_id, node2_id):
            self.__graph[node1_id][node2_id]['correspondences'].remove(correspondence)

            if not self.__graph.has_edge(node1_id, node2_id):
                self.__graph.remove_edge(node1_id, node2_id)

    def get_nodes(self) -> Set[Node]:
        return set([self.__graph.node[node_id]['node'] for node_id in self.__graph.nodes()])

    def get_correspondences(self, node1_id: NodeId, node2_id: NodeId) -> Set[Correspondence]:
        if not self.__graph.has_edge(node1_id, node2_id):
            return set()
        else:
            return self.__graph[node1_id][node2_id]['correspondences']
