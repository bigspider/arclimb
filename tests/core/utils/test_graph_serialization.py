import tests.core.graph.test_graph as tg
import arclimb.core.utils.graph_serialization as gs
import os

tmp_filename = 'tmp_serialization.json'


def test_from_json():
    with open(tmp_filename, 'w') as tmp_serial:
        tmp_serial.write('{"nodes": [{"id": "node2", "attributes": {}}, {"id": "node1", "attributes": {}},'
                         '{"id": "node3", "attributes": {}}], "edges": [{"src": "node1", "dest": "node2", '
                         '"correspondences": [{"point1": {"x": 2, "y": 1}, "point2": {"x": 3, "y": 2}}, '
                         '{"point1": {"x": 1, "y": 2}, "point2": {"x": 2, "y": 3}}]}, {"src": "node1", '
                         '"dest": "node3", "correspondences": [{"point1": {"x": 1, "y": 6}, '
                         '"point2": {"x": 3, "y": 3}}]}, {"src": "node2", "dest": "node3", '
                         '"correspondences": [{"point1": {"x": 0, "y": 0}, "point2": {"x": 0, "y": 0}}]}]}')

    graph = gs.from_json(tmp_filename)

    tg.TestGraph.assert_graphs_match(tg.TestGraph.create_sample_graph(), graph)

    # Clean up
    os.remove(tmp_filename)


def test_to_json():
    sample_graph = tg.TestGraph.create_sample_graph()
    gs.to_json(sample_graph, tmp_filename)
    graph = gs.from_json(tmp_filename)
    tg.TestGraph.assert_graphs_match(sample_graph, graph)

    # Clean up
    os.remove(tmp_filename)
