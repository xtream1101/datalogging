# Datalogging

This project is to provide a central database to store datapoints from sensors and/or scripts.

There is a web interface that you can create api keys so you can add data to the sites database by going to a url with the correct arguments.

The data is not displayed anywhere on the site, but you can use another api key that is linked to a host for security to pull your sensor data from the database and display it anywhere you like.


## Usage
- Config file is optional  
`python3 app.py <configfile>`


## Default config values
Config file is yaml syntax  
```
db_uri: sqlite:///datalogger.sqlite
debug: false
disable_registration: False
host: 0.0.0.0
port: 5000
secret_key: SECRET_KEY
```

## Sensor

### Data types
The data type that you expect the data to be. The data values will be returned in this format if possible 
- __String__ - Any string data
- __Int__ - Will return values as integers, truncates any float values
- __Float__ - Returns float values
- __Boolean__ - Returns `true` or `false`. Accepted input values are:
    + __True__ - `true, on, 1, yes, y`
    + __False__ - `false, off, 0, no, n`

## Api Params
- __apikey__ - _Required_ - Api key (use different keys for adding and getting) make sure a host is set if you are using it to get so no one else can use your key

### Adding data

#### Add data for single sensor
1. First way (Get)
    - Endpoint: `/api/v1/add/sensor`
    - __value__ - _Required_ - value you want to add to the database
    - __key__ - _Required_ - 6 char sensor key

2. Second way (Post), used of sending a large block of text
    - __key__ - _Required_ - 6 char sensor key
    -  JSON object to send: `{'value': <value>}`

#### Add data for multiple sensors using group key
- Endpoint: `/api/v1/add/group`
- __key__ - _Required_ - 6 char group key
- POST JSON object: *sensor_name is case-insensitive*
```
[
    {'sensor': '<sensor_key1>', 'value': <value1>},
    {'sensor': '<sensor_key2>', 'value': <value2>},
]
```
-OR-
```
[
    {'sensor_name': '<sensor_name1>', 'value': <value1>},
    {'sensor_name': '<sensor_name2>', 'value': <value2>},
]
```

### Getting data

#### Get list of groups
- Endpoint: `/api/v1/get/groups`
- Returns JSON object:
    + __data__ - _Type:  Array_ - Contains the list of groups, each object is as follows: 
        * __name__ - _Type: String_ - Group name
        * __key__ - _Type: String_ - Group key

#### Get data from sensor or group
- Endpoint: `/api/v1/get/sensor` or `/api/v1/get/group`
- __key__ - _Required_ - 6 char key
- __sort_by__ - _Optional_ - Default is `desc`, other option is `asc`
- __limit__ - _Optional_ - Default is to get all values. Must be an integer.
    + Advance __limit__ - _Optional_ - `<sensor_name>:<int>` - Will limit the results for `sensor_name` to the int passed with it. All other sensors in that group will get any data that is newr then the oldest item in the `sensor_name` passed in. This is useful to get an unknown number of logs that a group may have. Only works with `sort_by` as `desc` (which is the default)
- Returns a JSON object:
    + __data__ - _Type: Object or Array_ - Contains the requested data items. If called with a `sensor` endpoint, it will return an object with the data below. If called with a `group` endpoint, it will return an array with these objects in it. The list of sensors is not sorted, the values are.
        * __errors__ - _Type: Object_ - Holds any errors that the data may have returned with
            - __values__ - _Type: Array_ - An array of data point objects that returned errors on get
                + __error_msg__ - _Type: String_ - Message saying what went wrong
                + __timestamp__ - _Type: String_ - ISO timestamp of when the data point was added
                + __value__ - _Type: String_ - Original value of the data point
        * __sensor__ - _Type: Object_ - Info about the sensor that you are getting data for
            - __data_type__ - _Type: String_ - The Data type that the data is expected to be
            - __date_added__ - _Type: String_ - ISO timestamp of when the sensor was added
            - __key__ - _Type: String_ - Case-sensitive 6 char string to identify the sensor
            - __name__ - _Type: String_ - Name of the sensor to help identify it
        * __values__ - _Type: Array_ - List of data point objects sorted by `sort_by`, each object is as follows:
            - __timestamp__ - _Type: String_ - ISO timestamp of when the data point was added
            - __value__ - _Type: ?_ - The value converted to be the `sensor.data-type`
    + __message__ - _Type: String_ - Info text or an error message if `success` is false
    + __success__ - _Type: Boolean_ - `False` if there was a problem getting the data, see `messgae` for the error message

