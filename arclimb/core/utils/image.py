import cv2

DEFAULT_MAX_PIXELS = 1000

#Scale down an image so that each dimension is at most max_pixels (default to 1000), while preserving the aspect ratio.
def scale_down_image(image, max_pixels:int = DEFAULT_MAX_PIXELS):
    h, w, *_ = image.shape
    scale = min(1.0, float(DEFAULT_MAX_PIXELS)/w, float(max_pixels)/h)
    result = cv2.resize(image, None, fx=scale, fy=scale, interpolation = cv2.INTER_AREA)
    return result