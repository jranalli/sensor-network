from flask import Blueprint, request, jsonify
import requests
from db.dbmanager import DBManager
from config import SERVER_IP

bp = Blueprint('db', __name__)

@bp.route('/insert', methods=['POST'])
def insert():
    if request.method == 'POST':
        # Get the data from the request
        name = request.json['sensor']
        timestamp = request.json['timestamp']
        dict_data = request.json['data']
        try:
            netdata = request.json['netdata']
        except KeyError:
            netdata = None

        # Connect to the database
        db = DBManager(host=SERVER_IP)
        db.insert_reading(name, timestamp, dict_data, netdata)
        db.close()
        
        # Redirect to the index page
        return jsonify(dict_data)


@bp.route('/temperatures')
def get_data():
    db = DBManager(host=SERVER_IP)
    data = db.read_temperatures()
    db.close()
    return jsonify(data)
    
   
@bp.route('/initialize')
def init_db():
    db = DBManager(host=SERVER_IP)
    db.reinitialize_db()
    db.close()
    return jsonify({'status': 'ok'})

@bp.route('/sensor_list')
def get_sensor_list():
    db = DBManager(host=SERVER_IP)
    data = db.get_sensor_list()
    db.close()
    return jsonify(data)