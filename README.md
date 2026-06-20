# Danddobot (디스코드 챗봇)

로컬 서버 환경에서 작동하는 독립적인 로컬 LLM 컨테이너와 직접 통신하여 질문에 답변하는 Python 기반 디스코드 챗봇 프로젝트입니다. 
본 챗봇은 Docker 컨테이너 환경에서 실행되며, 로컬 LLM과의 의존성을 낮추는 어댑터 구조로 설계되었습니다.

---

## 주요 기능

1. **독립적인 도커 네트워크 통신:** 로컬 LLM과 디스코드 챗봇이 독립된 컨테이너로 가동되지만, 동일한 도커 네트워크(예: `danddobot-network`)를 공유하여 안전하고 다이렉트로 통신합니다.
2. **느슨한 결합 (어댑터 패턴):** 챗봇 메인 로직은 LLM의 하위 규격에 종속되지 않습니다. `BaseLLMClient` 추상 클래스를 기반으로 Ollama 및 OpenAI 호환 API 규격 클라이언트가 제공되므로, 환경 변수 수정만으로 손쉽게 LLM 엔진을 전환할 수 있습니다.
3. **실시간 페르소나 리로드:** 페르소나 설정 파일(`config/persona.txt`)이 호스트 볼륨으로 마운트됩니다. 챗봇을 재실행할 필요 없이 텍스트 파일만 편집하면 실시간으로 AI 챗봇의 성격과 지시사항(System Prompt)이 적용됩니다.
4. **2,000자 응답 분할 전송:** 디스코드 메시지의 2,000자 제한을 처리하기 위해 줄바꿈 단위를 보존하며 안전하게 청크 분할하여 전송합니다.

---

## 프로젝트 구조

```
danddobot-antigravity/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .gitignore
├── .env.example
├── config/
│   └── persona.txt       # 챗봇의 페르소나 설정 파일 (동적 반영)
└── src/
    ├── __init__.py
    ├── main.py           # 엔트리 포인트 및 환경 변수 검증
    ├── bot.py            # 디스코드 이벤트 루프 및 메시지 처리
    └── llm_client.py     # 로컬 LLM 연동 어댑터 패턴 모듈
```

---

## 환경 변수 설정 (`.env`)

로컬 데스크톱 또는 서버의 루트 디렉토리에 `.env` 파일을 생성하고 아래 형식을 기입합니다:

```ini
DISCORD_TOKEN=your_discord_bot_token
DISCORD_CHANNEL_ID=your_target_channel_id

# LLM 엔진 선택: OLLAMA 또는 OPENAI_COMPATIBLE
LLM_PROVIDER=OLLAMA
# 동일 도커 네트워크 상의 LLM 컨테이너 주소
LLM_API_URL=http://local-llm:11434
LLM_MODEL=llama3

# 페르소나 시스템 프롬프트 파일 경로
PERSONA_FILE_PATH=config/persona.txt
```

---

## 로컬 개발 및 실행 방법

### Prerequisite
- Python 3.11 이상 설치 권장
- Docker 및 Docker Compose

### 1. 패키지 설치 및 로컬 실행 (데스크톱)
```bash
pip install -r requirements.txt
# .env 설정 세팅 완료 후 실행
python -m src.main
```

### 2. 로컬 도커 빌드 및 실행
컨테이너 빌드 및 테스트:
```bash
# 가상 네트워크 생성 (이미 존재하면 생략 가능)
docker network create danddobot-network

# 빌드 및 실행
docker compose up --build -d
```

---

## DevOps 및 Git Hook 배포 프로세스

로컬 데스크톱에서 개발을 진행하고, 원격 Ubuntu 서버로 자동 빌드 및 배포를 수행하기 위해 **Git post-receive Hook** 방식을 설정합니다.

### 1. Ubuntu 서버 측 설정 (최초 1회)

서버 터미널에 접속하여 소스 코드가 체크아웃될 디렉토리와 Git 배포용 Bare 저장소를 만듭니다.

```bash
# 1. Bare 저장소 및 배포 타겟 폴더 생성
mkdir -p ~/danddobot.git
mkdir -p ~/danddobot-app

# 2. Bare 저장소 초기화
cd ~/danddobot.git
git init --bare
```

그 후, `~/danddobot.git/hooks/post-receive` 파일을 작성합니다:

```bash
#!/bin/bash
TARGET="/home/ubuntu/danddobot-app"
GIT_DIR="/home/ubuntu/danddobot.git"

# 1. 코드 체크아웃
mkdir -p $TARGET
git --work-tree=$TARGET --git-dir=$GIT_DIR checkout -f

# 2. 컨테이너 빌드 및 재기동
cd $TARGET

# 외부 네트워크 생성 확인
docker network inspect danddobot-network >/dev/null 2>&1 || docker network create danddobot-network

# 컨테이너 내리기 및 재생성 빌드 실행
docker compose down
docker compose up --build -d

echo "=== 배포가 성공적으로 완료되었습니다! ==="
```

작성된 훅 스크립트에 실행 권한을 부여합니다:
```bash
chmod +x ~/danddobot.git/hooks/post-receive
```

### 2. 로컬 데스크톱 측 설정

로컬 프로젝트 폴더(`c:\dev\danddobot-antigravity`) 터미널에서 서버 원격 저장소를 등록합니다:

```powershell
# git 원격 저장소 추가 (ubuntu 서버 IP 및 사용자 기입)
git remote add server ubuntu@서버IP:danddobot.git
```

### 3. 변경 사항 배포 흐름

코드를 수정하고 원하는 시점에 커밋 후 푸시하면 서버 컨테이너가 자동으로 재빌드 및 배포됩니다:

```bash
git add .
git commit -m "feat: 대답 기능 개선"
git push server main
```
