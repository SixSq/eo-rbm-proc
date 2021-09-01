#!/usr/bin/env python3.8

import sys
import rasterio
from rasterio.plot import show

fp = sys.argv[1]
img = rasterio.open(fp)
show(img)
