"""
자동매매 봇 - AI Agent + Execution Team 통합

AI가 자동으로 시장을 분석하고 주문을 실행합니다.
"""
import os
import sys
import time
import logging
from datetime import datetime
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

# 로깅 설정
logging.basicConfig(
    level=os.getenv('LOG_LEVEL', 'INFO'),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/auto_trading.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 실행 팀 임포트
try:
    from execution_team.core import ExecutionEngine, OrderManager, OrderSignal, OrderAction, OrderType
    from execution_team.brokers import AlpacaBroker
    from execution_team.config import config as exec_config
except ImportError as e:
    logger.error(f"Execution Team 임포트 실패: {e}")
    sys.exit(1)

# AI 팀 임포트
try:
    from ai_team.agents.trading_agent import TradingAgent
except ImportError as e:
    logger.error(f"AI Team 임포트 실패: {e}")
    sys.exit(1)


class AutoTradingBot:
    """
    자동매매 봇

    AI Agent가 시장을 분석하고 Execution Team이 주문을 실행합니다.
    """

    def __init__(self):
        """초기화"""
        logger.info("=" * 70)
        logger.info("자동매매 봇 초기화 중...")
        logger.info("=" * 70)

        # 설정 로드 (퍼센트 기반)
        self.auto_trading_enabled = os.getenv('AUTO_TRADING_ENABLED', 'false').lower() == 'true'
        self.max_investment_percent = float(os.getenv('MAX_INVESTMENT_PERCENT', '10.0'))
        self.max_daily_loss_percent = float(os.getenv('MAX_DAILY_LOSS_PERCENT', '5.0'))
        self.max_positions = int(os.getenv('MAX_POSITIONS', '5'))
        self.trading_interval = int(os.getenv('TRADING_INTERVAL_MINUTES', '60'))

        logger.info(f"자동매매 활성화: {self.auto_trading_enabled}")
        logger.info(f"1회 최대 투자: 현금의 {self.max_investment_percent}%")
        logger.info(f"1일 최대 손실: 현금의 {self.max_daily_loss_percent}%")
        logger.info(f"최대 동시 보유: {self.max_positions}개")
        logger.info(f"분석 주기: {self.trading_interval}분")

        # 주기에 따른 경고
        if self.trading_interval < 5:
            logger.warning("⚠️ 분석 주기가 5분 미만입니다. API 사용량에 주의하세요.")
        elif self.trading_interval >= 60:
            logger.warning("⚠️ 분석 주기가 60분 이상입니다. 단기 변동을 놓칠 수 있습니다.")

        if not self.auto_trading_enabled:
            logger.warning("⚠️ 자동매매가 비활성화되어 있습니다!")
            logger.warning("⚠️ AUTO_TRADING_ENABLED=true로 설정하세요.")

        # Execution Team 초기화
        self._init_execution_team()

        # AI Team 초기화
        self._init_ai_team()

        # 일일 손익 추적
        self.daily_pl = 0.0
        self.trade_count = 0

        logger.info("✓ 자동매매 봇 초기화 완료")

    def _init_execution_team(self):
        """Execution Team 초기화"""
        logger.info("\n[1] Execution Team 초기화 중...")

        try:
            # 브로커 설정
            broker_config = {
                'api_key': os.getenv('ALPACA_API_KEY'),
                'secret_key': os.getenv('ALPACA_SECRET_KEY'),
                'base_url': os.getenv('ALPACA_BASE_URL', 'https://paper-api.alpaca.markets')
            }

            # API 키 확인
            if not broker_config['api_key'] or not broker_config['secret_key']:
                raise ValueError("ALPACA_API_KEY 또는 ALPACA_SECRET_KEY가 설정되지 않았습니다")

            # 브로커 연결
            self.broker = AlpacaBroker(broker_config)
            self.broker.connect()
            logger.info(f"✓ 브로커 연결 성공 ({broker_config['base_url']})")

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

            # 계좌 정보 확인
            account = self.execution_engine.get_account()
            logger.info(f"✓ 계좌 자산: ${account.equity:,.2f}")

        except Exception as e:
            logger.error(f"✗ Execution Team 초기화 실패: {e}")
            raise

    def _init_ai_team(self):
        """AI Team 초기화"""
        logger.info("\n[2] AI Team 초기화 중...")

        try:
            # AI Agent 생성
            self.ai_agent = TradingAgent()
            logger.info("✓ AI Agent 초기화 완료")

        except Exception as e:
            logger.error(f"✗ AI Team 초기화 실패: {e}")
            raise

    def analyze_market(self):
        """
        AI가 시장을 분석하고 매매 신호 생성

        Returns:
            dict: 매매 신호 또는 None
        """
        logger.info("\n" + "=" * 70)
        logger.info("시장 분석 시작...")
        logger.info("=" * 70)

        try:
            # 계좌 정보 조회
            account = self.execution_engine.get_account()
            current_cash = account.cash

            # 투자 금액 계산 (현금의 %)
            max_investment_amount = current_cash * (self.max_investment_percent / 100.0)
            max_loss_amount = current_cash * (self.max_daily_loss_percent / 100.0)

            # AI에게 시장 분석 요청
            prompt = f"""
현재 미국 주식 시장을 분석하고 매매 기회를 찾아주세요.

**계좌 정보**:
- 현금: ${current_cash:,.2f}
- 자산 총액: ${account.equity:,.2f}
- 현재 포지션: {len(self.execution_engine.get_positions())}개
- 최대 포지션: {self.max_positions}개

**투자 제약**:
- 1회 최대 투자금: ${max_investment_amount:,.2f} (현금의 {self.max_investment_percent}%)
- 오늘 손익: ${self.daily_pl:,.2f}
- 최대 손실: ${max_loss_amount:,.2f} (현금의 {self.max_daily_loss_percent}%)

**요청사항**:
1. 현재 시장 상황 분석
2. 매수/매도 기회가 있는 종목 추천
3. 추천 이유 설명

**응답 형식** (JSON):
{{
    "action": "BUY" or "SELL" or "HOLD",
    "symbol": "종목코드",
    "quantity": 수량,
    "reason": "매매 이유",
    "confidence": 0.0~1.0
}}

매매 기회가 없으면 "HOLD"를 반환하세요.
"""

            # AI 실행
            response = self.ai_agent.run(prompt)
            logger.info(f"AI 응답: {response[:500]}...")

            # 응답 파싱 (간단한 예제)
            # 실제로는 더 정교한 파싱 필요
            signal = self._parse_ai_response(response)

            return signal

        except Exception as e:
            logger.error(f"시장 분석 실패: {e}")
            return None

    def _parse_ai_response(self, response: str) -> dict:
        """
        AI 응답 파싱

        실제 구현에서는 JSON 파싱 또는 정규표현식 사용
        """
        import json
        import re

        # JSON 추출 시도
        try:
            # JSON 블록 찾기
            json_match = re.search(r'\{[^}]+\}', response, re.DOTALL)
            if json_match:
                signal = json.loads(json_match.group())
                return signal
        except:
            pass

        # 파싱 실패 시 HOLD
        logger.warning("AI 응답 파싱 실패 - HOLD")
        return {"action": "HOLD"}

    def execute_signal(self, signal: dict):
        """
        매매 신호 실행

        Args:
            signal: AI가 생성한 매매 신호
        """
        if not signal or signal.get('action') == 'HOLD':
            logger.info("매매 신호 없음 (HOLD)")
            return

        if not self.auto_trading_enabled:
            logger.warning("⚠️ 자동매매가 비활성화되어 있어 주문을 실행하지 않습니다.")
            logger.info(f"신호: {signal}")
            return

        try:
            # 포지션 수 확인
            positions = self.execution_engine.get_positions()
            if signal['action'] == 'BUY' and len(positions) >= self.max_positions:
                logger.warning(f"최대 포지션 수 도달 ({len(positions)}/{self.max_positions}) - 매수 불가")
                return

            # 주문 신호 생성
            order_signal = OrderSignal(
                symbol=signal['symbol'],
                action=OrderAction[signal['action']],
                order_type=OrderType.MARKET,
                quantity=signal.get('quantity', 1),
                strategy_id="ai_auto_trading",
                reason=signal.get('reason', 'AI 추천')
            )

            logger.info(f"\n주문 실행: {order_signal.action.value} {order_signal.quantity} {order_signal.symbol}")
            logger.info(f"이유: {order_signal.reason}")

            # 주문 실행
            result = self.execution_engine.execute_order(order_signal)

            if result.success:
                logger.info(f"✓ 주문 성공!")
                logger.info(f"  주문 ID: {result.order_id}")
                logger.info(f"  상태: {result.status.value}")
                if result.filled_price:
                    logger.info(f"  체결가: ${result.filled_price:.2f}")
                    logger.info(f"  체결 수량: {result.filled_quantity}주")

                self.trade_count += 1
            else:
                logger.error(f"✗ 주문 실패: {result.error_message}")

        except Exception as e:
            logger.error(f"주문 실행 중 오류: {e}")

    def check_risk_limits(self):
        """리스크 한계 확인"""
        account = self.execution_engine.get_account()

        # 일일 손실 계산
        # 간단히 미실현 손익으로 추정
        self.daily_pl = account.unrealized_pl

        # 현금 기준 손실 한계 계산
        current_cash = account.cash
        max_loss_amount = current_cash * (self.max_daily_loss_percent / 100.0)

        if abs(self.daily_pl) > max_loss_amount:
            logger.error(f"⚠️ 일일 최대 손실 도달! (${self.daily_pl:,.2f} > ${max_loss_amount:,.2f})")
            logger.error(f"⚠️ 현금 ${current_cash:,.2f}의 {self.max_daily_loss_percent}% 초과")
            logger.error("⚠️ 모든 포지션 청산 권장")
            return False

        return True

    def run_once(self):
        """1회 실행"""
        try:
            # 리스크 확인
            if not self.check_risk_limits():
                logger.error("리스크 한계 초과 - 거래 중단")
                return

            # 시장 분석
            signal = self.analyze_market()

            # 신호 실행
            if signal:
                self.execute_signal(signal)

            # 통계 출력
            stats = self.execution_engine.get_execution_stats()
            logger.info(f"\n📊 통계: 총 {stats['total']}개 주문, 성공률 {stats['success_rate']:.1f}%")

        except Exception as e:
            logger.error(f"실행 중 오류: {e}")

    def run(self):
        """메인 루프"""
        logger.info("\n" + "=" * 70)
        logger.info("🚀 자동매매 봇 시작!")
        logger.info("=" * 70)

        if not self.auto_trading_enabled:
            logger.warning("\n⚠️⚠️⚠️ 자동매매가 비활성화되어 있습니다 ⚠️⚠️⚠️")
            logger.warning("시뮬레이션 모드로 실행됩니다 (실제 주문 없음)")
            logger.warning("AUTO_TRADING_ENABLED=true로 설정하세요.\n")

        try:
            while True:
                logger.info(f"\n{'=' * 70}")
                logger.info(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                logger.info(f"{'=' * 70}")

                # 1회 실행
                self.run_once()

                # 대기
                logger.info(f"\n다음 실행까지 {self.trading_interval}분 대기...")
                time.sleep(self.trading_interval * 60)

        except KeyboardInterrupt:
            logger.info("\n사용자에 의해 중단됨")
        except Exception as e:
            logger.error(f"치명적 오류: {e}")
        finally:
            self.cleanup()

    def cleanup(self):
        """정리"""
        logger.info("\n자동매매 봇 종료 중...")

        try:
            # 브로커 연결 해제
            if hasattr(self, 'broker'):
                self.broker.disconnect()
                logger.info("✓ 브로커 연결 해제")

        except Exception as e:
            logger.error(f"정리 중 오류: {e}")

        logger.info("✓ 자동매매 봇 종료 완료")


def main():
    """메인 함수"""
    try:
        bot = AutoTradingBot()
        bot.run()
    except Exception as e:
        logger.error(f"봇 시작 실패: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
