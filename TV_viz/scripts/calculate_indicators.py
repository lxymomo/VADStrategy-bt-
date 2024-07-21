import pandas as pd
import os

def calculate_vwma(data, period):
    vwma = []
    for i in range(len(data)):
        if i < period - 1 or data['volume'][i] == 0:
            vwma.append(None)
        else:
            price_volume_sum = sum(data['close'][j] * data['volume'][j] for j in range(i - period + 1, i + 1))
            volume_sum = sum(data['volume'][j] for j in range(i - period + 1, i + 1))
            vwma.append(price_volume_sum / volume_sum)
    return vwma

def load_and_process_data(filepath):
    print(f"Current working directory: {os.getcwd()}")
    print(f"Attempting to load file from: {filepath}")
    data = pd.read_csv(filepath, parse_dates=['time'])
    data['vwma14'] = calculate_vwma(data, 14)
    return data

if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.realpath(__file__))
    data_path = os.path.join(script_dir, '../data/BATS_QQQ_5.csv')
    processed_data_path = os.path.join(script_dir, '../data/processed_data.csv')
    data = load_and_process_data(data_path)
    data.to_csv(processed_data_path, index=False)
