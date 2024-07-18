import dash
from dash import dcc, html
from dash.dependencies import Input, Output, State
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import backtrader as bt
from datetime import datetime, timedelta

class VADStrategy(bt.Strategy):
    params = (
        ('k', 1.6),
        ('base_order_amount', 100000),
        ('DCAmultiplier', 1.5),
        ('max_dca_count', 3),
        ('profit_atr_multiplier', 1),
        ('loss_atr_multiplier', 1),
    )

    def __init__(self):
        self.vwma14 = bt.indicators.WeightedMovingAverage(self.data.close, period=14, subplot=False)
        self.atr = bt.indicators.ATR(self.data, period=14)
        
        self.long_signal = self.data.close < self.vwma14 - self.p.k * self.atr
        self.short_signal = self.data.close > self.vwma14 + self.p.k * self.atr
        
        self.order = None
        self.dca_count = 0
        self.last_buy_price = 0
        
        # Add these lines to track buy and sell dates
        self.buy_dates = []
        self.sell_dates = []

    def next(self):
        if self.order:
            return

        if not self.position:
            if self.long_signal:
                self.buy()
                self.dca_count = 1
                self.last_buy_price = self.data.close[0]
                self.buy_dates.append(self.data.datetime.date())  # 使用 .date() 方法
        
        elif self.position.size > 0:
            if self.long_signal and self.data.close < (self.last_buy_price - self.p.k * self.atr) and self.dca_count < self.p.max_dca_count:
                self.buy()
                self.dca_count += 1
                self.last_buy_price = self.data.close[0]
                self.buy_dates.append(self.data.datetime.date())  # 使用 .date() 方法
            
            total_profit = (self.data.close[0] - self.position.price) * self.position.size 
            if self.short_signal or total_profit >= self.position.size * self.atr[0] * self.p.profit_atr_multiplier or total_profit <= -self.position.size * self.atr[0] * self.p.loss_atr_multiplier:
                self.close()
                self.sell_dates.append(self.data.datetime.date())  # 使用 .date() 方法

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return

        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(f'BUY EXECUTED, Price: {order.executed.price:.2f}, Cost: {order.executed.value:.2f}, Comm: {order.executed.comm:.2f}')
            else:
                self.log(f'SELL EXECUTED, Price: {order.executed.price:.2f}, Cost: {order.executed.value:.2f}, Comm: {order.executed.comm:.2f}')
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log(f'Order Canceled/Margin/Rejected: {order.Status[order.status]}')

        self.order = None

    def log(self, txt, dt=None):
        dt = dt or self.datas[0].datetime.date(0)
        print(f'{dt.isoformat()} {txt}')
        
class VADSizer(bt.Sizer):
    params = (('base_order_amount', 100000),)

    def _getsizing(self, comminfo, cash, data, isbuy):
        if isbuy:
            return self.p.base_order_amount / data.close[0]
        return self.broker.getposition(data).size

def run_strategy(symbol, interval):
    cerebro = bt.Cerebro()

    try:
        filename = f'BATS_QQQ, {interval.replace("min", "")}_processed.csv'
        df = pd.read_csv(filename, parse_dates=['datetime'], index_col='datetime')
        
        # 设置固定的开始和结束日期
        start_date = df.index.min()
        end_date = df.index.max()
        
        data = bt.feeds.PandasData(dataname=df, fromdate=start_date, todate=end_date)

        cerebro.adddata(data)

        cerebro.addstrategy(VADStrategy)
        cerebro.addsizer(VADSizer)

        cerebro.broker.setcash(1000000)
        cerebro.broker.setcommission(commission=0.001)

        cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
        cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')

        results = cerebro.run()
        return results[0]
    
    except Exception as e:
        print(f"Error running strategy: {e}")
        import traceback
        traceback.print_exc()
        return None
    
def get_backtest_results(symbol, interval):
    strategy = run_strategy(symbol, interval)
    if strategy is None:
        return {
            'symbol': symbol,
            'portfolio_value': 0,
            'total_return': 0,
            'sharpe_ratio': 0,
            'max_drawdown': 0,
        }
    
    portfolio_value = strategy.broker.getvalue()
    returns = strategy.analyzers.returns.get_analysis()
    drawdown = strategy.analyzers.drawdown.get_analysis()
    
    return {
        'symbol': symbol,
        'portfolio_value': portfolio_value,
        'total_return': returns.get('rtot', 0),
        'sharpe_ratio': returns.get('sharpe', 0),
        'max_drawdown': drawdown['max'].get('drawdown', 0),
    }

app = dash.Dash(__name__)

app.layout = html.Div([
    html.H1('AIphaPilot'),
    html.Div([
        dcc.Dropdown(
            id='symbol-dropdown',
            options=[{'label': s, 'value': s} for s in ['QQQ', 'SPY', '000300']],
            value='QQQ',
            style={'width': '200px', 'display': 'inline-block', 'margin-right': '10px'}
        ),
        dcc.Dropdown(
            id='interval-dropdown',
            options=[{'label': i, 'value': i} for i in ['5min', '15min', '60min', '240min']],
            value='5min',
            style={'width': '200px', 'display': 'inline-block', 'margin-right': '10px'}
        ),
        dcc.Dropdown(
            id='timeframe-dropdown',
            options=[
                {'label': '1 Week', 'value': '1W'},
                {'label': '1 Month', 'value': '1M'},
                {'label': '3 Months', 'value': '3M'},
                {'label': '6 Months', 'value': '6M'},
                {'label': '1 Year', 'value': '1Y'},
                {'label': 'All', 'value': 'All'}
            ],
            value='All',
            style={'width': '200px', 'display': 'inline-block'}
        ),
    ]),
    dcc.Graph(id='price-chart', style={'height': '70vh'}),
    html.Div(id='performance-metrics')
])

@app.callback(
    [Output('price-chart', 'figure'),
     Output('performance-metrics', 'children')],
    [Input('symbol-dropdown', 'value'),
     Input('interval-dropdown', 'value'),
     Input('timeframe-dropdown', 'value')]
)

def update_chart(symbol, interval, timeframe):
    try:
        filename = f'BATS_QQQ, {interval.replace("min", "")}_processed.csv'
        df = pd.read_csv(filename, parse_dates=['datetime'], index_col='datetime')
        
        # 根据选择的timeframe过滤数据
        if timeframe != 'All':
            end_date = df.index.max()
            if timeframe == '1W':
                start_date = end_date - pd.Timedelta(days=7)
            elif timeframe == '1M':
                start_date = end_date - pd.Timedelta(days=30)
            elif timeframe == '3M':
                start_date = end_date - pd.Timedelta(days=90)
            elif timeframe == '6M':
                start_date = end_date - pd.Timedelta(days=180)
            elif timeframe == '1Y':
                start_date = end_date - pd.Timedelta(days=365)
            df = df.loc[start_date:]

        # 计算移动平均线
        df['MA20'] = df['close'].rolling(window=20).mean()
        df['MA50'] = df['close'].rolling(window=50).mean()

        # 运行策略获取买卖点
        cerebro = bt.Cerebro()
        data = bt.feeds.PandasData(dataname=df)
        cerebro.adddata(data)
        cerebro.addstrategy(VADStrategy)
        cerebro.addsizer(VADSizer)
        results = cerebro.run()

        strategy = results[0]
        buy_points = pd.to_datetime(strategy.buy_dates)
        sell_points = pd.to_datetime(strategy.sell_dates)

        # 创建主图和交易活动子图
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                            vertical_spacing=0.1, row_heights=[0.7, 0.3])

        # 添加蜡烛图
        fig.add_trace(go.Candlestick(
            x=df.index, open=df['open'], high=df['high'],
            low=df['low'], close=df['close'], name='Price'),
            row=1, col=1
        )

        # 添加移动平均线
        fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], name='MA20', line=dict(color='blue', width=1)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA50'], name='MA50', line=dict(color='red', width=1)), row=1, col=1)

        # 运行策略获取买卖点
        cerebro = bt.Cerebro()
        data = bt.feeds.PandasData(dataname=df)
        cerebro.adddata(data)
        cerebro.addstrategy(VADStrategy)
        cerebro.addsizer(VADSizer)
        results = cerebro.run()

        strategy = results[0]
        buy_points = pd.to_datetime(strategy.buy_dates)
        sell_points = pd.to_datetime(strategy.sell_dates)

        # 在主图上添加买卖点标记
        fig.add_trace(go.Scatter(
            x=buy_points, y=[df.loc[date, 'low'] if date in df.index else None for date in buy_points],
            mode='markers', name='Buy', marker=dict(symbol='triangle-up', size=8, color='green')
        ), row=1, col=1)

        fig.add_trace(go.Scatter(
            x=sell_points, y=[df.loc[date, 'high'] if date in df.index else None for date in sell_points],
            mode='markers', name='Sell', marker=dict(symbol='triangle-down', size=8, color='red')
        ), row=1, col=1)

        # 在子图上显示交易活动
        trade_activity = pd.Series(1, index=buy_points).append(pd.Series(-1, index=sell_points)).sort_index()
        fig.add_trace(go.Bar(
            x=trade_activity.index, y=trade_activity.values,
            name='Trade Activity', marker_color=['green' if v == 1 else 'red' for v in trade_activity.values]
        ), row=2, col=1)

        # 更新布局
        fig.update_layout(
            title=f"{symbol} Chart ({interval})",
            xaxis_title="Date",
            yaxis_title="Price",
            xaxis_rangeslider_visible=False,
            height=800,  # 增加图表高度以容纳子图
            hovermode="x unified"
        )

        # 添加范围选择器
        fig.update_xaxes(
            rangeslider_visible=False,
            rangeselector=dict(
                buttons=list([
                    dict(count=1, label="1m", step="month", stepmode="backward"),
                    dict(count=3, label="3m", step="month", stepmode="backward"),
                    dict(count=6, label="6m", step="month", stepmode="backward"),
                    dict(count=1, label="YTD", step="year", stepmode="todate"),
                    dict(count=1, label="1y", step="year", stepmode="backward"),
                    dict(step="all")
                ])
            )
        )

        # 获取回测结果
        backtest_results = get_backtest_results(symbol, interval)

        performance_metrics = [
            html.P(f"Portfolio Value: ${backtest_results['portfolio_value']:.2f}"),
            html.P(f"Total Return: {backtest_results['total_return']:.2%}"),
            html.P(f"Sharpe Ratio: {backtest_results['sharpe_ratio']:.2f}"),
            html.P(f"Max Drawdown: {backtest_results['max_drawdown']:.2%}")
        ]

        return fig, performance_metrics

    except Exception as e:
        print(f"Error updating chart: {e}")
        import traceback
        traceback.print_exc()
        return go.Figure(), html.P("Error loading data")

if __name__ == '__main__':
    app.run_server(debug=True)