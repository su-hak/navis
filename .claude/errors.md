Starting Container
INFO:     Started server process [2]
INFO:     Waiting for application startup.
2026-04-10 05:53:45,423 [INFO] notification_team.main: ============================================================
2026-04-10 05:53:45,423 [INFO] notification_team.main:   Navis 알림/리포트 팀 서버 시작
2026-04-10 05:53:45,423 [INFO] notification_team.main: ============================================================
2026-04-10 05:53:45,548 [INFO] notification_team.report_builder: ✓ 리포트 DB 연결: mysql.railway.internal:3306/railway
2026-04-10 05:53:45,548 [INFO] apscheduler.scheduler: Adding job tentatively -- it will be properly scheduled when the scheduler starts
2026-04-10 05:53:45,548 [INFO] notification_team.scheduler: ✓ 일일 리포트 등록: 월~금 16:10 ET
2026-04-10 05:53:45,548 [INFO] apscheduler.scheduler: Adding job tentatively -- it will be properly scheduled when the scheduler starts
2026-04-10 05:53:45,548 [INFO] notification_team.scheduler: ✓ 주간 리포트 등록: fri 16:30 ET
2026-04-10 05:53:45,550 [INFO] apscheduler.scheduler: Adding job tentatively -- it will be properly scheduled when the scheduler starts
2026-04-10 05:53:45,550 [INFO] notification_team.scheduler: ✓ 포지션 현황 등록: 매 60분
2026-04-10 05:53:45,550 [INFO] apscheduler.scheduler: Added job "일일 리포트" to job store "default"
2026-04-10 05:53:45,550 [INFO] apscheduler.scheduler: Added job "주간 리포트" to job store "default"
2026-04-10 05:53:45,550 [INFO] apscheduler.scheduler: Added job "포지션 현황" to job store "default"
2026-04-10 05:53:45,550 [INFO] apscheduler.scheduler: Scheduler started
2026-04-10 05:53:45,550 [INFO] notification_team.scheduler: ✓ 알림 스케줄러 시작: ['portfolio_status', 'daily_report', 'weekly_report']
ERROR:    Traceback (most recent call last):
  File "/usr/local/lib/python3.11/site-packages/starlette/routing.py", line 638, in lifespan
    async with self.lifespan_context(app) as maybe_state:
  File "/usr/local/lib/python3.11/contextlib.py", line 210, in __aenter__
    return await anext(self.gen)
           ^^^^^^^^^^^^^^^^^^^^^
  File "/app/notification_team/main.py", line 54, in lifespan
    positions = await _get_positions_from_backend()
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^
NameError: name '_get_positions_from_backend' is not defined
ERROR:    Application startup failed. Exiting.
INFO:     Started server process [2]
INFO:     Waiting for application startup.
2026-04-10 05:53:47,290 [INFO] notification_team.main: ============================================================
2026-04-10 05:53:47,290 [INFO] notification_team.main:   Navis 알림/리포트 팀 서버 시작
2026-04-10 05:53:47,290 [INFO] notification_team.main: ============================================================
2026-04-10 05:53:47,386 [INFO] notification_team.report_builder: ✓ 리포트 DB 연결: mysql.railway.internal:3306/railway
2026-04-10 05:53:47,386 [INFO] apscheduler.scheduler: Adding job tentatively -- it will be properly scheduled when the scheduler starts
2026-04-10 05:53:47,386 [INFO] notification_team.scheduler: ✓ 일일 리포트 등록: 월~금 16:10 ET
2026-04-10 05:53:47,387 [INFO] apscheduler.scheduler: Adding job tentatively -- it will be properly scheduled when the scheduler starts
2026-04-10 05:53:47,387 [INFO] notification_team.scheduler: ✓ 주간 리포트 등록: fri 16:30 ET
2026-04-10 05:53:47,388 [INFO] apscheduler.scheduler: Adding job tentatively -- it will be properly scheduled when the scheduler starts
2026-04-10 05:53:47,388 [INFO] notification_team.scheduler: ✓ 포지션 현황 등록: 매 60분
2026-04-10 05:53:47,389 [INFO] apscheduler.scheduler: Added job "일일 리포트" to job store "default"
2026-04-10 05:53:47,389 [INFO] apscheduler.scheduler: Added job "주간 리포트" to job store "default"
2026-04-10 05:53:47,389 [INFO] apscheduler.scheduler: Added job "포지션 현황" to job store "default"
2026-04-10 05:53:47,389 [INFO] apscheduler.scheduler: Scheduler started
2026-04-10 05:53:47,389 [INFO] notification_team.scheduler: ✓ 알림 스케줄러 시작: ['portfolio_status', 'daily_report', 'weekly_report']
ERROR:    Traceback (most recent call last):
  File "/usr/local/lib/python3.11/site-packages/starlette/routing.py", line 638, in lifespan
    async with self.lifespan_context(app) as maybe_state:
  File "/usr/local/lib/python3.11/contextlib.py", line 210, in __aenter__
    return await anext(self.gen)
           ^^^^^^^^^^^^^^^^^^^^^
  File "/app/notification_team/main.py", line 54, in lifespan
    positions = await _get_positions_from_backend()
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^
NameError: name '_get_positions_from_backend' is not defined
ERROR:    Application startup failed. Exiting.
INFO:     Started server process [2]
INFO:     Waiting for application startup.
2026-04-10 05:53:48,933 [INFO] notification_team.main: ============================================================
2026-04-10 05:53:48,933 [INFO] notification_team.main:   Navis 알림/리포트 팀 서버 시작
2026-04-10 05:53:48,933 [INFO] notification_team.main: ============================================================
2026-04-10 05:53:49,032 [INFO] notification_team.report_builder: ✓ 리포트 DB 연결: mysql.railway.internal:3306/railway
2026-04-10 05:53:49,032 [INFO] apscheduler.scheduler: Adding job tentatively -- it will be properly scheduled when the scheduler starts
2026-04-10 05:53:49,032 [INFO] notification_team.scheduler: ✓ 일일 리포트 등록: 월~금 16:10 ET
2026-04-10 05:53:49,033 [INFO] apscheduler.scheduler: Adding job tentatively -- it will be properly scheduled when the scheduler starts
2026-04-10 05:53:49,033 [INFO] notification_team.scheduler: ✓ 주간 리포트 등록: fri 16:30 ET
2026-04-10 05:53:49,034 [INFO] apscheduler.scheduler: Adding job tentatively -- it will be properly scheduled when the scheduler starts
2026-04-10 05:53:49,034 [INFO] notification_team.scheduler: ✓ 포지션 현황 등록: 매 60분
2026-04-10 05:53:49,034 [INFO] apscheduler.scheduler: Added job "일일 리포트" to job store "default"
2026-04-10 05:53:49,035 [INFO] apscheduler.scheduler: Added job "주간 리포트" to job store "default"
2026-04-10 05:53:49,035 [INFO] apscheduler.scheduler: Added job "포지션 현황" to job store "default"
2026-04-10 05:53:49,035 [INFO] apscheduler.scheduler: Scheduler started
2026-04-10 05:53:49,035 [INFO] notification_team.scheduler: ✓ 알림 스케줄러 시작: ['portfolio_status', 'daily_report', 'weekly_report']
ERROR:    Traceback (most recent call last):
  File "/usr/local/lib/python3.11/site-packages/starlette/routing.py", line 638, in lifespan
    async with self.lifespan_context(app) as maybe_state:
  File "/usr/local/lib/python3.11/contextlib.py", line 210, in __aenter__
    return await anext(self.gen)
           ^^^^^^^^^^^^^^^^^^^^^
  File "/app/notification_team/main.py", line 54, in lifespan
    positions = await _get_positions_from_backend()
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^
NameError: name '_get_positions_from_backend' is not defined
ERROR:    Application startup failed. Exiting.
INFO:     Started server process [2]
INFO:     Waiting for application startup.
2026-04-10 05:53:50,622 [INFO] notification_team.main: ============================================================
2026-04-10 05:53:50,623 [INFO] notification_team.main:   Navis 알림/리포트 팀 서버 시작
2026-04-10 05:53:50,623 [INFO] notification_team.main: ============================================================
2026-04-10 05:53:50,721 [INFO] notification_team.report_builder: ✓ 리포트 DB 연결: mysql.railway.internal:3306/railway
2026-04-10 05:53:50,722 [INFO] apscheduler.scheduler: Adding job tentatively -- it will be properly scheduled when the scheduler starts
2026-04-10 05:53:50,722 [INFO] notification_team.scheduler: ✓ 일일 리포트 등록: 월~금 16:10 ET
2026-04-10 05:53:50,722 [INFO] apscheduler.scheduler: Adding job tentatively -- it will be properly scheduled when the scheduler starts
2026-04-10 05:53:50,722 [INFO] notification_team.scheduler: ✓ 주간 리포트 등록: fri 16:30 ET
2026-04-10 05:53:50,723 [INFO] apscheduler.scheduler: Adding job tentatively -- it will be properly scheduled when the scheduler starts
2026-04-10 05:53:50,723 [INFO] notification_team.scheduler: ✓ 포지션 현황 등록: 매 60분
2026-04-10 05:53:50,724 [INFO] apscheduler.scheduler: Added job "일일 리포트" to job store "default"
2026-04-10 05:53:50,724 [INFO] apscheduler.scheduler: Added job "주간 리포트" to job store "default"
NameError: name '_get_positions_from_backend' is not defined
  File "/usr/local/lib/python3.11/contextlib.py", line 210, in __aenter__
    return await anext(self.gen)
2026-04-10 05:53:50,724 [INFO] apscheduler.scheduler: Added job "포지션 현황" to job store "default"
  File "/app/notification_team/main.py", line 54, in lifespan
           ^^^^^^^^^^^^^^^^^^^^^
ERROR:    Application startup failed. Exiting.
    positions = await _get_positions_from_backend()
2026-04-10 05:53:50,724 [INFO] apscheduler.scheduler: Scheduler started
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^
2026-04-10 05:53:50,724 [INFO] notification_team.scheduler: ✓ 알림 스케줄러 시작: ['portfolio_status', 'daily_report', 'weekly_report']
    async with self.lifespan_context(app) as maybe_state:
ERROR:    Traceback (most recent call last):
  File "/usr/local/lib/python3.11/site-packages/starlette/routing.py", line 638, in lifespan

