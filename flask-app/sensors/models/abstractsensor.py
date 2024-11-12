from db.dbmanager import DBManager

class Sensor():
    
    def __init__(self, postjson):
        self.postjson = postjson

    def get_calibration(self):
        db = DBManager()
        cal = db.get_calibration(self.name)
        db.close()
        return cal

    def process(self):
        self.name = self.postjson['name']
        self.type = self.postjson['type']
        self.timestamp = self.postjson['reading']['timestamp']
        self.data = self.postjson['reading']['data']
        try:
            self.netdata = self.postjson['netdata']
        except KeyError:
            self.netdata = None
        
        cal = self.get_calibration()
        if cal is None or cal == {}:
            self.calibration = None
        else:
            self.calibration = cal

    def post(self):
        db = DBManager()
        db.insert_reading(self.name, self.timestamp, self.data, self.netdata)
        db.close()