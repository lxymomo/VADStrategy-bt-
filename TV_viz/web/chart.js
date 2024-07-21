document.addEventListener("DOMContentLoaded", function() {
    console.log("Document loaded, fetching data...");
    fetch('../data/processed_data.csv')
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.text();
        })
        .then(data => {
            console.log("Data fetched, parsing CSV...");
            const parsedData = Papa.parse(data, { header: true }).data;
            console.log("CSV parsed:", parsedData);
            
            const chart = LightweightCharts.createChart(document.getElementById('chart'), {
                width: 800,
                height: 600,
            });

            const candleSeries = chart.addCandlestickSeries();
            const candles = parsedData.map(row => ({
                time: new Date(row.time).getTime() / 1000,
                open: parseFloat(row.open),
                high: parseFloat(row.high),
                low: parseFloat(row.low),
                close: parseFloat(row.close),
            }));
            console.log("Candles data:", candles);
            candleSeries.setData(candles);

            const vwmaSeries = chart.addLineSeries({ color: 'blue' });
            const vwmaData = parsedData.map(row => ({
                time: new Date(row.time).getTime() / 1000,
                value: parseFloat(row.vwma14),
            }));
            console.log("VWMA data:", vwmaData);
            vwmaSeries.setData(vwmaData);

            const atrSeries = chart.addLineSeries({ color: 'red' });
            const atrData = parsedData.map(row => ({
                time: new Date(row.time).getTime() / 1000,
                value: parseFloat(row.atr),
            }));
            console.log("ATR data:", atrData);
            atrSeries.setData(atrData);
        })
        .catch(error => console.error('Error loading CSV data:', error));
});
