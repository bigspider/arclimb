import numpy as np
import cv2
import argparse
from matplotlib import pyplot as plt

from arclimb import *
from arclimb_exp import *

MIN_MATCH_COUNT = 10


MAX_PIXELS = 1024

ORB_MAX_KEYPOINTS = 100
ORB_SCALE_FACTOR = 1.2
ORB_RATIO_TEST_THRESHOLD = 0.8

# Create ORB detector with 1000 keypoints with a scaling pyramid factor
# of 1.2
sift = cv2.xfeatures2d.SIFT_create()

def scale_down(img):
    h, w, *_ = img.shape
    scale = min(1.0, MAX_PIXELS/w, MAX_PIXELS/h)
    res = cv2.resize(img,None,fx=scale, fy=scale, interpolation = cv2.INTER_AREA)
    return res

ap = argparse.ArgumentParser()
ap.add_argument("file1", help="First input image")
ap.add_argument("file2", help="Second input image")
args = ap.parse_args()

img1 = cv2.imread(args.file1) # queryImage
img2 = cv2.imread(args.file2) # trainImage

#scale down images if too big.
img1 = scale_down(img1)
img2 = scale_down(img2)

#convert to rgb
img1_rgb = cv2.cvtColor(img1, cv2.COLOR_BGR2RGB)
img2_rgb = cv2.cvtColor(img2, cv2.COLOR_BGR2RGB)

#From now on, they are grayscale images
img1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
img2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)

#matcher = HomographyFilter(SIFTMatcher(nfeatures=500), 0.1)
for matcher in [ORBMatcher(1000), DoubleORBMatcher()]:
    matches, kp1, kp2 = matcher.match(img1, img2)

    matches = sorted(matches, key = lambda x:x.distance)

    img3 = cv2.drawMatches(img1_rgb,kp1,img2_rgb,kp2,matches[:100], cv2.DRAW_MATCHES_FLAGS_NOT_DRAW_SINGLE_POINTS)

    plt.imshow(img3),plt.show()
