from flask import Blueprint, send_file, url_for, render_template, request, jsonify, redirect
import requests
import json
import plotly.express as px

import pandas as pd


from config import SERVER_IP

bp = Blueprint('dashboard', __name__, static_folder='static', template_folder='templates')


@bp.route('/', methods=['GET','POST'])
def index():
    if request.method == 'POST':
        # Get the data from the request
        category = request.json['category']
        # Redirect to the same route with the category as a query parameter
        return jsonify({'redirect_url': url_for('dashboard.index', category=category)})
    else:
        # This handles both the initial GET request and the redirected GET request
        category = request.args.get('category', None)

    sensors = requests.get(f"http://{SERVER_IP}/db/sensor_list").json()
    print(sensors)
    from db.dbmanager import DBManager
    db = DBManager()
    data = db.get_categories()
    df = pd.DataFrame(data, columns=['sensor', 'timestamp', 'category'])
    categories = df['category'].unique()
    df.set_index('timestamp', inplace=True)

    fig_html = None
    if category is not None:
        df = df[df['category'] == category]
        df2 = pd.DataFrame(db.test_query(category=category), columns=['sensor', 'timestamp', 'data'])

    fig_html = None
    if category is not None:
        df = df[df['category'] == category]
        df2 = pd.DataFrame(db.test_query(category=category), columns=['sensor', 'timestamp', 'data'])

        # Align timestamps
        df2['timestamp'] = pd.to_datetime(df2['timestamp'])
        df2.sort_values('timestamp', inplace=True)
        df2['timestamp'] = df2['timestamp'].dt.round('min')  # Round to the nearest minute

        # Create a complete set of timestamps
        complete_timestamps = pd.DataFrame({'timestamp': pd.date_range(start=df2['timestamp'].min(), end=df2['timestamp'].max(), freq='min')})
        
        aligned_data = complete_timestamps.copy()
        for sensor in df2['sensor'].unique():
            sensor_data = df2[df2['sensor'] == sensor]
            sensor_data = pd.merge_asof(complete_timestamps, sensor_data, on='timestamp', direction='nearest')
            sensor_data.rename(columns={'data': f'{sensor}'}, inplace=True)
            aligned_data = pd.merge(aligned_data, sensor_data[['timestamp', f'{sensor}']], on='timestamp', how='left')
        aligned_data.set_index('timestamp', inplace=True)

        # Fill missing values
        # aligned_data.fillna(method='ffill', inplace=True)
        # aligned_data.fillna(method='bfill', inplace=True)
        
        plot_data = aligned_data.copy()
        fig = px.line(plot_data, x=plot_data.index, y=plot_data.columns)
        fig_html = fig.to_html()
    
    return render_template("dashboard/index.html", sensors=sensors, categories=categories, data=plot_data.to_html(), selected_category=category, plot=fig_html)

    
    # Consider flatpickr for date selection
    # https://flatpickr.js.org/


    # This is getting really messy, I think I need to have this happen client side, with filtering of the display rather than re-requests to the server

    


# This would let me request the data from the server and return it to the client, but I'd need to handle the way to manage timestamps
@bp.route('/observations/<sensor_id>')
def observations(sensor_id):
    # Fetch observations for the given sensor_id
    observations = requests.get(f"http://{SERVER_IP}/db/observations/{sensor_id}").json()
    # Render a template with the observations data
    return render_template("dashboard/observations.html", observations=observations, sensor_id=sensor_id)