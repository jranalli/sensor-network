from flask import Flask, render_template, send_file
from db.routes import bp as db_bp
from sensors.routes import bp as sensors_bp
from dashboard.routes import bp as dashboard_bp

app = Flask(__name__)

app.register_blueprint(db_bp, 
                       url_prefix='/db')

app.register_blueprint(sensors_bp, 
                       url_prefix='/sensors')

app.register_blueprint(dashboard_bp, 
                       url_prefix='/dashboard')

@app.route('/')
def index():
    return render_template('base.html')

if __name__ == '__main__':
    app.run(debug=True, port=50000)