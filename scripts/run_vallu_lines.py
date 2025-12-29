"""This package connects to EMME, processes VALLU bus lines from GTFS data into EMME
and modifies modes and line names of the imported data.
"""
import sys
import json
sys.path.append("C:/Program Files/INRO/Emme/Emme 4/Emme-23.00.01.23/Python37"\
            "/Lib/site-packages")
sys.path.append("C:/Program Files/INRO/Emme/Emme 4/Emme-23.00.01.23/Python37"\
            "/Lib/site-packages/win32")
sys.path.append("C:/Program Files/INRO/Emme/Emme 4/Emme-23.00.01.23/Python37"\
            "/Lib/site-packages/win32/lib")
import inro.emme.desktop.app as _app
import inro.modeller as _m
import inro.emme.desktop.exception as _error
from process_gtfs_data import process_gtfs
from import_gtfs import import_gtfs_to_emme
from modify_transit_lines import modf_transit_lines, create_time_attribute, set_vdfs
from shapely.geometry import shape, GeometryCollection
from shapely import prepare
from typing import Tuple, Dict

def get_helmet_zones(filepath: str) -> Tuple[Dict[str, str], GeometryCollection]:
    """Reads Helmet zone extent (sijoittelualueet) geojson into features
    and geometries. 

    Parameters
    ----------
    filepath : str
        path for Helmet area as a geojson

    Returns
    -------
    Tuple[Dict[str, str], GeometryCollection]
        Helmet area features and geometries
    """
    try:
        with open(filepath, encoding="utf-8") as f:
            features = json.load(f)["features"]
    except FileNotFoundError:
        raise FileNotFoundError("Invalid geojson filepath in dev config.")
    geometries = GeometryCollection([shape(feature["geometry"])\
                                     .buffer(0) for feature in features])
    prepare(geometries)
    return features, geometries

def main():
    """Initializes connection with Emme project. With said project, performs
    following tasks:
    1. processes GTFS data
    2. uses processed data in importing GTFS lines into defined Emme scenario
    3. performs d to e mode and transit line id naming actions

    Raises
    ------
    ValueError
        Invalid Emme project path
    AttributeError
        Invalid Emme id
    """
    print("--Reading dev config")
    with open("dev-config.json", encoding="utf-8") as file:
        dev_config = json.load(file)
    print("--Starting Emme")
    try:
        desktop = _app.start_dedicated(project=dev_config["emme_proj_path"], visible=False, user_initials="HSL")
    except _error.StartInvalidOption:
        raise ValueError("Invalid path for Emme project in dev config.")
    modeller = _m.Modeller(desktop)
    try:
        data_explorer = desktop.data_explorer()
        scenario_selection = modeller.emmebank.scenario(dev_config["emme_scen_id"])
        data_explorer.replace_primary_scenario(scenario_selection)
    except AttributeError:
        raise AttributeError("Invalid Emme scenario id in dev config.")
    
    features, geometries = get_helmet_zones(dev_config["helmet_zones_geojson_path"])
    gtfs_map = process_gtfs(dev_config["gtfs_folder_path"],
                            dev_config["gtfs_hsl_agency_id"],
                            geometries)
    set_vdfs(modeller)
    create_time_attribute(modeller)
    import_gtfs_to_emme(modeller, dev_config, gtfs_map)
    desktop.refresh_data()
    modf_transit_lines(desktop, modeller, dev_config, features, geometries)

main()