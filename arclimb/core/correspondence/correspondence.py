from typing import List

import cv2
import numpy as np
from scipy.spatial import KDTree

from arclimb.core.graph import Correspondence, Point


class Matcher:
    def __init__(self):
        pass

    def match(self, image1, image2):
        raise NotImplementedError


class SIFTMatcher(Matcher):
    def __init__(self, nfeatures=0):
        super().__init__()

        self._sift = cv2.xfeatures2d.SIFT_create(nfeatures=nfeatures)
        self._bf = cv2.BFMatcher()

    def match(self, image1, image2):

        # find the keypoints and descriptors with SIFT
        kp1, des1 = self._sift.detectAndCompute(image1, None)
        kp2, des2 = self._sift.detectAndCompute(image2, None)

        # Find matches
        matches = self._bf.knnMatch(des1, des2, k=2)

        # Apply ratio test
        res = []
        for m, n in matches:
            if m.distance < 0.75 * n.distance:
                res.append(m)
        return res, kp1, kp2


class ORBMatcher(Matcher):
    def __init__(self, nfeatures=500):
        super().__init__()

        self._orb = cv2.ORB_create(nfeatures=nfeatures)
        self._bf = cv2.BFMatcher(normType=cv2.NORM_HAMMING)

    def match(self, image1, image2):

        # find the keypoints and descriptors with ORB
        kp1, des1 = self._orb.detectAndCompute(image1, None)
        kp2, des2 = self._orb.detectAndCompute(image2, None)

        # Find matches
        matches = self._bf.knnMatch(des1, des2, k=2)

        # Apply ratio test
        res = []
        for m, n in matches:
            if m.distance < 0.75 * n.distance:
                res.append(m)
        return res, kp1, kp2


class HomographyFilter(Matcher):
    """
    Given another Matcher as input, this decorator returns another Matcher that attempts to
    refine the match by removing the best homography and removing the matching points that don't agree
    with the homography.
    """
    MIN_MATCH_COUNT = 10

    def __init__(self, matcher, threshold=0.2):
        super().__init__()
        self._matcher = matcher
        self.threshold = threshold

    def match(self, image1, image2):
        matches, kp1, kp2 = self._matcher.match(image1, image2)

        if len(matches) >= HomographyFilter.MIN_MATCH_COUNT:
            src_pts = np.float32([kp1[m.queryIdx].pt for m in matches]).reshape(-1, 1, 2)
            dst_pts = np.float32([kp2[m.trainIdx].pt for m in matches]).reshape(-1, 1, 2)

            M, _ = cv2.findHomography(src_pts, dst_pts, cv2.LMEDS)

            # TODO: add some sanity checks and fail if M does not make sense (e.g.: 4 clockwise points should alsways stay clockwise)

            # Apply the homography to each source points and retain only the ones whose destination is not too far from the transformed point
            res = []
            for m in matches:
                src_pt = kp1[m.queryIdx].pt
                dst_pt = kp2[m.trainIdx].pt

                src_transformed = cv2.perspectiveTransform(np.float32([src_pt]).reshape(-1, 1, 2), M)
                h, w, *_ = image2.shape
                diff_normalized = np.divide(dst_pt - src_transformed, [w, h])

                if np.linalg.norm(diff_normalized) < self.threshold:
                    res.append(m)

            return res, kp1, kp2
        else:
            return matches, kp1, kp2


class DoubleORBMatcher(Matcher):
    def __init__(self, max_displacement=0.01, min_kp_distance=0.15):
        super().__init__()
        self.max_displacement = max_displacement
        self.min_kp_distance = min_kp_distance

        # TODO: tune parameters, add constructor arguments
        self._fastORBMatcher = ORBMatcher(nfeatures=1000)
        self._orb = cv2.ORB_create(nfeatures=3000)  # ORB detector with many more points

    def match(self, image1, image2):
        initial_matches, initial_kp1, initial_kp2 = self._fastORBMatcher.match(image1, image2)  # TODO: parameter tuning

        initial_src_pts = np.float32([initial_kp1[m.queryIdx].pt for m in initial_matches]).reshape(-1, 1, 2)
        initial_dst_pts = np.float32([initial_kp2[m.trainIdx].pt for m in initial_matches]).reshape(-1, 1, 2)

        M, _ = cv2.findHomography(initial_src_pts, initial_dst_pts, method=cv2.RANSAC, ransacReprojThreshold=5.0)

        ##Debug code: print the homography and save the result
        # h, w, *_ = image1.shape
        # corners_src = np.float32([[0, 0], [0, h - 1], [w - 1, h - 1], [w - 1, 0]]).reshape(-1, 1, 2)
        # corners_dst = cv2.perspectiveTransform(corners_src, M)
        # temp = cv2.polylines(image2, [np.int32(corners_dst)], True, 255, 3, cv2.LINE_AA)
        # cv2.imwrite("temp.jpg", temp)

        # TODO: add sanity checks for M

        # Compute many more keypoints, this time
        kp1, des1 = self._orb.detectAndCompute(image1, None)
        kp2, des2 = self._orb.detectAndCompute(image2, None)
        n_kp1 = len(kp1)

        pts1 = np.float32([kp.pt for kp in kp1]).reshape(-1, 1, 2)
        pts1_transformed = cv2.perspectiveTransform(pts1, M)  # apply homography to all source keypoints

        # build KDTree of points in kp2
        tree = KDTree([kp.pt for kp in kp2])

        # For each point in kp1, find the keypoints in image2 that are near the transformed point, and do the rest like BFMatcher
        disp = self.max_displacement * min(
            image2.shape[:2])  # maximum displacement is a fraction of the minimum between width and height
        matches = []
        for pt1_idx in range(n_kp1):
            pt1_transformed = pts1_transformed[pt1_idx]

            points2_idxs = tree.query_ball_point(pt1_transformed, disp)[0]

            # find the best two keypoints (minimizing the Hamming distance)
            best_idx = None
            best_dist = float('inf')
            second_best_idx = None
            second_best_dist = float('inf')

            for pt2_idx in points2_idxs:
                dist = cv2.norm(des1[pt1_idx], des2[pt2_idx], normType=cv2.NORM_HAMMING)
                if dist < best_dist:
                    second_best_idx, second_best_dist = best_idx, best_dist
                    best_dist, best_idx = dist, pt2_idx
                elif dist < second_best_dist:
                    second_best_dist, second_best_idx = dist, pt2_idx

            if best_idx is not None:
                # Add the match only only there is one with the same source keypoint (not sure if this ever happens)
                # or if it passes the ratio test
                if second_best_idx is None or best_dist < 0.75 * second_best_dist:
                    matches.append(cv2.DMatch(pt1_idx, best_idx, best_idx))

        # Now keep adding the best matches, but skip if the source points are too close
        matches = sorted(matches, key=lambda x: x.distance)

        final_matches = []
        chosen_keypoints = []
        for match_candidate in matches:
            candidate_pt = kp1[match_candidate.queryIdx].pt
            if len(chosen_keypoints) == 0:
                min_dist = float('inf')
            else:
                min_dist = min(cv2.norm(candidate_pt, chosen_pt) for chosen_pt in chosen_keypoints)

            if min_dist > self.min_kp_distance * min(image1.shape[:2]):
                final_matches.append(match_candidate)
                chosen_keypoints.append(candidate_pt)

        return final_matches, kp1, kp2


# BruteForce Matcher based on ORB (for debug purposes, quite useless in practice)
class ORBMatcherBF(Matcher):
    def __init__(self, nfeatures=500):
        super().__init__()

        self._orb = cv2.ORB_create(nfeatures=nfeatures)
        self._bf = cv2.BFMatcher(normType=cv2.NORM_HAMMING)

    def match(self, image1, image2):
        # find the keypoints and descriptors with ORB
        kp1, des1 = self._orb.detectAndCompute(image1, None)
        kp2, des2 = self._orb.detectAndCompute(image2, None)

        matches = self._bf.match(des1, des2)

        # Find matches
        matches = sorted(matches, key=lambda x: x.distance)

        return matches, kp1, kp2


class DoubleORBMatcher(Matcher):
    def __init__(self, max_displacement=0.01, min_kp_distance=0.15):
        super().__init__()
        self.max_displacement = max_displacement
        self.min_kp_distance = min_kp_distance

        # TODO: tune parameters, add constructor arguments
        self._fastORBMatcher = ORBMatcher(nfeatures=1000)
        self._orb = cv2.ORB_create(nfeatures=1000)  # ORB detector with many more points

    def match(self, image1, image2):
        initial_matches, initial_kp1, initial_kp2 = self._fastORBMatcher.match(image1, image2)  # TODO: parameter tuning

        initial_src_pts = np.float32([initial_kp1[m.queryIdx].pt for m in initial_matches]).reshape(-1, 1, 2)
        initial_dst_pts = np.float32([initial_kp2[m.trainIdx].pt for m in initial_matches]).reshape(-1, 1, 2)

        M, _ = cv2.findHomography(initial_src_pts, initial_dst_pts, method=cv2.RANSAC, ransacReprojThreshold=5.0)

        ##Debug code: print the homography and save the result
        # h, w, *_ = image1.shape
        # corners_src = np.float32([[0, 0], [0, h - 1], [w - 1, h - 1], [w - 1, 0]]).reshape(-1, 1, 2)
        # corners_dst = cv2.perspectiveTransform(corners_src, M)
        # temp = cv2.polylines(image2, [np.int32(corners_dst)], True, 255, 3, cv2.LINE_AA)
        # cv2.imwrite("temp.jpg", temp)

        # TODO: add sanity checks for M

        # Compute many more keypoints, this time
        kp1, des1 = self._orb.detectAndCompute(image1, None)
        kp2, des2 = self._orb.detectAndCompute(image2, None)
        n_kp1 = len(kp1)

        pts1 = np.float32([kp.pt for kp in kp1]).reshape(-1, 1, 2)
        pts1_transformed = cv2.perspectiveTransform(pts1, M)  # apply homography to all source keypoints

        # build KDTree of points in kp2
        tree = KDTree([kp.pt for kp in kp2])

        # For each point in kp1, find the keypoints in image2 that are near the transformed point, and do the rest like BFMatcher
        disp = self.max_displacement * min(
            image2.shape[:2])  # maximum displacement is a fraction of the minimum between width and height
        matches = []
        for pt1_idx in range(n_kp1):
            pt1_transformed = pts1_transformed[pt1_idx]

            points2_idxs = tree.query_ball_point(pt1_transformed, disp)[0]

            # find the best two keypoints (minimizing the Hamming distance)
            best_idx = None
            best_dist = float('inf')
            second_best_idx = None
            second_best_dist = float('inf')

            for pt2_idx in points2_idxs:
                dist = cv2.norm(des1[pt1_idx], des2[pt2_idx], normType=cv2.NORM_HAMMING)
                if dist < best_dist:
                    second_best_idx, second_best_dist = best_idx, best_dist
                    best_dist, best_idx = dist, pt2_idx
                elif dist < second_best_dist:
                    second_best_dist, second_best_idx = dist, pt2_idx

            if best_idx is not None:
                # Add the match only only there is one with the same source keypoint (not sure if this ever happens)
                # or if it passes the ratio test
                if second_best_idx is None or best_dist < 0.75 * second_best_dist:
                    matches.append(cv2.DMatch(pt1_idx, best_idx, best_dist))

        # Now keep adding the best matches, but skip if the source points are too close
        matches = sorted(matches, key=lambda x: x.distance)

        final_matches = []
        chosen_keypoints = []
        for match_candidate in matches:
            candidate_pt = kp1[match_candidate.queryIdx].pt
            if len(chosen_keypoints) == 0:
                min_dist = float('inf')
            else:
                min_dist = min(cv2.norm(candidate_pt, chosen_pt) for chosen_pt in chosen_keypoints)

            if min_dist > self.min_kp_distance * min(image1.shape[:2]):
                final_matches.append(match_candidate)
                chosen_keypoints.append(candidate_pt)

        return final_matches, kp1, kp2


# BruteForce Matcher based on ORB (for debug purposes, quite useless in practice)
class ORBMatcherBF(Matcher):
    def __init__(self, nfeatures=500):
        super().__init__()

        self._orb = cv2.ORB_create(nfeatures=nfeatures)
        self._bf = cv2.BFMatcher(normType=cv2.NORM_HAMMING)

    def match(self, image1, image2):
        # find the keypoints and descriptors with ORB
        kp1, des1 = self._orb.detectAndCompute(image1, None)
        kp2, des2 = self._orb.detectAndCompute(image2, None)

        matches = self._bf.match(des1, des2)

        # Find matches
        matches = sorted(matches, key=lambda x: x.distance)

        return matches, kp1, kp2


# Convenience class to transform te output of a Matcher to a list of Correspondences
class CorrespondenceFinder():
    def __init__(self, matcher: Matcher):
        self.matcher = matcher

    def find_correspondences(self, image1, image2) -> List[Correspondence]:
        matches, kp1, kp2 = self.matcher.match(image1, image2)

        h1, w1, *_ = image1.shape
        h2, w2, *_ = image2.shape

        result = []
        for match in matches:
            pt1 = kp1[match.queryIdx].pt
            pt2 = kp2[match.trainIdx].pt
            result.append(Correspondence(
                Point(pt1[0] / w1, pt1[1] / h1),
                Point(pt2[0] / w2, pt2[1] / h2)
            ))

        return result
