"""
자동매매 봇 V2 - 2단계 감시 시스템

기획서 기반 구조:
[Stage 1] 전체 시장 스캔 (3~5분) → 워치리스트 생성
[Stage 2] 워치리스트 고주기 감시 (5~10초) → 즉시 실행
"""
import os
import sys
import asyncio
import logging
import threading
from datetime import datetime
from typing import Optional, List, Dict
from pathlib import Path
from dotenv import load_dotenv

# 현재 디렉토리를 Python 경로에 추가
current_dir = Path(__file__).parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

# 환경 변수 로드
load_dotenv()

# 로깅 설정 (UTF-8 인코딩)
import sys
import logging.handlers
logging.basicConfig(
    level=os.getenv('LOG_LEVEL', 'INFO'),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.handlers.RotatingFileHandler(
            'logs/auto_trading_v2.log',
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=3,
            encoding='utf-8'
        ),
        logging.StreamHandler(sys.stdout)
    ]
)
# Windows 콘솔 UTF-8 설정
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
logger = logging.getLogger(__name__)

# 로그 디렉토리 생성
os.makedirs('logs/execution', exist_ok=True)

# 실행 팀 임포트
try:
    from execution_team.core import ExecutionEngine, OrderManager, OrderSignal, OrderAction, OrderType
    from execution_team.brokers import AlpacaBroker
except ImportError as e:
    logger.error(f"Execution Team 임포트 실패: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 감시 시스템 임포트
try:
    from data_collection.monitoring import WatchlistGenerator, HighFrequencyMonitor
    from data_collection.monitoring.websocket_monitor import WebSocketPriceMonitor
except ImportError as e:
    logger.error(f"Monitoring 모듈 임포트 실패: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 시장 게이트 (선택적 - 실패해도 봇은 계속 동작)
try:
    from strategy_engine.market_gate import MarketGate
    MARKET_GATE_AVAILABLE = True
except Exception as _e:
    MARKET_GATE_AVAILABLE = False
    logger.warning(f"MarketGate 비활성화: {_e}")

# 전략 엔진 시그널 생성기 (선택적 - BLOCK-02)
try:
    from strategy_engine.signals.signal_generator import SignalGenerator
    SIGNAL_GENERATOR_AVAILABLE = True
except Exception as _e:
    SIGNAL_GENERATOR_AVAILABLE = False
    logger.warning(f"SignalGenerator 비활성화: {_e}")

# 갭 방향 검증기 (선택적)
try:
    from strategy_engine.filters.gap_validator import GapValidator
    GAP_VALIDATOR_AVAILABLE = True
except Exception as _e:
    GAP_VALIDATOR_AVAILABLE = False
    logger.warning(f"GapValidator 비활성화: {_e}")

# AI 뉴스 분석기 (선택적 - 실패해도 봇은 계속 동작)
try:
    import sys as _sys
    import os as _os
    _ai_team_path = str(Path(__file__).parent)
    if _ai_team_path not in _sys.path:
        _sys.path.insert(0, _ai_team_path)
    from ai_team.news.analyzer import NewsAnalyzer
    AI_SCORING_AVAILABLE = True
except Exception as _e:
    AI_SCORING_AVAILABLE = False
    logger.warning(f"AI 뉴스 분석기 비활성화 (선택적 기능): {_e}")


class AutoTradingBotV2:
    """
    자동매매 봇 V2 - 2단계 감시 시스템

    [Stage 1] 전체 시장 스캔 (3~5분)
        → gap > 3% or volume_ratio > 3배
        → 상위 20개 워치리스트 생성

    [Stage 2] 워치리스트 고주기 감시 (5~10초)
        → 1.5% 변동 감지
        → 즉시 매매 실행
    """

    def __init__(self):
        """초기화"""
        logger.info("=" * 70)
        logger.info("자동매매 봇 V2 초기화 중...")
        logger.info("=" * 70)

        # 설정 로드
        self.auto_trading_enabled = os.getenv('AUTO_TRADING_ENABLED', 'false').lower() == 'true'

        # Stage 1 설정 (전체 시장 스캔)
        self.market_scan_interval = int(os.getenv('MARKET_SCAN_INTERVAL_MINUTES', '5'))  # 3~5분
        self.gap_threshold = float(os.getenv('GAP_THRESHOLD', '3.0'))  # 3%
        self.volume_ratio_threshold = float(os.getenv('VOLUME_RATIO_THRESHOLD', '3.0'))  # 3배
        self.max_watchlist_size = int(os.getenv('MAX_WATCHLIST_SIZE', '20'))
        self.min_price = float(os.getenv('MIN_STOCK_PRICE', '5.0'))          # 최소 주가 ($5)
        self.min_avg_volume = int(os.getenv('MIN_AVG_VOLUME', '500000'))       # 최소 평균 거래량

        # Stage 2 설정 (고주기 감시)
        self.monitor_interval = int(os.getenv('MONITOR_INTERVAL_SECONDS', '10'))  # 5~10초
        # SPIKE_TRIGGER: constants 단일 소스 (env 오버라이드 금지)
        # .env 의 PRICE_CHANGE_THRESHOLD 오버라이드 불허:
        # 백테스트(IntradayBacktestConfig)와 라이브가 항상 같은 트리거 사용
        from config.trading_constants import TAKE_PROFIT_PCT, STOP_LOSS_PCT, SPIKE_TRIGGER_PCT
        self.price_change_threshold = SPIKE_TRIGGER_PCT * 100  # constants 단일 소스

        # 리스크 관리 — TP/SL 수치는 config/trading_constants.py 에서만 관리 (BLOCK-03)
        # .env 의 TAKE_PROFIT_PERCENT 오버라이드 불허: 백테스트와 라이브가 항상 같은 TP 사용
        self.max_investment_percent = float(os.getenv('MAX_INVESTMENT_PERCENT', '10.0'))
        self.stop_loss_percent = float(os.getenv('STOP_LOSS_PERCENT', str(STOP_LOSS_PCT * 100)))
        self.take_profit_percent = TAKE_PROFIT_PCT * 100  # constants 단일 소스 (env 오버라이드 금지)
        self.max_daily_loss_percent = float(os.getenv('MAX_DAILY_LOSS_PERCENT', '5.0'))
        self.max_positions = int(os.getenv('MAX_POSITIONS', '5'))

        # 알파카 API 키 (경고 메시지 전에 먼저 설정)
        self.api_key = os.getenv('ALPACA_API_KEY')
        self.api_secret = os.getenv('ALPACA_SECRET_KEY')
        self.base_url = os.getenv('ALPACA_BASE_URL', 'https://paper-api.alpaca.markets')

        # 설정 출력
        logger.info(f"자동매매 활성화: {self.auto_trading_enabled}")
        if self.auto_trading_enabled:
            logger.warning("=" * 70)
            logger.warning("!!! 자동매매가 활성화되어 있습니다 !!!")
            logger.warning("!!! 실제 주문이 실행될 수 있습니다 !!!")
            logger.warning(f"!!! 브로커: {self.base_url}")
            logger.warning("=" * 70)

        logger.info(f"[Stage 1] 시장 스캔 주기: {self.market_scan_interval}분")
        logger.info(f"[Stage 1] 워치리스트 조건: 갭>{self.gap_threshold}% or 거래량>{self.volume_ratio_threshold}배")
        logger.info(f"[Stage 1] 종목 필터: 최소 주가=${self.min_price}, 최소 평균 거래량={self.min_avg_volume:,}")
        logger.info(f"[Stage 2] 모니터링 주기: {self.monitor_interval}초")
        logger.info(f"[Stage 2] 변동 임계값: {self.price_change_threshold}%")
        logger.info(f"[리스크] 1회 투자: {self.max_investment_percent}%, 손절: -{self.stop_loss_percent}%, 익절: +{self.take_profit_percent}%, 일일 손실: -{self.max_daily_loss_percent}%")

        if not self.api_key or not self.api_secret:
            raise ValueError("ALPACA_API_KEY와 ALPACA_SECRET_KEY를 설정하세요")

        # 컴포넌트 초기화
        self._init_execution_team()
        self._init_monitoring_system()

        # 매매 쿨다운 설정 (매도 후 동일 종목 재진입 방지)
        self.trade_cooldown_minutes = int(os.getenv('TRADE_COOLDOWN_MINUTES', '120'))  # 기본 2시간
        self._recently_sold: Dict[str, datetime] = {}  # {symbol: 매도 완료 시각}
        self._pending_sell_symbols: set = set()  # 미체결 매도 주문 있는 종목 (중복 주문 방지)
        self._pending_buy_symbols: set = set()  # 매수 주문 처리 중인 종목 (중복 매수 방지)

        # BLOCK-02: 전략별 RSI 스코어링을 위한 시그널 생성기 및 유니버스 매핑
        if SIGNAL_GENERATOR_AVAILABLE:
            self.signal_generator = SignalGenerator()
        else:
            self.signal_generator = None
        self._symbol_strategy_types: Dict[str, str] = {}  # {symbol: "momentum"|"breakout"|"reversion"}

        # IMP-03: Trailing Stop 설정
        self.trailing_stop_pct = float(os.getenv('TRAILING_STOP_PCT', '5.0'))        # 최고가 대비 -5% 청산 (V4 백테스트 동일)
        self.partial_take_profit_pct = float(os.getenv('PARTIAL_TP_PCT', '3.0'))     # +3%에 50% 부분 청산
        self._highest_price: Dict[str, float] = {}   # {symbol: 진입 후 최고가}
        self._partial_tp_done: set = set()            # 부분 청산 완료 종목

        # V4 Multi-Day Hold 설정 (백테스트 검증 기준)
        self.v4_max_hold_days = int(os.getenv('V4_MAX_HOLD_DAYS', '10'))             # 최대 보유 거래일
        self.v4_entry_start_minute = int(os.getenv('V4_ENTRY_START_MINUTE', '20'))   # 09:30+20 = 09:50 ET
        self.v4_entry_end_hour = int(os.getenv('V4_ENTRY_END_HOUR', '10'))           # 10:15 ET 이후 진입 금지
        self.v4_entry_end_minute = int(os.getenv('V4_ENTRY_END_MINUTE', '15'))
        self._position_entry_date: Dict[str, "date"] = {}  # {symbol: 진입일} — 재시작 시 Alpaca로 복구

        # NEW-04: 일일 거래 횟수 제한
        self.max_entries_per_day = int(os.getenv('MAX_ENTRIES_PER_DAY', '5'))
        self.max_exits_per_day = int(os.getenv('MAX_EXITS_PER_DAY', '10'))
        self._daily_entry_count = 0
        self._daily_exit_count = 0
        self._last_trade_date: Optional[str] = None

        # 상태 추적
        self.daily_pl = 0.0
        self.trade_count = 0
        self.is_running = False

        # DB 연결 설정 (거래 로그 기록용)
        self._db_cfg = None
        self._init_database()

        logger.info("✓ 자동매매 봇 V2 초기화 완료")

    def _init_execution_team(self):
        """Execution Team 초기화"""
        logger.info("\n[1] Execution Team 초기화 중...")

        try:
            # 브로커 연결
            broker_config = {
                'api_key': self.api_key,
                'secret_key': self.api_secret,
                'base_url': self.base_url
            }

            self.broker = AlpacaBroker(broker_config)
            self.broker.connect()
            logger.info(f"✓ 브로커 연결 성공 ({self.base_url})")

            # 주문 관리자
            self.order_manager = OrderManager(
                storage_path=os.getenv('ORDER_STORAGE_PATH', 'logs/execution/orders')
            )
            logger.info("✓ 주문 관리자 초기화 완료")

            # 실행 엔진
            self.execution_engine = ExecutionEngine(
                broker=self.broker,
                order_manager=self.order_manager,
                enable_circuit_breaker=True
            )
            logger.info("✓ 실행 엔진 초기화 완료")

            # 계좌 정보
            account = self.execution_engine.get_account()
            logger.info(f"✓ 계좌 자산: ${account.equity:,.2f}")

            # 텔레그램 트레이딩 도구에 엔진 등록
            try:
                from tools.trading_tool import set_execution_engine
                set_execution_engine(self.execution_engine)
                logger.info("✓ 텔레그램 트레이딩 도구 연결 완료")
            except ImportError:
                logger.warning("⚠️ trading_tool 모듈 없음 - 텔레그램 매매 기능 비활성화")

        except Exception as e:
            logger.error(f"✗ Execution Team 초기화 실패: {e}")
            raise

    def _init_monitoring_system(self):
        """모니터링 시스템 초기화"""
        logger.info("\n[2] Monitoring System 초기화 중...")

        try:
            # 워치리스트 생성기 (Stage 1) — V4: ITC 16종목 고정 유니버스
            from config.trading_constants import ITC_UNIVERSE
            self.watchlist_generator = WatchlistGenerator(
                api_key=self.api_key,
                api_secret=self.api_secret,
                gap_threshold=self.gap_threshold,
                volume_ratio_threshold=self.volume_ratio_threshold,
                max_watchlist_size=self.max_watchlist_size,
                min_price=self.min_price,
                min_avg_volume=self.min_avg_volume,
                paper='paper-api' in self.base_url,
                fixed_universe=list(ITC_UNIVERSE),
            )
            logger.info(f"✓ 워치리스트 생성기 초기화 완료 (ITC {len(ITC_UNIVERSE)}종목 고정 유니버스)")

            # 갭 방향 검증기 (IMP-02)
            if GAP_VALIDATOR_AVAILABLE:
                try:
                    self.gap_validator = GapValidator(
                        api_key=self.api_key,
                        api_secret=self.api_secret,
                    )
                    logger.info("✓ 갭 방향 검증기 초기화 완료")
                except Exception as e:
                    self.gap_validator = None
                    logger.warning(f"갭 방향 검증기 초기화 실패 (무시): {e}")
            else:
                self.gap_validator = None

            # 시장 게이트 (IMP-01)
            if MARKET_GATE_AVAILABLE:
                try:
                    self.market_gate = MarketGate(
                        api_key=self.api_key,
                        api_secret=self.api_secret,
                    )
                    logger.info("✓ 시장 게이트(VIX/SPY) 초기화 완료")
                except Exception as e:
                    self.market_gate = None
                    logger.warning(f"시장 게이트 초기화 실패 (무시): {e}")
            else:
                self.market_gate = None

            # AI 뉴스 분석기 (선택적)
            if AI_SCORING_AVAILABLE:
                try:
                    self.news_analyzer = NewsAnalyzer()
                    logger.info("✓ AI 뉴스 분석기 초기화 완료")
                except Exception as e:
                    self.news_analyzer = None
                    logger.warning(f"AI 뉴스 분석기 초기화 실패 (무시): {e}")
            else:
                self.news_analyzer = None

            # 고주기 모니터 (Stage 2)
            self.high_freq_monitor = HighFrequencyMonitor(
                api_key=self.api_key,
                api_secret=self.api_secret,
                monitor_interval=self.monitor_interval,
                price_change_threshold=self.price_change_threshold,
                callback=self._on_price_spike  # 신호 발생 시 콜백
            )
            logger.info("✓ 고주기 모니터 초기화 완료")

            # NEW-02: WebSocket 실시간 SL/TP 모니터 (폴백: 30초 폴링)
            try:
                self.ws_monitor = WebSocketPriceMonitor(
                    api_key=self.api_key,
                    api_secret=self.api_secret,
                    on_sl_hit=self._on_ws_sl_hit,
                    stop_loss_pct=self.stop_loss_percent,
                    trailing_stop_pct=self.trailing_stop_pct,
                    partial_tp_pct=self.partial_take_profit_pct,
                )
                logger.info("✓ WebSocket 실시간 SL/TP 모니터 초기화 완료")
            except Exception as e:
                self.ws_monitor = None
                logger.warning(f"WebSocket 모니터 초기화 실패 (폴링 폴백): {e}")

        except Exception as e:
            logger.error(f"✗ Monitoring System 초기화 실패: {e}")
            raise

    def _init_database(self):
        """
        DB 연결 초기화 - backend 패키지 없이 mysql.connector 직접 사용.
        환경변수: MYSQL_URL(또는 DATABASE_URL) 또는 MYSQL_HOST/PORT/USER/PASSWORD/DATABASE
        """
        try:
            import mysql.connector
            from urllib.parse import urlparse

            db_url = os.getenv("MYSQL_URL") or os.getenv("DATABASE_URL")
            if db_url and "mysql" in db_url:
                for prefix in ("mysql2://", "mysql+pymysql://", "mariadb://"):
                    if db_url.startswith(prefix):
                        db_url = "mysql://" + db_url[len(prefix):]
                        break
                p = urlparse(db_url)
                host = p.hostname or "localhost"
                port = p.port or 3306
                user = p.username or "root"
                password = p.password or ""
                database = p.path[1:] if p.path else "trading_db"
            else:
                host     = os.getenv("MYSQL_HOST", "localhost")
                port     = int(os.getenv("MYSQL_PORT", "3306"))
                user     = os.getenv("MYSQL_USER", "root")
                password = os.getenv("MYSQL_PASSWORD", "")
                database = os.getenv("MYSQL_DATABASE", "trading_db")

            conn = mysql.connector.connect(
                host=host, port=port, user=user,
                password=password, database=database,
                charset="utf8mb4", autocommit=False,
            )
            conn.close()  # 연결 테스트만

            self._db_cfg = {
                "host": host, "port": port, "user": user,
                "password": password, "database": database,
            }
            logger.info(f"✓ DB 연결 확인 완료: {host}:{port}/{database}")

        except Exception as e:
            self._db_cfg = None
            logger.error(
                f"✗ DB 연결 실패 - 거래 로그 비활성화: {e}\n"
                "  → MYSQL_URL 또는 DATABASE_URL 환경변수를 확인하세요.\n"
                "  → 일일 리포트에 거래가 표시되지 않습니다."
            )

    def _log_trade_to_db(self, symbol: str, action: str, quantity: int,
                         price: float, pnl: float = None, order_id: str = None,
                         reason: str = None):
        """DB에 거래 기록 (실패해도 봇 동작 유지)"""
        if self._db_cfg is None:
            return
        try:
            import mysql.connector
            conn = mysql.connector.connect(**self._db_cfg, autocommit=False)
            cursor = conn.cursor()
            sql = """
                INSERT INTO trading_logs
                    (symbol, action, quantity, price, amount,
                     order_id, status, pnl, strategy_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            action_upper = action.upper()
            valid_actions = ("BUY", "SELL", "STOP_LOSS", "TAKE_PROFIT")
            if action_upper not in valid_actions:
                action_upper = "SELL"
            cursor.execute(sql, (
                symbol, action_upper, quantity, price,
                quantity * price,
                order_id, "FILLED", pnl,
                "auto_trading_bot_v2",
            ))
            conn.commit()
            row_id = cursor.lastrowid
            cursor.close()
            conn.close()
            logger.debug(f"[DB] {action_upper} {symbol} x{quantity} 기록 완료 (id={row_id})")
        except Exception as e:
            logger.error(f"[DB] {action} {symbol} 거래 로그 저장 실패: {e}")

    async def _on_price_spike(self, signal: dict):
        """
        가격 급등/급락 감지 시 콜백

        Args:
            signal: {
                'symbol': str,
                'prev_price': float,
                'current_price': float,
                'change_percent': float,
                'direction': 'UP' or 'DOWN',
                'timestamp': datetime,
                'reason': str
            }
        """
        logger.warning(f"\n{'=' * 70}")
        logger.warning(f"⚡ 가격 급변 감지!")
        logger.warning(f"  종목: {signal['symbol']}")
        logger.warning(f"  변동: {signal['change_percent']:+.2f}% ({signal['direction']})")
        logger.warning(f"  가격: ${signal['prev_price']:.2f} → ${signal['current_price']:.2f}")
        logger.warning(f"  시각: {signal['timestamp'].strftime('%H:%M:%S')}")
        logger.warning(f"{'=' * 70}\n")

        # 리스크 체크
        if not self.check_risk_limits():
            logger.error("리스크 한계 초과 - 거래 중단")
            return

        # 자동매매 활성화 확인
        if not self.auto_trading_enabled:
            logger.warning("⚠️ 자동매매 비활성화 - 시뮬레이션 모드")
            return

        # 매매 신호 생성 및 실행
        try:
            # 상승일 때만 매수 (하락은 공매도 필요)
            if signal['direction'] == 'UP':
                await self._execute_buy_signal(signal)
            else:
                logger.info(f"하락 신호는 현재 무시 (공매도 미지원)")

        except Exception as e:
            logger.error(f"신호 처리 중 오류: {e}")

    async def _execute_buy_signal(self, signal: dict):
        """
        매수 신호 실행

        Args:
            signal: 가격 급등 신호
        """
        symbol = signal['symbol']

        # 매수 주문 처리 중 중복 방지
        if symbol in self._pending_buy_symbols:
            logger.info(f"{symbol} 매수 주문 처리 중 - 중복 신호 무시")
            return
        self._pending_buy_symbols.add(symbol)

        try:
            await self._execute_buy_signal_inner(signal)
        finally:
            self._pending_buy_symbols.discard(symbol)

    def _reset_daily_counts_if_needed(self):
        """날짜 변경 시 일일 거래 카운터 초기화"""
        today = datetime.now().strftime("%Y-%m-%d")
        if self._last_trade_date != today:
            self._daily_entry_count = 0
            self._daily_exit_count = 0
            self._last_trade_date = today
            logger.info(f"[NEW-04] 일일 거래 카운터 초기화 ({today})")

    async def _execute_buy_signal_inner(self, signal: dict):
        """매수 신호 실행 (내부)"""
        symbol = signal['symbol']

        # V4 진입 시간 필터: 09:30+entry_start ~ entry_end ET 사이만 허용
        try:
            from zoneinfo import ZoneInfo
            _et_tz = ZoneInfo("America/New_York")
        except ImportError:
            import pytz
            _et_tz = pytz.timezone("America/New_York")
        _now_et = datetime.now(_et_tz)
        _entry_open = _now_et.replace(
            hour=9, minute=30 + self.v4_entry_start_minute, second=0, microsecond=0
        )
        _entry_close = _now_et.replace(
            hour=self.v4_entry_end_hour, minute=self.v4_entry_end_minute, second=0, microsecond=0
        )
        if self._is_market_hours() and not (_entry_open <= _now_et <= _entry_close):
            logger.info(
                f"{symbol} 진입 시간 외 — "
                f"허용: {_entry_open.strftime('%H:%M')}~{_entry_close.strftime('%H:%M')} ET, "
                f"현재: {_now_et.strftime('%H:%M')} ET"
            )
            return

        # NEW-04: 날짜 초기화 및 일일 진입 횟수 체크
        self._reset_daily_counts_if_needed()
        if self._daily_entry_count >= self.max_entries_per_day:
            logger.info(
                f"{symbol} 매수 신호 무시 - 일일 최대 진입 횟수 도달 "
                f"({self._daily_entry_count}/{self.max_entries_per_day})"
            )
            return

        # 거래 가능 시간 체크 (장중 또는 프리/애프터마켓만 허용)
        if not self._is_market_hours() and not self._is_extended_hours():
            logger.info(f"{symbol} 매수 신호 무시 - 거래 불가 시간 (ET 기준 장외시간)")
            return

        # 포지션 수 확인
        positions = self.execution_engine.get_positions()
        if len(positions) >= self.max_positions:
            logger.warning(f"최대 포지션 수 도달 ({len(positions)}/{self.max_positions}) - 매수 불가")
            return

        # 이미 보유 중인지 확인
        if any(p.symbol == symbol for p in positions):
            logger.info(f"{symbol} 이미 보유 중 - 중복 매수 방지")
            return

        # ── IMP-02: Gap & Go vs Gap & Fade 방향 검증 ──────────
        gap_pct = signal.get('change_percent', signal.get('gap_pct', 0.0))
        if self.gap_validator and self._is_market_hours() and gap_pct != 0:
            loop = asyncio.get_event_loop()
            is_gap_go = await loop.run_in_executor(
                None, self.gap_validator.validate_gap_direction, symbol, gap_pct
            )
            if not is_gap_go:
                logger.info(f"{symbol} Gap & Fade 감지 - 진입 거부")
                return

        # 쿨다운 체크 (최근 매도 종목 재진입 방지)
        if symbol in self._recently_sold:
            elapsed = (datetime.now() - self._recently_sold[symbol]).total_seconds() / 60.0
            if elapsed < self.trade_cooldown_minutes:
                remaining = self.trade_cooldown_minutes - elapsed
                logger.info(
                    f"{symbol} 쿨다운 중 - 재진입 차단 "
                    f"(남은 시간: {remaining:.0f}분 / 총 {self.trade_cooldown_minutes}분)"
                )
                return

        # ── BLOCK-02: strategy_type 조회 + 전략 엔진 점수 검증 ──────────────
        strategy_type = self._get_strategy_type(symbol)
        if self.signal_generator is not None:
            try:
                loop = asyncio.get_event_loop()
                bars_df = await loop.run_in_executor(
                    None, self._fetch_ohlcv_for_scoring, symbol
                )
                if bars_df is not None and len(bars_df) >= 50:
                    validated = self.signal_generator.generate_buy_signal(
                        symbol, bars_df, strategy_type=strategy_type
                    )
                    if validated is None:
                        logger.info(
                            f"{symbol} strategy_engine 점수 미달 "
                            f"(strategy_type={strategy_type}) — 진입 거부"
                        )
                        return
                    logger.info(
                        f"{symbol} strategy_engine 점수 통과: "
                        f"{validated.score:.1f} (strategy_type={strategy_type})"
                    )
                else:
                    logger.warning(
                        f"{symbol} OHLCV 부족 — strategy_engine 점수 검증 생략 "
                        f"(strategy_type={strategy_type})"
                    )
            except Exception as _se:
                logger.warning(
                    f"{symbol} strategy_engine 점수 검증 실패 (계속 진행): {_se}"
                )

        # 투자 금액 계산
        account = self.execution_engine.get_account()
        current_cash = account.cash
        investment_amount = current_cash * (self.max_investment_percent / 100.0)

        # 수량 계산
        quantity = int(investment_amount / signal['current_price'])
        if quantity == 0:
            logger.warning(f"투자 금액 부족: ${investment_amount:.2f} < ${signal['current_price']:.2f}")
            return

        # 주문 생성 (장중: 시장가 / 장외: 지정가 + extended_hours)
        is_market = self._is_market_hours()
        if is_market:
            order_signal = OrderSignal(
                symbol=symbol,
                action=OrderAction.BUY,
                order_type=OrderType.MARKET,
                quantity=quantity,
                strategy_id="high_freq_monitor_v2",
                reason=signal['reason']
            )
            session_label = "장중(시장가)"
        else:
            # 장외: 현재가 기준 +0.5% 슬리피지 허용 지정가
            limit_price = round(signal['current_price'] * 1.005, 2)
            order_signal = OrderSignal(
                symbol=symbol,
                action=OrderAction.BUY,
                order_type=OrderType.LIMIT,
                quantity=quantity,
                limit_price=limit_price,
                extended_hours=True,
                strategy_id="high_freq_monitor_v2",
                reason=signal['reason']
            )
            session_label = f"장외(지정가 ${limit_price:.2f})"

        logger.info(f"\n매수 주문 실행 [{session_label}]:")
        logger.info(f"  종목: {symbol}")
        logger.info(f"  전략: {strategy_type}")
        logger.info(f"  수량: {quantity}주")
        logger.info(f"  예상 투자금: ${investment_amount:.2f}")
        logger.info(f"  이유: {signal['reason']}")

        # 주문 실행
        result = self.execution_engine.execute_order(order_signal)

        from execution_team.core.order_models import OrderStatus as _OS
        if result.success:
            filled_price = result.filled_price
            filled_qty = result.filled_quantity or 0
            is_filled = (result.status == _OS.FILLED and filled_qty > 0)

            if is_filled:
                logger.info(f"✓ 매수 체결 완료!")
                logger.info(f"  주문 ID: {result.order_id}")
                logger.info(f"  체결가: ${filled_price:.2f}")
                logger.info(f"  체결 수량: {filled_qty}주")
                self.trade_count += 1
                self._daily_entry_count += 1
                # IMP-03: 최고가 초기화 (trailing stop 기준점)
                self._highest_price[symbol] = filled_price
                self._partial_tp_done.discard(symbol)
                # V4 Multi-Day: 진입일 기록 (hold_days 카운트 기준)
                from datetime import date as _d
                self._position_entry_date[symbol] = _d.today()
                self._log_trade_to_db(
                    symbol=symbol, action="BUY",
                    quantity=filled_qty, price=filled_price,
                    order_id=result.order_id, reason=signal.get('reason'),
                )
                self._send_telegram_notify("buy", symbol=symbol,
                                           filled_price=filled_price,
                                           quantity=filled_qty,
                                           reason=signal.get('reason'))
            else:
                logger.info(f"✓ 매수 주문 접수 (미체결 대기)")
                logger.info(f"  주문 ID: {result.order_id}")
                logger.info(f"  상태: {result.status}")
                # 체결 알림 없음 - 실제로 체결되지 않았으므로
        else:
            logger.error(f"✗ 매수 실패: {result.error_message}")
            self._send_telegram_notify("error", context=f"매수 실패 ({symbol})",
                                       error=result.error_message or "")

    def _send_telegram_notify(self, ntype: str, **kwargs):
        """텔레그램 알림 발송 (notification_team HTTP API 호출)"""
        import threading, requests, os
        notification_url = os.getenv("NOTIFICATION_URL", "http://localhost:8005")

        def _post():
            try:
                if ntype == "buy":
                    requests.post(f"{notification_url}/notify/buy", json={
                        "symbol": kwargs.get("symbol"),
                        "filled_price": kwargs.get("filled_price", 0),
                        "quantity": kwargs.get("quantity", 0),
                        "reason": kwargs.get("reason"),
                    }, timeout=5)
                elif ntype == "sell":
                    requests.post(f"{notification_url}/notify/sell", json={
                        "symbol": kwargs.get("symbol"),
                        "filled_price": kwargs.get("filled_price", 0),
                        "quantity": kwargs.get("quantity", 0),
                        "pnl": kwargs.get("pnl", 0),
                        "pnl_pct": kwargs.get("pnl_pct", 0),
                        "sell_type": kwargs.get("sell_type", "SELL"),
                    }, timeout=5)
                elif ntype == "error":
                    requests.post(f"{notification_url}/notify/error", json={
                        "context": kwargs.get("context", ""),
                        "error": kwargs.get("error", ""),
                    }, timeout=5)
            except Exception as e:
                logger.warning(f"텔레그램 알림 발송 실패 (무시): {e}")

        threading.Thread(target=_post, daemon=True).start()

    async def _apply_ai_scoring(self, watchlist: List[Dict]) -> List[Dict]:
        """
        AI 뉴스 감성 분석으로 워치리스트 필터링 및 재점수화

        gap/volume 필터를 통과한 후보에 대해서만 실행.
        - 부정 감성 점수 < -0.3이면 해당 종목 제거 (hard gate)
        - 나머지 종목은 감성 점수로 최대 ±30% 보정 및 재정렬
        - 분석 실패 시 원본 순위 유지 (safe fallback)
        """
        if not watchlist or not self.news_analyzer:
            return watchlist

        # 비용 절감: 상위 N개만 AI 분석 (한 번에 살 수 있는 종목은 1개)
        # 나머지는 gap/volume 점수 그대로 워치리스트에 유지
        MAX_AI_ANALYZE = int(os.getenv("MAX_AI_ANALYZE", "5"))
        tail = watchlist[MAX_AI_ANALYZE:]  # AI 분석 생략 종목
        candidates = watchlist[:MAX_AI_ANALYZE]

        logger.info(
            f"AI 뉴스 감성 분석 중 ({len(candidates)}개 종목, "
            f"상위 {MAX_AI_ANALYZE}개만 분석 / 전체 {len(watchlist)}개)..."
        )

        AI_BLOCK_THRESHOLD = -0.3  # 이 점수 미만이면 매수 차단

        loop = asyncio.get_event_loop()
        approved = []
        for stock in candidates:
            symbol = stock['symbol']
            try:
                # NEW-03: 갭 감지 시각을 gap_time으로 전달 (타이밍 필터)
                gap_time = stock.get('detected_at', datetime.now())
                sentiment = await asyncio.wait_for(
                    loop.run_in_executor(
                        None,
                        self.news_analyzer.analyze_news_sentiment,
                        symbol,
                        gap_time,
                    ),
                    timeout=10.0
                )
                score = sentiment.get('sentiment_score', 0.0)
                label = sentiment.get('sentiment_label', 'neutral')

                stock['ai_sentiment'] = score
                stock['ai_label'] = label

                # hard gate: 부정 감성이 임계값 미만이면 워치리스트에서 제거
                if score < AI_BLOCK_THRESHOLD:
                    logger.warning(
                        f"[AI 차단] {symbol}: 감성 점수 {score:+.2f} < {AI_BLOCK_THRESHOLD} "
                        f"({label}) → 워치리스트 제외"
                    )
                    continue

                # score 보정: 긍정(+1.0)이면 최대 +30%, 부정(-1.0)이면 최대 -30%
                stock['score'] = stock['volume_ratio'] * (1.0 + score * 0.3)
                stock['reason'] += f" | 감성:{label}({score:+.1f})"
                approved.append(stock)

            except asyncio.TimeoutError:
                logger.debug(f"{symbol}: AI 분석 타임아웃 - 원본 점수 유지 (통과)")
                approved.append(stock)
            except Exception as e:
                logger.debug(f"{symbol}: AI 분석 오류 - {e} (원본 점수 유지, 통과)")
                approved.append(stock)

        removed = len(candidates) - len(approved)
        if removed:
            logger.info(f"AI 감성 필터: {removed}개 종목 제거됨")

        # AI 보정된 score로 재정렬 후, 분석 생략 종목을 뒤에 붙임
        approved.sort(key=lambda x: x['score'], reverse=True)
        result = approved + tail
        logger.info(
            f"AI 감성 분석 완료: {len(approved)}개 통과 + {len(tail)}개 미분석 = "
            f"총 {len(result)}개 워치리스트"
        )
        return result

    def _get_strategy_type(self, symbol: str) -> str:
        """symbol의 전략 유형 반환 (BLOCK-02). 매핑 없으면 'momentum'."""
        return self._symbol_strategy_types.get(symbol, "momentum")

    def _fetch_ohlcv_for_scoring(self, symbol: str):
        """strategy_engine 점수 계산용 일봉 OHLCV DataFrame 반환 (동기)."""
        try:
            from alpaca.data import StockHistoricalDataClient
            from alpaca.data.requests import StockBarsRequest
            from alpaca.data.timeframe import TimeFrame
            from datetime import timedelta
            import pandas as pd

            client = StockHistoricalDataClient(self.api_key, self.api_secret)
            end = datetime.utcnow()
            start = end - timedelta(days=90)  # 약 60 거래일 확보
            req = StockBarsRequest(
                symbol_or_symbols=[symbol],
                timeframe=TimeFrame.Day,
                start=start,
                end=end,
            )
            bars = client.get_stock_bars(req)
            symbol_bars = bars.get(symbol, [])
            if not symbol_bars:
                return None
            df = pd.DataFrame([{
                'open': float(b.open), 'high': float(b.high),
                'low': float(b.low), 'close': float(b.close),
                'volume': float(b.volume),
            } for b in symbol_bars])
            df.index = pd.to_datetime([b.timestamp for b in symbol_bars])
            return df
        except Exception as e:
            logger.debug(f"{symbol} OHLCV fetch 실패: {e}")
            return None

    def check_risk_limits(self) -> bool:
        """
        리스크 한계 확인

        기획서 요구사항:
        - 1회 투자: 10%
        - 손절: -2%
        - 하루 손실: -5%
        """
        account = self.execution_engine.get_account()
        current_cash = account.cash

        # 일일 손실 계산
        self.daily_pl = account.unrealized_pl

        # 손실 한계
        max_loss_amount = current_cash * (self.max_daily_loss_percent / 100.0)

        if abs(self.daily_pl) > max_loss_amount:
            logger.error(f"⚠️ 일일 최대 손실 도달!")
            logger.error(f"  현재 손익: ${self.daily_pl:,.2f}")
            logger.error(f"  한계: ${max_loss_amount:,.2f} ({self.max_daily_loss_percent}%)")
            return False

        # 개별 포지션 손절 체크
        # unrealized_plpc: Alpaca가 제공하는 수익률 (소수점, 예: -0.02 = -2%)
        # cost_basis는 일부 환경에서 누락될 수 있으므로 unrealized_plpc 사용
        positions = self.execution_engine.get_positions()
        for position in positions:
            try:
                position_pl_percent = float(position.unrealized_plpc) * 100.0
            except (AttributeError, TypeError, ValueError):
                cost_basis = getattr(position, 'cost_basis', None)
                if cost_basis and float(cost_basis) != 0:
                    position_pl_percent = (float(position.unrealized_pl) / float(cost_basis)) * 100.0
                else:
                    continue

            if position_pl_percent < -self.stop_loss_percent:
                logger.warning(f"⚠️ {position.symbol} 손절 실행: {position_pl_percent:.2f}%")
                if self.auto_trading_enabled:
                    self._execute_stop_loss(position)
                else:
                    logger.warning(f"  (시뮬레이션 모드 - 실제 손절 미실행)")

        return True

    def _execute_stop_loss(self, position):
        """
        손절 주문 실행

        Args:
            position: Alpaca position 객체
        """
        symbol = position.symbol
        try:
            qty = int(float(position.qty))
            if qty <= 0:
                return

            order_signal = OrderSignal(
                symbol=symbol,
                action=OrderAction.SELL,
                order_type=OrderType.MARKET,
                quantity=qty,
                strategy_id="stop_loss",
                reason=f"손절: {float(position.unrealized_plpc) * 100:.2f}%"
            )
            result = self.execution_engine.execute_order(order_signal)
            if result.success:
                logger.warning(f"✓ {symbol} 손절 완료: {qty}주 @ ${result.filled_price:.2f}" if result.filled_price is not None else f"✓ {symbol} 손절 완료: {qty}주 @ (미체결)")
                # 쿨다운 등록
                self._recently_sold[symbol] = datetime.now()
                logger.info(f"[쿨다운 등록] {symbol} → {self.trade_cooldown_minutes}분간 재매수 차단")
                self._send_telegram_notify(
                    "sell",
                    symbol=symbol,
                    filled_price=result.filled_price or 0,
                    quantity=qty,
                    pnl=float(position.unrealized_pl),
                    pnl_pct=float(position.unrealized_plpc) * 100,
                    sell_type="STOP_LOSS"
                )
            else:
                logger.error(f"✗ {symbol} 손절 실패: {result.error_message}")
        except Exception as e:
            logger.error(f"{symbol} 손절 처리 중 오류: {e}")

    def _is_market_hours(self) -> bool:
        """미국 시장 시간인지 확인 (간단 체크)"""
        try:
            from zoneinfo import ZoneInfo
            et_tz = ZoneInfo("America/New_York")
        except ImportError:
            import pytz
            et_tz = pytz.timezone("America/New_York")

        now_et = datetime.now(et_tz)

        # 주말 체크
        if now_et.weekday() >= 5:  # 토요일(5), 일요일(6)
            return False

        # 시장 시간: 9:30 AM ~ 4:00 PM ET
        market_open = now_et.replace(hour=9, minute=30, second=0)
        market_close = now_et.replace(hour=16, minute=0, second=0)

        return market_open <= now_et <= market_close

    def _is_extended_hours(self) -> bool:
        """
        장외거래 가능 시간 여부 (프리마켓 4AM~9:30AM ET, 애프터마켓 4PM~8PM ET)
        장중 시간은 False 반환 (market order 사용)
        """
        try:
            from zoneinfo import ZoneInfo
            et_tz = ZoneInfo("America/New_York")
        except ImportError:
            import pytz
            et_tz = pytz.timezone("America/New_York")

        from datetime import time as dtime
        now_et = datetime.now(et_tz)

        if now_et.weekday() >= 5:
            return False

        t = now_et.time()
        premarket  = dtime(4, 0) <= t < dtime(9, 30)
        afterhours = dtime(16, 0) <= t < dtime(20, 0)
        return premarket or afterhours

    async def _stop_loss_monitor(self):
        """
        손절/익절 전용 독립 루프 (30초마다 실행)

        워치리스트와 무관하게 모든 보유 포지션을 체크.
        - 장중: market order
        - 장외(프리마켓/애프터마켓): limit order + extended_hours=True
        - 거래 불가 시간(새벽 등): 스킵
        """
        INTERVAL = 30  # 초
        while self.is_running:
            try:
                await asyncio.sleep(INTERVAL)
            except asyncio.CancelledError:
                break

            if not self.auto_trading_enabled:
                continue

            # 주말이면 긴 시간 대기
            try:
                from zoneinfo import ZoneInfo
                _et = ZoneInfo("America/New_York")
            except ImportError:
                import pytz
                _et = pytz.timezone("America/New_York")
            if datetime.now(_et).weekday() >= 5:
                await asyncio.sleep(3600)  # 1시간마다 재확인
                continue

            is_market = self._is_market_hours()
            is_extended = self._is_extended_hours()

            if not is_market and not is_extended:
                continue  # 거래 불가 시간 (새벽 등) 스킵

            try:
                loop = asyncio.get_event_loop()

                # ── pending_sell_symbols 정리: Alpaca open orders 확인 ──
                try:
                    all_open = await loop.run_in_executor(
                        None, lambda: self.broker.api.list_orders(status='open')
                    )
                    open_sell_symbols = {
                        o.symbol for o in all_open
                        if getattr(o, 'side', '') == 'sell'
                    }
                    # 체결 완료된 종목은 pending에서 제거
                    completed = self._pending_sell_symbols - open_sell_symbols
                    if completed:
                        self._pending_sell_symbols -= completed
                        logger.info(f"[pending 정리] 체결 완료 종목: {completed}")
                except Exception as _e:
                    logger.debug(f"open orders 전체 조회 실패 (무시): {_e}")

                positions = await loop.run_in_executor(
                    None, self.broker.api.list_positions
                )

                # ── V4 보유일 복구: 재시작 시 _position_entry_date에 없는 종목은
                #    Alpaca position.entry_at 에서 진입일 추출 ──────────────────
                from datetime import date as _today_date
                for _pos in positions:
                    _sym = _pos.symbol
                    if _sym not in self._position_entry_date:
                        try:
                            _entry_at = getattr(_pos, 'entry_at', None) or getattr(_pos, 'created_at', None)
                            if _entry_at:
                                if hasattr(_entry_at, 'date'):
                                    self._position_entry_date[_sym] = _entry_at.date()
                                else:
                                    from datetime import datetime as _dt
                                    self._position_entry_date[_sym] = _dt.fromisoformat(str(_entry_at)[:10]).date()
                            else:
                                # entry_at 없으면 현재가 기준 (보수적: hold_days=0)
                                self._position_entry_date[_sym] = _today_date.today()
                        except Exception:
                            self._position_entry_date[_sym] = _today_date.today()
                        logger.info(f"[복구] {_sym} 진입일: {self._position_entry_date[_sym]}")
                    # _highest_price 복구: 없으면 현재가로 초기화 (trailing 약간 느슨)
                    if _sym not in self._highest_price:
                        try:
                            _cur = float(getattr(_pos, 'current_price', 0) or 0)
                            if _cur > 0:
                                self._highest_price[_sym] = _cur
                                logger.info(f"[복구] {_sym} 최고가: ${_cur:.2f} (현재가 기준 초기화)")
                        except Exception:
                            pass

                # ── V4 EOD 강제 청산: 15:55 ET, max_hold_days 초과 포지션만 ──
                now_et_eod = datetime.now(_et)
                _eod_h, _eod_m = now_et_eod.hour, now_et_eod.minute
                _is_eod_window = is_market and (_eod_h == 15 and _eod_m >= 55)
                if _is_eod_window:
                    from datetime import date as _d2
                    _today = _d2.today()
                    for _pos in positions:
                        _sym = _pos.symbol
                        _entry = self._position_entry_date.get(_sym)
                        if _entry is None:
                            continue
                        _hold = (_today - _entry).days
                        if _hold < self.v4_max_hold_days:
                            continue
                        if _sym in self._pending_sell_symbols:
                            continue
                        try:
                            _qty = int(float(_pos.qty))
                            _px  = float(getattr(_pos, 'current_price', 0) or 0)
                            self._pending_sell_symbols.add(_sym)
                            await loop.run_in_executor(
                                None,
                                lambda s=_sym, q=_qty: self.broker.api.submit_order(
                                    symbol=s, qty=q, side='sell',
                                    type='market', time_in_force='day'
                                )
                            )
                            logger.warning(
                                f"[EOD 강제 청산] {_sym} | 보유 {_hold}일 ≥ {self.v4_max_hold_days}일 → 시장가 매도"
                            )
                            self._position_entry_date.pop(_sym, None)
                            self._highest_price.pop(_sym, None)
                            self._partial_tp_done.discard(_sym)
                            self._daily_exit_count += 1
                            _unrealized = float(getattr(_pos, 'unrealized_pl', 0) or 0)
                            _pl_pct = float(getattr(_pos, 'unrealized_plpc', 0) or 0) * 100
                            self._log_trade_to_db(
                                symbol=_sym, action="EOD_FORCE",
                                quantity=_qty, price=_px, pnl=_unrealized,
                                reason=f"V4 max_hold {_hold}일 초과"
                            )
                            self._send_telegram_notify(
                                "sell", symbol=_sym, filled_price=_px,
                                quantity=_qty, pnl=_unrealized,
                                pnl_pct=_pl_pct, sell_type="EOD_FORCE"
                            )
                        except Exception as _eoderr:
                            self._pending_sell_symbols.discard(_sym)
                            logger.error(f"[EOD 강제 청산] {_sym} 주문 실패: {_eoderr}")

                for position in positions:
                    try:
                        pl_pct = float(position.unrealized_plpc) * 100.0
                        current_price = float(getattr(position, 'current_price', 0) or 0)
                    except (AttributeError, TypeError, ValueError):
                        continue

                    symbol = position.symbol
                    qty = int(float(position.qty))
                    sell_type = None

                    # ── 손절 체크 (고정 SL) ───────────────────────────────
                    if pl_pct < -self.stop_loss_percent:
                        sell_type = "STOP_LOSS"
                        logger.warning(
                            f"[손절] {symbol}: {pl_pct:.2f}% "
                            f"(기준: -{self.stop_loss_percent}%) → 매도"
                        )

                    # ── IMP-03: Trailing Stop + 부분 청산 ────────────────
                    elif current_price > 0:
                        # 최고가 갱신
                        prev_high = self._highest_price.get(symbol, current_price)
                        if current_price > prev_high:
                            self._highest_price[symbol] = current_price
                            prev_high = current_price

                        trailing_stop_price = prev_high * (1 - self.trailing_stop_pct / 100)

                        # +3% 부분 청산 (50%) - 아직 미실행인 경우
                        if (pl_pct >= self.partial_take_profit_pct
                                and symbol not in self._partial_tp_done
                                and qty >= 2):
                            partial_qty = qty // 2
                            logger.warning(
                                f"[부분익절] {symbol}: {pl_pct:.2f}% ≥ "
                                f"+{self.partial_take_profit_pct}% → {partial_qty}주 50% 청산"
                            )
                            self._partial_tp_done.add(symbol)
                            # 부분 청산 실행
                            try:
                                if is_market:
                                    await loop.run_in_executor(
                                        None,
                                        lambda s=symbol, q=partial_qty: self.broker.api.submit_order(
                                            symbol=s, qty=q, side='sell',
                                            type='market', time_in_force='day'
                                        )
                                    )
                                else:
                                    lp = round(current_price * 0.995, 2)
                                    await loop.run_in_executor(
                                        None,
                                        lambda s=symbol, q=partial_qty, p=lp: self.broker.api.submit_order(
                                            symbol=s, qty=q, side='sell',
                                            type='limit', time_in_force='day',
                                            limit_price=p, extended_hours=True
                                        )
                                    )
                                logger.warning(f"[부분익절] {symbol} {partial_qty}주 주문 완료")
                                self._daily_exit_count += 1
                            except Exception as _pe:
                                self._partial_tp_done.discard(symbol)
                                logger.error(f"[부분익절] {symbol} 주문 실패: {_pe}")
                            continue

                        # Trailing Stop 히트 (V4 백테스트 동일: 손실 구간도 작동)
                        if current_price <= trailing_stop_price:
                            sell_type = "TRAILING_STOP"
                            logger.warning(
                                f"[트레일링스탑] {symbol}: 현재가 ${current_price:.2f} ≤ "
                                f"트레일링스탑 ${trailing_stop_price:.2f} "
                                f"(최고가 ${prev_high:.2f} × {100-self.trailing_stop_pct}%) → 매도"
                            )

                    if sell_type is None:
                        continue

                    # ── 중복 주문 방지: Alpaca open orders 직접 조회 ──
                    # in-memory set만으로는 배포 전 기존 미체결 주문을 감지 못하므로
                    # 항상 Alpaca API로 실제 open sell 주문 여부를 확인한다.
                    try:
                        open_orders = await loop.run_in_executor(
                            None,
                            lambda s=symbol: self.broker.api.list_orders(
                                status='open', symbols=[s]
                            )
                        )
                        has_open_sell = any(
                            getattr(o, 'side', '') == 'sell' for o in open_orders
                        )
                    except Exception as _oe:
                        logger.debug(f"{symbol} open orders 조회 실패 (계속 진행): {_oe}")
                        has_open_sell = symbol in self._pending_sell_symbols

                    if has_open_sell:
                        logger.info(
                            f"[{sell_type}] {symbol} 미체결 매도 주문 존재 - 중복 주문 스킵"
                        )
                        self._pending_sell_symbols.add(symbol)  # 동기화
                        continue

                    # NEW-04: 일일 청산 횟수 체크
                    self._reset_daily_counts_if_needed()
                    if self._daily_exit_count >= self.max_exits_per_day:
                        logger.warning(
                            f"[{sell_type}] {symbol} - 일일 최대 청산 횟수 도달 "
                            f"({self._daily_exit_count}/{self.max_exits_per_day}), 스킵"
                        )
                        continue

                    try:
                        current_price = float(getattr(position, 'current_price', 0) or 0)
                        unrealized_pl = float(getattr(position, 'unrealized_pl', 0) or 0)

                        # 미체결 주문 추적 등록
                        self._pending_sell_symbols.add(symbol)

                        if is_market:
                            # 장중: 시장가 주문
                            order = await loop.run_in_executor(
                                None,
                                lambda s=symbol, q=qty: self.broker.api.submit_order(
                                    symbol=s,
                                    qty=q,
                                    side='sell',
                                    type='market',
                                    time_in_force='day'
                                )
                            )
                        else:
                            # 장외: 지정가 주문 (현재가 기준, 0.5% 슬리피지 허용)
                            limit_price = round(current_price * 0.995, 2)
                            order = await loop.run_in_executor(
                                None,
                                lambda s=symbol, q=qty, lp=limit_price: self.broker.api.submit_order(
                                    symbol=s,
                                    qty=q,
                                    side='sell',
                                    type='limit',
                                    time_in_force='day',
                                    limit_price=lp,
                                    extended_hours=True
                                )
                            )

                        session = "장중" if is_market else "장외"
                        logger.warning(
                            f"[{sell_type}] {symbol} {session} 주문 완료 "
                            f"(Alpaca ID: {order.id})"
                        )
                        # 쿨다운 등록: 매도 완료 후 동일 종목 재진입 방지
                        self._recently_sold[symbol] = datetime.now()
                        # IMP-03: 최고가/부분청산/진입일 상태 초기화
                        self._highest_price.pop(symbol, None)
                        self._partial_tp_done.discard(symbol)
                        self._position_entry_date.pop(symbol, None)
                        self._daily_exit_count += 1
                        logger.info(
                            f"[쿨다운 등록] {symbol} → {self.trade_cooldown_minutes}분간 재매수 차단"
                        )
                        # DB 거래 로그 기록
                        self._log_trade_to_db(
                            symbol=symbol, action=sell_type,
                            quantity=qty, price=current_price,
                            pnl=unrealized_pl, order_id=str(order.id),
                            reason=f"자동 {sell_type} ({pl_pct:+.2f}%)",
                        )
                        # AI 성과 추적기에 결과 기록 (in-context 학습)
                        try:
                            from ai_team.performance.tracker import performance_tracker as _pt
                            _pt.record_outcome(
                                symbol=symbol,
                                action=sell_type,
                                pnl=unrealized_pl,
                                pnl_pct=pl_pct,
                            )
                        except Exception:
                            pass
                        self._send_telegram_notify(
                            "sell",
                            symbol=symbol,
                            filled_price=current_price,
                            quantity=qty,
                            pnl=unrealized_pl,
                            pnl_pct=pl_pct,
                            sell_type=sell_type
                        )
                    except Exception as e:
                        # 주문 실패 시 pending에서 제거하여 다음 사이클에 재시도 가능하게
                        self._pending_sell_symbols.discard(symbol)
                        logger.error(f"[{sell_type}] {symbol} 주문 실패: {e}")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"손절/익절 모니터 오류: {e}")

    def _seconds_until_monday_premarket(self) -> float:
        """주말일 경우 월요일 프리마켓(ET 04:00)까지 남은 초를 반환"""
        try:
            from zoneinfo import ZoneInfo
            et_tz = ZoneInfo("America/New_York")
        except ImportError:
            import pytz
            et_tz = pytz.timezone("America/New_York")

        from datetime import timedelta
        now_et = datetime.now(et_tz)
        # 토요일=5, 일요일=6
        days_until_monday = (7 - now_et.weekday()) % 7  # 0이면 오늘이 월요일
        if days_until_monday == 0:
            days_until_monday = 7  # 이미 월요일이면 다음 주 월요일 (이 함수는 주말에만 호출)
        next_monday = (now_et + timedelta(days=days_until_monday)).replace(
            hour=4, minute=0, second=0, microsecond=0
        )
        return (next_monday - now_et).total_seconds()

    async def _stage1_market_scan(self):
        """
        Stage 1: 전체 시장 스캔 및 워치리스트 생성

        3~5분마다 실행. 주말에는 월요일 프리마켓(ET 04:00)까지 대기.
        """
        scan_count = 0
        while self.is_running:
            try:
                scan_count += 1

                # 주말 체크 — 월요일 프리마켓까지 통째로 대기
                try:
                    from zoneinfo import ZoneInfo
                    et_tz = ZoneInfo("America/New_York")
                except ImportError:
                    import pytz
                    et_tz = pytz.timezone("America/New_York")

                now_et = datetime.now(et_tz)
                if now_et.weekday() >= 5:  # 토(5), 일(6)
                    # 고주기 모니터도 중지 (장 닫힘)
                    if self.high_freq_monitor.is_running:
                        await self.high_freq_monitor.stop()
                        logger.info("주말 휴장 — 고주기 모니터 중지")

                    sleep_sec = self._seconds_until_monday_premarket()
                    wake_time = now_et + __import__('datetime').timedelta(seconds=sleep_sec)
                    logger.info(
                        f"주말 휴장 — 월요일 프리마켓({wake_time.strftime('%Y-%m-%d %H:%M ET')})까지 "
                        f"{sleep_sec / 3600:.1f}시간 대기합니다."
                    )
                    await asyncio.sleep(sleep_sec)
                    continue

                logger.info(f"\n{'=' * 70}")
                logger.info(f"[Stage 1] 전체 시장 스캔 시작")
                logger.info(f"  시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

                # 시장 시간 체크
                is_market_hours = self._is_market_hours()
                is_extended = self._is_extended_hours()
                logger.info(f"  미국 시장 시간: {'YES (장중)' if is_market_hours else 'NO (장외)'}")
                if not is_market_hours and not is_extended:
                    logger.info("  장외 시간 — 스캔 생략, 다음 주기까지 대기")
                    await asyncio.sleep(self.market_scan_interval * 60)
                    continue

                logger.info(f"{'=' * 70}")

                # ── IMP-01: VIX/SPY 하드 게이트 체크 ──────────────
                if self.market_gate:
                    loop = asyncio.get_event_loop()
                    gate_result = await loop.run_in_executor(None, self.market_gate.check)
                    if not gate_result.allowed:
                        logger.warning(
                            f"[MarketGate] 신규 진입 금지: {gate_result.reason} "
                            f"— 워치리스트 스캔 건너뜀"
                        )
                        await asyncio.sleep(self.market_scan_interval * 60)
                        continue

                # 워치리스트 생성
                watchlist = await self.watchlist_generator.generate_watchlist()

                if watchlist:
                    # BLOCK-02: 워치리스트 종목 strategy_type 업데이트
                    # WatchlistGenerator는 gap+volume 기준(momentum) 종목만 생성
                    for _s in watchlist:
                        self._symbol_strategy_types[_s['symbol']] = "momentum"

                    # 포지션 여유가 있을 때만 AI 뉴스 감성 스코어링 실행 (비용 절감)
                    positions = self.execution_engine.get_positions()
                    if len(positions) < self.max_positions:
                        watchlist = await self._apply_ai_scoring(watchlist)
                    else:
                        logger.info(
                            f"최대 포지션 도달 ({len(positions)}/{self.max_positions}) "
                            f"- AI 스코어링 생략 (신규 매수 불가)"
                        )

                    logger.info(f"\n워치리스트 갱신:")
                    for i, stock in enumerate(watchlist[:10], 1):
                        logger.info(f"  {i}. {stock['symbol']}: {stock['reason']}")

                    # Stage 2 모니터에 워치리스트 전달
                    self.high_freq_monitor.set_watchlist(watchlist)

                    # 모니터 시작 (처음만)
                    if not self.high_freq_monitor.is_running:
                        await self.high_freq_monitor.start()
                else:
                    logger.warning("워치리스트가 비어있습니다")

                # 만료된 쿨다운 항목 정리
                now = datetime.now()
                expired = [
                    s for s, t in self._recently_sold.items()
                    if (now - t).total_seconds() / 60.0 >= self.trade_cooldown_minutes
                ]
                for s in expired:
                    del self._recently_sold[s]
                    logger.info(f"[쿨다운 해제] {s} 재매수 가능")

                # 1시간마다(약 12회 스캔) 오래된 주문 메모리 정리
                if scan_count % 12 == 0 and hasattr(self, 'order_manager') and self.order_manager:
                    deleted = self.order_manager.clear_old_orders(days=7)
                    if deleted:
                        logger.info(f"[메모리 정리] 오래된 주문 {deleted}개 삭제 완료")

                # 다음 스캔까지 대기
                logger.info(f"\n다음 시장 스캔까지 {self.market_scan_interval}분 대기...")
                await asyncio.sleep(self.market_scan_interval * 60)

            except Exception as e:
                logger.error(f"Stage 1 오류: {e}")
                await asyncio.sleep(60)  # 오류 시 1분 대기

    async def _on_ws_sl_hit(self, symbol: str, price: float, reason: str):
        """WebSocket SL/TP 히트 콜백 - 즉시 청산 주문 실행"""
        if not self.auto_trading_enabled:
            logger.warning(f"[WS {reason}] {symbol} @ ${price:.2f} - 시뮬레이션 모드, 실행 안 함")
            return

        if symbol in self._pending_sell_symbols:
            logger.info(f"[WS {reason}] {symbol} - 미체결 매도 주문 존재, 스킵")
            return

        self._pending_sell_symbols.add(symbol)
        try:
            loop = asyncio.get_event_loop()
            positions = await loop.run_in_executor(None, self.broker.api.list_positions)
            pos = next((p for p in positions if p.symbol == symbol), None)
            if pos is None:
                return

            qty = int(float(pos.qty))
            # 부분 익절: 50% 수량만 청산
            if reason == "PARTIAL_TP" and qty >= 2:
                qty = qty // 2

            order = await loop.run_in_executor(
                None,
                lambda s=symbol, q=qty: self.broker.api.submit_order(
                    symbol=s, qty=q, side='sell', type='market', time_in_force='day'
                )
            )
            logger.warning(f"[WS {reason}] {symbol} {qty}주 즉시 청산 완료 (order_id={order.id})")

            if reason != "PARTIAL_TP":
                self._recently_sold[symbol] = datetime.now()
                self._highest_price.pop(symbol, None)
                self._partial_tp_done.discard(symbol)
                self._daily_exit_count += 1
            else:
                self._partial_tp_done.add(symbol)
                self._daily_exit_count += 1

            unrealized_pl = float(getattr(pos, 'unrealized_pl', 0) or 0)
            pl_pct = float(getattr(pos, 'unrealized_plpc', 0) or 0) * 100
            current_price = float(getattr(pos, 'current_price', price) or price)
            self._log_trade_to_db(
                symbol=symbol, action=reason, quantity=qty,
                price=current_price, pnl=unrealized_pl, order_id=str(order.id),
            )
            self._send_telegram_notify(
                "sell", symbol=symbol, filled_price=current_price,
                quantity=qty, pnl=unrealized_pl, pnl_pct=pl_pct, sell_type=reason,
            )
        except Exception as e:
            self._pending_sell_symbols.discard(symbol)
            logger.error(f"[WS {reason}] {symbol} 즉시 청산 실패: {e}")
        finally:
            if reason != "PARTIAL_TP":
                self._pending_sell_symbols.discard(symbol)

    async def _sync_ws_positions(self):
        """보유 포지션을 WebSocket 모니터에 동기화 (30초마다)"""
        while self.is_running:
            try:
                await asyncio.sleep(30)
                if self.ws_monitor is None:
                    continue
                loop = asyncio.get_event_loop()
                positions = await loop.run_in_executor(None, self.broker.api.list_positions)
                pos_map = {}
                for pos in positions:
                    sym = pos.symbol
                    entry_price = float(getattr(pos, 'avg_entry_price', 0) or 0)
                    current_price = float(getattr(pos, 'current_price', entry_price) or entry_price)
                    sl_price = entry_price * (1 - self.stop_loss_percent / 100)
                    pos_map[sym] = {
                        'entry_price': entry_price,
                        'sl_price': sl_price,
                        'highest_price': self._highest_price.get(sym, current_price),
                        'partial_tp_done': sym in self._partial_tp_done,
                    }
                self.ws_monitor.update_positions(pos_map)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug(f"WS 포지션 동기화 오류 (무시): {e}")

    async def run_async(self):
        """메인 비동기 루프"""
        logger.info("\n" + "=" * 70)
        logger.info("자동매매 봇 V2 시작!")
        logger.info("=" * 70)

        if not self.auto_trading_enabled:
            logger.warning("\n자동매매가 비활성화되어 있습니다")
            logger.warning("시뮬레이션 모드로 실행됩니다 (실제 주문 없음)")
            logger.warning("AUTO_TRADING_ENABLED=true로 설정하세요.\n")

        self.is_running = True

        # NEW-02: WebSocket 실시간 SL/TP 모니터 시작
        if self.ws_monitor:
            await self.ws_monitor.start()
            ws_sync_task = asyncio.create_task(
                self._sync_ws_positions(), name="ws_position_sync"
            )
        else:
            ws_sync_task = None

        # 손절 모니터를 독립 태스크로 실행 (Stage 1 오류와 무관하게 유지)
        # WebSocket 연결 장애 시 폴백으로만 동작
        stop_loss_task = asyncio.create_task(
            self._stop_loss_monitor(), name="stop_loss_monitor"
        )

        try:
            await self._stage1_market_scan()

        except asyncio.CancelledError:
            logger.info("\n태스크 취소됨")
        except Exception as e:
            logger.error(f"치명적 오류: {e}")
            import traceback
            traceback.print_exc()
        finally:
            stop_loss_task.cancel()
            if ws_sync_task:
                ws_sync_task.cancel()
            await self.cleanup()

    def run(self):
        """메인 진입점 (동기) — 텔레그램 봇을 별도 스레드로 시작 후 매매 루프 실행."""
        # 로그 감시 AI 에이전트 시작 (에러 감지 → Claude 분석 → 텔레그램 전송)
        try:
            from log_monitor_agent import start_log_monitor_thread
            start_log_monitor_thread(log_file="logs/auto_trading_v2.log")
        except Exception as e:
            logger.warning(f"로그 감시 에이전트 시작 실패 (무시): {e}")

        # 텔레그램 봇 백그라운드 스레드 시작
        telegram_thread = threading.Thread(
            target=_run_telegram_bot,
            daemon=True,
            name="TelegramBot",
        )
        telegram_thread.start()
        logger.info("✓ 텔레그램 봇 스레드 시작")

        # 알림 스케줄러 백그라운드 스레드 시작 (일일/주간 리포트)
        notification_thread = threading.Thread(
            target=_run_notification_scheduler,
            daemon=True,
            name="NotificationScheduler",
        )
        notification_thread.start()
        logger.info("✓ 알림 스케줄러 스레드 시작")

        try:
            asyncio.run(self.run_async())
        except KeyboardInterrupt:
            logger.info("\n사용자에 의해 중단됨")

    async def cleanup(self):
        """정리"""
        logger.info("\n자동매매 봇 V2 종료 중...")

        self.is_running = False

        try:
            # WebSocket 모니터 중지
            if hasattr(self, 'ws_monitor') and self.ws_monitor:
                await self.ws_monitor.stop()
                logger.info("✓ WebSocket 실시간 모니터 중지")

            # 고주기 모니터 중지
            if hasattr(self, 'high_freq_monitor'):
                await self.high_freq_monitor.stop()
                logger.info("✓ 고주기 모니터 중지")

            # 브로커 연결 해제
            if hasattr(self, 'broker'):
                self.broker.disconnect()
                logger.info("✓ 브로커 연결 해제")

        except Exception as e:
            logger.error(f"정리 중 오류: {e}")

        logger.info("✓ 자동매매 봇 V2 종료 완료")


def _run_notification_scheduler():
    """알림 스케줄러를 별도 스레드에서 실행 (일일/주간 리포트, 포지션 현황)"""
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        from notification_team.scheduler import notification_scheduler
        notification_scheduler.start()
        logger.info("✓ 알림 스케줄러 시작 완료 (일일 16:10 ET, 주간 금요일 16:30 ET)")
        loop.run_forever()
    except ImportError as e:
        logger.warning(f"⚠️ 알림 스케줄러 로드 실패 (선택적 기능): {e}")
    except Exception as e:
        logger.error(f"알림 스케줄러 오류: {e}")
    finally:
        loop.close()


def _run_telegram_bot():
    """텔레그램 봇을 별도 스레드에서 실행.

    python-telegram-bot v20+는 내부적으로 asyncio를 사용하므로
    서브 스레드에서는 전용 이벤트 루프를 생성해야 함.

    Conflict(409) 발생 시: 이전 인스턴스가 죽을 때까지 재시도 (최대 10분).
    """
    import asyncio
    import time

    deadline = time.time() + 600  # 최대 10분 대기
    while time.time() < deadline:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            from telegram_bot import main as telegram_main
            logger.info("텔레그램 봇 시작 중...")
            telegram_main()
            break  # 정상 종료 시 루프 탈출
        except ImportError as e:
            logger.warning(f"⚠️ 텔레그램 봇 모듈 로드 실패 (선택적 기능): {e}")
            break
        except Exception as e:
            err_str = str(e)
            if "Conflict" in err_str or "409" in err_str:
                remaining = int(deadline - time.time())
                logger.warning(
                    f"텔레그램 Conflict - 이전 인스턴스 종료 대기 중 "
                    f"(남은 대기: {remaining}초)..."
                )
                loop.close()
                time.sleep(30)
                continue
            else:
                logger.error(f"텔레그램 봇 오류: {e}")
                import traceback
                traceback.print_exc()
                break
        finally:
            if not loop.is_closed():
                loop.close()
    else:
        logger.error("텔레그램 봇: 10분 내 이전 인스턴스가 종료되지 않아 포기합니다.")


def main():
    """메인 함수"""
    try:
        bot = AutoTradingBotV2()
        bot.run()
    except Exception as e:
        logger.error(f"봇 시작 실패: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
