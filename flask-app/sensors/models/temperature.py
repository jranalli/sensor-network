from sensors.models.abstractsensor import Sensor
from sensors.models.notifications import notify, PRIORITY

class TemperatureHumiditySensor(Sensor):
    calibration = None

    def __init__(self, postjson):
        super().__init__(postjson)


    def process(self):
        super().process()

        # Test notification, send the latest value at 6PM each day.
        if " 18:00" in self.timestamp:
            notify("Temperature Reading", f"At {self.timestamp} from {self.name}: \nTemperature: {self.data['temperature']}\nHumidity: {self.data['humidity']}!", PRIORITY.low)
    
