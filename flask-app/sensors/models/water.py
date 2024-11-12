from datetime import datetime, timedelta

from sensors.models.abstractsensor import Sensor
from sensors.models.notifications import notify, PRIORITY

from db.dbmanager import DBManager

class WaterSensor(Sensor):
    calibration = None

    def __init__(self, data):
        super().__init__(data)


    def process(self):
        super().process()
        # print(self.data)
        # if self.data['value'] > 100:
        #     print("Caution! Water level is high!")
        #     notify("Water Sensor", "Caution! Water level is high!", PRIORITY.urgent)

        # print(self.data)

    def post(self):
        db = DBManager()
        for d, m in zip(self.data["depth"],self.data["millis"]):
            data_i = {
                "depth": d,
            }
            
            # Adding 500 ms, and replacing us with 0 rounds to nearest second
            timestamp = (datetime.strptime(self.timestamp, "%Y-%m-%d %H:%M:%S") + timedelta(milliseconds=m+500)).replace(microsecond=0).strftime("%Y-%m-%d %H:%M:%S")
            db.insert_reading(self.name, timestamp, data_i, self.netdata)
        db.close()