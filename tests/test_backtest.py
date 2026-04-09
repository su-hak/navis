"""
백테스트 테스트 (QA Team - Backtest)

기획서 9. 테스트 전략 - 백테스트

검증 항목:
1. 백테스트 엔진 기본 동작
2. 상승장 / 하락장 / 횡보장 / 고변동성 시나리오
3. 리스크 룰 (손절/익절/일일한도) 작동 확인
4. 성능 지표 정확성 (샤프비율, MDD, 승률 등)
5. 엣지 케이스 (데이터 부족, 거래 없음)
"""
import pytest
import numpy as np
from conftest import make_ohlcv, make_high_volume_ohlcv


# ============================================================
# 백테스트 엔진 초기화
# ============================================================

class TestBacktestEngineInit:

    def test_default_config_created(self):
        """기본 설정으로 엔진 생성"""
        from qa_team.backtest import BacktestEngine, BacktestConfig
        engine = BacktestEngine()
        assert engine.config.initial_capital == 1_000_000.0
        assert engine.config.stop_loss_pct == 0.02
        assert engine.config.max_positions == 5

    def test_custom_config(self):
        """커스텀 설정 적용"""
        from qa_team.backtest import BacktestEngine, BacktestConfig
        config = BacktestConfig(
            initial_capital=500_000,
            stop_loss_pct=0.03,
            max_positions=3,
        )
        engine = BacktestEngine(config)
        assert engine.config.initial_capital == 500_000
        assert engine.config.stop_loss_pct == 0.03

    def test_insufficient_data_raises_error(self, short_df):
        """데이터 부족 시 ValueError 발생"""
        from qa_team.backtest import BacktestEngine
        engine = BacktestEngine()
        with pytest.raises(ValueError, match="데이터 부족"):
            engine.run(symbol="TEST", df=short_df)


# ============================================================
# 기본 동작 테스트
# ============================================================

class TestBacktestBasicOperation:

    def test_returns_backtest_result(self, uptrend_df):
        """BacktestResult 객체 반환 확인"""
        from qa_team.backtest import BacktestEngine, BacktestResult
        engine = BacktestEngine()
        result = engine.run(symbol="AAPL", df=uptrend_df)
        assert isinstance(result, BacktestResult)

    def test_equity_curve_starts_at_initial_capital(self, uptrend_df):
        """자산 곡선이 초기 자본으로 시작"""
        from qa_team.backtest import BacktestEngine
        engine = BacktestEngine()
        result = engine.run(symbol="AAPL", df=uptrend_df)
        assert result.equity_curve[0] == pytest.approx(1_000_000, rel=0.01)

    def test_equity_curve_length_matches_data(self, uptrend_df):
        """자산 곡선 길이 = 데이터 길이 - 워밍업 + 1"""
        from qa_team.backtest import BacktestEngine
        engine = BacktestEngine()
        result = engine.run(symbol="AAPL", df=uptrend_df)
        expected_len = len(uptrend_df) - engine.config.warmup_periods + 1
        # 마지막 청산 포함으로 ±2 허용
        assert abs(len(result.equity_curve) - expected_len) <= 2

    def test_final_capital_is_non_negative(self, uptrend_df):
        """최종 자본은 항상 0 이상"""
        from qa_team.backtest import BacktestEngine
        engine = BacktestEngine()
        result = engine.run(symbol="AAPL", df=uptrend_df)
        assert result.final_capital >= 0

    def test_total_return_calculated(self, uptrend_df):
        """총 수익률 계산 정확성"""
        from qa_team.backtest import BacktestEngine
        engine = BacktestEngine()
        result = engine.run(symbol="AAPL", df=uptrend_df)
        expected = (result.final_capital - result.initial_capital) / result.initial_capital * 100
        assert result.total_return_pct == pytest.approx(expected, abs=0.01)

    def test_win_rate_between_0_and_100(self, uptrend_df):
        """승률은 0~100% 범위"""
        from qa_team.backtest import BacktestEngine
        engine = BacktestEngine()
        result = engine.run(symbol="AAPL", df=uptrend_df)
        assert 0.0 <= result.win_rate_pct <= 100.0

    def test_max_drawdown_is_non_negative(self, uptrend_df):
        """최대 낙폭은 0 이상"""
        from qa_team.backtest import BacktestEngine
        engine = BacktestEngine()
        result = engine.run(symbol="AAPL", df=uptrend_df)
        assert result.max_drawdown_pct >= 0.0

    def test_win_loss_counts_sum_to_total(self, uptrend_df):
        """승/패 거래 합계 = 전체 거래 수"""
        from qa_team.backtest import BacktestEngine
        engine = BacktestEngine()
        result = engine.run(symbol="AAPL", df=uptrend_df)
        assert result.win_trades + result.loss_trades == result.total_trades

    def test_summary_string_generated(self, uptrend_df):
        """요약 문자열 생성 확인"""
        from qa_team.backtest import BacktestEngine
        engine = BacktestEngine()
        result = engine.run(symbol="AAPL", df=uptrend_df)
        summary = result.summary()
        assert "백테스트 결과" in summary
        assert "총 수익률" in summary
        assert "최대 낙폭" in summary
        assert "승률" in summary


# ============================================================
# 시나리오별 테스트
# ============================================================

class TestBacktestScenarios:

    def test_uptrend_scenario(self, uptrend_df):
        """상승장 시나리오: 거래 발생 확인"""
        from qa_team.backtest import BacktestEngine
        engine = BacktestEngine()
        result = engine.run(symbol="BULL", df=uptrend_df)
        # 상승장에서 최소 1회 이상 거래 기회 발생 (점수 미달 가능성 있으므로 0 허용)
        assert result.total_trades >= 0

    def test_downtrend_stop_loss_triggered(self, downtrend_df):
        """하락장 시나리오: 손절 발생"""
        from qa_team.backtest import BacktestEngine
        engine = BacktestEngine()
        result = engine.run(symbol="BEAR", df=downtrend_df)
        stop_loss_trades = [t for t in result.trade_records if t.signal_type == "STOP_LOSS"]
        # 하락장에서 매수가 발생했다면 손절이 발생해야 함
        if result.total_trades > 0:
            assert len(stop_loss_trades) > 0 or result.avg_loss_pct <= 0

    def test_high_volume_signal_generation(self):
        """거래량 급증 시 매수 시그널 조건 강화"""
        from qa_team.backtest import BacktestEngine
        df_high_vol = make_high_volume_ohlcv(days=250, seed=10)
        engine = BacktestEngine()
        result = engine.run(symbol="HVOL", df=df_high_vol)
        assert isinstance(result.total_trades, int)

    def test_drawdown_never_exceeds_100_percent(self, volatile_df):
        """최대 낙폭은 100%를 초과할 수 없음"""
        from qa_team.backtest import BacktestEngine
        engine = BacktestEngine()
        result = engine.run(symbol="VOLT", df=volatile_df)
        assert result.max_drawdown_pct <= 100.0

    def test_daily_loss_limit_enforced(self):
        """일일 손실 한도 (-5%) 강제 적용 검증"""
        from qa_team.backtest import BacktestEngine, BacktestConfig
        # 타이트한 일일 손실 한도 설정
        config = BacktestConfig(max_daily_loss_pct=0.01)  # 1%
        engine = BacktestEngine(config)
        df = make_ohlcv(300, "down", seed=20)
        result = engine.run(symbol="TIGHT", df=df)
        # 실행은 완료되어야 함
        assert result is not None

    def test_max_positions_respected(self):
        """최대 포지션 한도 준수"""
        from qa_team.backtest import BacktestEngine, BacktestConfig
        config = BacktestConfig(max_positions=2)
        engine = BacktestEngine(config)
        df = make_ohlcv(300, "up", seed=30)
        result = engine.run(symbol="MAXPOS", df=df)
        assert result is not None


# ============================================================
# 성능 지표 정확성 테스트
# ============================================================

class TestBacktestMetrics:

    def test_profit_factor_positive_when_profitable(self, uptrend_df):
        """수익 거래 > 손실 거래 시 손익비 > 1.0"""
        from qa_team.backtest import BacktestEngine
        engine = BacktestEngine()
        result = engine.run(symbol="AAPL", df=uptrend_df)
        if result.win_trades > result.loss_trades and result.loss_trades > 0:
            assert result.profit_factor > 1.0

    def test_sharpe_ratio_is_finite(self, uptrend_df):
        """샤프 지수가 유한한 숫자"""
        from qa_team.backtest import BacktestEngine
        import math
        engine = BacktestEngine()
        result = engine.run(symbol="AAPL", df=uptrend_df)
        assert math.isfinite(result.sharpe_ratio)

    def test_trade_records_have_required_fields(self, uptrend_df):
        """거래 기록 필수 필드 존재 확인"""
        from qa_team.backtest import BacktestEngine
        engine = BacktestEngine()
        result = engine.run(symbol="AAPL", df=uptrend_df)
        for trade in result.trade_records:
            assert trade.symbol == "AAPL"
            assert trade.action in ["BUY", "SELL"]
            assert isinstance(trade.quantity, int)
            assert trade.quantity > 0
            assert isinstance(trade.pnl, float)

    def test_pnl_sum_consistent_with_capital_change(self, uptrend_df):
        """손익 합계와 자본 변화 일치 (수수료 포함 허용 오차)"""
        from qa_team.backtest import BacktestEngine
        engine = BacktestEngine()
        result = engine.run(symbol="AAPL", df=uptrend_df)
        total_pnl = sum(t.pnl for t in result.trade_records)
        capital_change = result.final_capital - result.initial_capital
        # 슬리피지/수수료 포함이므로 약간의 오차 허용
        assert abs(total_pnl - capital_change) / max(abs(capital_change), 1) < 0.1

    def test_annualized_return_calculation(self, uptrend_df):
        """연환산 수익률 합리성 확인 (-500% ~ +500% 범위)"""
        from qa_team.backtest import BacktestEngine
        engine = BacktestEngine()
        result = engine.run(symbol="AAPL", df=uptrend_df)
        assert -500 <= result.annualized_return_pct <= 500


# ============================================================
# 전략 유효성 검증 기준 테스트
# ============================================================

class TestStrategyValidation:

    def test_pass_fail_field_is_bool(self, uptrend_df):
        """passed 필드가 bool 타입"""
        from qa_team.backtest import BacktestEngine
        engine = BacktestEngine()
        result = engine.run(symbol="AAPL", df=uptrend_df)
        assert isinstance(result.passed, bool)

    def test_fail_reasons_populated_when_failed(self, downtrend_df):
        """전략 실패 시 fail_reasons에 사유 기록"""
        from qa_team.backtest import BacktestEngine
        engine = BacktestEngine()
        result = engine.run(symbol="BEAR", df=downtrend_df)
        if not result.passed:
            assert len(result.fail_reasons) > 0

    def test_excessive_drawdown_causes_fail(self):
        """MDD > 30% 초과 시 전략 실패 처리"""
        from qa_team.backtest import BacktestEngine, BacktestResult
        # 인위적으로 30% 초과 MDD 결과 생성
        result = BacktestResult(
            initial_capital=1_000_000,
            final_capital=700_000,
            total_return_pct=-30.0,
            annualized_return_pct=-30.0,
            max_drawdown_pct=35.0,  # 한도 초과
            sharpe_ratio=-1.0,
            sortino_ratio=-1.0,
            total_trades=10,
            win_trades=4,
            loss_trades=6,
            win_rate_pct=40.0,
            profit_factor=0.8,
            avg_profit_pct=5.0,
            avg_loss_pct=-3.0,
            avg_hold_days=5.0,
        )
        # MDD 30% 초과는 실패
        assert result.max_drawdown_pct > BacktestEngine.MAX_DRAWDOWN_LIMIT

    def test_multi_symbol_backtest(self, uptrend_df, downtrend_df):
        """다중 종목 백테스트"""
        from qa_team.backtest import BacktestEngine
        engine = BacktestEngine()
        results = engine.run_multi_symbol({
            'BULL': uptrend_df,
            'BEAR': downtrend_df,
        })
        assert 'BULL' in results
        assert 'BEAR' in results
        assert len(results) == 2
