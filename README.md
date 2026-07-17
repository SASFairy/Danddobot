# Danddobot (디스코드 챗봇)

로컬 서버 환경에서 작동하는 독립적인 로컬 LLM 컨테이너와 직접 통신하여 질문에 답변하는 Python 기반 디스코드 챗봇 프로젝트입니다. 
본 챗봇은 Docker 컨테이너 환경에서 실행되며, 로컬 LLM과의 의존성을 낮추는 어댑터 구조와 풍부한 관리자 기능을 탑재하고 있습니다.

---

## 주요 기능 및 아키텍처 특징

Danddobot은 단순한 응답 봇을 넘어, 운영 편의성과 아키텍처 완성도를 높이기 위해 다음과 같은 설계와 고급 관리 기능을 도입했습니다:

### 1. 아키텍처 및 통신 최적화
* **느슨한 결합 (어댑터 패턴):** 챗봇 메인 로직은 LLM 규격에 종속되지 않습니다. `BaseLLMClient` 추상 클래스를 기반으로 Ollama, OpenAI 호환 API, llama.cpp, vLLM, LM Studio, Cerebras 등 다양한 엔진을 지원하며, 실시간 모델 변경이 가능합니다.
* **Cerebras 다중 API 키 자동 순환 및 Failover:** Cerebras 백엔드 사용 시 여러 개의 API 키를 등록하여 무료 할당량 소진 또는 요청 제한(Rate Limit) 발생 시 패스워드나 재부팅 없이 유효한 키로 자동 순환(Rotation) 및 예외 복구(Failover) 처리가 이루어집니다.
* **지속성 연결 풀링 (Connection Pooling):** `httpx.AsyncClient`를 이용한 지속성 연결 풀링을 적용하여 요청마다 소켓을 새로 생성하는 리소스 낭비(Socket Exhaustion)를 방지하고 대기 시간을 단축시켰습니다.
* **순차 동시성 처리 (FIFO Concurrency Lock):** 여러 사용자가 거의 동시에 질문을 입력하더라도, 컨텍스트 순서가 뒤섞이지 않고 요청 순서대로 안전하게 응답을 제어하는 `asyncio.Lock` 메커니즘을 내장하고 있습니다.

### 2. 중앙화된 상태 관리자 (`StateManager`)
* **원자적 상태 영구 저장:** 설정된 채널 ID, 타임아웃 수치, 대화 기억 모드 등 실시간으로 변경되는 설정값을 메모리 캐시에 동적으로 로드 및 관리합니다.
* **부작용 방지 및 성능 유지:** 잦은 파일 입출력으로 인한 병목을 해소하기 위해 캐시 형태로 메모리 단에서 값을 반환하며, 디스크 저장 시 임시 파일(`state.json.tmp`)에 기록 후 덮어쓰는 원자적(Atomic) 쓰기 방식으로 파일 손상을 완벽히 방지합니다.

### 3. 전용 대화 채널 제어 및 실시간 상태 동기화
* **실시간 채널 동적 전환:** 사전 등록된 대화 채널 목록(`config/channels.txt`) 내에서 활성 채널을 드롭다운 UI로 손쉽게 전환할 수 있습니다.
* **페르소나 리로드:** 페르소나 설정 파일(`config/persona.txt`)이 감지/수정되면 자동으로 동적 적용됩니다. 관리자 패널의 팝업 모달을 사용해 디스코드 내부에서 즉시 편집하고 반영하는 것도 가능합니다.

### 4. 세밀화된 대화 기억 (Memory) 커스텀 제어
* **대화 기억 ON/OFF 토글:** 단 한번의 버튼 클릭으로 대화 기억 모드를 활성화 또는 비활성화할 수 있습니다. 비활성화 시 즉시 대화 기록을 초기화하여 보안과 효율을 도모합니다.
* **유연한 기억 용량 설정:** 디스크 및 메모리 상태를 고려하여 2개에서 100개 사이의 메시지 수(최근 1~50회 대화 분량)로 기억 컨텍스트 용량을 모달 창을 통해 슬라이딩 제어하듯 정밀 수정할 수 있습니다.
* **기억 내역 실시간 조회:** 현재 각 채널에 챗봇이 기억하고 있는 대화 맥락(Context) 데이터를 관리자 패널에서 에페메럴(Ephemeral, 나에게만 보이는) 메시지로 실시간 추적하고 확인할 수 있어 자가 튜닝이 용이합니다.

### 5. 시스템 관리자 전용 대시보드 UI
디바이스 콘솔에 접속하지 않고도 디스코드 서버 내 지정된 관리자 전용 채널(`ADMIN_CHANNEL_ID`)에서 실시간 GUI 형태의 대시보드를 사용할 수 있습니다:
* **LLM 프로바이더 동적 전환:** `.env`에 정의된 개별 프로바이더들의 API URL(`*_API_URL` 형식으로 등록된 항목들)을 동적으로 감지하여 드롭다운으로 표시하며, 대시보드 내에서 즉시 전환 가능합니다. 전환 시 활성화된 클라이언트의 연결 풀(Connection Pool)을 즉각적이고 안정적으로 해제하고 새로운 프로바이더로 교체합니다.
* **LLM 모델 동적 선택:** LLM 백엔드 API로부터 불러온 로컬 모델 목록을 동적 드롭다운 메뉴에 노출하고, 챗봇 재부팅 없이 변경할 수 있습니다.
* **LLM 타임아웃 세밀 제어:** 네트워크 상태나 모델 성능에 따라 지연 타임아웃 시간을 자유롭게 변경 가능합니다. (0 입력 시 제한 없음)
* **시스템 자가 진단:** 디스코드 API의 웹소켓 지연 속도(Latency), 로컬 LLM 서버와의 네트워크 커넥션 상태, HTTP 상태 코드 및 서버 응답 지연 속도를 실시간으로 분석하여 출력해 주는 진단 툴을 제공합니다.

### 6. 출력 텍스트 지능형 분할 전송
* 디스코드 메시지의 2,000자 글자 제한을 지키며 긴 답변을 전송할 때, 무작위로 끊지 않고 마크다운 구조와 문장 단위를 보존하는 지능형 청킹 루프를 거쳐 순차적으로 안전하게 전송합니다.

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
│   ├── persona.txt.example      # 챗봇의 기본 페르소나 템플릿
│   ├── channels.txt.example     # 대화 참여 가능한 등록 채널 리스트 템플릿
│   └── state.json               # StateManager가 관리하는 실시간 설정값 영구 저장소 (자동 생성)
└── src/
    ├── __init__.py
    ├── main.py                  # 진입점, 환경 변수 검증 및 디스코드 클라이언트 부팅
    ├── bot.py                   # 디스코드 이벤트 핸들러, 대화 순서 제어 및 핵심 API 정의
    ├── admin/                   # 어드민 인터랙티브 대시보드 Embed, Select, Modals 구성
    ├── state_manager.py         # 메모리 캐시 지원 및 원자적 디스크 쓰기를 지원하는 상태 관리자
    └── llm_client.py            # HTTP 지속 풀링이 적용된 로컬 LLM 어댑터 패턴 모듈
```

---

## 환경 변수 설정 (`.env`)

로컬 데스크톱 또는 서버의 루트 디렉토리에 `.env` 파일을 생성하고 아래 환경 변수를 기입합니다:

| 변수명 | 설명 | 예시값 |
| :--- | :--- | :--- |
| `DISCORD_TOKEN` | 디스코드 봇 계정의 토큰 키 | `your_discord_bot_token` |
| `LLM_PROVIDER` | LLM 백엔드 제공자 (`OLLAMA`, `OPENAI_COMPATIBLE`, `CEREBRAS` 등) | `OLLAMA` |
| `LLM_API_URL` | 동일 도커 네트워크 상의 LLM 컨테이너 또는 호스트 주소 | `http://local-llm:11434` |
| `LLM_MODEL` | 기본 구동에 사용할 LLM 모델 식별자 | `llama3` |
| `LLM_TIMEOUT` | LLM 응답 대기 초과 제한 시간 (0 이하는 무제한) | `300.0` |
| `CEREBRAS_API_KEY` | Cerebras API 키 (복수 키 설정 시 콤마 단위로 기입) | `key1, key2, key3` |
| `PERSONA_FILE_PATH` | 페르소나 시스템 프롬프트가 정의된 파일 경로 | `config/persona.txt` |
| `CHANNELS_FILE_PATH` | 등록 가능한 채널 ID 목록 텍스트 파일 경로 | `config/channels.txt` |
| `ADMIN_CHANNEL_ID` | 관리자 대시보드가 상주하고 렌더링될 전용 채널 ID (선택) | `123456789012345678` |
| `LOG_CHANNEL_ID` | 치명적 예외 및 경고 로그를 전달받을 전용 채널 ID (선택) | `876543210987654321` |

---

## 로컬 개발 및 실행 방법

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

## GitHub Actions 기반 보안 무중단 배포 (CI/CD)

Danddobot 프로젝트는 보안을 최우선으로 고려하여 설계되었습니다. 관리자 권한(`ubuntu`)을 가상 환경에 직접 노출하지 않고, **제한된 배포 전용 계정(`deploy`)**을 생성하여 **비밀번호 없는 무중단 보안 자동 배포(Zero-Sudo 및 Docker Group 기반)** 환경을 운영합니다.

### 1. 배포 서버 보안 인프라 구축 (최초 1회)

서버 콘솔에 관리자(`ubuntu`) 계정으로 로그인한 뒤, 아래 설정을 안전하게 적용합니다.

#### 1) 배포 전용 계정 생성 및 세팅
```bash
# 1. deploy 계정 생성
sudo adduser deploy

# 2. 프로젝트 디렉토리 소유권을 deploy 계정으로 영구 양도
sudo chown -R deploy:deploy /data/hdd/git/danddobot
sudo chmod -R 755 /data/hdd/git/danddobot
```

#### 2) 무수도(Zero-Sudo) 도커 가동 환경 구축
배포 전용 계정이 보안을 침해하는 `sudo` 명령을 일절 사용하지 않고도 도커 컴포즈 서비스를 무중단 기동할 수 있도록 도커 전용 보안 그룹에 영입시킵니다.
```bash
# deploy 계정을 docker 그룹에 추가
sudo usermod -aG docker deploy
```
*이를 완료하면 `/etc/sudoers`에 deploy 관련 sudo 패스워드 면제(NOPASSWD) 설정을 남길 필요가 없어 가장 완벽한 보안 격리 상태가 됩니다.*

#### 3) 배포 계정 전용 SSH Key 생성 및 등록
서버에서 GitHub에 비밀번호 없이 안전하게 접근하여 최신 소스코드를 수령할 수 있도록 SSH Deploy Key를 만듭니다.
```bash
# 1. deploy 계정으로 전환
sudo su - deploy

# 2. SSH 배포 전용 키 쌍 생성
ssh-keygen -t ed25519 -C "deploy_key_danddobot" -f ~/.ssh/id_ed25519_deploy
# (비밀번호 대기 단계가 발생하지 않도록 패스프레이즈 없이 엔터키를 계속 입력해 생성합니다.)

# 3. SSH 자동 매핑 구성 설정
nano ~/.ssh/config
```
`~/.ssh/config` 파일 내에 다음 규격을 기록합니다:
```text
Host github.com
  IdentityFile ~/.ssh/id_ed25519_deploy
  User git
```
```bash
# 4. 최초 1회 깃허브 호스트 신뢰 검증 수동 등록
ssh -T git@github.com
# (Are you sure... 질문 창이 나타나면 yes를 입력해 영구 보관시킵니다.)
```

---

### 2. GitHub 설정 및 배포 파이프라인 연동

#### 1) GitHub Deploy Key 등록
배포 서버의 `deploy` 계정 콘솔에서 복사한 공개키 정보를 GitHub에 입력해 줍니다.
```bash
cat ~/.ssh/id_ed25519_deploy.pub
```
* **이동 경로**: 내 GitHub 레포지토리 페이지 ➡️ `Settings` ➡️ `Deploy keys` ➡️ `Add deploy key` 버튼 클릭
* **Title**: `Danddobot_Deploy_Server`
* **Key**: 복사한 공개키 전문 기입
* **Allow write access**: 체크 해제 (보안상 안전한 **Read-Only** 읽기 권한 보존)

#### 2) GitHub Actions Secrets 환경변수 세팅
GitHub 웹 페이지 설정창에서 원격 가상 워크플로우 구동에 필요한 암호화 비밀 환경 변수들을 등록합니다.
* **이동 경로**: `Settings` ➡️ `Secrets and variables` ➡️ `Actions` ➡️ `New repository secret` 버튼 클릭

| Secret 이름 | 기입 정보 예시 | 설명 |
| :--- | :--- | :--- |
| `SSH_HOST` | `192.168.219.101` (또는 외부 공인 IP) | 외부에서 접근할 수 있는 배포 서버 주소 |
| `SSH_USERNAME` | `deploy` | 보안 관리 하에 개설한 **전용 배포 계정명** |
| `SSH_KEY` | `-----BEGIN OPENSSH PRIVATE KEY----- ...` | 배포 계정에 로그인할 때 사용하는 **SSH Private Key 개인키** |
| `PROJECT_PATH` | `/data/hdd/git/danddobot` | 배포 서버 내 단또봇 프로젝트 실제 폴더 경로 |

---

### 3. 무중단 실시간 배포 작동 원리
이제 모든 세팅이 완료되었습니다. 로컬 개발 환경에서 작업을 완료한 후 코드를 깃허브로 업로드하면 즉각적인 릴레이 배포가 이루어집니다.

```bash
git add .
git commit -m "docs: update deployment documentation"
git push origin <원하는_어떤_브랜치든지>
```

1. **이벤트 감지**: GitHub Actions가 푸시 이벤트를 분석하여 가상 배포 컨테이너를 가동합니다.
2. **보안 SSH 핸드셰이크**: Secrets에 등록된 `deploy`용 SSH Key를 검증하여 패스워드 묻기 단계 없이 안전하게 배포 서버 터미널을 탈취합니다.
3. **소스 동기화**: `deploy` 소유의 프로젝트 폴더 내에서 꼬인 소스들을 클렌징(`git reset --hard`)하고, 푸시를 일으킨 그 브랜치와 100% 동일하게 헤드를 조율합니다.
4. **무수도 도커 컴포즈 업그레이드**: `sudo`를 배제하고 `docker compose up --build -d` 명령어를 직접 내려, 최신 파이썬 챗봇 모듈 빌드 및 백그라운드 구동에 착수하며 배포를 완수합니다.
