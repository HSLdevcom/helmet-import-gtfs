"""Changes subset of imported gtfs transit lines from mode d to e.
Assigns imported gtfs transit lines with new line names.
"""
import inro.emme.desktop.worksheet as _worksheet
import pandas
from math import sqrt
import re
from typing import Dict, Tuple, Any
from shapely import intersects, points
from tqdm import tqdm
import parameters.assignment as param

def get_line_data(desktop) -> Tuple[pandas.DataFrame]:
    """Fetches line data from Emme data tables using transit line, transit segment
    and node data tables.

    Returns avg stop distance for lines and start/terminus node coordinates
    for lines.

    Parameters
    ----------
    desktop : inro.emme.desktop
        Emme desktop api

    Returns
    -------
    Tuple[pandas.DataFrame]
        dataframes with line information
    """
    # Get avg stop distances
    attribute_map = {
        "table_type": "TRANSIT_SEGMENT",
        "transit_line": "line",
        "mode_id": "mode",
        "length": "length",
        "is_stop": "isIBoardingStop",
        "agency_name": "Pline->#agency_name",
    }
    summarize = {
        "group_by": ["line", "mode"],
        "condition": [["length", "SUM"], ["isIBoardingStop", "SUM"], ["Pline->#agency_name", "FIRST"]]
    }
    df_stop_dist = data_table_to_df(desktop, attribute_map, summarize)\
        .query("mode == 'd'")
    df_stop_dist = df_stop_dist.rename(columns={
        "Sum(length)": "sum_length",
        "Sum(isIBoardingStop)": "sum_stops"
    })
    df_stop_dist.loc[:, "avg"] = df_stop_dist["sum_length"] / df_stop_dist["sum_stops"]

    # Get start and terminus nodes for lines
    attribute_map = {
        "table_type": "TRANSIT_LINE",
        "transit_line": "line",
        "mode_id": "mode",
        "first_stop": "ca_first_t",
        "last_stop": "ca_last_t",
    }
    summarize = {
        "group_by": list(attribute_map.values())[1:],
        "condition": []
    }
    df_line_ends = data_table_to_df(desktop, attribute_map, summarize)\
        .query("mode == 'd'")\
        .astype({"ca_first_t": "int32", "ca_last_t": "int32"})

    # Get node coordinates
    attribute_map = {
        "table_type": "NODE",
        "node": "i",
        "x_coord": "xi",
        "y_coord": "yi",
    }
    summarize = {
        "group_by": list(attribute_map.values())[1:],
        "condition": []
    }
    df_node_coords = data_table_to_df(desktop, attribute_map, summarize)\
    .rename(columns={"i": "node"})\
    .astype({"node": "int32"})
    df_line_coords = pandas.merge(df_line_ends, df_node_coords,
                             left_on="ca_first_t", right_on="node", how="left")\
                            .merge(df_node_coords,
                               left_on="ca_last_t", right_on="node", how="left")
    df_line_coords = df_line_coords.drop(columns=["node_x", "node_y"])\
        .rename(columns={"xi_x": "xi", "yi_x": "yi", "xi_y": "xj", "yi_y": "yj"})
    return df_stop_dist, df_line_coords

def data_table_to_df(desktop, attr_map: Dict[str, str],
                     summarize: Dict[str, list]) -> pandas.DataFrame:
    """Helper func for converting Emme data tables to pandas dataframe.

    Parameters
    ----------
    desktop : inro.emme.desktop
        Emme desktop API
    attr_map : Dict[str, str]
        mapped attributes containing table type and columns
    summarize : Dict[str, list]
        data table summarize principles

    Returns
    -------
    pandas.DataFrame
        converted dataframe
    """
    column = _worksheet.Column()
    new_table = desktop.project.new_network_table(type=attr_map["table_type"])
    for index, val in enumerate(attr_map.values(), start=1):
        column.name, column.expression = val, val
        new_table.add_column(index, column)
    datatb = new_table.save_as_data_table("temp_table", overwrite=True)
    summary = datatb.get_data()\
    .summarize(summarize["group_by"], summarize["condition"])
    dfs = []
    for i in summary.attributes():
        if i.atype == 'GEOMETRY':
            dfs.append(pandas.DataFrame({i.name: [x.text for x in i.values]}))
        else:
            dfs.append(pandas.DataFrame({i.name: i.values}))
    df = pandas.concat(dfs, axis=1)
    df = df.rename(columns={"First(Pline->#agency_name)": "#agency_name"})
    desktop.project.data_tables().delete_table("temp_table")
    return df

def change_line_vehicle(modeller, df: pandas.DataFrame, dev_config: Dict[str, Any]) -> list:
    """Changes mode types from d to e for lines where avg bus stop distance
    is larger than specified threshold value. 
    Emme's transit line selector has line limit of 12 with comma separation. 

    Parameters
    ----------
    modeller : inro.modeller
        Emme modeller API
    df : pandas.DataFrame
        dataframe with average stop distance
    dev_config : Dict[str, Any]
        dev config json

    Returns
    -------
    list
        lines with mode change from d to e
    """
    min_stop_dist = dev_config["stop_distance"]
    line_limit_n = 12
    e_lines = df.query(f"avg > {min_stop_dist}")["line"].values.tolist()
    ob_lines = df[df['line'].str.startswith("O")]["line"].values.tolist()
    combined_lines = e_lines + ob_lines
    print(df.columns)
    ob_mega_lines = df[(df['line'].str.startswith("O")) & (df['#agency_name'] == "OnniBus MEGA")]["line"].values.tolist()

    concat_lines = [combined_lines[i:i+line_limit_n] \
                    for i in range(0, len(combined_lines), line_limit_n)]
    concat_lines = [",".join(i) for i in concat_lines]

    concat_ob_lines = [ob_mega_lines[i:i+line_limit_n] \
                    for i in range(0, len(ob_mega_lines), line_limit_n)]
    concat_ob_lines = [",".join(i) for i in concat_ob_lines]

    change_line_vehicle = modeller.tool("inro.emme.data.network.transit.change_line_vehicle")
    veh = modeller.scenario.transit_vehicle(dev_config["vehicle_ids"]["e"])
    for i in tqdm(concat_lines, desc = '--Changing express lines mode from d to e'):
        change_line_vehicle(vehicle=veh, selection="line = " + i)
    for i in tqdm(concat_ob_lines, desc = '--Changing OnniBus lines mode from d to e'):
        change_line_vehicle(vehicle=modeller.scenario.transit_vehicle(12), selection="line = " + i)
    return combined_lines

def change_line_names(modeller, dev_config: Dict[str, Any],
                      df_line_coords: pandas.DataFrame, features, geometries):
    """Changes line names using network object. Uses helper functions in
    formatting operator name, direction id and finally forming new name.

    Parameters
    ----------
    modeller : Type
        Emme modeller api
    dev_config : Dict[str, Any]
        Emme scenario id
    df_line_coords : pandas.DataFrame
        dataframe with start and terminus node xy coords
    """
    scenario = modeller.emmebank.scenario(dev_config["emme_scen_id"])
    network = scenario.get_network()
    tlines = network.transit_lines()

    lnames = []
    descriptions = []
    running_n = {}
    # i = 0
    print("--Changing line names based on area of operation")
    print("--Line name letters: B=Raasepori(Bosse), P=Porvoo, H=Hämeenlinna, L=Lahti, M=Mäntsälä, R=Riihimäki, S=Salo, U=Länsi-(U)usimaa, Y=H(Y)vinkää, O=OnniBus, V=Muut")
    for line in tqdm(tlines, desc="Forming new line names"):
        if line.mode.id in dev_config["vehicle_ids"].keys():
            line_id = line.id
            line_letter = get_operator_name(df_line_coords, line, features,
                                            geometries, dev_config["muni_col_name"],
                                            dev_config["muni_short_codes"])
            dir_id = get_direction_id(df_line_coords, line_id)
            linename, desc, lnames, running_n, descriptions = form_new_linename(line, line_letter,
                                                            dir_id, lnames, running_n, descriptions)
            line.id = linename
            re_short_route_name = re.split("\s*-\s*", desc)
            short_route_name = desc.split("-")
            # if i > 200 and i<210:
            #     print(re_short_route_name)
            #     print(short_route_name)
            #     print()
            if short_route_name[0] != " ":
                line.description = "-".join(re_short_route_name[0:])[0:115]
            else:
                line.description = "-".join(re_short_route_name[1:])[0:115]
        
        # i += 1
    print("--Publishing network with updated linenames")
    scenario.publish_network(network)

def get_operator_name(df: pandas.DataFrame, line: str,
                      features: Dict[str, Dict], geometries, muni_name_col: str,
                      muni_short_codes: Dict[str, str]) -> str:
    """Helper function for deducing operator letter.
    Confirms if line start and terminus nodes are within same municipality
    in Helmet zone geojson and adds municipality short code.
    Else returns common Vallu bus line letter 'V'.

    Parameters
    ----------
    df : pandas.DataFrame
        dataframe with node coordinate info
    line_id : str
        gtfs based line id
    features: Dict[str, Dict]
        helmet area geojson with feature information
    geometries: shapely GeometryCollection
        shapely geometry collection constructed from Helmet geojson
    muni_name_col: str
        column in geojson features containing municipality names
    muni_short_codes: Dict[str, str]
        dictionary of municipality name: short code 

    Returns
    -------
    str
        Short municipality name, else none
    """
    line_id = line.id
    if "OnniBus" in line['#agency_name']:
        return "O"
    p1 = points(df.loc[(df["line"] == line_id), "xi"],
                df.loc[(df["line"] == line_id), "yi"])
    p2 = points(df.loc[(df["line"] == line_id), "xj"],
                df.loc[(df["line"] == line_id), "yj"])
    muniname = []
    for index, value in enumerate(features):
        geometry = geometries.geoms[index]
        if intersects(p1, geometry) or intersects(p2, geometry):
            try:
                muniname.append(muni_short_codes[value["properties"][muni_name_col]])
            except KeyError:
                break
        if len(muniname) == 2:
            if muniname[0] == muniname[1] and muniname[0] in muni_short_codes.values():
                return muniname[0]
            break
    return "V"

def get_direction_id(df: pandas.DataFrame, line_id: str) -> int:
    """Helper function for deducing line direction id using start and end node 
    coordinates for line. Uses Helsinki central railway station node (GK25)
    as reference node.
    id 1 = direction away from Helsinki
    id 2 = direction towards Helsinki

    Parameters
    ----------
    df : pandas.DataFrame
        df with start and terminus x,y node coordinates for line id
    line_id : str
        gtfs based line id

    Returns
    -------
    int
        direction id
    """
    direction_id = 1
    first_node = int(df.loc[df["line"] == line_id, "ca_first_t"])
    last_node = int(df.loc[df["line"] == line_id, "ca_last_t"])
    if first_node == last_node:
        direction_id = 3
    else:
        hel_x, hel_y = 25496699, 6673208
        start_x = df.loc[(df["line"] == line_id), "xi"]
        start_y = df.loc[(df["line"] == line_id), "yi"]
        end_x = df.loc[(df["line"] == line_id), "xj"]
        end_y = df.loc[(df["line"] == line_id), "yj"]
        start_diff = sqrt((hel_x - start_x)**2 + (hel_y - start_y)**2)
        end_diff = sqrt((hel_x - end_x)**2 + (hel_y - end_y)**2)
        if start_diff > end_diff:
            direction_id = 2
    return direction_id

def form_new_linename(line: str, line_letter: str, dir_id: int,
                      lnames: list, running_n: dict, descriptions: list) -> Tuple[str, list, int]:
    """Helper function for forming new line name.
    Creates new linename using line letter + line id + direction id.
    Linename has to be unique. If line id does not contain integer, uses 
    running number as a substitute.

    Parameters
    ----------
    line_id : str
        gtfs based line id
    line_letter : str
        line letter, check get_operator_name()
    dir_id : int
        direction id, check get_direction_id()
    lnames : list
        listed operator unique operator names
    running_n : dict
        dictionary of line_letter to running number

    Returns
    -------
    Tuple
        new line name, updated list of line names, running number
    """
    def includes_numbers(s: str) -> bool:
        return any(char.isdigit() for char in s)
        
    def clean_line_code(s: str) -> str:
        # Remove everything but letters and digits
        cleaned = re.sub(r'[^a-zA-Z0-9]', '', s)
        cleaned = re.sub(r'/', '', cleaned)
        cleaned = re.sub(r'^ELY', '', cleaned)
        return cleaned

    def remove_last_letters(s):
        # Extract all trailing letters if they exist
        match = re.search(r'([a-zA-Z]+)$', s)
        if match:
            suffix = match.group(1)
            cleaned = s[:-len(suffix)]
        else:
            suffix = ''
            cleaned = s
        match = re.search(r'^([a-zA-Z]+)', cleaned)
        if match:
            prefix = match.group(0)
            cleaned = cleaned[len(prefix):]
        else:
            prefix = ''
        return cleaned, prefix, suffix    
    
    # Initialize running number for the line_letter if not already present
    if line_letter not in running_n:
        running_n[line_letter] = 99

    # Split the route by spaces and check if the first elements contain numbers
    parts = re.split(r'\s*-\s*', line['#route_name'])
    route_number = ''
    starting_point = re.split('\s+', parts[1])
    if len(starting_point)>1 and includes_numbers(parts[0]):
        # Save the number and remove the first two elements
        route_number = parts.pop(0)
        if len(starting_point) > 2:  # Name of first stop has multiple words
            if includes_numbers(starting_point[0]):
                parts = [' '.join(starting_point[1:])] + parts[1:]
            else:
                [' '.join(starting_point)] + parts[1:]
        elif includes_numbers(starting_point[0]):
            parts = [starting_point[1]] + parts[1:]
        else:
            parts = [starting_point[0]] + parts[1:]
    elif includes_numbers(parts[0]):
        route_number = parts.pop(0)
    elif parts[0] == '':
        parts = parts[1:]

    cleaned_route = ' - '.join(parts)
    reversed_route = ' - '.join(parts[::-1])  # For matching linenames with reverse direction of the same line
    print(f"Route: {cleaned_route}, route_number: {route_number}")
    n_to_fill = 4
    if len(line_letter) == 2:
        n_to_fill -= 1

    line_code_prefix = ''
    line_code_suffix = ''
    for used_route, used_linenumber, used_dir_id in descriptions:
        if used_route == cleaned_route and used_dir_id != dir_id:  # Same stops in desc, but reverse direction
            line_number = used_linenumber[0]
            break
        elif used_route == reversed_route and used_dir_id != dir_id:  # Reversse stops in desc, and reverse direction
            line_number = used_linenumber[0]
            break
        elif (used_route.split(' - ')[-1].strip('.') == cleaned_route.split(' - ')[0].strip('.') and 
              used_dir_id != dir_id and used_linenumber[0] == clean_line_code(route_number) and 
              line_letter==used_linenumber[1]):  # Same endpoints and number, different stops, assume it's the same line
            line_number = used_linenumber[0]
            break
        elif clean_line_code(route_number) == used_linenumber[0] and line_letter==used_linenumber[1]:  # Same number but different stops and endpoints, this is a different line.
            line_number, line_code_prefix, line_code_suffix = remove_last_letters(clean_line_code(route_number))
            try:
                if not line_code_suffix and len(line_number) + len(line_code_prefix) < 4:
                    line_code_suffix = 'B'
                    line_number = line_number
                else:
                    line_number = int(line_number) + 1
            except ValueError:
                print(route_number)
                print(line_number)
                print(line_code_suffix)
                raise ValueError("Line number is not a number")
            break
    else:
        if route_number:
            line_number, line_code_prefix, line_code_suffix = remove_last_letters(clean_line_code(route_number))
        else:
            line_number = running_n[line_letter]
            running_n[line_letter] += 1
    
    # Recombine prefix and suffix with line_number
    if line_code_suffix and line_code_prefix:
        line_number =  line_code_prefix[0] + str(line_number) + line_code_suffix[0]
    elif line_code_prefix:
        line_number =  line_code_prefix[0] + str(line_number)
    elif line_code_suffix:
        line_number =  str(line_number) + line_code_suffix[0]
    else:
        line_number = str(line_number)
        
    linename = f"{line_letter}{str(line_number).zfill(n_to_fill)}{dir_id}"
    while linename in lnames:
        line_number = running_n[line_letter]
        running_n[line_letter] += 1
        linename = f"{line_letter}{str(line_number).zfill(n_to_fill)}{dir_id}"
    lnames.append(linename)
    descriptions.append((cleaned_route, (line_number, line_letter), dir_id))
    return linename, cleaned_route, lnames, running_n, descriptions

def modf_transit_lines(desktop, modeller, dev_config, features, geometries):
    """Gets transit line data from Emme. Changes modes from d to e for
    subset of transit lines with long average stop distance.
    Changes transit line names. 

    Parameters
    ----------
    desktop : inro.emme.desktop
        Emme desktop API
    modeller : inro.modeller
        Emme modeller API
    dev_config : Dict[str, Any]
        dev config json
    features : Dict[str, Dict]
        helmet area geojson with feature information
    geometries : shapely GeometryCollection
        shapely geometry collection constructed from Helmet geojson
    """
    df_stop_dist, df_line_coords = get_line_data(desktop)
    change_line_names(modeller, dev_config, df_line_coords, features, geometries)
    desktop.refresh_data()
    df_stop_dist, df_line_coords = get_line_data(desktop)
    e_lines = change_line_vehicle(modeller, df_stop_dist, dev_config)
    df_line_coords.set_index("line", inplace=True)
    df_line_coords.loc[e_lines, "mode"] = "e"
    df_line_coords.reset_index(inplace=True)
    desktop.refresh_data()
    print("--GTFS to Emme transaction completed. Closing Emme API.")


def create_time_attribute(modeller):
    """Creates time attribute which is used in GTFS route selection
    as a fastest route

    Parameters
    ----------
    modeller : Type
        Emme modeller api
    """
    create_extra = modeller.tool("inro.emme.data.extra_attribute.create_extra_attribute")
    network_calulator = modeller.tool("inro.emme.network_calculation.network_calculator")

    create_extra(extra_attribute_type = "LINK",
                extra_attribute_name = "@time_freeflow_car",
                extra_attribute_description = "car time with free flow speed",
                extra_attribute_default_value = 999,
                overwrite=True)
    spec = {
        "type" : "NETWORK_CALCULATION",
        "result" : "@time_freeflow_car",
        "expression" : "length/ul2*60",
        "selections" : {
            "link" : "ul2=1,999"}}
    network_calulator(spec, full_report=True)

def set_vdfs(modeller):
    print("--Setting ul1 and ul2 for links")
    network = modeller.scenario.get_network()
    for link in network.links():
        # Car volume delay function definition
        linktype = link.type % 100
        if linktype in param.roadclasses:
            # Car link with standard attributes
            roadclass = param.roadclasses[linktype]
            link.volume_delay_func = roadclass.volume_delay_func
            link.data1 = roadclass.lane_capacity
            link.data2 = roadclass.free_flow_speed
        elif linktype in param.custom_roadtypes:
            # Custom car link
            link.volume_delay_func = linktype - 90
            for linktype in param.roadclasses:
                roadclass = param.roadclasses[linktype]
                if (link.volume_delay_func == roadclass.volume_delay_func
                        and link.data2 > roadclass.free_flow_speed-1):
                    # Find the most appropriate road class
                    break
        else:
            # Link with no car traffic
            link.volume_delay_func = 0
    modeller.scenario.publish_network(network)
