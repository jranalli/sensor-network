from typing import Any
import mysql.connector
import json

class DBManager:
    def __init__(self, database='databasedata', host="ip", user="user",
                     password="password"):
            """
            Initializes a new instance of the DBManager class.

            Args:
                database (str): The name of the database to connect to. Default is .
                host (str): The host address of the MySQL server. Default is .
                user (str): The username for the MySQL server. Default is .
                password (str): The password for the MySQL server. Default is .
            """
            self.connection = mysql.connector.connect(
                user=user,
                password=password,
                host=host,
                # name of the mysql service as set in the docker compose file
                database=database,
                auth_plugin='mysql_native_password'
            )
            self.cursor = self.connection.cursor()

    def __del__(self):
        """
        Clean up resources before the object is destroyed.
        """
        self.close()

    def reinitialize_db(self):
            """
            Reinitializes the database by dropping existing tables and creating new ones.

            This method drops the tables 'datavals', 'calibrations', 'observations', and 'sensors' if they exist,
            and then creates new tables with the same names and specified columns.
            """
            
            self.cursor.execute('DROP TABLE IF EXISTS datavals')
            self.cursor.execute('DROP TABLE IF EXISTS calibrations')
            self.cursor.execute('DROP TABLE IF EXISTS observations')
            self.cursor.execute('DROP TABLE IF EXISTS sensors')
            self.cursor.execute('DROP TABLE IF EXISTS heartbeats')


            self.cursor.execute('CREATE TABLE sensors ('
                                    'SID INT AUTO_INCREMENT PRIMARY KEY, '
                                    'Name VARCHAR(24), '
                                    'Location VARCHAR(36), '
                                    'Description VARCHAR(255), '
                                    'IP VARCHAR(255), '
                                    'MAC VARCHAR(255), '
                                    'UNIQUE(Name)'
                                ')'
                                )
            self.cursor.execute('CREATE TABLE calibrations ('
                                    'CID INT AUTO_INCREMENT PRIMARY KEY, '
                                    'SID INT, '
                                    'Timestamp TIMESTAMP, '
                                    'Calibration JSON, '
                                    'constraint fk_sid_cal foreign key(SID) references sensors(SID)'
                                ')'
                                )
            self.cursor.execute('CREATE TABLE observations ('
                                    'OID INT AUTO_INCREMENT PRIMARY KEY, '
                                    'SID INT, '
                                    'Timestamp TIMESTAMP, '
                                    'constraint fk_sid_obs foreign key(SID) references sensors(SID)'
                                ')'
                                )
            self.cursor.execute('CREATE TABLE datavals ('
                                    'VID INT AUTO_INCREMENT PRIMARY KEY, '
                                    'OID INT, '
                                    'Data DOUBLE PRECISION, '
                                    'Category VARCHAR(24), '
                                    'constraint fk_oid foreign key(OID) references observations(OID)'
                                ')'
                                )
            self.cursor.execute('CREATE TABLE heartbeats ('
                                    'HBID INT AUTO_INCREMENT PRIMARY KEY, '
                                    'SID INT, '
                                    'Timestamp TIMESTAMP, '
                                    'constraint fk_sid_hb foreign key(SID) references sensors(SID)'
                                ')'
                                )
            self.connection.commit()

    def close(self):
        """
        Closes the database connection.
        """
        self.connection.close()

    def query_db(self, name, start_timestamp=None, end_timestamp=None, category=None):
        """
        Query the database for data based on the given parameters.

        Args:
            name (str): The name of the sensor.
            start_timestamp (str, optional): The start timestamp for filtering the data. Defaults to None.
            end_timestamp (str, optional): The end timestamp for filtering the data. Defaults to None.
            category (str, optional): The category for filtering the data. Defaults to None.

        Returns:
            list: A list of data records matching the given parameters.
        """
        # First get the SID based on the sensor name
        self.cursor.execute('SELECT SID FROM sensors where Name = %s', [name])
        mysid = self.cursor.fetchone()   # Reads one row, which is still a tuple

        # Now select the all the observation ids for that sensor
        if start_timestamp is None or end_timestamp is None:
            self.cursor.execute('SELECT OID FROM observations where SID = %s', mysid)
        else:
            self.cursor.execute('SELECT OID FROM observations where SID = %s AND Timestamp BETWEEN %s AND %s', (mysid[0], start_timestamp, end_timestamp))
        myoids = tuple([val[0] for val in self.cursor])  # Parse through into a tuple

        # Now find all the datapoints corresponding to that list of OIDs
        n_formats = ','.join(['%s'] * len(myoids))  # Create a string of %s's separated by commas
        if category is None:
            self.cursor.execute(f'SELECT Data FROM datavals where OID in ({n_formats})', myoids)
        else:
            self.cursor.execute(f'SELECT Data FROM datavals where OID in ({n_formats}) AND Category = %s', (*myoids, category))
        blah = self.cursor.fetchall()

        # # An alternate format to combine the SID and OID search into one query
        # self.cursor.execute('SELECT Data from datavals t1 inner join observations t2 on t1.OID = t2.OID where t2.SID = %s', mysid)
        # blah2 = self.cursor.fetchall()
        # assert blah == blah2
        
        # Return records, this would need to be improved to return the data in a more sensible way.
        # Right now it would return data regardless of type.
        rec = []
        for c in blah:
            rec.append(str(c[0]))
        return rec
    
    def get_sensor_list(self):
            """
            Retrieves a list of all sensors in the database.

            Returns:
                list: A list of sensor names.
            """
            self.cursor.execute('SELECT Name FROM sensors')
            sens = self.cursor.fetchall()
            return [s[0] for s in sens]
    
    def get_observations(self, start_timestamp=None, end_timestamp=None):
            """
            Retrieves a list of all observations in the database.

            Args:
                start_timestamp (str, optional): The start timestamp for filtering the data. Defaults to None.
                end_timestamp (str, optional): The end timestamp for filtering the data. Defaults to None.

            Returns:
                list: A list of observation records.
            """
            # if start_timestamp is None or end_timestamp is None:
                # self.cursor.execute('SELECT * FROM observations')
            # else:
                # self.cursor.execute('SELECT * FROM observations WHERE Timestamp BETWEEN %s AND %s', (start_timestamp, end_timestamp))
            # join this selection on the sensors table to get the sensor name and datavals table to get the actual values
            self.cursor.execute('SELECT observations.Timestamp, datavals.Data, datavals.Category, sensors.Name FROM datavals JOIN observations ON datavals.OID = observations.OID JOIN sensors ON observations.SID = sensors.SID WHERE observations.Timestamp BETWEEN %s AND %s', (start_timestamp, end_timestamp))
            rec = self.cursor.fetchall()

            return rec

    def get_sensor_id(self, name, netdata=None, create_if_null=False):
            """
            Retrieves the sensor ID for the given sensor name from the database.

            Args:
                name (str): The name of the sensor.
                create_if_null (bool, optional): If True, creates a new sensor entry in the database if the sensor does not exist. Defaults to False.

            Returns:
                int or None: The sensor ID if the sensor exists, None if the sensor does not exist and create_if_null is False, or the newly created sensor ID if create_if_null is True.
            """
            self.cursor.execute('SELECT SID FROM sensors where Name = %s', [name])
            sens = self.cursor.fetchone()
            if sens is not None:
                mysid = sens[0]   # Reads one row, which is still a tuple
                return mysid
            else:
                if create_if_null:
                    if netdata is not None:
                        return self.init_sensor(name, ip=netdata['ip'], mac=netdata['mac'])        
                    else:
                        return self.init_sensor(name)        
                else:
                    return None
            
    def init_sensor(self, name, location=None, description=None, ip=None, mac=None):
            """
            Initializes a sensor in the database.

            Args:
                name (str): The name of the sensor.
                location (str, optional): The location of the sensor. Defaults to None.
                description (str, optional): The description of the sensor. Defaults to None.
                ip (str, optional): The IP address of the sensor. Defaults to None.
                mac (str, optional): The MAC address of the sensor. Defaults to None.

            Returns:
                int: The ID of the initialized sensor.
            """
            if location is None:
                location = 'Not Filled'
            if description is None:
                description = 'Not Filled'
            if ip is None:
                ip = 'Not Filled'
            if mac is None:
                mac = 'Not Filled'
            try:
                self.cursor.execute('INSERT INTO sensors (Name, Location, Description, IP, MAC) VALUES (%s, %s, %s, %s, %s);', (name, location, description, ip, mac))
                mysid = self.cursor.lastrowid
                self.connection.commit()
                self.set_calibration(mysid, '2024-01-01 12:00:00', '{}')
            except mysql.connector.errors.IntegrityError:
                print(f"Sensor {name} already exists, skipping...")
                mysid = self.get_sensor_id(name, create_if_null=False)
            return mysid

    def set_calibration(self, sid, timestamp, cal):
            """
            Sets the calibration for a sensor with the given SID.

            Parameters:
            - sid (int): The sensor ID.
            - timestamp (str): The timestamp of the calibration.
            - cal (dict): The calibration data.

            Raises:
            - ValueError: If the sensor does not exist.

            Returns:
            None
            """
            self.cursor.execute('SELECT * FROM calibrations where SID = %s', [sid])
            sens = self.cursor.fetchall()
            if len(sens) > 0:
                # check if the calibration has changed
                if cal == json.loads(sens[-1][3]):
                    # cal unchanged, don't do anything
                    self.connection.commit()
                    return
                else:
                    self.cursor.execute('INSERT INTO calibrations (SID, Timestamp, Calibration) VALUES (%s, %s, %s);', (sid, timestamp, json.dumps(cal)))
                # It exists, so update the calibration and timestamp
                # self.cursor.execute('UPDATE calibrations SET Timestamp = %s, Calibration = %s WHERE SID = %s;', (timestamp, json.dumps(cal), sid))
            else:
                # It doesn't exist, so initialize it
                try:
                    self.cursor.execute('INSERT INTO calibrations (SID, Timestamp, Calibration) VALUES (%s, %s, %s);', (sid, timestamp, json.dumps(cal)))
                except mysql.connector.errors.IntegrityError:
                    raise ValueError(f"Sensor {sid} does not exist, cannot set calibration.")
            self.connection.commit()

    def get_calibration(self, name):
            """
            Retrieves the calibration data for a given sensor name.

            Args:
                name (str): The name of the sensor.

            Returns:
                tuple: A tuple containing the timestamp and calibration data for the sensor.
                       If no calibration exists, returns None.
            """
            mysid = self.get_sensor_id(name, create_if_null=False)
            if mysid is not None:
                self.cursor.execute('SELECT Timestamp, Calibration FROM calibrations where SID = %s', [mysid])
                cal = self.cursor.fetchall()
                if len(cal) > 0:
                    cal = cal[-1]
                    cal = list(cal)
                    cal[1] = json.loads(cal[1])
                    return cal
                else:
                    # No calibration exists, so initialize it
                    self.set_calibration(mysid, '2024-01-01 12:00:00', '{}')
                    self.cursor.execute('SELECT Timestamp, Calibration FROM calibrations where SID = %s', [mysid])
                    return self.cursor.fetchone()
            else:
                return None

    def insert_reading(self, name, timestamp, data_dict, netdata=None):
            """
            Inserts a reading into the database.

            Args:
                name (str): The name of the sensor.
                timestamp (str): The timestamp of the reading.
                data_dict (dict): A dictionary containing the data values for the reading.
                netdata (dict): A dictionary containing the network data for the sensor. Defaults to None.

            Returns:
                None
            """
            
            mysid = self.get_sensor_id(name, netdata, create_if_null=True)
                            
            self.cursor.execute('INSERT INTO observations (SID, Timestamp) VALUES (%s, %s);', (mysid, timestamp))
            myoid = self.cursor.lastrowid

            # obs['data'] is a dictionary of {category: value}
            for cat, val in data_dict.items():
                self.cursor.execute('INSERT INTO datavals (OID, Data, Category) VALUES (%s, %s, %s);', (myoid, val, cat))
            self.connection.commit()

    def update_heartbeat(self, name, timestamp):
            """
            Inserts a heartbeat into the database.

            Args:
                name (str): The name of the sensor.
                timestamp (str): The timestamp of the heartbeat.
                data_dict (dict): A dictionary containing the data values for the heartbeat.

            Returns:
                None
            """
            mysid = self.get_sensor_id(name, create_if_null=True)
            # Update the value of the heartbeat with the latest timestamp
            self.cursor.execute('SELECT * FROM heartbeats where SID = %s', [mysid])
            sens = self.cursor.fetchall()
            if len(sens) > 0:
                # It exists, so update the timestamp
                self.cursor.execute('UPDATE heartbeats SET Timestamp = %s WHERE SID = %s;', (timestamp, mysid))
            else:
                # It doesn't exist, so initialize it
                self.cursor.execute('INSERT INTO heartbeats (SID, Timestamp) VALUES (%s, %s);', (mysid, timestamp))
            
            self.connection.commit()
    
    def read_heartbeat(self, name=None):
            """
            Reads all the heartbeat for a single sensor.

            Args:
                name (str, optional): The name of the sensor. Defaults to None.

            Returns:
                timestamp: The timestamp of the last post.
            """

            # Get just a single value that matches the name
            mysid = self.get_sensor_id(name, create_if_null=False)
            if mysid is None:
                return None
            else:
                self.cursor.execute('SELECT * FROM heartbeats where SID = %s', [mysid])
                
                # Extract the timestamp from the result and return it as a datetime (?)
                sens = self.cursor.fetchall()
                if len(sens) > 0:
                    return sens[-1][2]
                else:
                    return None
            
    def get_categories(self):
        query = """
            SELECT s.Name, o.Timestamp, d.Category
            FROM datavals d
            JOIN observations o ON d.OID = o.OID
            JOIN sensors s ON o.SID = s.SID
        """
        self.cursor.execute(query)
        results = self.cursor.fetchall()
        return results


    def test_query(self, category='depth'):
        # I want to develop a test query that will obtain all the data for a given measurement category

        query = """
            SELECT s.Name, o.Timestamp, d.Data
            FROM datavals d
            JOIN observations o ON d.OID = o.OID
            JOIN sensors s ON o.SID = s.SID
            WHERE d.Category = %s
        """
        self.cursor.execute(query, (category,))
        results = self.cursor.fetchall()
        return results

        