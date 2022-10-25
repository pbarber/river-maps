from genericpath import isfile
import geopandas as gpd
from shapely.geometry import Polygon
import numpy as np
import topojson as tp
import met_brewer
import requests
import os.path
from selenium import webdriver
import logging
import argparse

def extract_coord_lists(x):
    if x.type == 'MultiLineString':
#        return list([(y[0],y[1]) for y in x[0].coords])
        if len(x.geoms) == 1:
            return list([(y[0],y[1]) for y in x.geoms[0].coords])
        else:
            return [list([(y[0],y[1]) for y in line.coords]) for line in x.geoms]
    elif x.type == 'LineString':
        return list([(y[0],y[1]) for y in x.coords])
    else:
        raise Exception('Unknown type {x.type}')

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

def get_chrome_driver():
    options = webdriver.ChromeOptions()
    options.headless = True
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument("--window-size=1280,720")
    options.add_argument("--disable-gpu")
    options.add_argument("--hide-scrollbars")
    options.add_argument("--disable-infobars")
    options.add_argument("--enable-logging")
    options.add_argument("--log-level=0")
    options.add_argument("--v=99")
    options.add_argument("--verbose")
    options.add_argument("--single-process")
    options.add_argument("--user-data-dir=/tmp/user-data/")
    options.add_argument("--data-path=/tmp/data/")
    options.add_argument("--homedir=/tmp/homedir/")
    options.add_argument("--disk-cache-dir=/tmp/disk-cache/")
    options.add_argument("--disable-async-dns")
    options.add_argument("--remote-debugging-port=9222")
    options.add_argument("--log-path=/tmp/chromium.log")
    options.add_argument("--autoplay-policy=no-user-gesture-required")
    options.add_argument("--no-first-run")
    options.add_argument("--disable-sync")
    driver = None
    for attempt in range(3):
        try:
            driver = webdriver.Chrome(service_log_path='/tmp/chromedriver.log', options=options)
        except:
            logging.exception('Failed to setup chromium')
            if os.path.isfile('/tmp/chromedriver.log'):
                with open('/tmp/chromedriver.log') as log:
                    logging.warning(log.read())
            logging.error([f for f in os.listdir('/tmp/')])
        else:
            break
    else:
        logging.error('Failed to set up webdriver after %d attempts' %(attempt+1))
    return driver

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Create river map of the island of Ireland.')
    parser.add_argument('--colours', help='RMetBrewer colour scheme', default='Derain')
    args = parser.parse_args()

    driver = get_chrome_driver()

    if driver is not None:
        # Colour schemes from RMetBrewer
        colours = [(int(c[1:3], 16), int(c[3:5], 16), int(c[5:], 16)) for c in met_brewer.met_brew(args.colours)]

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
        eu['plotstrings'] = eu.geometry.apply(extract_coord_lists) # Convert to pydeck friendly format
        download_file_if_not_exists('https://data.hydrosheds.org/file/hydrobasins/standard/hybas_eu_lev01-12_v1c.zip')
        # Get Hydrobasins data for Ireland and apply colours
        eubas = gpd.read_file('hybas_eu_lev01-12_v1c.zip', layer='hybas_eu_lev06_v1c', bbox=(-10.56,51.39,-5.34,55.43))
        eubas["colour"] = colours[1:] + colours[1:6]
        eubas["hexcolour"] = met_brewer.met_brew(args.colours)[1:] + met_brewer.met_brew(args.colours)[1:6]
        # Spatial join of rivers to basins
        eugdf = eu.sjoin(eubas, how='left')
        # Add colour for any rivers not in basins
        eugdf["colour"] = eugdf["colour"].apply(lambda x: colours[0] if x is np.nan else x)
        eubas["hexcolour"] = eugdf["hexcolour"].apply(lambda x: met_brewer.met_brew(args.colours)[0] if x is np.nan else x)
