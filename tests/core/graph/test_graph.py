import arclimb.core.graph as gr


def test_create_node():
    _ = gr.Node(gr.NodeId('test_img.png'))


def test_create_point():
    _ = gr.Point(5.0, 10.0)


def test_create_correspondence():
    _ = gr.Correspondence(gr.Point(5.0, 10.0), gr.Point(1.0, 3.0))


class TestGraph(object):
    def test_create_graph(self):
        _ = gr.Graph()

    def test_add_node(self):
        graph = gr.Graph()
        node = gr.Node('test_img.png')
        graph.add_node(node)
        nodes = graph.get_nodes()
        assert (len(nodes) == 1)
        print(nodes)
        assert (node in nodes)

    def test_remove_node(self):
        graph = gr.Graph()
        node = gr.Node('test_img.png')
        graph.add_node(node)
        nodes = graph.get_nodes()
        assert (len(nodes) == 1)
        assert (node in nodes)

        graph.remove_node(node.id)
        nodes = graph.get_nodes()
        assert (len(nodes) == 0)
        assert (node not in nodes)

    def test_add_correspondence(self):
        graph = gr.Graph()
        node1 = gr.Node('view1.png')
        node2 = gr.Node('view2.png')
        corr = gr.Correspondence(gr.Point(1, 2), gr.Point(2, 3))
        graph.add_correspondence(node1.id, node2.id, corr)

        corrs = graph.get_correspondences(node1.id, node2.id)
        assert (len(corrs) == 1)
        assert (corr in corrs)

    def test_remove_correspondence(self):
        graph = gr.Graph()
        node1 = gr.Node('view1.png')
        node2 = gr.Node('view2.png')
        corr = gr.Correspondence(gr.Point(1, 2), gr.Point(2, 3))
        graph.add_correspondence(node1.id, node2.id, corr)

        corrs = graph.get_correspondences(node1.id, node2.id)
        assert (len(corrs) == 1)
        assert (corr in corrs)

        graph.remove_correspondence(node1.id, node2.id, corr)
        corrs = graph.get_correspondences(node1.id, node2.id)
        assert (len(corrs) == 0)
        assert (corr not in corrs)

    @staticmethod
    def create_sample_graph() -> gr.Graph:
        graph = gr.Graph()

        node1 = gr.Node('node1')
        node2 = gr.Node('node2')
        node3 = gr.Node('node3')

        graph.add_node(node1)
        graph.add_node(node2)
        graph.add_node(node3)

        corr12_1 = gr.Correspondence(gr.Point(1, 2), gr.Point(2, 3))
        corr12_2 = gr.Correspondence(gr.Point(2, 1), gr.Point(3, 2))

        corr13_1 = gr.Correspondence(gr.Point(1, 6), gr.Point(3, 3))

        corr23_1 = gr.Correspondence(gr.Point(0, 0), gr.Point(0, 0))

        graph.add_correspondence(node1.id, node2.id, corr12_1)
        graph.add_correspondence(node1.id, node2.id, corr12_2)

        graph.add_correspondence(node1.id, node3.id, corr13_1)

        graph.add_correspondence(node2.id, node3.id, corr23_1)

        return graph

    @staticmethod
    def assert_graphs_match(graph_a: gr.Graph, graph_b: gr.Graph):

        # Make sure they have the same edges
        assert set(graph_a.get_nodes()) == set(graph_b.get_nodes())

        # Make sure they have the same correspondences
        for node_a in graph_a.get_nodes():
            for node_b in graph_b.get_nodes():
                assert set(graph_a.get_correspondences(node_a.id, node_b.id)) == set(
                    graph_b.get_correspondences(node_a.id, node_b.id))

    def test_to_from_dict(self):
        sample_graph = TestGraph.create_sample_graph()
        graph_dict = sample_graph.to_dict()
        reconstructed = gr.Graph.from_dict(graph_dict)
        TestGraph.assert_graphs_match(sample_graph, reconstructed)