## The problem

Vision based image alignment for rock climbing locations.

Assumptions:

* The images have usually no obstructions.
* The surfaces do not change significantly over time, except because of different light, camera, season.
* Slight misalignments are acceptable.

We also assume that the graph contains at most tens or hundreds of samples.

## The graph
Each image in the database is a square image that represents a possible view of the location.

The goal is to build a graph G whose nodes are the image samples, and the edges contain the information needed to align the two images.

The graph needs to be globally sparse (since there is no correspondence between distant images), but locally dense, so that it can be used to provide reliable alignments.

### Querying the graph

The kind of queries that the graph must answer are as follows: where in image2 is the point corresponding to (x, y) in image1?
Note that the corresponding point could lie outside image2.

#### Querying edges of the graph

Let us first consider the case of two images image1, image2 that are adjacent in G. Then the information stored in the corresponding edge is enough to answer the query.

The query also return a *confidence* on the quality of the answer, which is a value between 0 and 1. Values close to 1 signal that the answer is expected to be very close to the correct one (that is, small relative error). For example, this value should be 1 if the two images have a significant overlap and there is an homography that aligns them (that is, they could easily be stitched together). 

#### Querying arbitrary pairs of nodes

By iterating the edge-query for successive edges, one can generalize the query to non-adjacent nodes.

Clearly, since such alignments are not perfect, we expect less precise mappings. There could be many paths in G from image1 to image2: for each such path, we query each edge and compute an answer, whose confidence is computed as the 

## Usage of the graph in a real world scenario

In a real world scenario, we want to map a new image (which is not in the graph) with an image in the graph. Once the best match is found, one can proceed to navigate the database.

For the first version, we can just iterate through all the images in the graph and try to find a match with a Keypoint detector (SIFT/ORB).

## Future improvements

* For each image in the graph, one could define a bitmap indicating what parts should not be considered in the matching (for example, the sky, any obstructing or non-permanent object, etc.).
* It would be nice to find a way of automatically selecting the images to be added to the database, based on their quality and on wether they improve on the matching.