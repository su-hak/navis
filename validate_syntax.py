"""
Syntax validation script
코드 구문이 올바른지 검증 (실행은 하지 않음)
"""

import py_compile
import sys
from pathlib import Path

files_to_check = [
    "ai_team/agents/trading_agent_native.py",
    "ai_team/agents/trading_agent.py",
    "ai_team/news/analyzer.py",
    "ai_team/news/collector.py",
    "ai_team/api/main.py",
    "ai_team/config.py",
]

print("=" * 60)
print("AI Team 구문 검증")
print("=" * 60)

errors = []
for file_path in files_to_check:
    full_path = Path(__file__).parent / file_path
    try:
        py_compile.compile(str(full_path), doraise=True)
        print(f"✓ {file_path}")
    except py_compile.PyCompileError as e:
        print(f"✗ {file_path}: {e}")
        errors.append(file_path)

print("=" * 60)
if errors:
    print(f"✗ {len(errors)}개 파일에 구문 오류가 있습니다")
    sys.exit(1)
else:
    print(f"✓ 모든 파일 구문 검증 성공! ({len(files_to_check)}개 파일)")
    print("=" * 60)
