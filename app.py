import pandas as pd
import numpy as np
from flask import Flask, jsonify, send_from_directory

app = Flask(__name__)

def load_data(file_path):
    data = pd.read_csv(file_path)
    data['time'] = pd.to_datetime(data['time'], unit='ns')
    data.set_index('time', inplace=True)
    return data

def calculate_vwma(data, window=20):
    volume_sum = data['Volume'].rolling(window=window).sum()
    vwma = (data['close'] * data['Volume']).rolling(window=window).sum() / volume_sum
    return vwma

def calculate_indicators(data, vwma_window=20):
    data['VWMA'] = calculate_vwma(data, vwma_window)
    return data

# 加载和处理数据
data = load_data('BATS_QQQ, 5.csv')
data = calculate_indicators(data)

@app.route('/data')
def get_data():
    result = data.reset_index().to_dict(orient='records')
    for item in result:
        item['time'] = item['time'].isoformat()
    return jsonify(result)

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

if __name__ == '__main__':
    app.run(debug=True)