import cv2
import numpy as np


class Matcher:
    def __init__(self):
        pass

    def match(self):
        raise NotImplementedError


class SIFTMatcher(Matcher):
    def __init__(self, nfeatures = 0):
        super().__init__()

        self._sift = cv2.xfeatures2d.SIFT_create(nfeatures=nfeatures)
        self._bf = cv2.BFMatcher()

    def match(self, image1, image2):

        # find the keypoints and descriptors with SIFT
        kp1, des1 = self._sift.detectAndCompute(image1, None)
        kp2, des2 = self._sift.detectAndCompute(image2, None)

        #Find matches
        matches = self._bf.knnMatch(des1, des2, k=2)

        # Apply ratio test
        res = []
        for m, n in matches:
            if m.distance < 0.75 * n.distance:
                res.append(m)
        return res, kp1, kp2


class ORBMatcher(Matcher):
    def __init__(self, nfeatures = 500):
        super().__init__()

        self._orb = cv2.ORB_create(nfeatures=nfeatures)
        self._bf = cv2.BFMatcher(normType=cv2.NORM_HAMMING)

    def match(self, image1, image2):

        # find the keypoints and descriptors with ORB
        kp1, des1 = self._orb.detectAndCompute(image1, None)
        kp2, des2 = self._orb.detectAndCompute(image2, None)

        #Find matches
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

            #TODO: add some sanity checks and fail if M does not make sense (e.g.: 4 clockwise points should alsways stay clockwise)

            #Apply the homography to each source points and retain only the ones whose destination is not too far from the transformed point
            res = []
            for m in matches:
                src_pt = kp1[m.queryIdx].pt
                dst_pt = kp2[m.trainIdx].pt

                src_transformed = cv2.perspectiveTransform(np.float32([src_pt]).reshape(-1,1,2), M)
                h, w, *_ = image2.shape
                diff_normalized = np.divide(dst_pt - src_transformed, [w, h])


                if np.linalg.norm(diff_normalized) < self.threshold:
                    res.append(m)

            return res, kp1, kp2
        else:
            return matches, kp1, kp2
