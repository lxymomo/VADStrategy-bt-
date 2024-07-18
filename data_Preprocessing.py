import pandas as pd
from datetime import datetime
import os

def process_csv(file_path):
    # 读取CSV文件
    df = pd.read_csv(file_path)
    
    # 转换时间戳
    df['datetime'] = pd.to_datetime(df['time'], unit='s')
    df = df.set_index('datetime')
    
    # 只保留所需的列
    columns_to_keep = ['open', 'high', 'low', 'close']
    df = df[columns_to_keep]
    
    # 处理缺失值：使用前向填充，这通常适合时间序列数据
    df = df.fillna(method='ffill')
    
    # 如果仍有缺失值，使用后向填充
    df = df.fillna(method='bfill')
    
    # 按时间排序
    df = df.sort_index()
    
    # 生成输出文件名
    output_file = file_path.replace('.csv', '_processed.csv')
    
    # 保存处理后的数据
    df.to_csv(output_file)
    
    print(f"Processed {file_path} and saved to {output_file}")

def main():
    file_names = ['BATS_QQQ, 5.csv', 'BATS_QQQ, 15.csv', 'BATS_QQQ, 60.csv', 'BATS_QQQ, 240.csv']
    
    for file_name in file_names:
        if os.path.exists(file_name):
            process_csv(file_name)
        else:
            print(f"File not found: {file_name}")

if __name__ == "__main__":
    main()