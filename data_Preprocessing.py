import pandas as pd
import os

def process_csv(file_path):
    # 从文件名中提取周期
    period = int(file_path.split(',')[-1].split('.')[0].strip())
    
    # 读取CSV文件
    df = pd.read_csv(file_path)
    
    # 检查 'time' 列是否存在，如果不存在，尝试使用第一列作为时间列
    if 'time' not in df.columns:
        df['time'] = df.iloc[:, 0]
    
    # 将 'time' 列转换为 datetime 对象
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df = df.set_index('time')
    
    # 只保留所需的列
    columns_to_keep = ['open', 'high', 'low', 'close', 'Volume', 'ATR']
    df = df[columns_to_keep]
    
    # 根据周期进行重采样和填充
    df = df.resample(f'{period}min').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'Volume': 'sum',
        'ATR': 'last'
    })
    
    # 使用前向填充处理缺失值
    df = df.ffill()
    
    # 如果仍有缺失值，使用后向填充
    df = df.bfill()
    
    # 重置索引，使 time 成为一个普通列
    df = df.reset_index()
    
    # 生成输出文件名
    output_file = os.path.join('data', os.path.basename(file_path))
    
    # 确保 data 文件夹存在
    os.makedirs('data', exist_ok=True)
    
    # 保存处理后的数据
    df.to_csv(output_file, index=False)
    
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