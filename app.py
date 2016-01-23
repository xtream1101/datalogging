import os
import sys
import yaml
import uuid
import datetime
from functools import wraps
from hashids import Hashids
from passlib.hash import sha256_crypt
from flask import Flask, request, flash, url_for, redirect, render_template, g
from flask.ext.sqlalchemy import SQLAlchemy
from flask.ext.restful import Resource, Api, abort
from flask.ext.login import LoginManager
from flask.ext.login import login_user, logout_user, current_user, login_required


#######################
# Setup / Configuration
#######################
# Set timezone to UTC
os.environ['TZ'] = 'UTC'

config = {'db_uri': 'sqlite:///datalogger.sqlite',
          'debug': False,
          'host': '0.0.0.0',
          'port': 5000,
          'secret_key': 'SECRET_KEY'
          }

if len(sys.argv) >= 2:
    if not os.path.isfile(sys.argv[1]):
        print(sys.argv[1], "cannot be found")
        sys.exit(0)
    with open(sys.argv[1], 'r') as stream:
        config.update(yaml.load(stream))

app = Flask(__name__)
app.config['SECRET_KEY'] = config['secret_key']
app.config['SQLALCHEMY_DATABASE_URI'] = config['db_uri']
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

api = Api(app, prefix='/api/v1')
db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)

login_manager.login_view = 'login'


#######################
# Key generators
#######################
def generate_api_key():
    return str(uuid.uuid4())


def generate_key(id, salt, size=6):
    hashids = Hashids(salt=salt, min_length=size)
    return hashids.encode(id)


#######################
# Database Models
#######################
class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(32))
    last_name = db.Column(db.String(32))
    password = db.Column(db.String(255))
    email = db.Column(db.String(50), unique=True, index=True)
    registered_on = db.Column(db.DateTime, default=datetime.datetime.now)
    apikeys = db.relationship('ApiKey', backref='user', cascade='all, delete', lazy='dynamic')
    sensors = db.relationship('Sensor', backref='user', cascade='all, delete', lazy='dynamic')
    groups = db.relationship('Group', backref='user', lazy='dynamic')

    def __init__(self, first_name, last_name, password, email):
        self.first_name = first_name
        self.last_name = last_name
        self.set_password(password)
        self.email = email

    def set_password(self, password):
        self.password = self.encrypt_password(password)

    def encrypt_password(self, password):
        return sha256_crypt.encrypt(password)

    def verify_password(self, password):
        return sha256_crypt.verify(password, self.password)

    def is_authenticated(self):
        return True

    def is_active(self):
        return True

    def is_anonymous(self):
        return False

    def get_id(self):
        return str(self.id)

    def __repr__(self):
        return '<emal %r>' % (self.email)


class ApiKey(db.Model):
    __tablename__ = 'apikeys'
    id = db.Column('id', db.Integer, primary_key=True)
    name = db.Column(db.String(60))
    host = db.Column(db.String(255))
    key = db.Column(db.String(36), default=generate_api_key, unique=True)
    date_added = db.Column(db.DateTime, default=datetime.datetime.now)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))

    def __init__(self, name, host):
        self.name = name
        self.host = host


class Sensor(db.Model):
    __tablename__ = 'sensors'
    id = db.Column('id', db.Integer, primary_key=True)
    name = db.Column(db.String(60))
    data_type = db.Column(db.String(16))
    key = db.Column(db.String(36), unique=True)
    date_added = db.Column(db.DateTime, default=datetime.datetime.now)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    group_id = db.Column(db.Integer, db.ForeignKey('groups.id'))
    sensor_data = db.relationship('SensorData', backref='sensor', cascade='all, delete', lazy='dynamic')

    def __init__(self, name, data_type):
        self.name = name
        self.data_type = data_type


class SensorData(db.Model):
    __tablename__ = 'sensor_data'
    id = db.Column('id', db.Integer, primary_key=True)
    value = db.Column(db.String(128))
    date_added = db.Column(db.DateTime, default=datetime.datetime.now)
    sensor_id = db.Column(db.Integer, db.ForeignKey('sensors.id'))

    def __init__(self, value):
        self.value = str(value)


class Group(db.Model):
    __tablename__ = 'groups'
    id = db.Column('id', db.Integer, primary_key=True)
    name = db.Column(db.String(32))
    key = db.Column(db.String(36), unique=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    sensor = db.relationship('Sensor', backref='group', lazy='dynamic')

    def __init__(self, name):
        self.name = name


#######################
# Webserver Routes
#######################
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'GET':
        return render_template('register.html')

    first_name = request.form['firstname']
    last_name = request.form['lastname']
    email = request.form['email']
    password = request.form['password']

    user = User.query.filter_by(email=email)
    if user.count() == 0:
        user = User(first_name, last_name, password, email)
        db.session.add(user)
        db.session.commit()
        flash('You have registered the email {0}. Please login'.format(email))
        return redirect(url_for('login'))
    else:
        flash('The mail {0} is already in use. Please try a new email.'.format(email))
        return redirect(url_for('register'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')

    email = request.form['email']
    password = request.form['password']
    remember_me = False
    if 'remember_me' in request.form:
        remember_me = True
    registered_user = User.query.filter_by(email=email).first()

    if registered_user is None:
        flash('Invalid email/password', 'error')
        return redirect(url_for('login'))

    if not registered_user.verify_password(password):
        flash('Invalid email/password', 'error')
        return redirect(url_for('login'))

    login_user(registered_user, remember=remember_me)
    flash('Logged in successfully')
    return redirect(request.args.get('next') or url_for('index'))


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))


###
# Api Key Routes
###
@app.route('/apikeys', methods=['GET', 'POST'])
@login_required
def apikeys():
    if request.method == 'POST':
        if not request.form['name']:
            flash('Name is required', 'error')
        else:
            apikey = ApiKey(request.form['name'], request.form['host'])
            apikey.user = g.user
            db.session.add(apikey)
            db.session.commit()
            flash('Api key was successfully created')
            return redirect(url_for('apikeys'))

    return render_template('apikeys.html',
                           apikeys=ApiKey.query.filter_by(user_id=g.user.id).all()
                           )


@app.route('/apikey/delete/<int:apikey_id>', methods=['GET'])
@login_required
def apikey_delete(apikey_id):
    api_key = ApiKey.query.filter_by(user_id=g.user.id).filter_by(id=apikey_id).scalar()
    db.session.delete(api_key)
    db.session.commit()
    flash("Deleted API key " + api_key.name)
    return redirect(url_for('apikeys'))


###
# Sensor Routes
###
@app.route('/sensors', methods=['GET', 'POST'])
@login_required
def sensors():
    if request.method == 'POST':
        name = request.form['name'].strip()
        data_type = request.form['data_type'].strip()
        group = request.form['group'].strip()
        if not name:
            flash('Name is required', 'error')
        elif not data_type:
            flash('Type is required', 'error')
        else:
            sensor = Sensor(name, data_type)
            sensor.user = g.user
            # If a group is selected, add it to sensors
            if group != "":
                sensor.group = Group.query.filter_by(id=int(group)).scalar()

            db.session.add(sensor)
            # Flush to get the id so it can be encoded
            db.session.flush()
            sensor.key = generate_key(sensor.id, 'Sensor salt xyz')
            db.session.commit()
            flash('Sensor {} was successfully created'.format(sensor.name))
            return redirect(url_for('sensors'))

    return render_template('sensors.html',
                           sensors=Sensor.query.filter_by(user_id=g.user.id).all(),
                           groups=Group.query.filter_by(user_id=g.user.id).order_by(Group.name.asc()).all()
                           )


@app.route('/sensor/delete/<int:sensor_id>', methods=['GET'])
@login_required
def sensor_delete(sensor_id):
    sensor = Sensor.query.filter_by(user_id=g.user.id).filter_by(id=sensor_id).scalar()
    db.session.delete(sensor)
    db.session.commit()
    flash("Deleted sensor " + sensor.name)
    return redirect(url_for('sensors'))


###
# Group Routes
###
@app.route('/groups', methods=['GET', 'POST'])
@login_required
def groups():
    if request.method == 'POST':
        name = request.form['name'].strip()
        if not name:
            flash('Name is required', 'error')
        else:
            # Check if group name for user already exists
            is_group = Group.query.filter_by(user_id=g.user.id).filter_by(name=name).scalar()
            if is_group is not None:
                flash('Group with name {} already exists'.format(name), 'error')
            else:
                group = Group(name)
                group.user = g.user
                db.session.add(group)
                # Flush to get the id so it can be encoded
                db.session.flush()
                group.key = generate_key(group.id, 'Group salt abc')
                db.session.commit()
                flash('Group {} was successfully created'.format(group.name))
                return redirect(url_for('groups'))

    return render_template('groups.html',
                           groups=Group.query.filter_by(user_id=g.user.id).all()
                           )


@app.route('/group/delete/<int:group_id>', methods=['GET'])
@login_required
def group_delete(group_id):
    group = Group.query.filter_by(user_id=g.user.id).filter_by(id=group_id).scalar()
    db.session.delete(group)
    db.session.commit()
    flash("Deleted group {}".format(group.name))
    return redirect(url_for('groups'))


#######################
# API Method Decorators
#######################
def authenticate_api(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            # Get apikey and check it against the database
            apikey = request.args['apikey']
            found_key = ApiKey.query.filter_by(key=apikey).scalar()
            if found_key is not None:
                # If valid, return
                return func(*args, **kwargs)
            # If invalid, abort
            abort(401)
        except KeyError:
            # If apikey is not even passed
            abort(401)
    return wrapper


def validate_api_sensor(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        rdata = {'success': False,
                 'message': ""
                 }
        try:
            user_id = None
            api_key = request.args['apikey']
            if 'sensor' in request.args:
                sensor_key = request.args['sensor']
                # Check that the apikey has acccess to the sensor
                user_id = Sensor.query.filter_by(key=sensor_key).scalar().user_id
            elif 'group' in request.args:
                group_key = request.args['group']
                # Check that the apikey has acccess to the group
                user_id = Group.query.filter_by(key=group_key).scalar().user_id
            else:
                rdata['message'] = "Missing sensor/group key"
                return rdata

            key_user_id = ApiKey.query.filter_by(key=api_key).scalar().user_id
            if key_user_id == user_id:
                # The api key and sensor/group both belong to the same user
                return func(*args, **kwargs)
            else:
                rdata['message'] = "Invalid sensor/group key"
        except AttributeError:
            rdata['message'] = "Invalid sensor/group key"
        except Exception as e:
            print(str(e))
            rdata['message'] = "Oops, somthing went wrong"

        return rdata
    return wrapper


#######################
# API Endpoints
#######################
class APIAddData(Resource):
    method_decorators = [validate_api_sensor, authenticate_api]

    def get(self):
        rdata = {'success': False,
                 'message': ""
                 }
        try:
            sensor_key = request.args['sensor']
            value = request.args['value']
            # Add sensor data to db
            sensor = Sensor.query.filter_by(key=sensor_key).scalar()
            sensor_data = SensorData(value)
            sensor_data.sensor = sensor

            db.session.add(sensor_data)
            db.session.commit()
            rdata['success'] = True
        except KeyError:
            # sensor key is checked with `validate_api_sensor`
            rdata['message'] = "You are missing the value"
        except Exception as e:
            print(str(e))
            rdata['message'] = "Oops, something went wrong"

        return rdata


class APIGetData(Resource):
    method_decorators = [validate_api_sensor, authenticate_api]

    def get(self):
        rdata = {'success': False,
                 'message': "",
                 'data': None,
                 }
        try:
            # Default sort_by
            sort_by = 'desc'
            if 'sort_by' in request.args:
                if request.args['sort_by'] == 'asc':
                    sort_by = 'asc'

            # Default limit
            limit = None
            if 'limit' in request.args:
                # Limit number of values that are returned per sensor
                try:
                    limit = abs(int(request.args['limit']))
                except:
                    rdata['message'] = "Invalid limit: {}".format(request.args['limit'])
                    return rdata

            if 'sensor' in request.args:
                # Requesting a single sensor
                sensor_key = request.args['sensor']
                rdata['data'] = get_sensor_data(sensor_key, limit=limit, sort_by=sort_by)
                rdata['success'] = True
            elif 'group' in request.args:
                # Requesting all sensors in a group
                group_key = request.args['group']
                group = Group.query.filter_by(key=group_key).scalar()
                group_sensors = Sensor.query.filter_by(group=group).all()
                rdata['data'] = []
                for sensor in group_sensors:
                    rdata['data'].append(get_sensor_data(sensor.key, limit=limit, sort_by=sort_by))

                rdata['success'] = True
            else:
                rdata['message'] = "Must pass in a `group` or `sensor` key"
        except Exception as e:
            print(str(e))
            rdata['message'] = "Oops, something went wrong"

        return rdata


api.add_resource(APIAddData, '/add')
api.add_resource(APIGetData, '/get')


#######################
# API Utils
#######################
def get_sensor_data(sensor_key, limit=None, sort_by='desc'):
    data = {}
    data['errors'] = {}

    # Get sensor to find what data type the values are
    sensor = Sensor.query.filter_by(key=sensor_key).scalar()
    # Get all of the data for that sensor
    if sort_by == 'asc':
        sensor_data = SensorData.query.filter_by(sensor=sensor).order_by(SensorData.date_added.asc()).limit(limit)
    else:
        sensor_data = SensorData.query.filter_by(sensor=sensor).order_by(SensorData.date_added.desc()).limit(limit)

    data['sensor'] = {'name': sensor.name,
                      'date_added': datetime_to_str(sensor.date_added),
                      'key': sensor.key,
                      'group': sensor.group.name,
                      'data_type': sensor.data_type
                      }

    data['values'], data['errors']['values'] = get_value_list(sensor_data, sensor.data_type)

    return data


#######################
# App Utils
#######################
def datetime_to_str(timestamp):
    # The script is set to use UTC, so all times are in UTC
    return timestamp.isoformat() + "+00:00"


def convert_value(data_type):
    def default(value):
        # Just return as a string
        return value

    def to_int(value):
        try:
            # First try to convert string -> int
            return int(value)
        except ValueError:
            try:
                # Next try and convert string -> float -> int
                return int(float(value))
            except ValueError:
                # Give up and just give back the string
                return None

    def to_float(value):
        try:
            return float(value)
        except ValueError:
            # Give up and just give back the string
            return None

    def to_boolean(value):
        true_values  = ['true',  'on',  '1', 'yes', 'y']
        false_values = ['false', 'off', '0', 'no',  'n']
        if value.lower() in true_values:
            return True
        elif value.lower() in false_values:
            return False
        else:
            return None

    if data_type == "int":
        return to_int
    elif data_type == "float":
        return to_float
    elif data_type == "boolean":
        return to_boolean

    # By default convert to string
    return default


def get_value_list(values, data_type):
    """
    :returns: list of valid data points, list of failed data points
    """
    data_list = []
    data_errors = []
    convert = convert_value(data_type)
    for data in values:
        converted_value = convert(data.value)
        if converted_value is not None:
            data_list.append({'timestamp': datetime_to_str(data.date_added),
                              'value': converted_value
                              })
        else:
            data_errors.append({'timestamp': datetime_to_str(data.date_added),
                                'value': data.value,
                                'error_msg': "Could not convert data point to " + data_type
                                })
    return data_list, data_errors


@login_manager.user_loader
def load_user(id):
    return User.query.get(int(id))


@app.before_request
def before_request():
    g.user = current_user


if __name__ == '__main__':
    db.create_all()
    app.run(debug=config['debug'],
            host=config['host'],
            port=int(config['port'])
            )
