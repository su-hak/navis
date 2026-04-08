#!/bin/bash

# Strategy Engine API - Railway 빠른 배포 스크립트

echo "============================================================"
echo "  Strategy Engine API - Railway 배포"
echo "============================================================"

# 1. Railway CLI 확인
if ! command -v railway &> /dev/null
then
    echo ""
    echo "❌ Railway CLI가 설치되지 않았습니다."
    echo ""
    echo "설치 방법:"
    echo "  npm install -g @railway/cli"
    echo ""
    exit 1
fi

echo ""
echo "✅ Railway CLI 확인 완료"
echo ""

# 2. 로그인 확인
echo "Railway 로그인 확인 중..."
if ! railway whoami &> /dev/null
then
    echo ""
    echo "Railway에 로그인이 필요합니다."
    echo "로그인하시겠습니까? (y/n)"
    read -r response
    if [[ "$response" == "y" || "$response" == "Y" ]]; then
        railway login
    else
        echo "로그인이 취소되었습니다."
        exit 1
    fi
fi

echo ""
echo "✅ 로그인 완료"
echo ""

# 3. 프로젝트 초기화 (이미 있으면 스킵)
if [ ! -f ".railway" ]; then
    echo "Railway 프로젝트를 초기화합니다..."
    railway init
fi

echo ""
echo "✅ 프로젝트 초기화 완료"
echo ""

# 4. 배포
echo "============================================================"
echo "  배포 시작..."
echo "============================================================"
echo ""

railway up

echo ""
echo "============================================================"
echo "  ✅ 배포 완료!"
echo "============================================================"
echo ""
echo "다음 명령어로 앱을 열 수 있습니다:"
echo "  railway open"
echo ""
echo "API 문서: https://YOUR_APP.railway.app/docs"
echo ""
