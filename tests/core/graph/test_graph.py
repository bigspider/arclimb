import arclimb.core.graph as gr


def test_create_node():
    node = gr.Node(gr.NodeId('test_img.png'))


def test_create_point():
    point = gr.Point(5.0, 10.0)


def test_create_correspondence():
    correspondence = gr.Correspondence(gr.Point(5.0, 10.0), gr.Point(1.0, 3.0))


class TestGraph(object):

    def test_create_graph(self):
        graph = gr.Graph()

    def test_add_node(self):
        graph = gr.Graph()
        node = gr.Node('test_img.png')
        graph.add_node(node)
        nodes = graph.get_nodes()
        assert(len(nodes) == 1)
        print(nodes)
        assert(node in nodes)

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

