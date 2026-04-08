"""
전략 엔진 구조 검증 스크립트

파일이 제대로 생성되었는지 확인합니다.
"""

import os
from pathlib import Path

def validate_strategy_engine():
    """전략 엔진 구조 검증"""

    print("=" * 60)
    print("전략 엔진 구조 검증")
    print("=" * 60)

    # 프로젝트 루트 찾기
    current_dir = Path(__file__).parent

    # 필수 파일 목록
    required_files = {
        "indicators": [
            "__init__.py",
            "technical_indicators.py"
        ],
        "filters": [
            "__init__.py",
            "stock_filter.py"
        ],
        "scoring": [
            "__init__.py",
            "score_calculator.py"
        ],
        "signals": [
            "__init__.py",
            "signal_generator.py"
        ],
        "api": [
            "__init__.py",
            "strategy_api.py"
        ],
        "tests": [
            "__init__.py",
            "test_strategy_engine.py"
        ]
    }

    root_files = [
        "__init__.py",
        "README.md",
        "example.py",
        "quick_test.py",
        "RUN_TESTS.md",
        "validate_structure.py"
    ]

    all_ok = True

    # 루트 파일 확인
    print("\n[루트 파일 확인]")
    for file in root_files:
        file_path = current_dir / file
        if file_path.exists():
            size = file_path.stat().st_size
            print(f"  ✅ {file} ({size:,} bytes)")
        else:
            print(f"  ❌ {file} - 없음")
            all_ok = False

    # 모듈별 파일 확인
    for module, files in required_files.items():
        print(f"\n[{module} 모듈]")
        module_path = current_dir / module

        if not module_path.exists():
            print(f"  ❌ {module} 디렉토리 없음")
            all_ok = False
            continue

        for file in files:
            file_path = module_path / file
            if file_path.exists():
                size = file_path.stat().st_size
                print(f"  ✅ {file} ({size:,} bytes)")
            else:
                print(f"  ❌ {file} - 없음")
                all_ok = False

    # 통계
    print("\n" + "=" * 60)
    print("통계")
    print("=" * 60)

    total_files = 0
    total_size = 0

    for root, dirs, files in os.walk(current_dir):
        for file in files:
            if file.endswith('.py'):
                file_path = Path(root) / file
                total_files += 1
                total_size += file_path.stat().st_size

    print(f"  총 Python 파일: {total_files}개")
    print(f"  총 코드 크기: {total_size:,} bytes ({total_size / 1024:.1f} KB)")

    # 핵심 함수 확인
    print("\n" + "=" * 60)
    print("핵심 함수 확인")
    print("=" * 60)

    # score_calculator.py에서 score_stock 함수 확인
    score_calc_file = current_dir / "scoring" / "score_calculator.py"
    if score_calc_file.exists():
        content = score_calc_file.read_text(encoding='utf-8')
        if 'def score_stock(' in content:
            print("  ✅ score_stock() 함수 발견")
        else:
            print("  ❌ score_stock() 함수 없음")
            all_ok = False

    # signal_generator.py에서 generate_buy_signal 함수 확인
    signal_gen_file = current_dir / "signals" / "signal_generator.py"
    if signal_gen_file.exists():
        content = signal_gen_file.read_text(encoding='utf-8')
        if 'def generate_buy_signal(' in content:
            print("  ✅ generate_buy_signal() 함수 발견")
        else:
            print("  ❌ generate_buy_signal() 함수 없음")
            all_ok = False

        if 'def generate_sell_signal(' in content:
            print("  ✅ generate_sell_signal() 함수 발견")
        else:
            print("  ❌ generate_sell_signal() 함수 없음")
            all_ok = False

    # 최종 결과
    print("\n" + "=" * 60)
    if all_ok:
        print("🎉 구조 검증 완료! 모든 파일이 정상입니다.")
        print("=" * 60)
        print("\n다음 단계:")
        print("1. PowerShell에서 실행: cd C:\\navis")
        print("2. 의존성 설치: pip install pandas numpy ta")
        print("3. 테스트 실행: python strategy_engine/tests/test_strategy_engine.py")
        return True
    else:
        print("❌ 일부 파일이 누락되었습니다.")
        print("=" * 60)
        return False

if __name__ == "__main__":
    try:
        success = validate_strategy_engine()
        exit(0 if success else 1)
    except Exception as e:
        print(f"\n오류 발생: {e}")
        exit(1)
