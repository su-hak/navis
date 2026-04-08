# AI 자동매매 시스템 풀스택 개발 기획서 (최종 확장판)

## 🎯 목적

실제 수익 창출을 위한 자동매매 시스템 (감시 + 실행 + 전략 + 확장 구조
포함)

------------------------------------------------------------------------

# 1. 시스템 전체 구조

\[시장 데이터\] → \[워치리스트 생성\] → \[고주기 감시\] → \[즉시 실행\]
→ \[리스크 관리\] → \[DB 저장\] → \[리포트/알림\]

------------------------------------------------------------------------

# 2. 감시 전략

## 2단계 구조

-   전체 시장: 3\~5분
-   선별 종목: 5\~10초

------------------------------------------------------------------------

# 3. 워치리스트 자동화

``` python
def select_watchlist(stocks):
    return sorted(
        [s for s in stocks if s.gap > 3 or s.volume_ratio > 3],
        key=lambda x: x.volume_ratio,
        reverse=True
    )[:20]
```

------------------------------------------------------------------------

# 4. 고주기 감시 시스템

``` python
import asyncio

async def monitor(stock):
    price = await get_price(stock)
    change = (price - stock.prev_price) / stock.prev_price

    if change > 0.015:
        execute_trade(stock)

async def run(watchlist):
    await asyncio.gather(*[monitor(s) for s in watchlist])
```

------------------------------------------------------------------------

# 5. WebSocket 기반 실시간 확장 (준 HFT)

## 구조

\[WebSocket Tick Data\] → \[Event Trigger\] → \[즉시 실행\]

------------------------------------------------------------------------

## 예시 코드 (개념)

``` python
import websocket
import json

def on_message(ws, message):
    data = json.loads(message)
    price = data['price']

    if detect_spike(price):
        execute_trade(data['symbol'])

ws = websocket.WebSocketApp("wss://stream.data",
                            on_message=on_message)
ws.run_forever()
```

------------------------------------------------------------------------

# 6. Alpaca 자동매매 코드

``` python
import requests

def execute_order(symbol, qty):
    url = "https://paper-api.alpaca.markets/v2/orders"
    headers = {
        "APCA-API-KEY-ID": "KEY",
        "APCA-API-SECRET-KEY": "SECRET"
    }

    data = {
        "symbol": symbol,
        "qty": qty,
        "side": "buy",
        "type": "market",
        "time_in_force": "gtc"
    }

    return requests.post(url, json=data, headers=headers).json()
```

------------------------------------------------------------------------

# 7. 멀티 전략 시스템 (핵심 확장)

## 구조

Strategy A (모멘텀) Strategy B (돌파) Strategy C (리버전)

→ 동시에 실행

------------------------------------------------------------------------

## 포트폴리오 분배

-   전략 A: 40%
-   전략 B: 30%
-   전략 C: 30%

------------------------------------------------------------------------

# 8. 백테스트 시스템

``` python
def backtest(data):
    balance = 1000000

    for row in data:
        if buy_signal(row):
            balance *= 1.02
        elif sell_signal(row):
            balance *= 0.98

    return balance
```

------------------------------------------------------------------------

# 9. DB 설계

## trades

  필드          설명
  ------------- ------
  id            PK
  symbol        종목
  entry_price   진입
  exit_price    청산
  pnl           손익
  created_at    시간

------------------------------------------------------------------------

# 10. 리스크 관리

-   1회 투자: 10%
-   손절: -2%
-   하루 손실: -5%

------------------------------------------------------------------------

# 11. 수익률 최적화

## 핵심 공식

수익 = 승률 × 손익비

------------------------------------------------------------------------

## 추천 세팅

-   승률: 55\~60%
-   손익비: 1:1.5

------------------------------------------------------------------------

# 12. 텔레그램 알림

``` python
def send_msg(text):
    requests.post(f"https://api.telegram.org/botTOKEN/sendMessage",
                  data={"chat_id": "CHAT_ID", "text": text})
```

------------------------------------------------------------------------

# 13. 최종 결론

이 시스템은

👉 단순 자동매매가 아니라 👉 멀티 전략 + 실시간 감시 + 실행 엔진

------------------------------------------------------------------------

# 🚀 핵심

-   감시는 선택과 집중
-   실행은 빠르게
-   리스크는 철저하게
