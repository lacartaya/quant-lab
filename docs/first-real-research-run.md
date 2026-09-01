# First real research run: SPY 50/200

This walkthrough uses a previously imported real SPY daily DatasetSnapshot. It
does not assume a fixed database ID and does not imply that the strategy will pass.

1. Open the dashboard and choose **New Research**, or list snapshots with:

   ```bash
   curl http://127.0.0.1:8000/api/v1/datasets
   ```

2. Select the SPY `1Day` snapshot ID. Create the hypothesis **SPY daily 50/200
   trend**. Quant Lab checks prior art before saving it.
3. Create `moving_average_trend` with `short_window=50` and `long_window=200`.
   The returned StrategyVersion is immutable.
4. Create an experiment by selecting the new hypothesis, StrategyVersion, and
   existing DatasetSnapshot.
5. Run it with explicit initial cash, position fraction, fee, slippage, annual
   periods, and risk-free rate.
6. Open the returned experiment. The run detail and BACKTEST validation contain
   metrics, Buy & Hold evidence, execution versions, and the result fingerprint.

The dashboard offers **Copy curl** beside each write action. The same executable
sequence is committed in `bruno/Example - SPY Research/README.md`. Further
validation evidence can be inspected through the API, but the current HTTP API
does not yet start those application-only validation workflows.
## Understanding how your strategy actually traded

After **Run Experiment**, inspect the ExperimentRun and BACKTEST, open **View
backtest chart**, then inspect Dataset Quality. The requested 2016-01-01 start is
not the actual 2018-11-01 first returned SPY bar. The chart shows MA50/MA200,
distinct signal-close and next-open fills, completed trades, LONG/FLAT periods,
and strategy equity beside Buy & Hold.

This is historical explainability. It does not make unexecuted OOS or robustness
stages pass and does not authorize paper or live trading.
