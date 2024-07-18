import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QLabel, QComboBox
from PyQt5.QtWebEngineWidgets import QWebEngineView
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import backtrader as bt
import pandas as pd
import plotly.graph_objects as go

class TradingViewLikeApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('TradingView-like App')
        self.setGeometry(100, 100, 1200, 800)

        main_widget = QWidget(self)
        main_layout = QHBoxLayout(main_widget)

        left_layout = QVBoxLayout()

        self.chart_widget = QWebEngineView()
        left_layout.addWidget(self.chart_widget, 2)

        self.performance_widget = PerformanceWidget()
        left_layout.addWidget(self.performance_widget, 1)

        self.interval_selector = QComboBox()
        self.interval_selector.addItems(['5min', '15min', '60min', '240min'])
        self.interval_selector.currentTextChanged.connect(self.update_chart)
        left_layout.addWidget(self.interval_selector)

        data_sources = QListWidget()
        data_sources.addItems(["QQQ", "SPY", "000300"])
        data_sources.itemClicked.connect(self.update_chart)

        main_layout.addLayout(left_layout, 2)
        main_layout.addWidget(data_sources, 1)
        self.setCentralWidget(main_widget)

        self.plot_data("QQQ", "5min")

    def plot_data(self, symbol, interval):
        try:
            filename = f'BATS_QQQ, {interval.replace("min", "")}_processed.csv'
            df = pd.read_csv(filename, parse_dates=['datetime'], index_col='datetime')

            fig = go.Figure(data=[go.Candlestick(x=df.index,
                    open=df['open'],
                    high=df['high'],
                    low=df['low'],
                    close=df['close'])])
            
            fig.update_layout(title=f"{symbol} Chart ({interval})")
            
            html = fig.to_html(include_plotlyjs='cdn')
            self.chart_widget.setHtml(html)
        except Exception as e:
            print(f"Error plotting data: {e}")

    def update_chart(self, item):
        symbol = item.text() if hasattr(item, 'text') else "QQQ"
        interval = self.interval_selector.currentText()
        self.plot_data(symbol, interval)
        try:
            results = get_backtest_results(symbol, interval)
            self.performance_widget.update_results(results)
        except Exception as e:
            print(f"Error updating chart: {e}")

class PerformanceWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.labels = {}
        for metric in ['Portfolio Value', 'Total Return', 'Sharpe Ratio', 'Max Drawdown']:
            self.labels[metric] = QLabel(f"{metric}: ")
            self.layout.addWidget(self.labels[metric])

    def update_results(self, results):
        self.labels['Portfolio Value'].setText(f"Portfolio Value: ${results['portfolio_value']:.2f}")
        self.labels['Total Return'].setText(f"Total Return: {results['total_return']:.2%}")
        self.labels['Sharpe Ratio'].setText(f"Sharpe Ratio: {results['sharpe_ratio']:.2f}")
        self.labels['Max Drawdown'].setText(f"Max Drawdown: {results['max_drawdown']:.2%}")


class VADStrategy(bt.Strategy):
    params = (
        ('k', 1.6),
        ('base_order_amount', 100000),
        ('DCAmultiplier', 1.5),
        ('max_dca_count', 4),
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

    def next(self):
        if self.order:
            return

        if not self.position:
            if self.long_signal:
                self.buy()
                self.dca_count = 1
                self.last_buy_price = self.data.close[0]
        
        elif self.position.size > 0:
            if self.long_signal and self.data.close < (self.last_buy_price - self.p.k * self.atr) and self.dca_count < self.p.max_dca_count:
                self.buy()
                self.dca_count += 1
                self.last_buy_price = self.data.close[0]
            
            total_profit = (self.data.close[0] - self.position.price) * self.position.size 
            if self.short_signal or total_profit >= self.position.size * self.atr[0] * self.p.profit_atr_multiplier or total_profit <= -self.position.size * self.atr[0] * self.p.loss_atr_multiplier:
                self.close()

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return

        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(f'BUY EXECUTED, Price: {order.executed.price:.2f}, Cost: {order.executed.value:.2f}, Comm: {order.executed.comm:.2f}')
            else:
                self.log(f'SELL EXECUTED, Price: {order.executed.price:.2f}, Cost: {order.executed.value:.2f}, Comm: {order.executed.comm:.2f}')

        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('Order Canceled/Margin/Rejected')

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
        data = bt.feeds.GenericCSVData(
            dataname=filename,
            datetime=0,
            open=1,
            high=2,
            low=3,
            close=4,
            volume=-1,
            openinterest=-1
        )

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

if __name__ == '__main__':
    app = QApplication(sys.argv)
    main_window = TradingViewLikeApp()
    main_window.show()
    sys.exit(app.exec_())