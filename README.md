# helmet-import-gtfs
Tool used to import transit lines from gtfs to emme in a HELMET compatible format

Currently only compatible with old EMME versions using Python 3.7.6.


This package automates the process of converting GTFS based bus lines
into Emme by using Emme's import from gtfs tool, and it was originally created by WSP Finland for 
Helsinki Region Transportation (HSL) with the organization's collaboration, and further developed by HSL.

## Setup
Setup of this package uses pipenv package control, and it follows same setup
principle as HSL's helmet model system. Referenced detailed setup guide can be found
in Helmet model system's repository: https://github.com/HSLdevcom/helmet-model-system

1. Install Python 3.7 to be compatible with Emme. Add to PATH.
2. Install pipenv with cmd using python -m pip install --user pipenv\
    i. pipenv install into user appdata. Add to path: %APPDATA%\Python\Python37\Scripts
3. Clone repo. It is recommended to have the package in same directory with the 
Emme project where transit lines will be imported into. 
4. cd to cloned repo and install dependencies from Pipfile: pipenv --python 3.7 install --dev\
    i. this will create a new virtual environment for the project into: Users\virtualenvs\
    ii. activate environment with pipenv shell

## Running import vallu lines
The program is executed with python scripts/run_vallu_lines.py

The program uses venv created by pipenv as interpreter to prevent dependencies from being installed
into Emme's site packages. Therefore to connect into Emme API, run_vallu_lines.py
appends Emme's Python37 lib collections to path for the duration of the run. 
**Therefore it is expected that the user has Emme added into PATH and Emme is installed in C:/Program Files/**.
Otherwise the program will raise ModuleNotFoundError, and the user has to manually change
Emme's Python37 lib collections in run_vallu_lines.py.

Before launching, confirm that pipenv is activated and review dev-config contents 
including necessary paths, GTFS folder, Helmet5 geojson and other parameters.
Additionally, the scenario id given in dev-config has to exist in the Emme project, and
Helmet5 area geojson has to be in utf-8. Besides these steps, there are no 
other matters that the user needs to consider. 

The program will print short messages and progress bars to indicate overall progress. 
The imported transit lines can be imported into a scenario with existing HSL lines.


## Configure dev-config.json

### emme_proj_path
Set path for desired Emme project .emp file.

### helmet_zones_geojson_path
Set path for Helmet assignment zones (sijoittelualueet) geojson file. The file
will be used in reading zone features and geometries.

### emme_scen_id
Define Emme scenario id where GTFS transit lines will be imported into. The scenario
has to exist and an error will be raised otherwise.

### gtfs_hsl_agency_id
Define HSL agency id that is present in the GTFS data. This id is used in excluding 
HSL transit lines from being imported. The id can vary between GTFS collections.

### gtfs_folder_path
Set path for folder containing GTFS files. Necessary gtfs files include agency.txt,
calendar.txt, calendar_dates.txt, routes.txt, stop_times.txt, stops.txt and trips.txt.

### gtfs_import_date
Define date for importing. Date has to be **string** and follow **year-month-day** date format.
The program does not check for invalid GTFS date and Emme import from gtfs will
raise an error in case invalid date is being defined for set GTFS data.

### gtfs_start_time
Define starting timestamp for importing transit lines. Time has to be **string** and
follow **HH:MM** time format. Import from gtfs tool will start considering trips from
this time point onwards.

### gtfs_end_time
Define ending timestamp for importing transit lines. Time has to be **string** and
follow **HH:MM** time format. Import from gtfs tool will considering trips until this
point in time.

### vehicle_ids
Defines vehicle modes and ids. These have to be changed only if vehicle mode or
ids are being changed within Helmet system environment. Dictionary with vehicle mode
as key and vehicle id as value.

The program uses order of the keys in converting modes. Therefore 

### period_headways
Defines timestamps for saving peak hour headways into attributes. Formatted as a list
that contains a dictionary for transit line extra attribute, start time and 
end time for each observed time period. The transit line extra attribute must 
exist in the processed scenario.

### mapmatching_criteria
Define criterias for Emme import from gtfs tool. Currently defined values 
have been tested to work well for mapmatching GTFS results into Helmet 5 network.
For detailed variable explanation, check Emme help for import from gtfs tool. 

### use_shapes
Whether to use GTFS shapes.txt in mapmatching transit lines. **true/false**. 
Testing indicated not using shapes to be the better alternative with Helmet 5 network
due to rough network illustration on highways.

### stop_variance
Define stop variance for aggregating routes with similar itineraries as a single transit line.
**int >= 0**. Default value 8 has been tested to work well. For more information, 
check trip aggregation section of import from GTFS tool.

### headway_calc_type
Defines headway calculation type. "DEPARTURES_STUDY_PERIOD" method is default calculation type.

### gtfs_attributes
Define network field and extra attributes to import information from GTFS data.
Running the program will create said attributes if the are defined in dev-config.
Every attribute has to have variable name and field type. Description is optional.
**Network field attributes route name, trip id and stop name must be always defined.**

### stop_distance
Define average stop distance as **int** which is used as a threshold in converting 
transit lines from mode d to mode e. By default transit lines with average stop 
distance greater or equal to 10 (kilometers) are being converted to mode e (ValluPika). 

### muni_col_name
Geojson column name containing Helmet 5 area municipality names.

### muni_short_codes
Municipality short codes for imported Vallu lines. Dictionary where key is municipality
name and value is short 2-letter code. Default dictionary includes all Helmet 5 areas 
that are for the time being outside of HSL operation.