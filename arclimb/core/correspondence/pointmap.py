import cv2
import numpy as np

from typing import List, Optional
from abc import ABCMeta, abstractmethod

from arclimb.core.graph import Point, Correspondence


# noinspection PyPep8Naming
class PointMap(metaclass=ABCMeta):
    @abstractmethod
    def __init__(self, correspondences: List[Correspondence]):
        pass

    @abstractmethod
    def map(self, point: Point) -> (Point, Optional[float]):
        pass

    def __call__(self, point: Point) -> (Point, Optional[float]):
        return self.map(point)


# noinspection PyPep8Naming
class HomographicPointMap(PointMap):
    def __init__(self, correspondences: List[Correspondence]):
        super().__init__()
        src_pts = np.float32([[corr.point1.x, corr.point1.y] for corr in correspondences]).reshape(-1, 1, 2)
        dst_pts = np.float32([[corr.point2.x, corr.point2.y] for corr in correspondences]).reshape(-1, 1, 2)

        M, _ = cv2.findHomography(src_pts, dst_pts, method=cv2.RANSAC,ransacReprojThreshold=5.0)

        # TODO: handle failure cases (not enough points, M not a homography, etc)

        self._M = M

    def map(self, point: Point) -> (Point, Optional[float]):
        pt = np.array([point.x, point.y]).reshape(-1, 1, 2)
        x, y = cv2.perspectiveTransform(pt, self._M).flatten()
        return Point(x, y), None

    def getPerspectiveTransformation(self):
        return self._M