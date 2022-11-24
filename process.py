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
from itertools import cycle

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

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Create river map of the island of Ireland.')
    parser.add_argument('--colours', help='RMetBrewer colour scheme (colourblind safe)', default='Hokusai2', choices=met_brewer.COLORBLIND_PALETTES_NAMES)
    parser.add_argument('--allcolours', help='Try all colour themes', default=False, action='store_true')
    parser.add_argument('--maps', help='Choose maps to create', nargs='+', default=['Hydro', 'NI', 'ROI'], choices=['Hydro', 'NI', 'ROI', 'Border'])
    parser.add_argument('--basinlevel', help='Basin level to use', default=7, type=int, choices=range(1,10))
    parser.add_argument('--strahlerpower', help='Exponential to use when calculating line width from Strahler level', default=0.5, type=float)
    args = parser.parse_args()

    if args.allcolours is True:
        colours = met_brewer.COLORBLIND_PALETTES_NAMES
    else:
        colours = [args.colours]
    for colour in colours:
        # Colour schemes from RMetBrewer
        hexcolours = met_brewer.met_brew(colour)
        # Get Hydrobasins data for Ireland and apply colours
        eubas = gpd.read_file('hybas_eu_lev01-12_v1c.zip', layer=f'hybas_eu_lev0{args.basinlevel}_v1c', bbox=(-10.56,51.39,-5.34,55.43))
        logging.info('Colouring {basins} basins with {colours} colours'.format(basins = len(eubas), colours = len(hexcolours)))
        colourcycle = cycle(hexcolours[1:])
        eubas["hexcolour"] = [next(colourcycle)for i in range(len(eubas))]

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

            eugdf['linewidth'] = eugdf['ORD_STRA'].pow(args.strahlerpower)

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
            ).configure_view(
                strokeWidth=0
            ).properties(
                height = 2600,
                width = 2000,
                background = '#000000',
                title=alt.TitleParams(
                    text="Ireland's river basins",
                    subtitle=['Based on HydroRivers and HydroBasins datasets','Created by Paul Barber'],
                    baseline='bottom',
                    orient='bottom',
                    anchor='end',
                    font='Optima',
                    fontWeight='bold',
                    fontSize=40,
                    dy=-100,
                    color='#fff',
                    subtitleColor='#fff',
                    subtitleFont='Optima',
                    subtitleFontSize=24,
                    subtitleFontWeight='normal',
                ),
            )

            save(lines, f'hydrorivers_hydrobasins-{colour}-{args.basinlevel}.html', format='html')

        if 'Border' in args.maps:
            download_file_if_not_exists('https://opendata.arcgis.com/api/v3/datasets/577487bb7ce94c76b5a7a5f6c29e6ee9_0/downloads/data?format=shp&spatialRefId=2157&where=1%3D1', 'ROI_landmask.zip')
            roioutline = gpd.read_file('ROI_landmask.zip')
            roioutline.geometry = roioutline.geometry.to_crs('4326')
            download_file_if_not_exists('http://osni-spatialni.opendata.arcgis.com/datasets/159c80fe1ad54140b429f8799f624962_0.zip', 'NI_land_area.zip')
            niboundary = gpd.read_file('NI_land_area.zip')
            niboundary.geometry = niboundary.geometry.to_crs('4326')
            # Extend the NI boundary by 0.015 units
            niboundary['geometry'] = niboundary.buffer(0.015)
            bbox = box(-8.415527,-5.605774,53.998083,55.152197)
            # Identify ROI border within the extended NI boundary, and apply a bounding box to remove point where
            # boundaries get too close
            border = gpd.clip(roioutline.boundary.clip(niboundary), mask=bbox)
            # Create a buffer zone 5km round the border
            border = border.to_crs('EPSG:29902')
            buffer = border.buffer(5000)
            buffer = buffer.to_crs('EPSG:4326')

        if 'NI' in args.maps:
            download_file_if_not_exists('https://opendata-daerani.hub.arcgis.com/datasets/DAERANI::rivers-strahler-ranking.zip?outSR=%7B%22latestWkid%22%3A29902%2C%22wkid%22%3A29900%7D', 'ni-rivers-strahler-ranking.zip')
            nirivers = gpd.read_file('ni-rivers-strahler-ranking.zip')
            nirivers.geometry = nirivers.geometry.to_crs('4326')
            nirivers['linewidth'] = nirivers.strahler.pow(args.strahlerpower)
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
            )

            ni = alt.layer(
                niareas.properties(
                    height = 2000,
                    width = 2000
                ),
                nilines).configure_view(
                strokeWidth=0
            ).properties(
                background = '#000000',
                title=alt.TitleParams(
                    text="Northern Ireland's river basins",
                    subtitle=['Based on DAERA and HydroBasins datasets','Created by Paul Barber'],
                    baseline='bottom',
                    orient='bottom',
                    anchor='end',
                    font='Optima',
                    fontWeight='bold',
                    fontSize=80,
                    dy=-100,
                    color='#fff',
                    subtitleColor='#fff',
                    subtitleFont='Optima',
                    subtitleFontSize=48,
                    subtitleFontWeight='normal',
                ),
            )

            save(ni, f'ni_rivers_lakes-{colour}-{args.basinlevel}.html', format='html')

        if 'ROI' in args.maps:
            download_file_if_not_exists('http://gis.epa.ie/geoserver/EPA/ows?service=WFS&version=1.0.0&request=GetFeature&typeName=EPA:WATER_RIVNETROUTES&outputFormat=application%2Fjson&srsName=EPSG:4326', 'roi-river-netroutes.json')
            roirivers = gpd.read_file('roi-river-netroutes.json')
            roirivers.geometry = roirivers.geometry.to_crs('4326')
            roirivers['linewidth'] = roirivers.ORDER_.pow(args.strahlerpower)
            roirivers = roirivers.sjoin(eubas, how='left')

            download_file_if_not_exists('https://opendata.arcgis.com/api/v3/datasets/0081128602fa45f49fe4f56e159040b3_0/downloads/data?format=geojson&spatialRefId=4326&where=1%3D1', 'Lakes_&_Reservoirs_-_OSi_National_250k_Map_Of_Ireland.geojson')
            roilakes = gpd.read_file('Lakes_&_Reservoirs_-_OSi_National_250k_Map_Of_Ireland.geojson')
            roilakes.geometry = roilakes.geometry.to_crs('4326')
            roilakes = roilakes.sjoin(eubas, how='left')

            roiareas = alt.Chart(roilakes).mark_geoshape().encode(
                color=alt.Color(
                    "hexcolour", 
                    scale=None
                )
            )

            roilines = alt.Chart(roirivers).mark_geoshape(
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
                height = 2600,
                width = 2000
            )

            roi = alt.layer(roiareas, roilines).configure_view(
                strokeWidth=0
            ).properties(
                background = '#000000',
                title=alt.TitleParams(
                    text="Republic of Ireland's river basins",
                    subtitle=['Based on EPA, OSi and HydroBasins datasets','Created by Paul Barber'],
                    baseline='bottom',
                    orient='bottom',
                    anchor='end',
                    font='Optima',
                    fontWeight='bold',
                    fontSize=80,
                    dy=-100,
                    color='#fff',
                    subtitleColor='#fff',
                    subtitleFont='Optima',
                    subtitleFontSize=48,
                    subtitleFontWeight='normal',
                ),
            )
            save(roi, f'roi_rivers_lakes-{colour}-{args.basinlevel}.html', format='html')

        if 'ROI' in args.maps and 'NI' in args.maps:
            if 'Border' in args.maps:
                title = 'Rivers around NI/ROI border'
                fname = f'border_rivers_lakes-{colour}-{args.basinlevel}.html'
                nirivers = nirivers.clip(buffer)
                nilakes = nilakes.clip(buffer)
                roirivers = roirivers.clip(buffer)
                roilakes = roilakes.clip(buffer)
            else:
                title = "Ireland's river basins"
                fname = f'ie_rivers_lakes-{colour}-{args.basinlevel}.html'
            ie = alt.layer(niareas, roiareas, nilines, roilines).configure_view(
                strokeWidth=0
            ).properties(
                background = '#000000',
                title=alt.TitleParams(
                    text=title,
                    subtitle=['Based on DAERA, EPA, OSi and HydroBasins datasets','Created by Paul Barber'],
                    baseline='bottom',
                    orient='bottom',
                    anchor='end',
                    font='Optima',
                    fontWeight='bold',
                    fontSize=80,
                    dy=-100,
                    color='#fff',
                    subtitleColor='#fff',
                    subtitleFont='Optima',
                    subtitleFontSize=48,
                    subtitleFontWeight='normal',
                ),
            )
            save(ie, fname, format='html')
