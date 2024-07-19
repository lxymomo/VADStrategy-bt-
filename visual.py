import pandas as pd
import holoviews as hv
import panel as pn
from bokeh.models import HoverTool, WheelZoomTool
import hvplot.pandas
from holoviews import opts

# 设置 HoloViews 扩展
hv.extension('bokeh')

# 读取数据
try:
    data = pd.read_csv('results/BATS_QQQ, 5_minute_returns.csv', parse_dates=['time'], index_col='time')
    trades = pd.read_csv('results/BATS_QQQ, 5_completed_trades.csv', parse_dates=['buy_date', 'sell_date'])
except FileNotFoundError as e:
    print(f"Error: File not found. {e}")
    exit()
except ValueError as e:
    print(f"Error reading files: {e}")
    exit()

# 打印数据列名，用于调试
print("Data columns:", data.columns)
print("Trades columns:", trades.columns)

# 创建买入和卖出信号
buy_signals = trades[['buy_date', 'buy_price']].rename(columns={'buy_date': 'time', 'buy_price': 'price'})
buy_signals['type'] = 'BUY'
sell_signals = trades[['sell_date', 'sell_price']].rename(columns={'sell_date': 'time', 'sell_price': 'price'})
sell_signals['type'] = 'SELL'

# 合并买入和卖出信号
all_signals = pd.concat([buy_signals, sell_signals]).sort_values('time')

# 计算移动平均线
data['MA20'] = data['close'].rolling(window=20).mean()
data['MA50'] = data['close'].rolling(window=50).mean()

# 定义图表创建函数
def create_chart(data, all_signals):
    # 主 OHLC 图表
    ohlc = data.hvplot.ohlc(y=['open', 'high', 'low', 'close'], width=1000, height=400, xlabel='Time', ylabel='Price')
    
    # 移动平均线
    ma20 = data.hvplot.line(y='MA20', color='blue', line_dash='dashed', label='MA20')
    ma50 = data.hvplot.line(y='MA50', color='red', line_dash='dotted', label='MA50')
    
    # 买卖信号
    buy_scatter = all_signals[all_signals['type'] == 'BUY'].hvplot.scatter(
        x='time', y='price', color='green', marker='^', size=10, label='Buy'
    )
    sell_scatter = all_signals[all_signals['type'] == 'SELL'].hvplot.scatter(
        x='time', y='price', color='red', marker='v', size=10, label='Sell'
    )
    
    # 组合图表
    combined = (ohlc * ma20 * ma50 * buy_scatter * sell_scatter)
    
    # 添加悬停工具
    hover = HoverTool(tooltips=[
        ('Time', '@time{%F %H:%M}'),
        ('Open', '@open{0.00}'),
        ('High', '@high{0.00}'),
        ('Low', '@low{0.00}'),
        ('Close', '@close{0.00}')
    ], formatters={'@time': 'datetime'})
    
    # 设置图表选项
    combined = combined.opts(
        title='Trading Strategy Visualization',
        width=1000,
        height=600,
        legend_position='top_left',
        show_grid=True,
        tools=[hover, WheelZoomTool(dimensions='width')]
    )
    
    # 如果存在 'Volume' 列，添加成交量图表
    if 'Volume' in data.columns:
        volume = data.hvplot.bar(y='Volume', width=1000, height=200, xlabel='Time', ylabel='Volume')
        return (combined + volume).cols(1)
    else:
        return combined

# 创建初始图表
initial_chart = create_chart(data, all_signals)

# 创建日期范围选择器
date_range = pn.widgets.DateRangeSlider(
    name='Date Range',
    start=data.index.min(),
    end=data.index.max(),
    value=(data.index.min(), data.index.max())
)

# 定义更新函数
@pn.depends(date_range.param.value)
def update_chart(date_range):
    start, end = date_range
    filtered_data = data.loc[start:end]
    filtered_signals = all_signals[(all_signals['time'] >= start) & (all_signals['time'] <= end)]
    return create_chart(filtered_data, filtered_signals)

# 创建仪表板
dashboard = pn.Column(
    pn.Row(date_range),
    pn.panel(update_chart, loading_indicator=True)
)

# 启动 Panel 服务器
pn.serve(dashboard, start=True)