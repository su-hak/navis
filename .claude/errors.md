PS C:\navis> python auto_trading_bot_v2.py
2026-04-08 11:10:38,288 - __main__ - INFO - ======================================================================
2026-04-08 11:10:38,288 - __main__ - INFO - 자동매매 봇 V2 초기화 중...
2026-04-08 11:10:38,288 - __main__ - INFO - ======================================================================
2026-04-08 11:10:38,288 - __main__ - INFO - 자동매매 활성화: True
2026-04-08 11:10:38,288 - __main__ - WARNING - ======================================================================
2026-04-08 11:10:38,289 - __main__ - WARNING - !!! 자동매매가 활성화되어 있습니다 !!!
2026-04-08 11:10:38,289 - __main__ - WARNING - !!! 실제 주문이 실행될 수 있습니다 !!!
2026-04-08 11:10:38,289 - __main__ - WARNING - !!! 브로커: https://paper-api.alpaca.markets
2026-04-08 11:10:38,289 - __main__ - WARNING - ======================================================================
2026-04-08 11:10:38,289 - __main__ - INFO - [Stage 1] 시장 스캔 주기: 5분
2026-04-08 11:10:38,289 - __main__ - INFO - [Stage 1] 워치리스트 조건: 갭>3.0% or 거래량>3.0배
2026-04-08 11:10:38,290 - __main__ - INFO - [Stage 2] 모니터링 주기: 10초
2026-04-08 11:10:38,290 - __main__ - INFO - [Stage 2] 변동 임계값: 1.5%
2026-04-08 11:10:38,290 - __main__ - INFO - [리스크] 1회 투자: 10.0%, 손절: -2.0%, 일일 손실: -5.0%
2026-04-08 11:10:38,290 - __main__ - INFO -
[1] Execution Team 초기화 중...
2026-04-08 11:10:38,292 - urllib3.connectionpool - DEBUG - Starting new HTTPS connection (1): paper-api.alpaca.markets:443
2026-04-08 11:10:39,372 - urllib3.connectionpool - DEBUG - https://paper-api.alpaca.markets:443 "GET /v2/account HTTP/1.1" 200 None
2026-04-08 11:10:39,372 - execution_team.brokers.alpaca_broker - INFO - Alpaca 연결 성공 - 계좌 ID: 0e31cabc-2863-4c6e-884f-84d9c85015ec
2026-04-08 11:10:39,373 - __main__ - INFO - ✓ 브로커 연결 성공 (https://paper-api.alpaca.markets)
2026-04-08 11:10:39,374 - execution_team.core.order_manager - INFO - 0개 주문 로드 완료
2026-04-08 11:10:39,374 - execution_team.core.order_manager - INFO - OrderManager 초기화 - 저장소: logs/execution/orders
2026-04-08 11:10:39,374 - __main__ - INFO - ✓ 주문 관리자 초기화 완료
2026-04-08 11:10:39,374 - execution_team.core.execution_engine - INFO - ExecutionEngine 초기화 완료
2026-04-08 11:10:39,374 - __main__ - INFO - ✓ 실행 엔진 초기화 완료
2026-04-08 11:10:39,557 - urllib3.connectionpool - DEBUG - https://paper-api.alpaca.markets:443 "GET /v2/account HTTP/1.1" 200 None
2026-04-08 11:10:39,558 - execution_team.brokers.alpaca_broker - DEBUG - 계좌 조회 성공 - 자산: $100,000.00
2026-04-08 11:10:39,559 - __main__ - INFO - ✓ 계좌 자산: $100,000.00
2026-04-08 11:10:39,559 - __main__ - INFO -
[2] Monitoring System 초기화 중...
2026-04-08 11:10:39,559 - __main__ - INFO - ✓ 워치리스트 생성기 초기화 완료
2026-04-08 11:10:39,559 - data_collection.monitoring.high_frequency_monitor - INFO - 고주기 모니터 초기화: 10초 간격, 1.5% 변동 감지
2026-04-08 11:10:39,559 - __main__ - INFO - ✓ 고주기 모니터 초기화 완료
2026-04-08 11:10:39,559 - __main__ - INFO - ✓ 자동매매 봇 V2 초기화 완료
2026-04-08 11:10:39,560 - asyncio - DEBUG - Using proactor: IocpProactor
2026-04-08 11:10:39,561 - __main__ - INFO -
======================================================================
2026-04-08 11:10:39,561 - __main__ - INFO - 🚀 자동매매 봇 V2 시작!
2026-04-08 11:10:39,561 - __main__ - INFO - ======================================================================
2026-04-08 11:10:39,561 - __main__ - INFO -
======================================================================
2026-04-08 11:10:39,561 - __main__ - INFO - [Stage 1] 전체 시장 스캔 시작
2026-04-08 11:10:39,561 - __main__ - INFO -   시각: 2026-04-08 11:10:39
2026-04-08 11:10:39,562 - __main__ - INFO -   미국 시장 시간: NO (장외)
2026-04-08 11:10:39,562 - __main__ - WARNING -   장외 시간이므로 워치리스트가 비어있을 수 있습니다
2026-04-08 11:10:39,562 - __main__ - INFO - ======================================================================
2026-04-08 11:10:39,562 - data_collection.monitoring.watchlist_generator - INFO - 워치리스트 생성 시작 (유니버스: 48개 종목)
2026-04-08 11:10:39,563 - urllib3.connectionpool - DEBUG - Starting new HTTPS connection (1): data.alpaca.markets:443
2026-04-08 11:10:40,617 - urllib3.connectionpool - DEBUG - https://data.alpaca.markets:443 "GET /v2/stocks/snapshots?symbols=AAPL%2CMSFT%2CGOOGL%2CAMZN%2CMETA%2CNVDA%2CTSLA%2CNFLX%2CJPM%2CBAC%2CWFC%2CGS%2CMS%2CJNJ%2CUNH%2CPFE%2CABBV%2CTMO%2CWMT%2CHD%2CDIS%2CNKE%2CSBUX%2CXOM%2CCVX%2CCOP%2CT%2CVZ%2CTMUS%2CBA%2CCAT%2CGE%2CUPS%2CCOST%2CTGT%2CAMD%2CINTC%2CCSCO%2CORCL%2CADBE%2CCOIN%2CSNAP%2CUBER%2CLYFT%2CSQ%2CROKU%2CPLTR%2CSOFI HTTP/1.1" 200 None
2026-04-08 11:10:40,794 - data_collection.monitoring.watchlist_generator - INFO - 스냅샷 조회 완료: 48개
2026-04-08 11:10:41,080 - urllib3.connectionpool - DEBUG - https://data.alpaca.markets:443 "GET /v2/stocks/bars?start=2026-03-14T11%3A10%3A40.794437%2B00%3A00&end=2026-04-08T11%3A10%3A40.794437%2B00%3A00&timeframe=1Day&feed=iex&symbols=AAPL%2CMSFT%2CGOOGL%2CAMZN%2CMETA%2CNVDA%2CTSLA%2CNFLX%2CJPM%2CBAC%2CWFC%2CGS%2CMS%2CJNJ%2CUNH%2CPFE%2CABBV%2CTMO%2CWMT%2CHD%2CDIS%2CNKE%2CSBUX%2CXOM%2CCVX%2CCOP%2CT%2CVZ%2CTMUS%2CBA%2CCAT%2CGE%2CUPS%2CCOST%2CTGT%2CAMD%2CINTC%2CCSCO%2CORCL%2CADBE%2CCOIN%2CSNAP%2CUBER%2CLYFT%2CSQ%2CROKU%2CPLTR%2CSOFI HTTP/1.1" 200 None
2026-04-08 11:10:41,279 - data_collection.monitoring.watchlist_generator - INFO - 거래량 평균 계산 완료: 47개
2026-04-08 11:10:41,279 - data_collection.monitoring.watchlist_generator - DEBUG - SQ: 거래량 평균 없음
2026-04-08 11:10:41,280 - data_collection.monitoring.watchlist_generator - INFO - 처리 결과: 총 48개, 후보 1개, 스킵 1개
2026-04-08 11:10:41,280 - data_collection.monitoring.watchlist_generator - INFO - [OK] 워치리스트 생성 완료: 1개 종목
2026-04-08 11:10:41,280 - data_collection.monitoring.watchlist_generator - INFO - 상위 5개:
2026-04-08 11:10:41,280 - data_collection.monitoring.watchlist_generator - INFO -   1. UNH: 거래량 3.2배
2026-04-08 11:10:41,280 - __main__ - INFO -
워치리스트 갱신:
2026-04-08 11:10:41,280 - __main__ - INFO -   1. UNH: 거래량 3.2배
2026-04-08 11:10:41,281 - data_collection.monitoring.high_frequency_monitor - INFO - 워치리스트 설정 완료: 1개 종목
2026-04-08 11:10:41,281 - data_collection.monitoring.high_frequency_monitor - INFO -   - UNH
2026-04-08 11:10:41,281 - data_collection.monitoring.high_frequency_monitor - INFO - 🚀 고주기 모니터링 시작 (1개 종목)
2026-04-08 11:10:41,281 - __main__ - INFO -
다음 시장 스캔까지 5분 대기...
2026-04-08 11:10:41,281 - data_collection.monitoring.high_frequency_monitor - DEBUG - [모니터링 루프 #1] 1개 종목 체크 중...
2026-04-08 11:10:41,283 - urllib3.connectionpool - DEBUG - Starting new HTTPS connection (1): data.alpaca.markets:443
2026-04-08 11:10:42,328 - urllib3.connectionpool - DEBUG - https://data.alpaca.markets:443 "GET /v2/stocks/trades/latest?symbols=UNH HTTP/1.1" 200 124
2026-04-08 11:10:42,328 - data_collection.monitoring.high_frequency_monitor - DEBUG - [UNH] $307.31 → $307.31 (+0.00%)
2026-04-08 11:10:52,343 - data_collection.monitoring.high_frequency_monitor - DEBUG - [모니터링 루프 #2] 1개 종목 체크 중...
2026-04-08 11:10:52,523 - urllib3.connectionpool - DEBUG - https://data.alpaca.markets:443 "GET /v2/stocks/trades/latest?symbols=UNH HTTP/1.1" 200 124
2026-04-08 11:10:52,524 - data_collection.monitoring.high_frequency_monitor - DEBUG - [UNH] $307.31 → $307.31 (+0.00%)
2026-04-08 11:11:02,531 - data_collection.monitoring.high_frequency_monitor - DEBUG - [모니터링 루프 #3] 1개 종목 체크 중...
2026-04-08 11:11:02,710 - urllib3.connectionpool - DEBUG - https://data.alpaca.markets:443 "GET /v2/stocks/trades/latest?symbols=UNH HTTP/1.1" 200 124
2026-04-08 11:11:02,711 - data_collection.monitoring.high_frequency_monitor - DEBUG - [UNH] $307.31 → $307.31 (+0.00%)
2026-04-08 11:11:12,718 - data_collection.monitoring.high_frequency_monitor - DEBUG - [모니터링 루프 #4] 1개 종목 체크 중...
2026-04-08 11:11:12,897 - urllib3.connectionpool - DEBUG - https://data.alpaca.markets:443 "GET /v2/stocks/trades/latest?symbols=UNH HTTP/1.1" 200 124
2026-04-08 11:11:12,898 - data_collection.monitoring.high_frequency_monitor - DEBUG - [UNH] $307.31 → $307.31 (+0.00%)
2026-04-08 11:11:22,907 - data_collection.monitoring.high_frequency_monitor - DEBUG - [모니터링 루프 #5] 1개 종목 체크 중...
2026-04-08 11:11:23,095 - urllib3.connectionpool - DEBUG - https://data.alpaca.markets:443 "GET /v2/stocks/trades/latest?symbols=UNH HTTP/1.1" 200 124
2026-04-08 11:11:23,096 - data_collection.monitoring.high_frequency_monitor - DEBUG - [UNH] $307.31 → $307.31 (+0.00%)
2026-04-08 11:11:33,109 - data_collection.monitoring.high_frequency_monitor - DEBUG - [모니터링 루프 #6] 1개 종목 체크 중...
2026-04-08 11:11:33,288 - urllib3.connectionpool - DEBUG - https://data.alpaca.markets:443 "GET /v2/stocks/trades/latest?symbols=UNH HTTP/1.1" 200 124
2026-04-08 11:11:33,289 - data_collection.monitoring.high_frequency_monitor - DEBUG - [UNH] $307.31 → $307.31 (+0.00%)
2026-04-08 11:11:43,301 - data_collection.monitoring.high_frequency_monitor - DEBUG - [모니터링 루프 #7] 1개 종목 체크 중...
2026-04-08 11:11:43,481 - urllib3.connectionpool - DEBUG - https://data.alpaca.markets:443 "GET /v2/stocks/trades/latest?symbols=UNH HTTP/1.1" 200 124
2026-04-08 11:11:43,482 - data_collection.monitoring.high_frequency_monitor - DEBUG - [UNH] $307.31 → $307.31 (+0.00%)
2026-04-08 11:11:53,488 - data_collection.monitoring.high_frequency_monitor - DEBUG - [모니터링 루프 #8] 1개 종목 체크 중...
2026-04-08 11:11:53,668 - urllib3.connectionpool - DEBUG - https://data.alpaca.markets:443 "GET /v2/stocks/trades/latest?symbols=UNH HTTP/1.1" 200 124
2026-04-08 11:11:53,669 - data_collection.monitoring.high_frequency_monitor - DEBUG - [UNH] $307.31 → $307.31 (+0.00%)
2026-04-08 11:12:03,671 - data_collection.monitoring.high_frequency_monitor - DEBUG - [모니터링 루프 #9] 1개 종목 체크 중...
2026-04-08 11:12:03,858 - urllib3.connectionpool - DEBUG - https://data.alpaca.markets:443 "GET /v2/stocks/trades/latest?symbols=UNH HTTP/1.1" 200 124
2026-04-08 11:12:03,858 - data_collection.monitoring.high_frequency_monitor - DEBUG - [UNH] $307.31 → $307.31 (+0.00%)
2026-04-08 11:12:13,859 - data_collection.monitoring.high_frequency_monitor - DEBUG - [모니터링 루프 #10] 1개 종목 체크 중...
2026-04-08 11:12:14,039 - urllib3.connectionpool - DEBUG - https://data.alpaca.markets:443 "GET /v2/stocks/trades/latest?symbols=UNH HTTP/1.1" 200 124
2026-04-08 11:12:14,040 - data_collection.monitoring.high_frequency_monitor - DEBUG - [UNH] $307.31 → $307.31 (+0.00%)
2026-04-08 11:12:24,042 - data_collection.monitoring.high_frequency_monitor - DEBUG - [모니터링 루프 #11] 1개 종목 체크 중...
2026-04-08 11:12:24,222 - urllib3.connectionpool - DEBUG - https://data.alpaca.markets:443 "GET /v2/stocks/trades/latest?symbols=UNH HTTP/1.1" 200 124
2026-04-08 11:12:24,223 - data_collection.monitoring.high_frequency_monitor - DEBUG - [UNH] $307.31 → $307.31 (+0.00%)
2026-04-08 11:12:34,223 - data_collection.monitoring.high_frequency_monitor - DEBUG - [모니터링 루프 #12] 1개 종목 체크 중...
2026-04-08 11:12:34,404 - urllib3.connectionpool - DEBUG - https://data.alpaca.markets:443 "GET /v2/stocks/trades/latest?symbols=UNH HTTP/1.1" 200 124
2026-04-08 11:12:34,404 - data_collection.monitoring.high_frequency_monitor - DEBUG - [UNH] $307.31 → $307.31 (+0.00%)
2026-04-08 11:12:44,417 - data_collection.monitoring.high_frequency_monitor - DEBUG - [모니터링 루프 #13] 1개 종목 체크 중...
2026-04-08 11:12:44,599 - urllib3.connectionpool - DEBUG - https://data.alpaca.markets:443 "GET /v2/stocks/trades/latest?symbols=UNH HTTP/1.1" 200 124
2026-04-08 11:12:44,599 - data_collection.monitoring.high_frequency_monitor - DEBUG - [UNH] $307.31 → $307.31 (+0.00%)
2026-04-08 11:12:54,602 - data_collection.monitoring.high_frequency_monitor - DEBUG - [모니터링 루프 #14] 1개 종목 체크 중...
2026-04-08 11:12:54,787 - urllib3.connectionpool - DEBUG - https://data.alpaca.markets:443 "GET /v2/stocks/trades/latest?symbols=UNH HTTP/1.1" 200 124
2026-04-08 11:12:54,787 - data_collection.monitoring.high_frequency_monitor - DEBUG - [UNH] $307.31 → $307.31 (+0.00%)
2026-04-08 11:13:04,792 - data_collection.monitoring.high_frequency_monitor - DEBUG - [모니터링 루프 #15] 1개 종목 체크 중...
2026-04-08 11:13:05,010 - urllib3.connectionpool - DEBUG - https://data.alpaca.markets:443 "GET /v2/stocks/trades/latest?symbols=UNH HTTP/1.1" 200 124
2026-04-08 11:13:05,010 - data_collection.monitoring.high_frequency_monitor - DEBUG - [UNH] $307.31 → $307.31 (+0.00%)
2026-04-08 11:13:15,015 - data_collection.monitoring.high_frequency_monitor - DEBUG - [모니터링 루프 #16] 1개 종목 체크 중...
2026-04-08 11:13:15,195 - urllib3.connectionpool - DEBUG - https://data.alpaca.markets:443 "GET /v2/stocks/trades/latest?symbols=UNH HTTP/1.1" 200 124
2026-04-08 11:13:15,195 - data_collection.monitoring.high_frequency_monitor - DEBUG - [UNH] $307.31 → $307.31 (+0.00%)
2026-04-08 11:13:25,202 - data_collection.monitoring.high_frequency_monitor - DEBUG - [모니터링 루프 #17] 1개 종목 체크 중...
2026-04-08 11:13:25,383 - urllib3.connectionpool - DEBUG - https://data.alpaca.markets:443 "GET /v2/stocks/trades/latest?symbols=UNH HTTP/1.1" 200 124
2026-04-08 11:13:25,383 - data_collection.monitoring.high_frequency_monitor - DEBUG - [UNH] $307.31 → $307.31 (+0.00%)
2026-04-08 11:13:35,389 - data_collection.monitoring.high_frequency_monitor - DEBUG - [모니터링 루프 #18] 1개 종목 체크 중...
2026-04-08 11:13:35,569 - urllib3.connectionpool - DEBUG - https://data.alpaca.markets:443 "GET /v2/stocks/trades/latest?symbols=UNH HTTP/1.1" 200 124
2026-04-08 11:13:35,569 - data_collection.monitoring.high_frequency_monitor - DEBUG - [UNH] $307.31 → $307.31 (+0.00%)
2026-04-08 11:13:45,579 - data_collection.monitoring.high_frequency_monitor - DEBUG - [모니터링 루프 #19] 1개 종목 체크 중...
2026-04-08 11:13:45,764 - urllib3.connectionpool - DEBUG - https://data.alpaca.markets:443 "GET /v2/stocks/trades/latest?symbols=UNH HTTP/1.1" 200 124
2026-04-08 11:13:45,765 - data_collection.monitoring.high_frequency_monitor - DEBUG - [UNH] $307.31 → $307.31 (+0.00%)
2026-04-08 11:13:55,767 - data_collection.monitoring.high_frequency_monitor - DEBUG - [모니터링 루프 #20] 1개 종목 체크 중...
2026-04-08 11:13:55,947 - urllib3.connectionpool - DEBUG - https://data.alpaca.markets:443 "GET /v2/stocks/trades/latest?symbols=UNH HTTP/1.1" 200 124
2026-04-08 11:13:55,948 - data_collection.monitoring.high_frequency_monitor - DEBUG - [UNH] $307.31 → $307.31 (+0.00%)
2026-04-08 11:14:05,959 - data_collection.monitoring.high_frequency_monitor - DEBUG - [모니터링 루프 #21] 1개 종목 체크 중...
2026-04-08 11:14:06,141 - urllib3.connectionpool - DEBUG - https://data.alpaca.markets:443 "GET /v2/stocks/trades/latest?symbols=UNH HTTP/1.1" 200 124
2026-04-08 11:14:06,142 - data_collection.monitoring.high_frequency_monitor - DEBUG - [UNH] $307.31 → $307.31 (+0.00%)
2026-04-08 11:14:16,156 - data_collection.monitoring.high_frequency_monitor - DEBUG - [모니터링 루프 #22] 1개 종목 체크 중...
2026-04-08 11:14:16,338 - urllib3.connectionpool - DEBUG - https://data.alpaca.markets:443 "GET /v2/stocks/trades/latest?symbols=UNH HTTP/1.1" 200 124
2026-04-08 11:14:16,338 - data_collection.monitoring.high_frequency_monitor - DEBUG - [UNH] $307.31 → $307.31 (+0.00%)
2026-04-08 11:14:26,340 - data_collection.monitoring.high_frequency_monitor - DEBUG - [모니터링 루프 #23] 1개 종목 체크 중...
2026-04-08 11:14:26,522 - urllib3.connectionpool - DEBUG - https://data.alpaca.markets:443 "GET /v2/stocks/trades/latest?symbols=UNH HTTP/1.1" 200 124
2026-04-08 11:14:26,523 - data_collection.monitoring.high_frequency_monitor - DEBUG - [UNH] $307.31 → $307.31 (+0.00%)
2026-04-08 11:14:36,528 - data_collection.monitoring.high_frequency_monitor - DEBUG - [모니터링 루프 #24] 1개 종목 체크 중...
2026-04-08 11:14:36,710 - urllib3.connectionpool - DEBUG - https://data.alpaca.markets:443 "GET /v2/stocks/trades/latest?symbols=UNH HTTP/1.1" 200 124
2026-04-08 11:14:36,711 - data_collection.monitoring.high_frequency_monitor - DEBUG - [UNH] $307.31 → $307.31 (+0.00%)
2026-04-08 11:14:46,717 - data_collection.monitoring.high_frequency_monitor - DEBUG - [모니터링 루프 #25] 1개 종목 체크 중...
2026-04-08 11:14:46,899 - urllib3.connectionpool - DEBUG - https://data.alpaca.markets:443 "GET /v2/stocks/trades/latest?symbols=UNH HTTP/1.1" 200 124
2026-04-08 11:14:46,899 - data_collection.monitoring.high_frequency_monitor - DEBUG - [UNH] $307.31 → $307.31 (+0.00%)
2026-04-08 11:14:56,907 - data_collection.monitoring.high_frequency_monitor - DEBUG - [모니터링 루프 #26] 1개 종목 체크 중...
2026-04-08 11:14:57,092 - urllib3.connectionpool - DEBUG - https://data.alpaca.markets:443 "GET /v2/stocks/trades/latest?symbols=UNH HTTP/1.1" 200 124
2026-04-08 11:14:57,092 - data_collection.monitoring.high_frequency_monitor - DEBUG - [UNH] $307.31 → $307.31 (+0.00%)
2026-04-08 11:15:07,094 - data_collection.monitoring.high_frequency_monitor - DEBUG - [모니터링 루프 #27] 1개 종목 체크 중...
2026-04-08 11:15:07,274 - urllib3.connectionpool - DEBUG - https://data.alpaca.markets:443 "GET /v2/stocks/trades/latest?symbols=UNH HTTP/1.1" 200 124
2026-04-08 11:15:07,274 - data_collection.monitoring.high_frequency_monitor - DEBUG - [UNH] $307.31 → $307.31 (+0.00%)
2026-04-08 11:15:17,284 - data_collection.monitoring.high_frequency_monitor - DEBUG - [모니터링 루프 #28] 1개 종목 체크 중...
2026-04-08 11:15:17,466 - urllib3.connectionpool - DEBUG - https://data.alpaca.markets:443 "GET /v2/stocks/trades/latest?symbols=UNH HTTP/1.1" 200 124
2026-04-08 11:15:17,466 - data_collection.monitoring.high_frequency_monitor - DEBUG - [UNH] $307.31 → $307.31 (+0.00%)
2026-04-08 11:15:27,474 - data_collection.monitoring.high_frequency_monitor - DEBUG - [모니터링 루프 #29] 1개 종목 체크 중...
2026-04-08 11:15:27,655 - urllib3.connectionpool - DEBUG - https://data.alpaca.markets:443 "GET /v2/stocks/trades/latest?symbols=UNH HTTP/1.1" 200 124
2026-04-08 11:15:27,655 - data_collection.monitoring.high_frequency_monitor - DEBUG - [UNH] $307.31 → $307.31 (+0.00%)
2026-04-08 11:15:37,660 - data_collection.monitoring.high_frequency_monitor - DEBUG - [모니터링 루프 #30] 1개 종목 체크 중...
2026-04-08 11:15:37,855 - urllib3.connectionpool - DEBUG - https://data.alpaca.markets:443 "GET /v2/stocks/trades/latest?symbols=UNH HTTP/1.1" 200 124
2026-04-08 11:15:37,856 - data_collection.monitoring.high_frequency_monitor - DEBUG - [UNH] $307.31 → $307.31 (+0.00%)
2026-04-08 11:15:41,292 - __main__ - INFO -
======================================================================
2026-04-08 11:15:41,292 - __main__ - INFO - [Stage 1] 전체 시장 스캔 시작
2026-04-08 11:15:41,292 - __main__ - INFO -   시각: 2026-04-08 11:15:41
2026-04-08 11:15:41,292 - __main__ - INFO -   미국 시장 시간: NO (장외)
2026-04-08 11:15:41,292 - __main__ - WARNING -   장외 시간이므로 워치리스트가 비어있을 수 있습니다
2026-04-08 11:15:41,293 - __main__ - INFO - ======================================================================
2026-04-08 11:15:41,293 - data_collection.monitoring.watchlist_generator - INFO - 워치리스트 생성 시작 (유니버스: 48개 종목)
2026-04-08 11:15:41,295 - urllib3.connectionpool - DEBUG - Resetting dropped connection: data.alpaca.markets
2026-04-08 11:15:42,413 - urllib3.connectionpool - DEBUG - https://data.alpaca.markets:443 "GET /v2/stocks/snapshots?symbols=AAPL%2CMSFT%2CGOOGL%2CAMZN%2CMETA%2CNVDA%2CTSLA%2CNFLX%2CJPM%2CBAC%2CWFC%2CGS%2CMS%2CJNJ%2CUNH%2CPFE%2CABBV%2CTMO%2CWMT%2CHD%2CDIS%2CNKE%2CSBUX%2CXOM%2CCVX%2CCOP%2CT%2CVZ%2CTMUS%2CBA%2CCAT%2CGE%2CUPS%2CCOST%2CTGT%2CAMD%2CINTC%2CCSCO%2CORCL%2CADBE%2CCOIN%2CSNAP%2CUBER%2CLYFT%2CSQ%2CROKU%2CPLTR%2CSOFI HTTP/1.1" 200 None
2026-04-08 11:15:42,591 - data_collection.monitoring.watchlist_generator - INFO - 스냅샷 조회 완료: 48개
2026-04-08 11:15:42,890 - urllib3.connectionpool - DEBUG - https://data.alpaca.markets:443 "GET /v2/stocks/bars?start=2026-03-14T11%3A15%3A42.592872%2B00%3A00&end=2026-04-08T11%3A15%3A42.592872%2B00%3A00&timeframe=1Day&feed=iex&symbols=AAPL%2CMSFT%2CGOOGL%2CAMZN%2CMETA%2CNVDA%2CTSLA%2CNFLX%2CJPM%2CBAC%2CWFC%2CGS%2CMS%2CJNJ%2CUNH%2CPFE%2CABBV%2CTMO%2CWMT%2CHD%2CDIS%2CNKE%2CSBUX%2CXOM%2CCVX%2CCOP%2CT%2CVZ%2CTMUS%2CBA%2CCAT%2CGE%2CUPS%2CCOST%2CTGT%2CAMD%2CINTC%2CCSCO%2CORCL%2CADBE%2CCOIN%2CSNAP%2CUBER%2CLYFT%2CSQ%2CROKU%2CPLTR%2CSOFI HTTP/1.1" 200 None
2026-04-08 11:15:43,082 - data_collection.monitoring.watchlist_generator - INFO - 거래량 평균 계산 완료: 47개
2026-04-08 11:15:43,083 - data_collection.monitoring.watchlist_generator - DEBUG - SQ: 거래량 평균 없음
2026-04-08 11:15:43,083 - data_collection.monitoring.watchlist_generator - INFO - 처리 결과: 총 48개, 후보 1개, 스킵 1개
2026-04-08 11:15:43,083 - data_collection.monitoring.watchlist_generator - INFO - [OK] 워치리스트 생성 완료: 1개 종목
2026-04-08 11:15:43,083 - data_collection.monitoring.watchlist_generator - INFO - 상위 5개:
2026-04-08 11:15:43,083 - data_collection.monitoring.watchlist_generator - INFO -   1. UNH: 거래량 3.2배
2026-04-08 11:15:43,084 - __main__ - INFO -
워치리스트 갱신:
2026-04-08 11:15:43,084 - __main__ - INFO -   1. UNH: 거래량 3.2배
2026-04-08 11:15:43,084 - data_collection.monitoring.high_frequency_monitor - INFO - 워치리스트 설정 완료: 1개 종목
2026-04-08 11:15:43,084 - data_collection.monitoring.high_frequency_monitor - INFO -   - UNH
2026-04-08 11:15:43,084 - __main__ - INFO -
다음 시장 스캔까지 5분 대기...
2026-04-08 11:15:47,862 - data_collection.monitoring.high_frequency_monitor - DEBUG - [모니터링 루프 #31] 1개 종목 체크 중...
2026-04-08 11:15:48,047 - urllib3.connectionpool - DEBUG - https://data.alpaca.markets:443 "GET /v2/stocks/trades/latest?symbols=UNH HTTP/1.1" 200 124
2026-04-08 11:15:48,047 - data_collection.monitoring.high_frequency_monitor - DEBUG - [UNH] $307.31 → $307.31 (+0.00%)
2026-04-08 11:15:58,062 - data_collection.monitoring.high_frequency_monitor - DEBUG - [모니터링 루프 #32] 1개 종목 체크 중...
2026-04-08 11:15:58,245 - urllib3.connectionpool - DEBUG - https://data.alpaca.markets:443 "GET /v2/stocks/trades/latest?symbols=UNH HTTP/1.1" 200 124
2026-04-08 11:15:58,246 - data_collection.monitoring.high_frequency_monitor - DEBUG - [UNH] $307.31 → $307.31 (+0.00%)
2026-04-08 11:16:08,248 - data_collection.monitoring.high_frequency_monitor - DEBUG - [모니터링 루프 #33] 1개 종목 체크 중...
2026-04-08 11:16:08,429 - urllib3.connectionpool - DEBUG - https://data.alpaca.markets:443 "GET /v2/stocks/trades/latest?symbols=UNH HTTP/1.1" 200 124
2026-04-08 11:16:08,430 - data_collection.monitoring.high_frequency_monitor - DEBUG - [UNH] $307.31 → $307.31 (+0.00%)
2026-04-08 11:16:18,438 - data_collection.monitoring.high_frequency_monitor - DEBUG - [모니터링 루프 #34] 1개 종목 체크 중...
2026-04-08 11:16:18,618 - urllib3.connectionpool - DEBUG - https://data.alpaca.markets:443 "GET /v2/stocks/trades/latest?symbols=UNH HTTP/1.1" 200 124
2026-04-08 11:16:18,619 - data_collection.monitoring.high_frequency_monitor - DEBUG - [UNH] $307.31 → $307.31 (+0.00%)
2026-04-08 11:16:28,632 - data_collection.monitoring.high_frequency_monitor - DEBUG - [모니터링 루프 #35] 1개 종목 체크 중...
2026-04-08 11:16:28,825 - urllib3.connectionpool - DEBUG - https://data.alpaca.markets:443 "GET /v2/stocks/trades/latest?symbols=UNH HTTP/1.1" 200 124
2026-04-08 11:16:28,825 - data_collection.monitoring.high_frequency_monitor - DEBUG - [UNH] $307.31 → $307.31 (+0.00%)
2026-04-08 11:16:38,835 - data_collection.monitoring.high_frequency_monitor - DEBUG - [모니터링 루프 #36] 1개 종목 체크 중...
2026-04-08 11:16:39,017 - urllib3.connectionpool - DEBUG - https://data.alpaca.markets:443 "GET /v2/stocks/trades/latest?symbols=UNH HTTP/1.1" 200 124
2026-04-08 11:16:39,018 - data_collection.monitoring.high_frequency_monitor - DEBUG - [UNH] $307.31 → $307.31 (+0.00%)
2026-04-08 11:16:49,021 - data_collection.monitoring.high_frequency_monitor - DEBUG - [모니터링 루프 #37] 1개 종목 체크 중...
2026-04-08 11:16:49,203 - urllib3.connectionpool - DEBUG - https://data.alpaca.markets:443 "GET /v2/stocks/trades/latest?symbols=UNH HTTP/1.1" 200 124
2026-04-08 11:16:49,203 - data_collection.monitoring.high_frequency_monitor - DEBUG - [UNH] $307.31 → $307.31 (+0.00%)
2026-04-08 11:16:59,211 - data_collection.monitoring.high_frequency_monitor - DEBUG - [모니터링 루프 #38] 1개 종목 체크 중...
2026-04-08 11:16:59,394 - urllib3.connectionpool - DEBUG - https://data.alpaca.markets:443 "GET /v2/stocks/trades/latest?symbols=UNH HTTP/1.1" 200 124
2026-04-08 11:16:59,395 - data_collection.monitoring.high_frequency_monitor - DEBUG - [UNH] $307.31 → $307.31 (+0.00%)
2026-04-08 11:17:09,400 - data_collection.monitoring.high_frequency_monitor - DEBUG - [모니터링 루프 #39] 1개 종목 체크 중...
2026-04-08 11:17:09,583 - urllib3.connectionpool - DEBUG - https://data.alpaca.markets:443 "GET /v2/stocks/trades/latest?symbols=UNH HTTP/1.1" 200 124
2026-04-08 11:17:09,583 - data_collection.monitoring.high_frequency_monitor - DEBUG - [UNH] $307.31 → $307.31 (+0.00%)
2026-04-08 11:17:19,586 - data_collection.monitoring.high_frequency_monitor - DEBUG - [모니터링 루프 #40] 1개 종목 체크 중...
2026-04-08 11:17:19,766 - urllib3.connectionpool - DEBUG - https://data.alpaca.markets:443 "GET /v2/stocks/trades/latest?symbols=UNH HTTP/1.1" 200 124
2026-04-08 11:17:19,767 - data_collection.monitoring.high_frequency_monitor - DEBUG - [UNH] $307.31 → $307.31 (+0.00%)
2026-04-08 11:17:29,777 - data_collection.monitoring.high_frequency_monitor - DEBUG - [모니터링 루프 #41] 1개 종목 체크 중...
2026-04-08 11:17:29,957 - urllib3.connectionpool - DEBUG - https://data.alpaca.markets:443 "GET /v2/stocks/trades/latest?symbols=UNH HTTP/1.1" 200 124
2026-04-08 11:17:29,958 - data_collection.monitoring.high_frequency_monitor - DEBUG - [UNH] $307.31 → $307.31 (+0.00%)
2026-04-08 11:17:39,967 - data_collection.monitoring.high_frequency_monitor - DEBUG - [모니터링 루프 #42] 1개 종목 체크 중...
2026-04-08 11:17:40,147 - urllib3.connectionpool - DEBUG - https://data.alpaca.markets:443 "GET /v2/stocks/trades/latest?symbols=UNH HTTP/1.1" 200 124
2026-04-08 11:17:40,147 - data_collection.monitoring.high_frequency_monitor - DEBUG - [UNH] $307.31 → $307.31 (+0.00%)
2026-04-08 11:17:50,155 - data_collection.monitoring.high_frequency_monitor - DEBUG - [모니터링 루프 #43] 1개 종목 체크 중...
2026-04-08 11:17:50,338 - urllib3.connectionpool - DEBUG - https://data.alpaca.markets:443 "GET /v2/stocks/trades/latest?symbols=UNH HTTP/1.1" 200 124
2026-04-08 11:17:50,338 - data_collection.monitoring.high_frequency_monitor - DEBUG - [UNH] $307.31 → $307.31 (+0.00%)
2026-04-08 11:18:00,338 - __main__ - INFO -
태스크 취소됨
2026-04-08 11:18:00,338 - __main__ - INFO -
자동매매 봇 V2 종료 중...
2026-04-08 11:18:00,338 - data_collection.monitoring.high_frequency_monitor - INFO - 모니터링 루프 취소됨
2026-04-08 11:18:00,338 - data_collection.monitoring.high_frequency_monitor - INFO - 고주기 모니터링 중지
2026-04-08 11:18:00,339 - __main__ - INFO - ✓ 고주기 모니터 중지
2026-04-08 11:18:00,340 - execution_team.brokers.alpaca_broker - INFO - Alpaca 연결 해제
2026-04-08 11:18:00,340 - __main__ - INFO - ✓ 브로커 연결 해제
2026-04-08 11:18:00,340 - __main__ - INFO - ✓ 자동매매 봇 V2 종료 완료