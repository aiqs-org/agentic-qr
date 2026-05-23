# quant-lib Codex

## Role
Object Factory — sits between pipelines and strategy-core.
Converts raw pipeline data into typed NautilusTrader objects.

## Does
- Reads shared/data/market/ (Alpaca OHLCV)
- Reads shared/data/macro/ (FRED series)
- Builds Equity instrument objects
- Builds Bar objects (1-min LAST EXTERNAL) per symbol
- Writes bars as parquet to shared/backtesting/bars/{SYMBOL}/bars.parquet
- Writes instrument catalog to shared/models/instruments.json
- Writes macro catalog to shared/models/macro_catalog.json
- Annotates catalogs with researcher context from shared/knowledge/
- Publishes quant_lib_objects_built to vault/bus/quant-lib-outbox/
- Responds to query_object_catalog events from strategy-core

## Does NOT
- Feature engineering
- Signal construction
- Backtesting execution
- Strategy code
- Research hypotheses

## Model
MiniMax via OpenRouter (default: minimax/minimax-m2.7)
Token budget: 1500 per call

## Bus Events
Inbox:  pipeline_data_updated → rebuild objects
        rebuild_objects       → force rebuild
        query_object_catalog  → return catalog JSON

Outbox: quant_lib_objects_built  → objects ready
        object_catalog_response  → reply to catalog queries
