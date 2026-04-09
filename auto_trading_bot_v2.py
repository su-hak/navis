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
except ImportError as e:
    logger.error(f"Monitoring 모듈 임포트 실패: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

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

        # Stage 2 설정 (고주기 감시)
        self.monitor_interval = int(os.getenv('MONITOR_INTERVAL_SECONDS', '10'))  # 5~10초
        self.price_change_threshold = float(os.getenv('PRICE_CHANGE_THRESHOLD', '1.5'))  # 1.5%

        # 리스크 관리 (기획서: 1회 10%, 손절 -2%, 일일 -5%)
        self.max_investment_percent = float(os.getenv('MAX_INVESTMENT_PERCENT', '10.0'))
        self.stop_loss_percent = float(os.getenv('STOP_LOSS_PERCENT', '2.0'))
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
        logger.info(f"[Stage 2] 모니터링 주기: {self.monitor_interval}초")
        logger.info(f"[Stage 2] 변동 임계값: {self.price_change_threshold}%")
        logger.info(f"[리스크] 1회 투자: {self.max_investment_percent}%, 손절: -{self.stop_loss_percent}%, 일일 손실: -{self.max_daily_loss_percent}%")

        if not self.api_key or not self.api_secret:
            raise ValueError("ALPACA_API_KEY와 ALPACA_SECRET_KEY를 설정하세요")

        # 컴포넌트 초기화
        self._init_execution_team()
        self._init_monitoring_system()

        # 상태 추적
        self.daily_pl = 0.0
        self.trade_count = 0
        self.is_running = False

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
            # 워치리스트 생성기 (Stage 1)
            self.watchlist_generator = WatchlistGenerator(
                api_key=self.api_key,
                api_secret=self.api_secret,
                gap_threshold=self.gap_threshold,
                volume_ratio_threshold=self.volume_ratio_threshold,
                max_watchlist_size=self.max_watchlist_size,
                paper='paper-api' in self.base_url
            )
            logger.info("✓ 워치리스트 생성기 초기화 완료")

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

        except Exception as e:
            logger.error(f"✗ Monitoring System 초기화 실패: {e}")
            raise

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

        # 포지션 수 확인
        positions = self.execution_engine.get_positions()
        if len(positions) >= self.max_positions:
            logger.warning(f"최대 포지션 수 도달 ({len(positions)}/{self.max_positions}) - 매수 불가")
            return

        # 이미 보유 중인지 확인
        if any(p.symbol == symbol for p in positions):
            logger.info(f"{symbol} 이미 보유 중 - 중복 매수 방지")
            return

        # 투자 금액 계산
        account = self.execution_engine.get_account()
        current_cash = account.cash
        investment_amount = current_cash * (self.max_investment_percent / 100.0)

        # 수량 계산
        quantity = int(investment_amount / signal['current_price'])
        if quantity == 0:
            logger.warning(f"투자 금액 부족: ${investment_amount:.2f} < ${signal['current_price']:.2f}")
            return

        # 주문 생성
        order_signal = OrderSignal(
            symbol=symbol,
            action=OrderAction.BUY,
            order_type=OrderType.MARKET,
            quantity=quantity,
            strategy_id="high_freq_monitor_v2",
            reason=signal['reason']
        )

        logger.info(f"\n매수 주문 실행:")
        logger.info(f"  종목: {symbol}")
        logger.info(f"  수량: {quantity}주")
        logger.info(f"  예상 투자금: ${investment_amount:.2f}")
        logger.info(f"  이유: {signal['reason']}")

        # 주문 실행
        result = self.execution_engine.execute_order(order_signal)

        if result.success:
            logger.info(f"✓ 매수 성공!")
            logger.info(f"  주문 ID: {result.order_id}")
            logger.info(f"  체결가: ${result.filled_price:.2f}")
            logger.info(f"  체결 수량: {result.filled_quantity}주")
            self.trade_count += 1
        else:
            logger.error(f"✗ 매수 실패: {result.error_message}")

    async def _apply_ai_scoring(self, watchlist: List[Dict]) -> List[Dict]:
        """
        AI 뉴스 감성 분석으로 워치리스트 재점수화

        gap/volume 필터를 통과한 후보에 대해서만 실행.
        감성 점수를 volume_ratio에 최대 ±30% 보정 적용.
        분석 실패 시 원본 순위 유지.
        """
        if not watchlist or not self.news_analyzer:
            return watchlist

        logger.info(f"AI 뉴스 감성 분석 중 ({len(watchlist)}개 종목)...")

        loop = asyncio.get_event_loop()
        for stock in watchlist:
            symbol = stock['symbol']
            try:
                sentiment = await asyncio.wait_for(
                    loop.run_in_executor(
                        None,
                        self.news_analyzer.analyze_news_sentiment,
                        symbol
                    ),
                    timeout=10.0
                )
                score = sentiment.get('sentiment_score', 0.0)
                label = sentiment.get('sentiment_label', 'neutral')

                # score 보정: 긍정(+1.0)이면 최대 +30%, 부정(-1.0)이면 최대 -30%
                stock['ai_sentiment'] = score
                stock['ai_label'] = label
                stock['score'] = stock['volume_ratio'] * (1.0 + score * 0.3)

                if score != 0.0:
                    stock['reason'] += f" | 감성:{label}({score:+.1f})"

            except asyncio.TimeoutError:
                logger.debug(f"{symbol}: AI 분석 타임아웃 - 원본 점수 유지")
            except Exception as e:
                logger.debug(f"{symbol}: AI 분석 오류 - {e}")

        # AI 보정된 score로 재정렬
        watchlist.sort(key=lambda x: x['score'], reverse=True)
        logger.info("AI 감성 분석 완료, 워치리스트 재정렬됨")
        return watchlist

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
                logger.warning(f"⚠️ {position.symbol} 손절 필요: {position_pl_percent:.2f}%")
                # 자동 손절 실행 (옵션)
                # self._execute_stop_loss(position)

        return True

    def _is_market_hours(self) -> bool:
        """미국 시장 시간인지 확인 (간단 체크)"""
        from datetime import timezone, timedelta

        # 미국 동부시간 (ET)
        et_tz = timezone(timedelta(hours=-5))  # EST (겨울) / EDT는 -4
        now_et = datetime.now(et_tz)

        # 주말 체크
        if now_et.weekday() >= 5:  # 토요일(5), 일요일(6)
            return False

        # 시장 시간: 9:30 AM ~ 4:00 PM ET
        market_open = now_et.replace(hour=9, minute=30, second=0)
        market_close = now_et.replace(hour=16, minute=0, second=0)

        return market_open <= now_et <= market_close

    async def _stage1_market_scan(self):
        """
        Stage 1: 전체 시장 스캔 및 워치리스트 생성

        3~5분마다 실행
        """
        scan_count = 0
        while self.is_running:
            try:
                scan_count += 1
                logger.info(f"\n{'=' * 70}")
                logger.info(f"[Stage 1] 전체 시장 스캔 시작")
                logger.info(f"  시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

                # 시장 시간 체크
                is_market_hours = self._is_market_hours()
                logger.info(f"  미국 시장 시간: {'YES (장중)' if is_market_hours else 'NO (장외)'}")
                if not is_market_hours:
                    logger.warning("  장외 시간이므로 워치리스트가 비어있을 수 있습니다")

                logger.info(f"{'=' * 70}")

                # 워치리스트 생성
                watchlist = await self.watchlist_generator.generate_watchlist()

                if watchlist:
                    # AI 뉴스 감성 스코어링 (선택적)
                    watchlist = await self._apply_ai_scoring(watchlist)

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

    async def run_async(self):
        """메인 비동기 루프"""
        logger.info("\n" + "=" * 70)
        logger.info("🚀 자동매매 봇 V2 시작!")
        logger.info("=" * 70)

        if not self.auto_trading_enabled:
            logger.warning("\n⚠️⚠️⚠️ 자동매매가 비활성화되어 있습니다 ⚠️⚠️⚠️")
            logger.warning("시뮬레이션 모드로 실행됩니다 (실제 주문 없음)")
            logger.warning("AUTO_TRADING_ENABLED=true로 설정하세요.\n")

        self.is_running = True

        try:
            # Stage 1 태스크 시작 (Stage 2는 Stage 1에서 자동으로 시작)
            await self._stage1_market_scan()

        except asyncio.CancelledError:
            logger.info("\n태스크 취소됨")
        except Exception as e:
            logger.error(f"치명적 오류: {e}")
            import traceback
            traceback.print_exc()
        finally:
            await self.cleanup()

    def run(self):
        """메인 진입점 (동기) — 텔레그램 봇을 별도 스레드로 시작 후 매매 루프 실행."""
        # 텔레그램 봇 백그라운드 스레드 시작
        telegram_thread = threading.Thread(
            target=_run_telegram_bot,
            daemon=True,
            name="TelegramBot",
        )
        telegram_thread.start()
        logger.info("✓ 텔레그램 봇 스레드 시작")

        try:
            asyncio.run(self.run_async())
        except KeyboardInterrupt:
            logger.info("\n사용자에 의해 중단됨")

    async def cleanup(self):
        """정리"""
        logger.info("\n자동매매 봇 V2 종료 중...")

        self.is_running = False

        try:
            # 모니터 중지
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


def _run_telegram_bot():
    """텔레그램 봇을 별도 스레드에서 실행.

    python-telegram-bot v20+는 내부적으로 asyncio를 사용하므로
    서브 스레드에서는 전용 이벤트 루프를 생성해야 함.
    """
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        from telegram_bot import main as telegram_main
        logger.info("텔레그램 봇 시작 중...")
        telegram_main()
    except ImportError as e:
        logger.warning(f"⚠️ 텔레그램 봇 모듈 로드 실패 (선택적 기능): {e}")
    except Exception as e:
        logger.error(f"텔레그램 봇 오류: {e}")
        import traceback
        traceback.print_exc()
    finally:
        loop.close()


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
