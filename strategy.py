import backtrader as bt
import config
# from indicators import VWMA
import pandas as pd
from datetime import datetime

'''
策略
'''

class BaseStrategy(bt.Strategy):
    def __init__(self):
        self.trades = []

    def record_trade(self, order):
        # 假设 "time" 是数据源中的列名
        trade_time = self.data.datetime.datetime(0)
        trade_info = {
            'time': trade_time.strftime('%Y/%m/%d %H:%M'), # 使用 strftime 格式化日期时间
            'type': 'BUY' if order.isbuy() else 'SELL',
            'price': order.executed.price,
            'size': order.executed.size,
            'value': order.executed.value,
            'commission': order.executed.comm,
        }
        self.trades.append(trade_info)

    def get_trades_df(self):
        return pd.DataFrame(self.trades)

    def save_trades_to_csv(self, filename):
        df = self.get_trades_df()
        df.to_csv(filename, index=False, date_format='%Y/%m/%d %H:%M')

    def calculate_trade_profit(self, trade):
        buy_cost = trade['buy_value'] + trade['buy_commission']
        sell_revenue = trade['sell_value'] - trade['sell_commission']
        profit = sell_revenue - buy_cost
        profit_percentage = (profit / buy_cost) * 100
        return profit, profit_percentage

class VADStrategy(BaseStrategy):
    params = (
        ('k', 1.6),
        ('base_order_amount', 100000),
        ('DCAmultiplier', 1.5),
        ('max_dca_count', 4),
        ('profit_atr_multiplier', 1),  # 止盈ATR乘数
        ('loss_atr_multiplier', 1),    # 止损ATR乘数
    )

    def __init__(self):
        super().__init__()
        self.vwma14 = bt.indicators.WeightedMovingAverage(
            self.data.close, period=14, subplot=False
        )
        self.atr = bt.indicators.ATR(self.data, period=14)
        
        self.long_signal = self.data.close < self.vwma14 - self.p.k * self.atr
        self.short_signal = self.data.close > self.vwma14 + self.p.k * self.atr
        
        self.order = None
        self.dca_count = 0
        self.last_buy_price = 0
        self.buy_count = 0
        self.sell_count = 0
        
        # 为绘图记录数据
        self.buy_dates = []
        self.sell_dates = []
        self.prices = []
        self.vwma14_values = []
        self.atr_values = []

        # 完整交易记录
        self.current_trade = None
        self.completed_trades = []

    def prenext(self):
        # 在没有足够数据时，只记录价格
        self.prices.append(self.data.close[0])

    def next(self):
        # 只在所有指标都有有效值时执行
        if len(self.vwma14) > 0 and len(self.atr) > 0:
            # 绘图用
            self.prices.append(self.data.close[0])
            self.vwma14_values.append(self.vwma14[0])
            self.atr_values.append(self.atr[0])
        
            if self.order:
                return

            #开仓逻辑
            if not self.position:
                if self.long_signal:
                    size = self.p.base_order_amount / self.data.close
                    self.order = self.buy(size=size)
                    self.dca_count = 1
                    self.last_buy_price = self.data.close[0]
            
            elif self.position.size > 0:
                # 加仓逻辑
                if self.long_signal and self.data.close < (self.last_buy_price - self.p.k * self.atr) and self.dca_count < self.p.max_dca_count:
                    dca_amount = self.p.base_order_amount * (self.p.DCAmultiplier ** (self.dca_count - 1))
                    size = dca_amount / self.data.close
                    self.order = self.buy(size=size)
                    self.dca_count += 1
                    self.last_buy_price = self.data.close[0]
                
                # 止盈止损逻辑
                total_profit = (self.data.close[0] - self.position.price) * self.position.size 
                if self.short_signal or total_profit >= self.position.size * self.atr[0] * self.p.profit_atr_multiplier or total_profit <= -self.position.size * self.atr[0] * self.p.loss_atr_multiplier:
                    self.order = self.close()

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return

        if order.status in [order.Completed]:
            self.record_trade(order)
            if order.isbuy():
                self.buy_count += 1
                self.buy_dates.append(self.data.datetime.date())
                # 记录新的买入交易
                self.current_trade = {
                    'buy_price': order.executed.price,
                    'buy_size': order.executed.size,
                    'buy_value': order.executed.value,
                    'buy_commission': order.executed.comm,
                    'buy_date': self.data.datetime.date(0)
                }
            elif order.issell():
                self.sell_count += 1
                self.dca_count = 0
                self.sell_dates.append(self.data.datetime.date())
                # 完成交易并计算收益
                if self.current_trade is not None:
                    self.current_trade.update({
                        'sell_price': order.executed.price,
                        'sell_size': order.executed.size,
                        'sell_value': order.executed.value,
                        'sell_commission': order.executed.comm,
                        'sell_date': self.data.datetime.date(0)
                    })
                    # 计算收益
                    buy_cost = self.current_trade['buy_value'] + self.current_trade['buy_commission']
                    sell_revenue = self.current_trade['sell_value'] - self.current_trade['sell_commission']
                    profit = sell_revenue - buy_cost
                    profit_percentage = (profit / buy_cost) * 100
                    profit, profit_percentage = self.calculate_trade_profit(self.current_trade)
                    self.current_trade['profit'] = profit
                    self.current_trade['profit_percentage'] = profit_percentage
                    self.completed_trades.append(self.current_trade)
                    self.current_trade = None

        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('Order Canceled/Margin/Rejected')

        self.order = None

    def log(self, txt, dt=None):
        dt = dt or self.datas[0].datetime.date(0)
        print(f'{dt.isoformat()} {txt}')

    def save_completed_trades_to_csv(self, filename):
        df = pd.DataFrame(self.completed_trades)
        df.to_csv(filename, index=False)

    def calculate_performance_metrics(self):
        cumulative_profit = sum(trade['profit'] for trade in self.completed_trades)
        total_trades = len(self.completed_trades)
        winning_trades = sum(1 for trade in self.completed_trades if trade['profit'] > 0)
        losing_trades = total_trades - winning_trades
        win_rate = winning_trades / total_trades if total_trades > 0 else 0

        return {
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': win_rate,
            'cumulative profit':cumulative_profit
        }

class BuyAndHoldStrategy(BaseStrategy):
    def __init__(self):
        super().__init__()
        self.buy_count = 0
        self.sell_count = 0
        self.order = None  
        self.buy_executed = False
        self.sell_executed = False

    def next(self):
        # 在第一个可交易的 bar 买入
        if len(self) == 1 and not self.position and not self.buy_executed:
            cash = self.broker.get_cash()
            close_price = self.data.close[0]
            commission_rate = config.broker_params['commission_rate']
            slippage_rate = config.broker_params['slippage']

            # 计算总成本
            size = int(cash / (close_price * (1 + commission_rate + slippage_rate)))
            total_cost = size * close_price * (1 + commission_rate + slippage_rate)
            
            # self.log(f'Trying to buy: Cash={cash}, Close={close_price}, Size={size}, Total Cost={total_cost}')
            if total_cost <= cash and size > 0:
                self.order = self.buy(size=size)
                self.buy_executed = True
                # self.log(f'Buy order created: Size={size}')

        # 判断是否达到最后一个bar
        if len(self) == len(self.data) - 1 and self.position and not self.sell_executed:
            self.log(f'Trying to sell: Position Size={self.position.size}')
            self.order = self.sell(size=self.position.size)
            self.sell_executed = True

    def notify_order(self, order):
        if order.status in [order.Completed]:
            self.record_trade(order)
            if order.isbuy():
                self.buy_count += 1
            elif order.issell():
                self.sell_count += 1
            self.order = None
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.order = None

    def log(self, txt, dt=None):
        dt = dt or self.datas[0].datetime.date(0)
        print(f'{dt.isoformat()}, {txt}')