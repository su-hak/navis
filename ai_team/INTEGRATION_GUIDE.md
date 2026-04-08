# AI Team 통합 가이드

다른 팀(Data Collection, Strategy Engine 등)과 AI Team을 통합하는 방법

---

## 아키텍처 개요

```
┌─────────────────┐
│ Data Collection │
└────────┬────────┘
         │ (뉴스 수집)
         ↓
┌─────────────────┐      ┌──────────────────┐
│   AI Team       │ ←──→ │ Strategy Engine  │
│   (Port 8001)   │      │   (Port 8000)    │
└─────────────────┘      └──────────────────┘
         │
         ↓
┌─────────────────┐
│ Risk Manager /  │
│ Execution Team  │
└─────────────────┘
```

---

## 1. Strategy Engine과의 통합

Strategy Engine은 기본 점수를 계산하고, AI Team은 뉴스 기반으로 점수를 보정합니다.

### Strategy Engine → AI Team

```python
# strategy_engine/scoring/final_score.py

import requests

def calculate_final_score(symbol: str, base_score: float) -> float:
    """
    최종 점수 계산 (기본 점수 + AI 보정)

    Args:
        symbol: 종목 심볼
        base_score: 전략 엔진의 기본 점수 (0-100)

    Returns:
        최종 점수 (0-100)
    """
    try:
        # AI Team에 점수 보정 요청
        response = requests.post(
            'http://localhost:8001/api/news/score-adjustment',
            json={'symbol': symbol},
            timeout=10
        )

        if response.status_code == 200:
            adjustment = response.json()['adjustment']
            final_score = base_score + adjustment

            # 0-100 범위로 제한
            final_score = max(0, min(100, final_score))

            return final_score
        else:
            # AI Team 오류 시 기본 점수 사용
            return base_score

    except Exception as e:
        print(f"AI Team 연결 오류: {e}")
        return base_score


# 사용 예제
base_score = 75.0
final_score = calculate_final_score('AAPL', base_score)
print(f"Base: {base_score}, Final: {final_score}")
```

### AI Team의 응답 형식

```json
{
  "symbol": "AAPL",
  "adjustment": 8.5,
  "timestamp": "2024-01-15T10:30:00"
}
```

---

## 2. Data Collection과의 통합

Data Collection이 수집한 뉴스를 AI Team의 RAG 시스템에 추가합니다.

### Data Collection → AI Team

```python
# data_collection/collectors/news_collector.py

import requests

def save_news_to_rag(news_list: list):
    """
    수집한 뉴스를 AI Team RAG에 저장

    Args:
        news_list: 뉴스 리스트
    """
    try:
        response = requests.post(
            'http://localhost:8001/api/rag/add-news',
            json={'news_list': news_list},
            timeout=30
        )

        if response.status_code == 200:
            result = response.json()
            print(f"✓ {result['message']}")
        else:
            print(f"✗ RAG 저장 실패: {response.status_code}")

    except Exception as e:
        print(f"AI Team 연결 오류: {e}")


# 사용 예제
news_list = [
    {
        'title': 'Apple announces new product',
        'description': 'Apple unveiled...',
        'content': 'Full article...',
        'source': 'Reuters',
        'url': 'https://...',
        'published_at': '2024-01-15'
    }
]

save_news_to_rag(news_list)
```

---

## 3. Risk Manager와의 통합

Risk Manager는 시장 리스크를 평가할 때 AI Team의 분석을 참고합니다.

### Risk Manager → AI Team

```python
# risk_manager/market_risk.py

import requests

def assess_market_risk() -> dict:
    """
    시장 전체 리스크 평가

    Returns:
        {
            'risk_level': 'low/medium/high',
            'should_trade': bool
        }
    """
    try:
        # AI Team에서 시장 리스크 조회
        response = requests.get(
            'http://localhost:8001/api/market/risk',
            timeout=10
        )

        if response.status_code == 200:
            result = response.json()

            risk_level = result['risk_level']

            # 리스크에 따른 거래 여부 결정
            should_trade = risk_level in ['low', 'medium']

            return {
                'risk_level': risk_level,
                'risk_score': result['risk_score'],
                'factors': result['factors'],
                'should_trade': should_trade
            }
        else:
            # 기본값 (보수적)
            return {
                'risk_level': 'medium',
                'should_trade': True
            }

    except Exception as e:
        print(f"AI Team 연결 오류: {e}")
        return {'risk_level': 'medium', 'should_trade': True}


# 사용 예제
risk = assess_market_risk()
if risk['should_trade']:
    print("거래 가능")
else:
    print("리스크 높음 - 거래 중단")
```

---

## 4. 전체 통합 예제

전체 매매 파이프라인에서 AI Team을 통합하는 예제입니다.

```python
# trading/orchestrator.py

import requests

def execute_trading_pipeline(symbol: str):
    """
    전체 매매 파이프라인
    """
    print(f"\n{'='*60}")
    print(f"종목 분석 시작: {symbol}")
    print(f"{'='*60}")

    # 1. 시장 리스크 체크 (AI Team)
    print("\n[1] 시장 리스크 평가...")
    market_risk = requests.get('http://localhost:8001/api/market/risk').json()
    print(f"  리스크 레벨: {market_risk['risk_level']}")

    if market_risk['risk_level'] == 'high':
        print("  ⚠️  시장 리스크 높음 - 거래 중단")
        return

    # 2. 데이터 수집 (Data Collection)
    print("\n[2] 데이터 수집...")
    # data = get_market_data(symbol)

    # 3. 전략 점수 계산 (Strategy Engine)
    print("\n[3] 전략 점수 계산...")
    # base_score = calculate_base_score(symbol, data)
    base_score = 75.0  # 예시
    print(f"  기본 점수: {base_score}")

    # 4. AI 점수 보정 (AI Team)
    print("\n[4] AI 점수 보정...")
    adjustment_response = requests.post(
        'http://localhost:8001/api/news/score-adjustment',
        json={'symbol': symbol}
    ).json()
    adjustment = adjustment_response['adjustment']
    print(f"  보정값: {adjustment:+.2f}")

    final_score = base_score + adjustment
    print(f"  최종 점수: {final_score:.2f}")

    # 5. AI Agent 분석 (AI Team)
    print("\n[5] AI Agent 종합 분석...")
    agent_response = requests.post(
        'http://localhost:8001/api/agent/analyze',
        json={
            'symbol': symbol,
            'context': {
                'base_score': base_score,
                'final_score': final_score
            }
        }
    ).json()

    print(f"  추천: {agent_response['recommendation']}")
    print(f"  분석: {agent_response['analysis'][:200]}...")

    # 6. 매매 결정
    print("\n[6] 매매 결정...")
    if final_score >= 75 and agent_response['recommendation'] in ['BUY', 'STRONG_BUY']:
        print("  ✓ 매수 신호!")
        # execute_order(symbol, 'BUY')
    elif final_score < 50 or agent_response['recommendation'] == 'SELL':
        print("  ✓ 매도 신호!")
        # execute_order(symbol, 'SELL')
    else:
        print("  - 관망")

    print(f"\n{'='*60}\n")


# 실행
if __name__ == "__main__":
    execute_trading_pipeline('AAPL')
