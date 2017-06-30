import numpy as np
import cv2
import argparse
from matplotlib import pyplot as plt

MIN_MATCH_COUNT = 10

MAX_PIXELS_X = 800.0
MAX_PIXELS_Y = 800.0

ORB_MAX_KEYPOINTS = 10000
ORB_SCALE_FACTOR = 1.2
ORB_RATIO_TEST_THRESHOLD = 0.8

# Create ORB detector with 1000 keypoints with a scaling pyramid factor
# of 1.2
orb = cv2.ORB_create(ORB_MAX_KEYPOINTS, ORB_SCALE_FACTOR)


class coord_translator_perspective:
    def __init__(self, perspectiveMatrix):
        self.perspectiveMatrix = perspectiveMatrix
    
    def f(self, p):
        pt = np.float32([p]).reshape(-1,1,2)
        res = cv2.perspectiveTransform(pt, self.perspectiveMatrix)
        return np.int32(res.flatten())
   #TODO: add inverse function?

def scale_down(img):
    h, w = img.shape
    scale = min(1.0, MAX_PIXELS_X/w, MAX_PIXELS_X/h)
    res = cv2.resize(img,None,fx=scale, fy=scale, interpolation = cv2.INTER_AREA)
    return res


def get_translator_orb(img1, img2):
    # Detect keypoints
    (kp1, des1) = orb.detectAndCompute(img1, None)
    (kp2, des2) = orb.detectAndCompute(img2, None)
    
    # Create matcher
    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
    
    matches = bf.knnMatch(des1,des2, k=2)
    
    # Apply ratio test
    good = []
    for m,n in matches:
        if m.distance < ORB_RATIO_TEST_THRESHOLD*n.distance:
            good.append(m)
    
    if len(good) > MIN_MATCH_COUNT:
        src_pts = np.float32([ kp1[m.queryIdx].pt for m in good ]).reshape(-1,1,2)
        dst_pts = np.float32([ kp2[m.trainIdx].pt for m in good ]).reshape(-1,1,2)
    
        M, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC,5.0)
#        matchesMask = mask.ravel().tolist()
        #TODO: add some sanity checks to M
        return coord_translator_perspective(M)
    else:
        return None    

def compose_sidewise(img1, img2):
    rows1, cols1 = img1.shape
    rows2, cols2 = img2.shape
    
    out = np.zeros((max(rows1, rows2), cols1 + cols2, 3), dtype='uint8')
    
    # Place the first image to the left
    out[:rows1,:cols1,:] = np.dstack([img1, img1, img1])
    
    # Place the next image to the right of it
    out[:rows2,cols1:cols1+cols2,:] = np.dstack([img2, img2, img2])
    return out;
    


def mouse_handler(event, x, y, flags, param):
    if event == cv2.EVENT_MOUSEMOVE:
        if x < param['width'] and y < param['height']:
            x_, y_ = param['translator'].f([x,y])
            out = param['image'].copy()
            cv2.circle(out, (param['width'] + int(x_),int(y_)), 3, (255, 0, 0), 1)
            cv2.imshow("image", out)
        else:
            cv2.imshow("image", param['image'])

ap = argparse.ArgumentParser()
ap.add_argument("file1", help="First input image")
ap.add_argument("file2", help="Second input image")
args = ap.parse_args()

img1 = cv2.imread(args.file1,0) # queryImage
img2 = cv2.imread(args.file2,0) # trainImage

#scale down images if too big.
img1 = scale_down(img1)
img2 = scale_down(img2)

tr = get_translator_orb(img1, img2)


composed_image = compose_sidewise(img1, img2)

param = dict(translator = tr, image = composed_image, width = img1.shape[1], height = img1.shape[0])
cv2.namedWindow("image")
cv2.setMouseCallback("image", mouse_handler, param = param)

cv2.imshow("image", composed_image)
while(cv2.waitKey(0) != 27):
    pass
