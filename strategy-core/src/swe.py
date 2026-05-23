import os
import ast
import json
import re
import importlib.util
from pathlib import Path
from datetime import datetime, timezone
from openai import OpenAI
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

def env_first(*names_and_defaults: str) -> str:
    for name in names_and_defaults[:-1]:
        value = os.getenv(name)
        if value:
            return value
    return names_and_defaults[-1]


OPENROUTER_BASE_URL = env_first('OPENROUTER_BASE_URL', 'https://openrouter.ai/api/v1')
GENERATOR_MODEL = env_first('GENERATOR_MODEL', 'KIMI_MODEL', 'moonshotai/kimi-k2')
ANALYST_MODEL = env_first('ANALYST_MODEL', 'QWEN_MODEL', 'qwen/qwen3.6-35b-a3b')
GENERATOR_BASE_URL = env_first('GENERATOR_BASE_URL', 'OPENROUTER_BASE_URL', OPENROUTER_BASE_URL)
ANALYST_BASE_URL = env_first('ANALYST_BASE_URL', 'QWEN_BASE_URL', OPENROUTER_BASE_URL)
GENERATOR_API_KEY = env_first('GENERATOR_API_KEY', 'OPENROUTER_API_KEY', '')
ANALYST_API_KEY = os.getenv('ANALYST_API_KEY')
if not ANALYST_API_KEY:
    if 'openrouter.ai' in ANALYST_BASE_URL:
        ANALYST_API_KEY = os.getenv('OPENROUTER_API_KEY')
    else:
        ANALYST_API_KEY = os.getenv('QWEN_API_KEY') or os.getenv('OPENROUTER_API_KEY')

def get_generator():
    return OpenAI(api_key=GENERATOR_API_KEY, base_url=GENERATOR_BASE_URL)

def get_analyst():
    return OpenAI(api_key=ANALYST_API_KEY, base_url=ANALYST_BASE_URL)

def get_kimi():
    return get_generator()

def get_qwen():
    return get_analyst()

SHARED_KNOWLEDGE  = Path(os.getenv('SHARED_KNOWLEDGE',  '/shared/knowledge'))
SHARED_MODELS     = Path(os.getenv('SHARED_MODELS',     '/shared/models'))
SHARED_BACKTESTING= Path(os.getenv('SHARED_BACKTESTING','/shared/backtesting'))
SHARED_HYPOTHESES = Path(os.getenv('SHARED_HYPOTHESES', '/shared/hypotheses'))
VAULT_ARTIFACTS   = Path(os.getenv('VAULT_ARTIFACTS',   '/vault/artifacts'))
BACKTEST_CONFIG   = Path('/shared/backtesting/config')


def get_strategy_code_from_file(hyp_data: dict):
    strat_file = hyp_data.get('strategy_file')
    if strat_file:
        p = Path(strat_file)
        if p.exists():
            return p.read_text()
    return None


def load_config_context() -> str:
    """Read the actual config Python files and inject into Kimi's prompt."""
    ctx = ''
    for fname in ['venue.py', 'instruments.py', 'loader.py']:
        p = BACKTEST_CONFIG / fname
        if p.exists():
            ctx += f'# === /shared/backtesting/config/{fname} ===\n'
            ctx += p.read_text() + '\n\n'
    return ctx


QWEN_SYS = 'You are a quant analyst. Given a hypothesis and data, produce a refined spec. Output ONLY valid JSON with: assessment, refined_hypothesis, entry_conditions, exit_conditions, relevant_instruments, relevant_macro, risks, implementation_notes.'

KIMI_SYS = '''You are a NautilusTrader 1.221 expert writing backtest strategies.

You have access to helper modules at /shared/backtesting/config/:
  - venue.py      → build_engine()
  - instruments.py → get_instrument(), get_bar_type()
  - loader.py     → load_bars(), load_macro()

ALWAYS use these helpers. NEVER build engine or load data from scratch.

The complete source of these modules is provided below — read them carefully before writing code.

Rules:
- Raw Python only. No markdown. No explanation.
- Strategy class must be named GeneratedStrategy.
- on_start() must call self.subscribe_bars(self.bar_type) where bar_type is a BarType object.
- NEVER call subscribe_bars(self.instrument_id) — instrument_id is not a BarType.
- Price precision: always f"{value:.2f}" — never str(round(x,2)).
- Results: engine.get_result().stats_pnls
'''

STRATEGY_SKELETON = '''import sys
sys.path.insert(0, '/shared/backtesting')
from config import build_engine, get_instrument, get_bar_type, load_bars
from nautilus_trader.trading.strategy import Strategy
from nautilus_trader.config import StrategyConfig
from nautilus_trader.model.data import Bar, BarType
from nautilus_trader.model.enums import OrderSide
from nautilus_trader.model.objects import Quantity


class GeneratedStrategy(Strategy):
    def __init__(self):
        super().__init__()
        self.instrument_id = get_instrument("SPY").id
        self.bar_type = get_bar_type("SPY")
        self.closes = []
        self.in_position = False
        # TODO: add any extra state variables (integers, floats, booleans only)

    def on_start(self):
        self.subscribe_bars(self.bar_type)  # DO NOT CHANGE

    def on_bar(self, bar: Bar):
        self.closes.append(float(bar.close))
        # TODO: implement entry/exit logic using self.closes (list of floats)
        # Call self._buy() to enter, self._sell() to exit
        # Example MA crossover:
        # if len(self.closes) >= 20:
        #     fast = sum(self.closes[-5:]) / 5
        #     slow = sum(self.closes[-20:]) / 20
        #     if fast > slow: self._buy()
        #     elif fast < slow: self._sell()

    def _buy(self):
        if not self.in_position:
            order = self.order_factory.market(
                instrument_id=self.instrument_id,
                order_side=OrderSide.BUY,
                quantity=Quantity.from_int(100),
            )
            self.submit_order(order)
            self.in_position = True

    def _sell(self):
        if self.in_position:
            order = self.order_factory.market(
                instrument_id=self.instrument_id,
                order_side=OrderSide.SELL,
                quantity=Quantity.from_int(100),
            )
            self.submit_order(order)
            self.in_position = False

    def on_stop(self):
        self.close_all_positions(self.instrument_id)


if __name__ == "__main__" or True:
    instrument = get_instrument("SPY")
    bar_type = get_bar_type("SPY")
    bars = load_bars("SPY", bar_type)
    engine = build_engine()
    engine.add_instrument(instrument)
    engine.add_data(bars)
    engine.add_strategy(GeneratedStrategy())
    engine.run()
    result = engine.get_result()
    print("=== BACKTEST RESULTS ===")
    print(result.stats_pnls)
    engine.dispose()
'''


def load_context():
    ctx = ''
    # Inject real config source files so Kimi sees actual working code
    ctx += '=== ENVIRONMENT CONFIG (read before writing any code) ===\n'
    ctx += load_config_context()
    # Instrument and macro catalogs
    p = SHARED_MODELS / 'instruments.json'
    if p.exists():
        ctx += 'INSTRUMENTS:\n' + p.read_text() + '\n\n'
    p = SHARED_MODELS / 'macro_catalog.json'
    if p.exists():
        ctx += 'MACRO:\n' + p.read_text() + '\n\n'
    # Recent research
    if SHARED_KNOWLEDGE.exists():
        for f in sorted(SHARED_KNOWLEDGE.glob('*.md'))[-3:]:
            ctx += 'RESEARCH (' + f.name + '):\n' + f.read_text()[:1500] + '\n\n'
    return ctx


def load_pending_hypotheses():
    if not SHARED_HYPOTHESES.exists():
        return []
    out = []
    for f in sorted(SHARED_HYPOTHESES.glob('*.json')):
        if '.done' not in f.name:
            try:
                out.append({'path': f, 'data': json.loads(f.read_text())})
            except Exception as e:
                logger.error('Failed ' + f.name + ': ' + str(e))
    return out


def analyze_hypothesis(hyp, ctx):
    logger.info('[QWEN] analyzing...')
    try:
        r = get_analyst().chat.completions.create(
            model=ANALYST_MODEL,
            max_tokens=8000,
            messages=[
                {'role': 'system', 'content': QWEN_SYS},
                {'role': 'user', 'content': 'HYPOTHESIS:\n' + json.dumps(hyp, indent=2) + '\n\nDATA:\n' + ctx + '\n\nReturn ONLY valid JSON.'},
            ]
        )
        msg = r.choices[0].message
        raw = msg.content if msg.content else getattr(msg, 'reasoning', None)
        if raw is None:
            raise ValueError('Empty response from Qwen')
        raw = raw.strip().replace('```json', '').replace('```', '').strip()
        result = json.loads(raw)
        logger.success('[QWEN] done: ' + str(result.get('assessment', ''))[:80])
        return result
    except Exception as e:
        logger.error('[QWEN] failed: ' + str(e))
        return {
            'refined_hypothesis': hyp.get('description', ''),
            'entry_conditions': [],
            'exit_conditions': [],
            'relevant_instruments': hyp.get('instruments', ['SPY']),
            'relevant_macro': [],
            'risks': [],
            'implementation_notes': 'Use description directly.'
        }


def write_strategy_code(analysis, ctx):
    logger.info('[KIMI] writing code...')
    r = get_generator().chat.completions.create(
        model=GENERATOR_MODEL,
        max_tokens=2000,
        messages=[
            {'role': 'system', 'content': KIMI_SYS},
            {'role': 'user', 'content': (
                'ENVIRONMENT (helper module source):\n' + load_config_context() +
                '\nSPEC:\n' + json.dumps(analysis, indent=2) +
                '\n\nSKELETON:\n' + STRATEGY_SKELETON +
                '\n\nFill in the TODO sections. Use the helper modules shown above. Return complete Python file.'
            )},
        ]
    )
    code = r.choices[0].message.content.strip().replace('```python', '').replace('```', '').strip()
    logger.success('[KIMI] code written')
    return code


def validate_code(code):
    try:
        ast.parse(code)
    except SyntaxError as e:
        return False, 'SyntaxError: ' + str(e)
    tmp = Path('/tmp/validate_strategy.py')
    tmp.write_text(code)
    try:
        spec = importlib.util.spec_from_file_location('validate_strategy', tmp)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        if not hasattr(mod, 'GeneratedStrategy'):
            return False, 'GeneratedStrategy class not found'
    except Exception as e:
        return False, type(e).__name__ + ': ' + str(e)
    if 'subscribe_bars(self.instrument_id)' in code:
        return False, 'subscribe_bars() called with InstrumentId instead of BarType'
    return True, None


def fix_strategy_code(code, error):
    logger.info('[KIMI] fixing: ' + error[:100])
    r = get_generator().chat.completions.create(
        model=GENERATOR_MODEL,
        max_tokens=2000,
        messages=[
            {'role': 'system', 'content': KIMI_SYS},
            {'role': 'user', 'content': (
                'ENVIRONMENT:\n' + load_config_context() +
                '\nBROKEN CODE:\n' + code +
                '\n\nERROR:\n' + error +
                '\n\nFix the error. Use helper modules. Return complete fixed Python only.'
            )},
        ]
    )
    return r.choices[0].message.content.strip().replace('```python', '').replace('```', '').strip()


def write_and_validate_strategy(analysis, ctx, max_retries=5):
    code = write_strategy_code(analysis, ctx)
    for attempt in range(max_retries):
        is_valid, error = validate_code(code)
        if is_valid:
            # Also do a runtime test to catch 'no market' and other runtime errors
            is_valid, error = test_run_strategy(code)
        if is_valid:
            logger.success('[KIMI] validated on attempt ' + str(attempt + 1))
            return code
        logger.warning('[KIMI] attempt ' + str(attempt + 1) + ' invalid: ' + str(error))
        if attempt < max_retries - 1:
            code = fix_strategy_code(code, error)
    is_valid, error = validate_code(code)
    if is_valid:
        return code
    logger.error('[KIMI] still invalid after retries: ' + str(error))
    return code


def run_backtest(strategy_path, instruments_catalog):
    """Run backtest using the shared config helpers."""
    import sys
    sys.path.insert(0, '/shared/backtesting')
    from config import build_engine, get_instrument, get_bar_type, load_bars

    spec = importlib.util.spec_from_file_location('generated_strategy', strategy_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    G = mod.GeneratedStrategy

    symbols = list(instruments_catalog.keys()) if instruments_catalog else ['SPY']

    engine = build_engine()
    for sym in symbols:
        try:
            instrument = get_instrument(sym)
            bar_type = get_bar_type(sym)
            bars = load_bars(sym, bar_type)
            from config import load_quotes_from_bars
            quotes = load_quotes_from_bars(sym, bar_type)
            engine.add_instrument(instrument)
            engine.add_data(quotes)
            engine.add_data(bars)
            logger.info(f'[BACKTEST] loaded {len(bars)} bars for {sym}')
        except FileNotFoundError as e:
            logger.warning(f'[BACKTEST] skipping {sym}: {e}')

    engine.add_strategy(G())
    engine.run()
    result = engine.get_result()
    stats = result.stats_pnls if hasattr(result, 'stats_pnls') else {}
    engine.dispose()
    return {'status': 'completed', 'stats': stats, 'strategy': str(strategy_path)}


def interpret_results(results, analysis):
    logger.info('[QWEN] interpreting...')
    try:
        r = get_analyst().chat.completions.create(
            model=ANALYST_MODEL,
            max_tokens=2000,
            messages=[
                {'role': 'system', 'content': 'You are a quant analyst interpreting backtest results.'},
                {'role': 'user', 'content': 'SPEC:\n' + json.dumps(analysis, indent=2)[:1000] + '\n\nRESULTS:\n' + json.dumps(results, indent=2)[:1000] + '\n\nSummarize in 3-5 sentences.'},
            ]
        )
        return r.choices[0].message.content.strip()
    except Exception as e:
        logger.warning('[QWEN] interpretation failed: ' + str(e))
        return str(results.get('stats', 'no stats'))


def process_hypothesis(hypothesis_entry, context):
    hyp_path = hypothesis_entry['path']
    hyp_data = hypothesis_entry['data']
    ts = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')
    logger.info('[SWE] processing: ' + hyp_path.name)

    prewritten_code = get_strategy_code_from_file(hyp_data)
    if prewritten_code:
        logger.info('[SWE] using pre-written strategy from hypothesis')
        analysis = {'id': hyp_data.get('id', 'unknown'), 'title': hyp_data.get('title', '')}
        sp = VAULT_ARTIFACTS / ('strategy_' + ts + '.py')
        sp.parent.mkdir(parents=True, exist_ok=True)
        sp.write_text(prewritten_code)
    else:
        analysis = analyze_hypothesis(hyp_data, context)
        code = write_and_validate_strategy(analysis, context)
        sp = VAULT_ARTIFACTS / ('strategy_' + ts + '.py')
        sp.parent.mkdir(parents=True, exist_ok=True)
        sp.write_text(code)
    logger.info('[SWE] written -> ' + str(sp))

    result = {'status': 'strategy_written', 'strategy_path': str(sp), 'analysis': analysis}
    try:
        inst_path = SHARED_MODELS / 'instruments.json'
        instruments = json.loads(inst_path.read_text()) if inst_path.exists() else {}
        br = run_backtest(sp, instruments)
        result.update(br)
        result['interpretation'] = interpret_results(br, analysis)
        logger.success('[SWE] done: ' + result['interpretation'][:100])
    except Exception as e:
        logger.error('[SWE] backtest failed: ' + str(e))
        result['backtest_error'] = str(e)

    rp = SHARED_BACKTESTING / 'results' / ('result_' + ts + '.json')
    rp.parent.mkdir(parents=True, exist_ok=True)
    rp.write_text(json.dumps(result, indent=2, default=str))
    hyp_path.rename(str(hyp_path) + '.done')
    return result


def test_run_strategy(code: str) -> tuple[bool, str | None]:
    """
    Actually runs the strategy for 1 bar to catch runtime errors like 'no market'.
    Returns (is_valid, error_message).
    """
    import sys
    sys.path.insert(0, '/shared/backtesting')
    from config import build_engine, get_instrument, get_bar_type, load_bars

    tmp = Path('/tmp/test_strategy.py')
    tmp.write_text(code)
    try:
        spec = importlib.util.spec_from_file_location('test_strategy', tmp)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        G = mod.GeneratedStrategy

        instrument = get_instrument('SPY')
        bar_type = get_bar_type('SPY')
        bars = load_bars('SPY', bar_type)

        engine = build_engine()
        from config import load_quotes_from_bars
        quotes = load_quotes_from_bars('SPY', bar_type)
        engine.add_instrument(instrument)
        engine.add_data(quotes[:25])
        engine.add_data(bars[:25])  # just enough bars to trigger a signal

        rejected = []
        original_init = G.__init__

        # Monkey-patch on_order_rejected to capture rejections
        def on_order_rejected(self, event):
            rejected.append(event.reason)

        G.on_order_rejected = on_order_rejected
        engine.add_strategy(G())
        engine.run()
        engine.dispose()

        if rejected:
            reasons = ', '.join(set(rejected))
            return False, f'Orders rejected at runtime: {reasons}'
        return True, None
    except Exception as e:
        return False, f'{type(e).__name__}: {e}'
