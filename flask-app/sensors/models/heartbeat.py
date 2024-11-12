from datetime import datetime

from sensors.models.abstractsensor import Sensor
from sensors.models.notifications import notify, PRIORITY
from db.dbmanager import DBManager

from config import HEARTBEAT_INTERVAL_MINS


class HeartbeatSensor(Sensor):
    calibration = None

    def __init__(self, postjson):
        super().__init__(postjson)


    def process(self):
        super().process()

        db = DBManager()
        last = db.read_heartbeat(self.name)
        db.close()

        # If it's none, that meant we've not got any info for this sensor.
        if last is None:
            notify("Heartbeat", f"First heartbeat for {self.name}!", PRIORITY.low)
            return

        now = datetime.strptime(self.timestamp, "%Y-%m-%d %H:%M:%S") 
        
        if (now - last).total_seconds() > HEARTBEAT_INTERVAL_MINS * 60:
            notify("Heartbeat Missed", f"Missed heartbeat from {self.name} at {self.timestamp}! Gap was {(now-last).seconds/60} mins!", PRIORITY.high)

    
    def post(self):
        db = DBManager()
        db.update_heartbeat(self.name, self.timestamp)
        db.close()
