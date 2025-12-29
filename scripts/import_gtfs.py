"""This module imports bus lines from GTFS data into Emme scenario using Emme tools.
"""
import inro.emme.core as _core
from typing import Dict, Any
from time import process_time

def del_current_vallu_lines(modeller, scen_id: int, veh_modes: list):
    """Tries to delete transit lines with d and e modes form current Emme scenario.

    Parameters
    ----------
    modeller : inro.modeller
        Emme modeller API
    scen_id : int
        Emme scenario id
    veh_modes : list
        Defined vehicle modes in dev config
    """
    for index, mode in enumerate(veh_modes):
        veh_modes[index] = f"mode = {mode}"
    modes = (" | ").join(veh_modes)
    try:
        del_lines = modeller.tool("inro.emme.data.network.transit.delete_transit_lines")
        del_lines(selection=modes)
        print(f"--Deleted current mode d and e transit lines for scenario {scen_id}")
    except _core.exception.ArgumentError:
        pass
    except _core.exception.ExistenceError:
        pass

def create_attributes(modeller, gtfs_attributes: Dict[str, Dict[str, str]]) -> Dict[str, str]:
    """Creates new network field and extra attributes for GTFS importer tool
    to store attributes into. Does not overwrite if attribute already exists.

    Parameters
    ----------
    modeller : inro.modeller
        Emme modeller API
    gtfs_attributes : Dict[str, Dict[str, str]]
        dev config gtfs network field and extra attributes

    Returns
    -------
    Dict[str, str]
        attribute name : Emme attribute name
    """
    create_netfield = modeller.tool("inro.emme.data.network_field.create_network_field")
    create_extra = modeller.tool("inro.emme.data.extra_attribute.create_extra_attribute")
    stored_attributes = {}
    print("--Checking attributes")
    for i in gtfs_attributes["network_field_attributes"]:
        var = gtfs_attributes["network_field_attributes"]
        stored_attributes[i] = var[i]["field_type"] + "#" + var[i]["field_name"]
        try:
            create_netfield(
                network_field_type=var[i]["field_type"],
                network_field_atype="STRING",
                network_field_name="#" +  var[i]["field_name"],
                network_field_description=var[i]["field_description"],
                overwrite=False)
        except _core.exception.ExistenceError:
            pass
    if gtfs_attributes["create_extra"]:
        for i in gtfs_attributes["extra_attributes"]:
            var = gtfs_attributes["extra_attributes"]
            stored_attributes[i] = "@" + var[i]["field_name"]
            try:
                create_extra(
                    extra_attribute_type = var[i]["field_type"],
                    extra_attribute_name = "@" + var[i]["field_name"],
                    extra_attribute_description = var[i]["field_description"],
                    overwrite=False)
            except _core.exception.ExistenceError:
                pass
    return stored_attributes

def import_gtfs(modeller, dev_config: Dict[str, Any], gtfs_map: Dict[str, list],
                gtfs_attributes: Dict[str, str]):
    """Runs Emme tool 'import from gtfs'. 

    Parameters
    ----------
    modeller : inro.modeller
        Emme modeller API
    dev_config : Dict[str, str]
        dev config json
    gtfs_map : Dict[str, list]
        mapped gtfs variables (agency ids, route types, route ids)
    gtfs_attributes : Dict[str, str]
        mapped gtfs attributes for Emme to store
    """
    route_representation = {}
    for i in gtfs_map["route_types"]:
        try:
            route_representation[i] = {"ttf": 0, "vehicle": str(dev_config["vehicle_ids"]["d"])}
        except KeyError:
            raise KeyError("Not vehicle mode 'd' in dev-config.")

    print("--Launching Emme's GTFS importer tool.")
    time_start = process_time()
    import_from_gtfs = modeller.tool("inro.emme.data.network.transit.import_from_gtfs")
    import_from_gtfs(
        gtfs_dir=dev_config["gtfs_folder_path"],
        selection={
            "date": dev_config["gtfs_import_date"],
            "start_time": dev_config["gtfs_start_time"],
            "end_time": dev_config["gtfs_end_time"],
            "route_types": gtfs_map["route_types"],
            "route_ids": gtfs_map["route_ids"],
            "agency_ids": gtfs_map["agency_ids"]
        },
        gtfs_information=gtfs_attributes,
        period_headways= dev_config["period_headways"],
        split_times=False,
        route_representation=route_representation,
        mapmatching_criteria= dev_config["mapmatching_criteria"],
        use_shapes=dev_config["use_shapes"],
        stop_variance=dev_config["stop_variance"],
        headway_calc_type=dev_config["headway_calc_type"]
    )
    time_stop = process_time()
    print(f"--Import processing time: {time_stop - time_start:.2f} seconds")

def import_gtfs_to_emme(modeller, dev_config: Dict[str, Any],
                        gtfs_map: Dict[str, list]):
    """Removes d and e mode transit lines from current scenario, checks 
    attributes for gtfs importing and runs gtfs importer tool.

    Parameters
    ----------
    modeller : inro.modeller
        Emme modeller API
    dev_config : Dict[str, str]
        dev config json
    gtfs_map : Dict[str, list]
        mapped gtfs variables (agency ids, route types, route ids)
    """
    del_current_vallu_lines(modeller, dev_config["emme_scen_id"],
                            list(dev_config["vehicle_ids"].keys()))
    gtfs_attributes = create_attributes(modeller, dev_config["gtfs_attributes"])
    import_gtfs(modeller, dev_config, gtfs_map, gtfs_attributes)
    print("--Importing completed. Starting mode id and line name transaction.")
