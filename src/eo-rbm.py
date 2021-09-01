#!/usr/bin/env python3.9

import argparse

import snappy
from snappy import Product
from snappy import ProductIO
from snappy import ProductUtils
from snappy import WKTReader
from snappy import HashMap
from snappy import GPF
from snappy import jpy

# For shapefiles
import shapefile
import pygeoif


# Helper functions

def show_product_information(product):
    width = product.getSceneRasterWidth()
    print("Width: {} px".format(width))
    height = product.getSceneRasterHeight()
    print("Height: {} px".format(height))
    name = product.getName()
    print("Name: {}".format(name))
    band_names = product.getBandNames()
    print("Band names: {}".format(", ".join(band_names)))


def shape_to_wkt(shp_path):
    r = shapefile.Reader(shp_path)
    g = []
    for s in r.shapes():
        g.append(pygeoif.geometry.as_shape(s))
    m = pygeoif.MultiPoint(g)
    return str(m.wkt).replace("MULTIPOINT", "POLYGON(") + ")"


# Preprocessing functions

def apply_orbit(product):
    parameters = HashMap()
    parameters.put('orbitType', 'Sentinel Precise (Auto Download)')
    parameters.put('polyDegree', '3')
    parameters.put('continueOnFail', 'false')
    return GPF.createProduct('Apply-Orbit-File', parameters, product)


def subset(product, shapePath):
    parameters = HashMap()
    wkt = shape_to_wkt(shapePath)
    SubsetOp = jpy.get_type('org.esa.snap.core.gpf.common.SubsetOp')
    geometry = WKTReader().read(wkt)
    parameters.put('copyMetadata', True)
    parameters.put('geoRegion', geometry)
    return GPF.createProduct('Subset', parameters, product)


def calibration(product):
    parameters = HashMap()
    parameters.put('outputSigmaBand', True)
    parameters.put('sourceBands', 'Intensity_VV')
    parameters.put('selectedPolarisations', "VV")
    parameters.put('outputImageScaleInDb', False)
    return GPF.createProduct("Calibration", parameters, product)


def speckle_filter(product):
    parameters = HashMap()

    filterSizeY = '5'
    filterSizeX = '5'

    parameters.put('sourceBands', 'Sigma0_VV')
    parameters.put('filter', 'Lee')
    parameters.put('filterSizeX', filterSizeX)
    parameters.put('filterSizeY', filterSizeY)
    parameters.put('dampingFactor', '2')
    parameters.put('estimateENL', 'true')
    parameters.put('enl', '1.0')
    parameters.put('numLooksStr', '1')
    parameters.put('targetWindowSizeStr', '3x3')
    parameters.put('sigmaStr', '0.9')
    parameters.put('anSize', '50')
    return GPF.createProduct('Speckle-Filter', parameters, product)


def terrain_correction(product):
    parameters = HashMap()
    parameters.put('demName', 'SRTM 3Sec')
    parameters.put('pixelSpacingInMeter', 10.0)
    parameters.put('sourceBands', 'Sigma0_VV')
    return GPF.createProduct("Terrain-Correction", parameters, product)


# Flooding processing

def generate_binary_flood(product):
    parameters = HashMap()

    BandDescriptor = snappy.jpy.get_type('org.esa.snap.core.gpf.common.BandMathsOp$BandDescriptor')

    targetBand = BandDescriptor()
    targetBand.name = 'flooded'
    targetBand.type = 'uint8'
    targetBand.expression = '(Sigma0_VV < 1.13E-2) ? 1 : 0'

    targetBands = snappy.jpy.array('org.esa.snap.core.gpf.common.BandMathsOp$BandDescriptor', 1)
    targetBands[0] = targetBand

    parameters.put('targetBands', targetBands)

    return GPF.createProduct('BandMaths', parameters, product)


def mask_known_water(product):
    # Add land cover band
    parameters = HashMap()
    parameters.put("landCoverNames", "GlobCover")
    mask_with_land_cover = GPF.createProduct('AddLandCover', parameters, product)
    del parameters

    # Create binary water band
    BandDescriptor = snappy.jpy.get_type('org.esa.snap.core.gpf.common.BandMathsOp$BandDescriptor')
    parameters = HashMap()
    targetBand = BandDescriptor()
    targetBand.name = 'BinaryWater'
    targetBand.type = 'uint8'
    targetBand.expression = '(land_cover_GlobCover == 210) ? 0 : 1'
    targetBands = snappy.jpy.array('org.esa.snap.core.gpf.common.BandMathsOp$BandDescriptor', 1)
    targetBands[0] = targetBand
    parameters.put('targetBands', targetBands)

    water_mask = GPF.createProduct('BandMaths', parameters, mask_with_land_cover)
    del parameters

    parameters = HashMap()

    BandDescriptor = snappy.jpy.get_type('org.esa.snap.core.gpf.common.BandMathsOp$BandDescriptor')
    try: water_mask.addBand(product.getBand("flooded"))
    except: pass
    targetBand = BandDescriptor()
    targetBand.name = 'Sigma0_VV_Flood_Masked'
    targetBand.type = 'uint8'
    targetBand.expression = '(BinaryWater == 1 && flooded == 1) ? 1 : 0'
    targetBands = snappy.jpy.array('org.esa.snap.core.gpf.common.BandMathsOp$BandDescriptor', 1)
    targetBands[0] = targetBand
    parameters.put('targetBands', targetBands)
    return GPF.createProduct('BandMaths', parameters, water_mask)


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='EO Flood Monitoring')
    required_args = parser.add_argument_group('required named arguments')

    required_args.add_argument('--product-path', dest='product', help='Sentinel 1 data product archive',
                               metavar='PRODUCT', required=True)
    required_args.add_argument('--shape-path', dest='shape', help='Shape file in .shp format',
                               metavar='SHAPE', required=True)
    required_args.add_argument('--result-path', dest='result', help='Path to resulting TIF file (w/o .tif)',
                               metavar='RESULT', required=True)

    args = parser.parse_args()

    path_to_sentinel_data = args.product
    shapefile_path = args.shape
    result_path = args.result

    # GPF Initialization
    GPF.getDefaultInstance().getOperatorSpiRegistry().loadOperatorSpis()

    # Product initialization
    product = ProductIO.readProduct(path_to_sentinel_data)
    show_product_information(product)
    product_orbitfile = apply_orbit(product)
    product_subset = subset(product_orbitfile, shapefile_path)
    show_product_information(product_subset)

    # Apply remainder of processing steps in a nested function call
    product_preprocessed = terrain_correction(speckle_filter(calibration(product_subset)))

    product_binaryflood = mask_known_water(generate_binary_flood(product_preprocessed))
    print('writing product ...')
    ProductIO.writeProduct(product_binaryflood, result_path, 'GeoTIFF')
    print('done.')
