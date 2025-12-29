"""This module reads agency ids, route types and route ids from GTFS data, and
returns a map where said variables are included as lists of strings.
"""
import pandas
from shapely import union_all, prepare, points
from pyproj import Transformer, CRS
from tqdm import tqdm
from typing import Dict

def get_helmet_stops(gtfs_path: str, geometries) -> list:
    """Returns GTFS stop ids that intersect with Helmet zone extent.

    Parameters
    ----------
    gtfs_path : str
        GTFS data folder
    geometries : shapely GeometryCollection
        Helmet zones (sjoittelualue)

    Returns
    -------
    list
        list of intersecting stop ids
    """
    try:
        gtfs_stops_df = pandas.read_csv(gtfs_path + "/stops.txt")
    except FileNotFoundError:
        raise FileNotFoundError("Invalid GTFS folder path in dev config.")
    helmet_area = union_all(geometries)
    prepare(helmet_area)
    source_crs = CRS('epsg:4326') # Coordinate system of GTFS
    target_crs = CRS('epsg:3879') # Helmet coordinate system
    source_to_target = Transformer.from_crs(source_crs, target_crs)

    y, x = source_to_target.transform(gtfs_stops_df["stop_lat"],
                                      gtfs_stops_df["stop_lon"])
    gtfs_stops_df["geometry"] = points(x, y)
    gtfs_stops_df["in_helmet"] = False
    for row in tqdm(range(len(gtfs_stops_df)), desc="Filtering out of bounds stops"):
        if helmet_area.intersects(gtfs_stops_df.loc[row, "geometry"]):
            gtfs_stops_df.loc[row, "in_helmet"] = True
    
    helmet_stops = gtfs_stops_df.query("in_helmet == True")
    helmet_stops = helmet_stops["stop_id"].values.astype(str).tolist()
    return helmet_stops

def get_agency_ids(gtfs_path: str, hsl_agency_id: int) -> list:
    """Returns agency ids in GTFS data where HSL agency id has been filtered.
    HSL agency id can vary between GTFS datas.
    Define agency id in dev_config.json

    Parameters
    ----------
    gtfs_path : str
        GTFS data folder
    hsl_agency_id : int
        HSL agency id in read GTFS data

    Returns
    -------
    list
        list of agency ids besides hsl 
    """
    agencies_df = pandas.read_csv(gtfs_path + "/agency.txt")\
        .query(f"agency_id != {hsl_agency_id}")\
        .reset_index()
    agency_ids = agencies_df["agency_id"].values.astype(str).tolist()
    return agency_ids
    
def get_route_types() -> list:
    """Returns list of route type ids for mode bus.
    Currently listed route types are supported GTFS route types. 

    Returns
    -------
    list
        list of bus route types
    """
    gtfs_route_types = {
        "3": "Bus",
        "700": "Bus Service",
        "701": "Regional Bus Service",
        "702": "Express Bus Service",
        "704": "Local Bus Service",
        "715": "Demand And Responsive Bus Service"
    }
    route_types = list(gtfs_route_types.keys())
    return route_types

def get_route_ids(gtfs_path: str, helmet_stops: list,
                  agency_ids: list, route_types: list) -> list:
    """Returns route ids that have been filtered with agency ids, route types
    and route ids that intersect with helmet zone area.

    Parameters
    ----------
    gtfs_path : str
        GTFS data folder
    helmet_stops : list
        list of stops that intersect with Helmet zone
    agency_ids : list
        list of agency ids besides hsl id
    route_types : list
        GTFS route types

    Returns
    -------
    list
        list of filtered route ids
    """


    stop_times_df = pandas.read_csv(gtfs_path + "/stop_times.txt",
                                    dtype = {"stop_headsign": str})
    trips_df = pandas.read_csv(gtfs_path + "/trips.txt")
    routes_df = pandas.read_csv(gtfs_path + "/routes.txt")

    trip_ids = stop_times_df.query(f"stop_id in {helmet_stops}")["trip_id"]\
        .unique().tolist()
    filtered_routes = trips_df.query(f"trip_id in {trip_ids}")\
        .merge(routes_df, on="route_id", how="left")
    helmet_routes = filtered_routes["route_id"].unique().tolist()
    
    routes_df = routes_df.query(f"agency_id in {agency_ids}"
                                f"& route_type in {route_types}"
                                f"& route_id in {helmet_routes}")
    route_ids = routes_df["route_id"].values.astype(str).tolist()
    return route_ids

def process_gtfs(gtfs_path: str, hsl_agency_id: str, geometries) -> Dict[str, list]:
    """Maps agency ids, route types and route ids for Emme's GTFS importer tool.

    Parameters
    ----------
    dev_config : Dict[str, str]
        Developed config file
    geometries : shapely GeometryCollection
        Helmet zones (sjoittelualue)

    Returns
    -------
    Dict[str, list]
        Mapped GTFS variables
    """
    gtfs_map = {}
    helmet_stops = get_helmet_stops(gtfs_path, geometries)
    gtfs_map["agency_ids"] = get_agency_ids(gtfs_path, hsl_agency_id)
    gtfs_map["route_types"] = get_route_types()
    gtfs_map["route_ids"] = get_route_ids(gtfs_path, helmet_stops, gtfs_map["agency_ids"],
                                          gtfs_map["route_types"])
    return gtfs_map