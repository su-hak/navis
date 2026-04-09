"""
로그 감시 AI 에이전트

auto_trading_bot_v2.py의 로그 파일을 실시간 감시하여
에러 감지 시 Claude API로 원인 분석 + 수정 방안을 텔레그램으로 전송합니다.
"""

import os
import asyncio
import logging
import hashlib
import re
from datetime import datetime, timedelta
from typing import Optional
from pathlib import Path

import anthropic
import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# 텔레그램 메시지 최대 길이
TELEGRAM_MAX_LEN = 4000
# 동일 에러 재알림 억제 기간 (분)
ERROR_COOLDOWN_MINUTES = 30
# 에러 감지 후 수집 대기 (초) - traceback 전체가 쌓일 시간
ERROR_COLLECT_SECONDS = 2.0


class LogMonitorAgent:
    """
    로그 파일을 tail하며 에러를 감지하고
    Claude API로 분석하여 텔레그램으로 전송합니다.
    """

    def __init__(
        self,
        log_file: str = "logs/auto_trading_v2.log",
        poll_interval: float = 5.0,
    ):
        self.log_file = Path(log_file)
        self.poll_interval = poll_interval
        self._file_position = 0
        self._seen_errors: dict[str, datetime] = {}  # hash → 마지막 알림 시각

        self.anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        self.telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")

        if not self.anthropic_key:
            raise ValueError("ANTHROPIC_API_KEY가 설정되지 않았습니다")
        if not self.telegram_token or not self.telegram_chat_id:
            raise ValueError("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID가 설정되지 않았습니다")

        self.claude = anthropic.Anthropic(api_key=self.anthropic_key)

    # ──────────────────────────────────────────────
    # 로그 파일 tail
    # ──────────────────────────────────────────────

    def _read_new_lines(self) -> list[str]:
        """마지막 읽은 위치 이후의 새 줄을 반환합니다."""
        if not self.log_file.exists():
            return []
        try:
            with open(self.log_file, "r", encoding="utf-8", errors="replace") as f:
                f.seek(self._file_position)
                new_content = f.read()
                self._file_position = f.tell()
            return new_content.splitlines() if new_content else []
        except OSError as e:
            logger.warning(f"로그 파일 읽기 실패: {e}")
            return []

    def _fast_forward_to_end(self):
        """기동 시 기존 로그를 건너뜁니다 (과거 에러 무시)."""
        if self.log_file.exists():
            self._file_position = self.log_file.stat().st_size

    # ──────────────────────────────────────────────
    # 에러 블록 추출
    # ──────────────────────────────────────────────

    @staticmethod
    def _extract_error_blocks(lines: list[str]) -> list[str]:
        """
        로그 줄에서 Traceback 블록을 추출합니다.
        여러 개의 독립적인 에러가 있으면 각각 반환합니다.
        """
        blocks: list[str] = []
        current: list[str] = []
        in_traceback = False

        for line in lines:
            if "Traceback (most recent call last)" in line:
                if current:
                    blocks.append("\n".join(current))
                current = [line]
                in_traceback = True
            elif in_traceback:
                current.append(line)
                # Error:/Exception: 로 끝나는 줄이 나오면 블록 종료
                if re.search(r"^\w+Error:|^\w+Exception:|^RuntimeError:|^ValueError:|^AttributeError:", line):
                    blocks.append("\n".join(current))
                    current = []
                    in_traceback = False
            elif " - ERROR - " in line and not in_traceback:
                # Traceback 없는 단순 ERROR 로그도 포함
                blocks.append(line)

        if current:
            blocks.append("\n".join(current))

        return blocks

    # ──────────────────────────────────────────────
    # 중복 억제
    # ──────────────────────────────────────────────

    def _is_duplicate(self, error_text: str) -> bool:
        """동일 에러가 COOLDOWN 이내에 이미 전송됐으면 True."""
        key = hashlib.md5(error_text[:300].encode()).hexdigest()
        last_sent = self._seen_errors.get(key)
        if last_sent and datetime.now() - last_sent < timedelta(minutes=ERROR_COOLDOWN_MINUTES):
            return True
        self._seen_errors[key] = datetime.now()
        return False

    # ──────────────────────────────────────────────
    # Claude API 분석
    # ──────────────────────────────────────────────

    def _analyze_with_claude(self, error_text: str) -> str:
        """Claude API로 에러 원인 분석 및 수정 방안을 생성합니다."""
        prompt = f"""나는 Python 자동매매 봇(navis)을 운영 중입니다.
아래 에러가 발생했습니다. 간결하게 분석해 주세요.

에러:
```
{error_text[:2000]}
```

다음 형식으로 답하세요:

**원인**: (1~2줄)
**수정 파일**: 파일명:줄번호
**수정 코드**:
```python
# 수정 전
...
# 수정 후
...
```
**위험도**: 낮음 / 중간 / 높음 (매매에 미치는 영향)"""

        try:
            response = self.claude.messages.create(
                model="claude-haiku-4-5-20251001",  # 빠르고 저렴한 모델 사용
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"Claude API 호출 실패: {e}")
            return f"(Claude 분석 실패: {e})\n\n원본 에러:\n{error_text[:500]}"

    # ──────────────────────────────────────────────
    # 텔레그램 전송
    # ──────────────────────────────────────────────

    async def _send_telegram(self, text: str):
        """텔레그램 메시지를 전송합니다. 길면 분할 전송합니다."""
        url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"

        # 길이 초과 시 분할
        chunks = [text[i:i + TELEGRAM_MAX_LEN] for i in range(0, len(text), TELEGRAM_MAX_LEN)]

        async with httpx.AsyncClient(timeout=10) as client:
            for chunk in chunks:
                payload = {
                    "chat_id": self.telegram_chat_id,
                    "text": chunk,
                    "parse_mode": "Markdown",
                }
                try:
                    resp = await client.post(url, json=payload)
                    resp.raise_for_status()
                except Exception as e:
                    logger.error(f"텔레그램 전송 실패: {e}")

    # ──────────────────────────────────────────────
    # 메인 루프
    # ──────────────────────────────────────────────

    async def run(self):
        """로그 감시 메인 루프"""
        logger.info(f"로그 감시 에이전트 시작: {self.log_file}")
        self._fast_forward_to_end()  # 기존 로그 건너뜀

        await self._send_telegram("🤖 *로그 감시 에이전트 시작*\n에러 감지 시 자동으로 분석 결과를 전송합니다.")

        while True:
            try:
                await asyncio.sleep(self.poll_interval)

                lines = self._read_new_lines()
                if not lines:
                    continue

                # 에러 블록이 쌓일 시간 확보
                await asyncio.sleep(ERROR_COLLECT_SECONDS)
                lines += self._read_new_lines()

                error_blocks = self._extract_error_blocks(lines)

                for error_text in error_blocks:
                    if self._is_duplicate(error_text):
                        logger.debug("중복 에러 - 스킵")
                        continue

                    logger.warning(f"에러 감지, Claude 분석 중...\n{error_text[:200]}")

                    # 동기 Claude 호출을 executor로 실행
                    loop = asyncio.get_event_loop()
                    analysis = await loop.run_in_executor(
                        None, self._analyze_with_claude, error_text
                    )

                    now_str = datetime.now().strftime("%m/%d %H:%M:%S")
                    message = (
                        f"🚨 *navis 에러 감지* `{now_str}`\n\n"
                        f"```\n{error_text[:600]}\n```\n\n"
                        f"{analysis}"
                    )
                    await self._send_telegram(message)

            except asyncio.CancelledError:
                logger.info("로그 감시 에이전트 종료")
                break
            except Exception as e:
                logger.error(f"로그 감시 루프 오류: {e}")
                await asyncio.sleep(30)


# ──────────────────────────────────────────────
# auto_trading_bot_v2.py와 통합하기 위한 헬퍼
# ──────────────────────────────────────────────

def start_log_monitor_thread(log_file: str = "logs/auto_trading_v2.log"):
    """
    별도 스레드에서 로그 감시 에이전트를 실행합니다.
    auto_trading_bot_v2.py의 run()에서 호출하세요.

    사용법:
        from log_monitor_agent import start_log_monitor_thread
        start_log_monitor_thread()
    """
    import threading

    def _run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        agent = LogMonitorAgent(log_file=log_file)
        try:
            loop.run_until_complete(agent.run())
        except Exception as e:
            logger.error(f"로그 감시 에이전트 종료: {e}")
        finally:
            loop.close()

    thread = threading.Thread(target=_run, daemon=True, name="LogMonitorAgent")
    thread.start()
    logger.info("✓ 로그 감시 에이전트 스레드 시작")
    return thread


if __name__ == "__main__":
    # 단독 실행 테스트
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    asyncio.run(LogMonitorAgent().run())
