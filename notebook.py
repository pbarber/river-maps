# %%
import pydeck as pdk
import geopandas as gpd
import numpy as np
import met_brewer

def extract_coord_lists(x):
    if x.type == 'MultiLineString':
#        return list([(y[0],y[1]) for y in x[0].coords])
        if len(x) == 1:
            return list([(y[0],y[1]) for y in x[0].coords])
        else:
            return [list([(y[0],y[1]) for y in line.coords]) for line in x]
    elif x.type == 'LineString':
        return list([(y[0],y[1]) for y in x.coords])
    else:
        raise Exception('Unknown type {x.type}')

# Colour schemes from RMetBrewer
colours = [(int(c[1:3], 16), int(c[3:5], 16), int(c[5:], 16)) for c in met_brewer.met_brew('Derain')]

# %%
gdf = gpd.read_file('https://opendata-daerani.hub.arcgis.com/datasets/DAERANI::rivers-strahler-ranking.zip?outSR=%7B%22latestWkid%22%3A29902%2C%22wkid%22%3A29900%7D')
gdf.geometry = gdf.geometry.to_crs('4326')
gdf['plotstrings'] = gdf.geometry.apply(extract_coord_lists)
basins = gpd.read_file('https://opendata-daerani.hub.arcgis.com/datasets/DAERANI::river-basin-districts.zip?outSR=%7B%22latestWkid%22%3A29902%2C%22wkid%22%3A29900%7D')
basins.geometry = basins.geometry.to_crs('4326')
basins["colour"] = colours[1:4]
gdf = gdf.sjoin(basins, how='left')
gdf["colour"] = gdf["colour"].apply(lambda x: colours[0] if x is np.nan else x)

# %%
view_state = pdk.ViewState(latitude=54.78, longitude=-6.49, zoom=7)

layer = pdk.Layer(
    type="PathLayer",
    data=gdf,
    pickable=True,
    get_color="colour",
    width_scale=200,
    width_min_pixels=1,
    get_path="plotstrings",
    get_width="strahler",
    tooltip=False
)

r = pdk.Deck(
    layers=[layer], 
    initial_view_state=view_state,
    map_style=None)

r

# %%
ie = gpd.read_file('http://gis.epa.ie/geoserver/EPA/ows?service=WFS&version=1.0.0&request=GetFeature&typeName=EPA:WATER_RIVNETROUTES&outputFormat=application%2Fjson&srsName=EPSG:4326')
ie.geometry = ie.geometry.to_crs('4326')
ie['plotstrings'] = ie.geometry.apply(extract_coord_lists)
ie["colour"] = ""
ie["colour"] = ie["colour"].apply(lambda x: colours[0] if x == ""  else x)

# %%
view_state = pdk.ViewState(latitude=54.78, longitude=-6.49, zoom=7)

layer = pdk.Layer(
    type="PathLayer",
    data=ie,
    pickable=True,
    get_color="colour",
    width_scale=200,
    width_min_pixels=1,
    get_path="plotstrings",
    get_width="ORDER_",
    tooltip=False
)

r = pdk.Deck(
    layers=[layer], 
    initial_view_state=view_state,
    map_style='light')

r.to_html('test.html')


# %%
eu = gpd.read_file('HydroRIVERS_v10_eu.gdb.zip', bbox=(-10.56,51.39,-5.34,55.43))
eu['plotstrings'] = eu.geometry.apply(extract_coord_lists)
eu["colour"] = ""
eu["width"] = 0.5
eu["colour"] = eu["colour"].apply(lambda x: colours[0] if x == ""  else x)

# %%
view_state = pdk.ViewState(latitude=54.78, longitude=-6.49, zoom=7)

layer = pdk.Layer(
    type="PathLayer",
    data=eu.head(3),
    pickable=True,
    get_color="colour",
    width_scale=2000,
    width_min_pixels=1,
    get_path="plotstrings",
    get_width="ORD_STRA",
    tooltip=False
)

r = pdk.Deck(
    layers=[layer], 
    initial_view_state=view_state,
    map_style='light')

r.to_html('test.html')

