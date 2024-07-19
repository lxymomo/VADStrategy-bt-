import pandas as pd
import holoviews as hv
import hvplot.pandas
from bokeh.models import WheelZoomTool
from holoviews.operation.datashader import datashade
import panel as pn

hv.extension('bokeh')

# 尝试读取回测结果
try:
    data = pd.read_csv('results/BATS_QQQ_5_minute_returns.csv', parse_dates=['time'], index_col='time')
except ValueError as e:
    print(f"Error reading results file: {e}")
    data = None

# 尝试读取交易记录
try:
    trades = pd.read_csv('results/BATS_QQQ_5_trades.csv', parse_dates=['time'])
except ValueError as e:
    print(f"Error reading trades file: {e}")
    trades = None

if data is not None and trades is not None:
    # 将 returns 数据合并到交易记录中
    trades = pd.merge(trades, data[['returns']], left_on='time', right_index=True, how='left')
    
    # 确认合并后的数据
    print(trades.head())

    # 创建买卖点标记，并调整位置
    buy_signals = trades[trades['type'] == 'BUY']
    sell_signals = trades[trades['type'] == 'SELL']

    # 调整三角形标记位置，使其离candlestick更远
    buy_signals['price'] = buy_signals['price'] - 0.1
    sell_signals['price'] = sell_signals['price'] + 0.1

    buy_points = hv.Scatter(buy_signals, kdims=['time'], vdims=['price']).opts(color='green', marker='^', size=10)
    sell_points = hv.Scatter(sell_signals, kdims=['time'], vdims=['price']).opts(color='red', marker='v', size=10)
    
    # 在卖点标记上添加 returns 文本，并调整位置
    sell_returns = hv.Labels([(row.time, row.price, f"卖出，收益{row.returns:.4%}") for idx, row in sell_signals.iterrows()]).opts(text_color='red', text_font_size='8pt', text_align='left', text_baseline='top')

    # 合并图表
    combined_plot = (data.hvplot.ohlc(y=['open', 'high', 'low', 'close'], label='OHLC', width=1200, height=600) * 
                     buy_points * 
                     sell_points * 
                     sell_returns).opts(
        title='Price and Buy/Sell Signals with Returns',
        width=1200,
        height=600,
        hooks=[lambda plot, element: plot.state.add_tools(WheelZoomTool(dimensions="width"))  # 仅在x轴上缩放
        ]
    )

    # 启动Bokeh服务器以显示图表
    pn.serve(combined_plot, start=True)
else:
    print("Required data files are missing or incorrect.")
