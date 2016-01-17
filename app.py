import os
import sys
import yaml
import uuid
import datetime
from hashids import Hashids
from flask import Flask, request, flash, url_for, redirect, render_template, abort, g
from flask.ext.sqlalchemy import SQLAlchemy
from flask.ext.login import LoginManager
from flask.ext.login import login_user, logout_user, current_user, login_required
from passlib.hash import sha256_crypt


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
db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)

login_manager.login_view = 'login'


#######################
# Key generators
#######################
def generate_api_key():
    return str(uuid.uuid4())


def generate_sensor_key(sensor_id):
    hashids = Hashids(salt='Sensor salt xyz', min_length=6)
    return hashids.encode(sensor_id)


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
    apikeys = db.relationship('ApiKey', backref='user', lazy='dynamic')
    sensor_keys = db.relationship('Sensor', backref='user', lazy='dynamic')

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
    host = db.Column(db.String)
    key = db.Column(db.String(36), default=generate_api_key, unique=True)
    date_added = db.Column(db.DateTime, default=datetime.datetime.now)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))

    def __init__(self, name, host):
        self.name = name
        self.host = host


class Sensor(db.Model):
    __tablename__ = 'sesors'
    id = db.Column('id', db.Integer, primary_key=True)
    name = db.Column(db.String(60))
    data_type = db.Column(db.String(16))
    key = db.Column(db.String(36), unique=True)
    date_added = db.Column(db.DateTime, default=datetime.datetime.now)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))

    def __init__(self, name, data_type):
        self.name = name
        self.data_type = data_type


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
                           apikeys=ApiKey.query.filter_by(user_id=g.user.id).order_by(ApiKey.date_added.desc()).all()
                           )


@app.route('/apikey/delete/<int:apikey_id>', methods=['GET'])
@login_required
def apikey_delete(apikey_id):
    ApiKey.query.filter_by(user_id=g.user.id).filter_by(id=apikey_id).delete()
    db.session.commit()
    flash("Deleted API Key")
    return redirect(url_for('apikeys'))


###
# Sensor Routes
###
@app.route('/sensors', methods=['GET', 'POST'])
@login_required
def sensors():
    if request.method == 'POST':
        if not request.form['name']:
            flash('Name is required', 'error')
        elif not request.form['data_type']:
            flash('Type is required', 'error')
        else:
            sensor = Sensor(request.form['name'], request.form['data_type'])
            sensor.user = g.user
            db.session.add(sensor)
            # Flush to get the id so it can be encoded
            db.session.flush()
            sensor.key = generate_sensor_key(sensor.id)
            db.session.commit()
            flash('Sensor was successfully created')
            return redirect(url_for('sensors'))

    return render_template('sensors.html',
                           sensors=Sensor.query.filter_by(user_id=g.user.id).order_by(Sensor.name.asc()).all()
                           )


@app.route('/sensor/delete/<int:sensor_id>', methods=['GET'])
@login_required
def sensor_delete(sensor_id):
    Sensor.query.filter_by(user_id=g.user.id).filter_by(id=sensor_id).delete()
    db.session.commit()
    flash("Deleted sensor")
    return redirect(url_for('sensors'))


#######################
# Utils
#######################
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
