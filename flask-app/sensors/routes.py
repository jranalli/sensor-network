from flask import Blueprint, send_file, url_for, render_template, request, jsonify

from sensors.models.abstractsensor import Sensor
from sensors.models.water import WaterSensor
from sensors.models.heartbeat import HeartbeatSensor
from sensors.models.temperature import TemperatureHumiditySensor as ths

bp = Blueprint('sensors', __name__)


managermap = {
    "water": WaterSensor,
    "temphum": ths,
    "heartbeat": HeartbeatSensor,
    "default": Sensor
}

# Sensor Reply Formats should be:
# { "name": <name>, 
#   "type": <type>, 
#   "reading": {
#                "timestamp": <value>, 
#                "data": {"field1": <value>, "field2": <value>}
#              }
#   "netdata": {
#                "ip": <value>, 
#                "mac": <value>
#              }
# }


@bp.route('/', methods=['POST'])
def index():
    postjson = request.get_json()

    if postjson["type"] in managermap:
        sensortype = postjson["type"]
    else:
        sensortype = "default"
    
    sensor = managermap[sensortype](postjson)
    sensor.process()
    sensor.post()

    return jsonify({'time': f"{postjson['reading']['timestamp']}",
                    'type': f"{postjson['type']}",
                    'name': f"{postjson['name']}"}), 200
