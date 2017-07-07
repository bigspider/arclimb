import numpy as np
import cv2
import argparse
from matplotlib import pyplot as plt

from arclimb import *

MAX_PIXELS = 1024

#Scales down the image so that the biggest dimension is at most MAX_PIXELS, while preserving the aspect ratio
def scale_down(img):
    h, w, *_ = img.shape
    scale = min(1.0, MAX_PIXELS/w, MAX_PIXELS/h)
    res = cv2.resize(img,None,fx=scale, fy=scale, interpolation = cv2.INTER_AREA)
    return res

ap = argparse.ArgumentParser()
ap.add_argument("file1", help="First input image")
ap.add_argument("file2", help="Second input image")
args = ap.parse_args()

img1 = cv2.imread(args.file1)
img2 = cv2.imread(args.file2)

#scale down images if too big.
img1 = scale_down(img1)
img2 = scale_down(img2)

#convert to rgb
img1_rgb = cv2.cvtColor(img1, cv2.COLOR_BGR2RGB)
img2_rgb = cv2.cvtColor(img2, cv2.COLOR_BGR2RGB)

#From now on, they are grayscale images
img1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
img2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)

matcher = HomographyFilter(SIFTMatcher(nfeatures=300))

matches, kp1, kp2 = matcher.match(img1, img2)

img3 = cv2.drawMatches(img1_rgb,kp1,img2_rgb,kp2,matches, cv2.DRAW_MATCHES_FLAGS_NOT_DRAW_SINGLE_POINTS)

plt.imshow(img3),plt.show()
