import networkx as nw
import math
from typing import NamedTuple, Tuple, Dict, Set, Any, NewType, Union

from PyQt5.QtCore import QPointF, QRectF

NodeId = NewType('NodeId', str)

PointUnion = NewType('PointUnion', Union['Point', QPointF, Tuple[float, float]])


# noinspection PyPep8Naming
class Point:
    """Immutable point class with floating point coordinates."""

    def __init__(self, *args, **kwargs):
        if len(args) == 2 and len(kwargs) == 0:
            super().__setattr__("x", args[0])
            super().__setattr__("y", args[1])
        elif len(args) == 1 and len(kwargs) == 0:
            p = args[0]
            if isinstance(p, QPointF):
                self.__init__(p.x(), p.y())
            else:
                # p is a Point or a tuple, so it's indexable
                self.__init__(p[0], p[1])
        elif len(args) == 0 and len(kwargs) == 2 and 'x' in kwargs and 'y' in kwargs:
            self.__init__(kwargs['x'], kwargs['y'])
        else:
            raise TypeError("Wrong arguments in constructor.")

    def __getitem__(self, key: int) -> float:
        if key == 0:
            return self.x
        elif key == 1:
            return self.y
        else:
            raise IndexError("Index out of bounds; it must be 0 or 1")

    def __setitem__(self, key: int, value: float) -> None:
        if key == 0:
            self.x = value
        elif key == 1:
            self.y = value
        else:
            raise IndexError("Index out of bounds; it must be 0 or 1")

    def __setattr__(self, key: int, value: float) -> None:
        raise AttributeError("Point objects are immutable")

    def __add__(self, p: PointUnion) -> 'Point':
        p = Point(p)
        return Point(self.x+p.x, self.y+p.y)

    def __radd__(self, p: PointUnion) -> 'Point':
        return Point(p) + self

    def __sub__(self, p: PointUnion) -> 'Point':
        p = Point(p)
        return Point(self.x-p.x, self.y-p.y)

    def __rsub__(self, p: PointUnion) -> 'Point':
        p = Point(p)
        return Point(p) - self

    def __mul__(self, scalar: float) -> 'Point':
        return Point(self.x*scalar, self.y*scalar)

    def __rmul__(self, scalar: float) -> 'Point':
        return Point(self.x*scalar, self.y*scalar)

    def __div__(self, scalar: float) -> 'Point':
        return Point(self.x/scalar, self.y/scalar)

    def __eq__(self, p: PointUnion) -> bool:
        p = Point(p)
        return self.x == p.x and self.y == p.y

    def __hash__(self):
        return hash(self.asTuple())

    def __ne__(self, p: PointUnion) -> bool:
        return not self == p

    def __neg__(self) -> 'Point':
        return Point(-self.x, -self.y)

    def __pos__(self) -> 'Point':
        return Point(self)

    def __abs__(self) -> 'Point':
        return Point(abs(self.x), abs(self.y))

    def __str__(self):
        return "(%s, %s)" % (self.x, self.y)

    def __repr__(self):
        return "%s(%r, %r)" % (self.__class__.__name__, self.x, self.y)

    def asTuple(self) -> Tuple[float, float]:
        return (self.x, self.y)

    def asQPointF(self) -> QPointF:
        return QPointF(self.x, self.y)

    def dist(self, p: PointUnion) -> float:
        p = Point(p)
        return math.hypot(self.x - p.x, self.y - p.y)

    def toRelativeCoordinates(self, rect: QRectF) -> 'Point':
        x = (self.x - rect.x()) / rect.width()
        y = (self.y - rect.y()) / rect.height()
        return Point(x, y)

    def toAbsoluteCoordinates(self, rect: QRectF) -> 'Point':
        return Point(rect.x() + rect.width() * self.x, rect.y() + rect.height() * self.y)

    def inRect(self, rect: QRectF) -> bool:
        return self.asQPointF() in rect


Correspondence = NamedTuple('Correspondence', [
    ('point1', Point),
    ('point2', Point),
])


# Create a node class, and make it have an optional argument
class Node(NamedTuple('Node', [('id', NodeId), ('attributes', Dict[str, Any])])):
    def __hash__(self):
        return hash(self.id)

Node.__new__.__defaults__ = ({},)


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
