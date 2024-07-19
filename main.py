import backtrader as bt
import config
import pandas as pd
import os
import pydoc
from texttable import Texttable
from strategy import *
from datetime import datetime

# 确保结果目录存在
output_dir = 'results'
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

def get_csv_date_range(data_file):
    df = pd.read_csv(data_file)
    if 'time' in df.columns:
        df['time'] = pd.to_datetime(df['time'])
        return df['time'].min().date(), df['time'].max().date()
    else:
        raise ValueError("CSV file does not contain 'time' column")

def add_data_and_run_strategy(strategy_class, data_file, name):
    cerebro = bt.Cerebro()

    # 获取CSV文件的日期范围
    csv_start_date, csv_end_date = get_csv_date_range(data_file)

    # 比较CSV日期范围和配置的回测日期范围
    config_start_date = datetime.strptime(config.backtest_params['start_date'], '%Y/%m/%d %H:%M').date()
    config_end_date = datetime.strptime(config.backtest_params['end_date'], '%Y/%m/%d %H:%M').date()

    start_date = max(csv_start_date, config_start_date)
    end_date = min(csv_end_date, config_end_date)

    data = bt.feeds.GenericCSVData(
        dataname=data_file,
        dtformat='%Y-%m-%d %H:%M:%S',
        timeframe=bt.TimeFrame.Minutes,
        datetime=0,
        open=1,
        high=2,
        low=3,
        close=4,
        volume=5,
        openinterest=-1,
        atr=6,  # 添加 ATR 列
        separator=',',
    )
    
    # 添加数据、策略
    cerebro.adddata(data, name=name)
    cerebro.addstrategy(strategy_class) 

    # 添加资金、佣金、滑点
    cerebro.broker.setcash(config.broker_params['initial_cash'])
    cerebro.broker.setcommission(commission=config.broker_params['commission_rate'])
    
    # 添加分析器
    cerebro.addanalyzer(bt.analyzers.TimeReturn, timeframe=bt.TimeFrame.Minutes, _name='timereturn')
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')

    # 运行回测
    results = cerebro.run()
    return results, start_date, end_date

def run_backtest():
    output = ""  # 用于存储所有输出
    last_start_date, last_end_date = None, None  # 初始化回测日期
    for name, data_file in config.data_files:
        output += f"\n{name} 分析结果:\n"

        # 运行策略
        VADStrategy_results, start_date, end_date = add_data_and_run_strategy(VADStrategy, data_file, name)
        VADStrategy_strat = VADStrategy_results[0]

        # 更新回测日期
        last_start_date, last_end_date = start_date, end_date

        # 获取分析结果
        returns_analyzer = VADStrategy_strat.analyzers.returns.get_analysis()
        sharpe_analyzer = VADStrategy_strat.analyzers.sharpe.get_analysis()
        drawdown_analyzer = VADStrategy_strat.analyzers.drawdown.get_analysis()

        total_return = returns_analyzer['rtot']
        annual_return = returns_analyzer['rnorm']
        sharpe_ratio = sharpe_analyzer['sharperatio']
        max_drawdown = drawdown_analyzer['max']['drawdown']

        # 输出每分钟的回测结果
        VAD_analysis = VADStrategy_strat.analyzers.timereturn.get_analysis()
        VAD_returns = pd.Series(list(VAD_analysis.values()), index=pd.to_datetime(list(VAD_analysis.keys()), format='%Y-%m-%d %H:%M:%S'))

        # 打印调试信息，确认返回值生成
        print("VAD_returns:")
        print(VAD_returns.head())

        VAD_returns_df = VAD_returns.reset_index()
        VAD_returns_df.columns = ['time', 'returns']
        
        # 确保包含 'close' 列
        original_data = pd.read_csv(data_file, parse_dates=['time'])

        # 打印调试信息，检查数据框
        print("Original Data:")
        print(original_data.head())
        print("VAD Returns DataFrame:")
        print(VAD_returns_df.head())
        
        merged_data = pd.merge(original_data, VAD_returns_df, on='time', how='left')

        # 打印合并后的数据框
        print("Merged Data:")
        print(merged_data.head())
        
        merged_data.to_csv(f'results/{name}_minute_returns.csv', index=False)

        output += f"回测时间：从 {start_date} 到 {end_date}\n"
        output += f'VADStrategy 初始本金为 {config.broker_params["initial_cash"]:.2f}\n'
        output += f'VADStrategy 最终本金为 {config.broker_params["initial_cash"] * (1 + total_return):0.2f}\n'
        
        table = Texttable()
        table.add_rows([
            ["分析项目", "VADStrategy"],
            ["总收益率", f"{total_return * 100:.2f}%"],
            ["年化收益率", f"{annual_return * 100:.2f}%"],
            ["最大回撤", f"{max_drawdown:.2f}%"],
            ["夏普比率", f"{sharpe_ratio:.2f}" if sharpe_ratio is not None else "N/A"],
        ])

        output += table.draw() + "\n\n"

        # 保存完整的交易记录
        VADStrategy_strat.save_completed_trades_to_csv(f'results/{name}_completed_trades.csv')
        
        # 读取并分析完整的交易记录
        try:
            completed_trades_df = pd.read_csv(f'results/{name}_completed_trades.csv')
            avg_profit = completed_trades_df['profit'].mean()
            avg_profit_percentage = completed_trades_df['profit_percentage'].mean()

            output += f"平均每笔交易利润: {avg_profit:.2f}\n"
            output += f"平均每笔交易利润百分比: {avg_profit_percentage:.2f}%\n"

            # 获取性能指标
            performance_metrics = VADStrategy_strat.calculate_performance_metrics()
            
            output += f"累积利润: {performance_metrics['cumulative profit']:.2f}\n"
            output += f"总交易次数: {performance_metrics['total_trades']}\n"
            output += f"盈利交易次数: {performance_metrics['winning_trades']}\n"
            output += f"亏损交易次数: {performance_metrics['losing_trades']}\n"
            output += f"胜率: {performance_metrics['win_rate']:.2%}\n"

        except FileNotFoundError:
            print(f"警告: 未找到文件 'results/{name}_completed_trades.csv'")
        except pd.errors.EmptyDataError:
            print(f"警告: 文件 'results/{name}_completed_trades.csv' 是空的")

    # 使用分页器显示输出
    pydoc.pager(output)

if __name__ == '__main__':
    run_backtest()
