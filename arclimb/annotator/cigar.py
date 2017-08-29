import sys, os
import cmd
import json

from PyQt5.QtWidgets import QApplication

from arclimb.core.graph import Graph, Node

from arclimb.annotator import ImagePairEditorDialog

class Cigar(cmd.Cmd):
    """
    Command Interpreter for the Graphical Annotation of Rocks
    """
    intro = 'Welcome to the Cigar shell.   Type help or ? to list commands.\n'
    prompt = '(cigar) '
    filename = None

    graph = Graph()

    def __init__(self, filename=None):
        super().__init__()
        if filename is not None:
            self.open(filename)

    # ignore empty commands
    def emptyline(self):
        pass

    # ----- basic commands -----
    def do_exit(self, arg):
        'Exit cigar:  exit'
        print('Thank you for using the only cigar that is not bad for your health.')
        self.close()
        return True

    do_EOF = do_exit

    # ----- I/O commands -----
    def do_open(self, arg):
        """Open a graph file:  open my_graph.json"""
        self.open(arg)

    def do_save(self, arg):
        """Save the current graph to file:  save my_graph.json"""

        filename = arg.strip()

        if filename == '':
            if self.filename is None:
                print("No file name provided. Using \"labels.json\"")
                self.filename = filename = "labels.json"
            else:
                filename = self.filename

        self.save(filename)

    def do_cwd(self, arg):
        """Print the working directory:  cwd"""
        print(os.getcwd())

    def do_ls(self, arg):
        os.system("ls")

    # ----- graph manipulation commands -----
    def do_show(self, arg):
        """Shows the current graph in JSON format:  show"""
        print(json.dumps(self.graph.to_dict(), indent=4))

    def do_add(self, arg):
        if arg.strip() == "":
            # Add all jpg/jpeg in current folder
            files = []
            for entry in os.scandir():
                name_lowercase = entry.name.lower()
                if not entry.name.startswith('.') and entry.is_file():
                    if name_lowercase.endswith('.jpg') or name_lowercase.endswith('.jpeg'):
                        files.append(entry.name)
        else:
            files = arg.split()
            # Check if all files exist
            for file in files:
                try:
                    os.stat(file)
                except FileNotFoundError:
                    print("Error: %s does not exist. No change was made." % file)
                    return

        # Add each file as new node if there is no node with the same name
        for file in files:
            if not self.graph.has_node(file):
                self.graph.add_node(Node(file))
        print("%d images added (or already present)." % len(files))

    def help_add(self):
        print("Adds one or more files from the current directory as nodes.")
        print()
        print("add: adds all .jpg or .jpeg files.")
        print("add file1 [file2]...: adds file1, [file2...].")

    def do_label(self, arg):
        """Label two images:  label img1 img2"""
        images = arg.split()
        if len(images) != 2:
            print("Error: wrong parameters.")
            return

        for img_name in images:
            if not self.graph.has_node(img_name):
                print("Error: the graph does not have the node %s." % img_name)
                return

        img1, img2 = images

        # if the edge already exists, pass the correspondences
        correspondences = []
        if self.graph.has_edge(img1, img2):
            correspondences = self.graph.get_correspondences(img1, img2)
        corr, accepted = ImagePairEditorDialog.run(img1, img2, correspondences)

        if accepted:
            if not self.graph.has_edge(img1, img2):
                self.graph.add_edge(img1, img2)
            self.graph.set_correspondences(img1, img2, corr)

    def open(self, filename: str):
        try:
            with open(filename) as f:
                self.graph = Graph.from_dict(json.load(f))
            self.filename = filename
            print("Opened %s" % filename)
        except:
            print("Error opening %s." % filename)

    def save(self, filename: str):
        try:
            with open(filename, 'w') as f:
                json.dump(self.graph.to_dict(), f)
            self.filename = filename
            print("Saved %s." % filename)
        except:
            print("Error saving %s." % filename)

    def close(self):
        self.graph = Graph()
        self.filename = None

    def precmd(self, line):
        # any preprocessing of line goes here
        return line


def run_cigar():
    # TODO: add command line arguments and a default behaviour (e.g.: preadd all jpegs in current folder)

    filename = "labels.json"

    app = QApplication(sys.argv)
    Cigar(filename if os.path.isfile(filename) else None).cmdloop()

if __name__ == '__main__':
    run_cigar()