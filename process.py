import geopandas as gpd
from shapely.geometry import *
import numpy as np
import topojson as tp
import met_brewer
import requests
import os.path
import logging
import argparse
import altair as alt
from altair_saver import save

alt.data_transformers.disable_max_rows()

def download_file_if_not_exists(url, fname=None):
    if fname is None:
        fname = os.path.basename(url)
    if not os.path.isfile(fname):
        session = requests.Session()
        with session.get(url, stream=True) as stream:
            stream.raise_for_status()
            with open(fname, 'wb') as f:
                for chunk in stream.iter_content(chunk_size=8192): 
                    f.write(chunk)

# From https://gis.stackexchange.com/a/220374
def remove_third_dimension(geom):
    if geom.is_empty:
        return geom

    if isinstance(geom, Polygon):
        exterior = geom.exterior
        new_exterior = remove_third_dimension(exterior)

        interiors = geom.interiors
        new_interiors = []
        for int in interiors:
            new_interiors.append(remove_third_dimension(int))

        return Polygon(new_exterior, new_interiors)

    elif isinstance(geom, LinearRing):
        return LinearRing([xy[0:2] for xy in list(geom.coords)])

    elif isinstance(geom, LineString):
        return LineString([xy[0:2] for xy in list(geom.coords)])

    elif isinstance(geom, Point):
        return Point([xy[0:2] for xy in list(geom.coords)])

    elif isinstance(geom, MultiPoint):
        points = list(geom.geoms)
        new_points = []
        for point in points:
            new_points.append(remove_third_dimension(point))

        return MultiPoint(new_points)

    elif isinstance(geom, MultiLineString):
        lines = list(geom.geoms)
        new_lines = []
        for line in lines:
            new_lines.append(remove_third_dimension(line))

        return MultiLineString(new_lines)

    elif isinstance(geom, MultiPolygon):
        pols = list(geom.geoms)

        new_pols = []
        for pol in pols:
            new_pols.append(remove_third_dimension(pol))

        return MultiPolygon(new_pols)

    elif isinstance(geom, GeometryCollection):
        geoms = list(geom.geoms)

        new_geoms = []
        for geom in geoms:
            new_geoms.append(remove_third_dimension(geom))

        return GeometryCollection(new_geoms)

    else:
        raise RuntimeError("Currently this type of geometry is not supported: {}".format(type(geom)))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Create river map of the island of Ireland.')
    parser.add_argument('--colours', help='RMetBrewer colour scheme', default='Derain')
    parser.add_argument('--maps', help='Choose maps to create', nargs='+', default=['Hydro', 'NI', 'ROI'])
    args = parser.parse_args()

    # Colour schemes from RMetBrewer
    hexcolours = met_brewer.met_brew(args.colours)
    # Get Hydrobasins data for Ireland and apply colours
    eubas = gpd.read_file('hybas_eu_lev01-12_v1c.zip', layer='hybas_eu_lev06_v1c', bbox=(-10.56,51.39,-5.34,55.43))
    eubas["hexcolour"] = hexcolours[1:] + hexcolours[1:6]

    if 'Hydro' in args.maps:
        # Get Hydrorivers data for Ireland and cut off the Scotland area of the bounding box
        download_file_if_not_exists('https://data.hydrosheds.org/file/HydroRIVERS/HydroRIVERS_v10_eu.gdb.zip')
        eu = gpd.read_file('HydroRIVERS_v10_eu.gdb.zip', bbox=(-10.56,51.39,-5.34,55.43))
        eu = eu[~eu.intersects(Polygon([
            (-5.34, 55.43), 
            (-5.85, 55.43), 
            (-5.85, 55.23), 
            (-5.34, 55.23)
            ]
        ))]
        download_file_if_not_exists('https://data.hydrosheds.org/file/hydrobasins/standard/hybas_eu_lev01-12_v1c.zip')
        # Spatial join of rivers to basins
        eugdf = eu.sjoin(eubas, how='left')
        # Add colour for any rivers not in basins
        eugdf["hexcolour"] = eugdf["hexcolour"].apply(lambda x: hexcolours[0] if x is np.nan else x)

        eugdf['linewidth'] = eugdf['ORD_STRA']/3

        lines = alt.Chart(eugdf).mark_geoshape(
            filled=False,
        ).encode(
            strokeWidth=alt.StrokeWidth(
                "linewidth",
                legend=None
            ),
            color=alt.Color(
                "hexcolour", 
                scale=None
            )
        ).properties(
            height = 1300,
            width = 1000
        )

        save(lines, 'hydrorivers_hydrobasins.html', format='html')

    if 'NI' in args.maps:
        download_file_if_not_exists('https://opendata-daerani.hub.arcgis.com/datasets/DAERANI::rivers-strahler-ranking.zip?outSR=%7B%22latestWkid%22%3A29902%2C%22wkid%22%3A29900%7D', 'ni-rivers-strahler-ranking.zip')
        nirivers = gpd.read_file('ni-rivers-strahler-ranking.zip')
        nirivers.geometry = nirivers.geometry.to_crs('4326')
        nirivers['linewidth'] = nirivers.strahler / 3
        nirivers = nirivers.sjoin(eubas, how='left')

        download_file_if_not_exists('https://opendata-daerani.hub.arcgis.com/datasets/DAERANI::lake-water-bodies.geojson?outSR=%7B%22latestWkid%22%3A29902%2C%22wkid%22%3A29900%7D', 'ni-lake-water-bodies.geojson')
        nilakes = gpd.read_file('ni-lake-water-bodies.geojson')
        nilakes.geometry = nilakes.geometry.to_crs('4326')
        nilakes = nilakes.sjoin(eubas, how='left')

        niareas = alt.Chart(nilakes).mark_geoshape().encode(
            color=alt.Color(
                "hexcolour", 
                scale=None
            )
        )

        nilines = alt.Chart(nirivers).mark_geoshape(
            filled=False,
        ).encode(
            strokeWidth=alt.StrokeWidth(
                "linewidth",
                legend=None
            ),
            color=alt.Color(
                "hexcolour", 
                scale=None
            )
        ).properties(
            height = 1300,
            width = 1000
        )

        save(niareas + nilines, 'ni_rivers_lakes.html', format='html')

    if 'ROI' in args.maps:
        download_file_if_not_exists('http://gis.epa.ie/geoserver/EPA/ows?service=WFS&version=1.0.0&request=GetFeature&typeName=EPA:WATER_RIVNETROUTES&outputFormat=application%2Fjson&srsName=EPSG:4326', 'roi-river-netroutes.json')
        ie = gpd.read_file('roi-river-netroutes.json')
        ie.geometry = ie.geometry.to_crs('4326')
#        ie.geometry = ie.geometry.apply(lambda x: remove_third_dimension(x))
        ie['linewidth'] = ie.ORDER_ / 3

        ie = ie.sjoin(eubas, how='left')

        roilines = alt.Chart(ie).mark_geoshape(
            filled=False,
        ).encode(
            strokeWidth=alt.StrokeWidth(
                "linewidth",
                legend=None
            ),
            color=alt.Color(
                "hexcolour", 
                scale=None
            )
        ).properties(
            height = 1300,
            width = 1000
        )

        print('Created plot')

        save(roilines, 'roi_rivers.html', format='html')

    if 'ROI' in args.maps and 'NI' in args.maps:
        save(niareas + nilines + roilines, 'ie_rivers_lakes.html', format='html')
