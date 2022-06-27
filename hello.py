# %%
import pydeck as pdk
import geopandas as gpd

# %%
gdf = gpd.read_file('https://opendata-daerani.hub.arcgis.com/datasets/DAERANI::rivers-strahler-ranking.zip?outSR=%7B%22latestWkid%22%3A29902%2C%22wkid%22%3A29900%7D')
gdf.geometry = gdf.geometry.to_crs('4326')
gdf['colour'] = [(180,0,200,150)] * len(gdf)

# %%
def extract_coord_lists(x):
    if x.type == 'MultiLineString':
        return [list(line.coords) for line in x]
    elif x.type == 'LineString':
        return list(x.coords)
    else:
        raise Exception('Unknown type {x.type}')

gdf['plotstrings'] = gdf.geometry.apply(extract_coord_lists)
gdf["colour"] = [(180,0,200,150)] * len(gdf)

# %%
view_state = pdk.ViewState(latitude=54.78, longitude=-6.49, zoom=7)

layer = pdk.Layer(
    type="PathLayer",
    data=gdf,
    pickable=True,
    get_color="colour",
    width_scale=20,
    width_min_pixels=2,
    get_path="plotstrings",
    get_width=5,
    tooltip=True
)

r = pdk.Deck(
    layers=[layer], 
    initial_view_state=view_state,
    map_style='light')

r.to_html("path_layer.html")
