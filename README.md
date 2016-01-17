# Datalogging

This project is to provide a central database to store datapoints from sensors and/or scripts.

There is a web interface that you can create api keys so you can add data to the sites database by going to a url with the correct arguments.

The data is not displayed anywhere on the site, but you can use another api key that is linked to a host for security to pull your sensor data from the database and display it anywhere you like.


### Usage
* Config file is optional  
`python3 app.py <configfile>`


### Default config file
Config file is yaml syntax  
```
db_uri: sqlite:///datalogger.sqlite
debug: false
host: 0.0.0.0
port: 5000
secret_key: SECRET_KEY
```
