"""
Native Tool Calling Agent 테스트

완전한 Agent가 도구를 자율적으로 선택하는지 확인
"""

import os
import sys
from pathlib import Path

# 부모 디렉토리를 Python 경로에 추가
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

from dotenv import load_dotenv
load_dotenv()

# Agent 타입 강제 설정
os.environ["AI_AGENT_TYPE"] = "native"

print("\n" + "="*60)
print("Native Tool Calling Agent 테스트")
print("="*60)

# API 키 확인
if not os.getenv('ANTHROPIC_API_KEY'):
    print("\n⚠️  ANTHROPIC_API_KEY가 설정되지 않았습니다.")
    exit(1)

print("\n[1] Agent 초기화 중...")
try:
    from ai_team.agents.trading_agent_native import NativeTradingAgent
    agent = NativeTradingAgent()
    print("✓ Native Tool Calling Agent 초기화 성공!")
    print(f"✓ 사용 가능한 도구: {agent.get_tool_names()}")
except Exception as e:
    print(f"✗ Agent 초기화 실패: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

print("\n[2] 간단한 질문 테스트...")
try:
    response = agent.chat("시장 리스크를 평가해주세요.")
    print(f"\n응답:\n{response}")
    print("\n✓ 대화 기능 작동!")
except Exception as e:
    print(f"✗ 대화 실패: {e}")

print("\n[3] 종목 분석 테스트...")
print("Agent가 자율적으로 도구를 선택하여 분석합니다...")

try:
    result = agent.analyze_stock("AAPL", context={
        "base_score": 75,
        "rsi": 65
    })

    print(f"\n분석 결과:")
    print(f"- 실행 단계: {result['steps_taken']}")
    print(f"- 사용된 도구: {result['tools_used']}")
    print(f"- 점수 보정: {result['score_adjustment']:+.2f}")
    print(f"- 추천: {result['recommendation']}")
    print(f"\n상세 분석:\n{result['analysis']}")

    print("\n✓ Agent가 자율적으로 도구를 선택하여 분석 완료!")

except Exception as e:
    print(f"✗ 분석 실패: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*60)
print("테스트 완료!")
print("="*60 + "\n")
