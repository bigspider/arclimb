class FakeCorrespondenceDetector:
    def __init__(self, *params):
        pass

    def detect(self, left_fn, right_fn):
        return [{'x1': '400', 'y1': '305', 'x2': '1200', 'y2': '505'},
                {'x1': '400', 'y1': '100', 'x2': '1200', 'y2': '600'}]