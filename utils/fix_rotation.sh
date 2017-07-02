#!/bin/bash

#Auto-rotates the image according to its Exif.
#Requires 'convert' (from ImageMagick)

for f in "$@"
do
	echo Rotating $f...
	mv $f $f.bak
    convert -auto-orient $f.bak $f
done
