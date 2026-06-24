# Danddobot (디스코드 챗봇)

로컬 서버 환경에서 작동하는 독립적인 로컬 LLM 컨테이너와 직접 통신하여 질문에 답변하는 Python 기반 디스코드 챗봇 프로젝트입니다. 
본 챗봇은 Docker 컨테이너 환경에서 실행되며, 로컬 LLM과의 의존성을 낮추는 어댑터 구조와 풍부한 관리자 기능을 탑재하고 있습니다.

---

## 🚀 주요 기능 및 최근 개선 사항

Danddobot은 단순한 단순 응답 봇을 넘어, 운영 편의성과 아키텍처 완성도를 높이기 위해 다음과 같은 설계와 고급 관리 기능을 도입했습니다:

### 1. ⚙️ 아키텍처 및 통신 최적화
* **느슨한 결합 (어댑터 패턴):** 챗봇 메인 로직은 LLM 규격에 종속되지 않습니다. `BaseLLMClient` 추상 클래스를 기반으로 Ollama, OpenAI 호환 API, llama.cpp, vLLM, LM Studio 등 다양한 엔진을 지원하며, 실시간 모델 변경이 가능합니다.
* **지속성 연결 풀링 (Connection Pooling):** `httpx.AsyncClient`를 이용한 지속성 연결 풀링을 적용하여 요청마다 소켓을 새로 생성하는 리소스 낭비(Socket Exhaustion)를 방지하고 대기 시간을 단축시켰습니다.
* **순차 동시성 처리 (FIFO Concurrency Lock):** 여러 사용자가 거의 동시에 질문을 입력하더라도, 컨텍스트 순서가 뒤섞이지 않고 요청 순서대로 안전하게 응답을 제어하는 `asyncio.Lock` 메커니즘을 내장하고 있습니다.

### 2. 🧠 중앙화된 상태 관리자 (`StateManager`)
* **원자적 상태 영구 저장:** 설정된 채널 ID, 타임아웃 수치, 대화 기억 모드 등 실시간으로 변경되는 설정값을 메모리 캐시에 동적으로 로드 및 관리합니다.
* **부작용 방지 및 성능 유지:** 잦은 파일 입출력으로 인한 병목을 해소하기 위해 캐시 형태로 메모리 단에서 값을 반환하며, 디스크 저장 시 임시 파일(`state.json.tmp`)에 기록 후 덮어쓰는 원자적(Atomic) 쓰기 방식으로 파일 손상을 완벽히 배포 방지합니다.

### 3. 🤖 전용 대화 채널 제어 및 실시간 상태 동기화
* **실시간 채널 동적 전환:** 사전 등록된 대화 채널 목록(`config/channels.txt`) 내에서 활성 채널을 드롭다운 UI로 손쉽게 전환할 수 있습니다.
* **페르소나 리로드:** 페르소나 설정 파일(`config/persona.txt`)이 감지/수정되면 자동으로 동적 적용됩니다. 관리자 패널의 팝업 모달을 사용해 디스코드 내부에서 즉시 편집하고 반영하는 것도 가능합니다.

### 4. 💬 세밀화된 대화 기억 (Memory) 커스텀 제어
* **대화 기억 ON/OFF 토글:** 단 한번의 버튼 클릭으로 대화 기억 모드를 활성화 또는 비활성화할 수 있습니다. 비활성화 시 즉시 대화 기록을 초기화하여 보안과 효율을 도모합니다.
* **유연한 기억 용량 설정:** 디스크 및 메모리 상태를 고려하여 2개에서 100개 사이의 메시지 수(최근 1~50회 대화 분량)로 기억 컨텍스트 용량을 모달 창을 통해 슬라이딩 제어하듯 정밀 수정할 수 있습니다.
* **기억 내역 실시간 조회:** 현재 각 채널에 챗봇이 기억하고 있는 대화 맥락(Context) 데이터를 관리자 패널에서 에페메럴(Ephemeral, 나에게만 보이는) 메시지로 실시간 추적하고 확인할 수 있어 자가 튜닝이 용이합니다.

### 5. 🩺 시스템 관리자 전용 대시보드 UI
디바이스 콘솔에 접속하지 않고도 디스코드 서버 내 지정된 관리자 전용 채널(`ADMIN_CHANNEL_ID`)에서 실시간 GUI 형태의 대시보드를 사용할 수 있습니다:
* **LLM 모델 동적 선택:** LLM 백엔드 API로부터 불러온 로컬 모델 목록을 동적 드롭다운 메뉴에 노출하고, 챗봇 재부팅 없이 변경할 수 있습니다.
* **LLM 타임아웃 세밀 제어:** 네트워크 상태나 모델 성능에 따라 지연 타임아웃 시간을 자유롭게 변경 가능합니다. (0 입력 시 제한 없음)
* **시스템 자가 진단:** 디스코드 API의 웹소켓 지연 속도(Latency), 로컬 LLM 서버와의 네트워크 커넥션 상태, HTTP 상태 코드 및 서버 응답 지연 속도를 실시간으로 분석하여 출력해 주는 진단 툴을 제공합니다.

### 6. 📄 출력 텍스트 지능형 분할 전송
* 디스코드 메시지의 2,000자 글자 제한을 지키며 긴 답변을 전송할 때, 무작위로 끊지 않고 마크다운 구조와 문장 단위를 보존하는 지능형 청킹 루프를 거쳐 순차적으로 안전하게 전송합니다.

---

## 📂 프로젝트 구조

```
danddobot-antigravity/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .gitignore
├── .env.example
├── config/
│   ├── persona.txt.example      # 챗봇의 기본 페르소나 템플릿
│   ├── channels.txt.example     # 대화 참여 가능한 등록 채널 리스트 템플릿
│   └── state.json               # StateManager가 관리하는 실시간 설정값 영구 저장소 (자동 생성)
└── src/
    ├── __init__.py
    ├── main.py                  # 진입점, 환경 변수 검증 및 디스코드 클라이언트 부팅
    ├── bot.py                   # 디스코드 이벤트 핸들러, 대화 순서 제어 및 핵심 API 정의
    ├── admin_panel.py           # 어드민 인터랙티브 대시보드 Embed, Select, Modals 구성
    ├── state_manager.py         # 메모리 캐시 지원 및 원자적 디스크 쓰기를 지원하는 상태 관리자
    └── llm_client.py            # HTTP 지속 풀링이 적용된 로컬 LLM 어댑터 패턴 모듈
```

---

## ⚙️ 환경 변수 설정 (`.env`)

로컬 데스크톱 또는 서버의 루트 디렉토리에 `.env` 파일을 생성하고 아래 환경 변수를 기입합니다:

| 변수명 | 설명 | 예시값 |
| :--- | :--- | :--- |
| `DISCORD_TOKEN` | 디스코드 봇 계정의 토큰 키 | `your_discord_bot_token` |
| `LLM_PROVIDER` | LLM 백엔드 제공자 (`OLLAMA`, `OPENAI_COMPATIBLE`, `LLAMA_CPP`, `VLLM`, `LM_STUDIO`) | `OLLAMA` |
| `LLM_API_URL` | 동일 도커 네트워크 상의 LLM 컨테이너 또는 호스트 주소 | `http://local-llm:11434` |
| `LLM_MODEL` | 기본 구동에 사용할 LLM 모델 식별자 | `llama3` |
| `LLM_TIMEOUT` | LLM 응답 대기 초과 제한 시간 (0 이하는 무제한) | `300.0` |
| `PERSONA_FILE_PATH` | 페르소나 시스템 프롬프트가 정의된 파일 경로 | `config/persona.txt` |
| `CHANNELS_FILE_PATH` | 등록 가능한 채널 ID 목록 텍스트 파일 경로 | `config/channels.txt` |
| `ADMIN_CHANNEL_ID` | 관리자 대시보드가 상주하고 렌더링될 전용 채널 ID (선택) | `123456789012345678` |
| `LOG_CHANNEL_ID` | 치명적 예외 및 경고 로그를 전달받을 전용 채널 ID (선택) | `876543210987654321` |

---

## 🛠️ 로컬 개발 및 실행 방법

### 요구 사항
* Python 3.11 이상 설치 권장
* Docker 및 Docker Compose

### 1. 설정 파일 초기화
가동 전에 설정 파일을 예제 파일로부터 복사하여 구성해 주어야 합니다.
```bash
# 1. 환경 변수 복사 및 편집
cp .env.example .env

# 2. 페르소나 및 채널 목록 생성
cp config/persona.txt.example config/persona.txt
cp config/channels.txt.example config/channels.txt
```
> [!IMPORTANT]
> `config/channels.txt`에 챗봇이 접근할 수 있는 디스코드 채널 ID를 줄바꿈 단위로 입력해 주어야 봇이 활성화 및 제어가 가능합니다.

### 2. 패키지 설치 및 로컬 실행 (데스크톱 개발용)
```bash
pip install -r requirements.txt

# 세팅 완료 후 실행
python -m src.main
```

### 3. 로컬 도커 빌드 및 가동
컨테이너 기반 독립 빌드 및 테스트:
```bash
# 가상 네트워크 생성 (이미 존재하면 생략 가능)
docker network create danddobot-network

# 빌드 및 백그라운드 가동
docker compose up --build -d
```

---

## 🖥️ 관리자 대시보드(Admin Console) 사용 가이드

`ADMIN_CHANNEL_ID`에 지정된 관리자 전용 채널에 접속하면 다음과 같은 인터랙티브 콘솔이 고정 렌더링됩니다. 이 UI를 사용하면 서버 콘솔 환경에 접속하지 않고도 디스코드 채팅방 내에서 실시간 원격 제어가 가능합니다:

```
+--------------------------------------------------------+
| 🤖 Danddobot 관리 대시보드                                |
| • 시스템 상태: 정상 작동 중                                |
| • 활성 대화 채널: #일반대화                             |
| • 대화 기억 상태: 활성화 (최대 10개)                       |
| • LLM 엔진: OLLAMA / Model: llama3 / Timeout: 300초     |
+--------------------------------------------------------+
| [💬 활성 대화 채널 선택 ▾] [🧠 LLM 모델 선택 ▾]           |
|                                                        |
|  [✏️ 페르소나 편집]    [⏱️ 타임아웃 설정]   [🩺 시스템 진단] |
|  [🧠 대화 기억: On]   [🔢 기억 용량 설정]   [📋 기억 내역 조회] |
+--------------------------------------------------------+
```

### 대시보드 주요 컴포넌트 상세:
* **💬 활성 대화 채널 선택:** `config/channels.txt`에 등록해 둔 여러 채널 중 챗봇이 유저들과 메시지를 주고받을 "현재 활성 채널"을 실시간으로 교체합니다.
* **🧠 LLM 모델 선택:** 로컬 LLM 서버(예: Ollama 등)와 연계되어 구동 중인 백엔드에서 가용한 모델 태그들을 조회하여 버튼 클릭 한 번으로 인퍼런스 모델을 스위칭합니다.
* **✏️ 페르소나 편집:** 디스코드 UI 내부에서 모달 프롬프트를 띄워 직접 캐릭터의 성격이나 지침 사항(system prompt)을 실시간 편집 후 파일에 자동 저장합니다.
* **⏱️ 타임아웃 설정:** 복잡하거나 느린 로컬 장비의 추론 환경에 대응하기 위해 최대 타임아웃 지연 시간을 수동으로 변경 및 저장합니다.
* **🩺 시스템 진단:** 현재 봇의 Discord 게이트웨이 웹소켓 지연율, LLM API 호스트 접속 유효성 검사, 네트워크 라운드 트립(RTT) 속도를 정밀 진단하여 에페메럴 창으로 표기합니다.
* **🧠 대화 기억 On/Off:** 기억을 비활성화(Off)하면 즉시 대화 버퍼를 완전히 비우고 단발성 질문-답변(Single-turn) 모드로 전환합니다.
* **🔢 기억 용량 설정:** 컨텍스트 윈도우 한계를 수동 조율하기 위해 최근 저장할 대화 메시지의 누적 한도를 미세 튜닝합니다.
* **📋 기억 내역 조회:** 현재 챗봇의 메모리에 상주하는 대화 이력의 원문을 비밀스럽게 열람하여 챗봇 컨텍스트 오염을 진단할 수 있습니다.

---

## 🌐 DevOps 및 Git Hook 배포 프로세스

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

로컬 프로젝트 폴더(`C:\dev\danddobot-antigravity`) 터미널에서 서버 원격 저장소를 등록합니다:

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

