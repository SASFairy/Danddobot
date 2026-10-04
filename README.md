# Danddobot

Danddobot은 Python과 `discord.py`로 만든 Discord 챗봇입니다. 등록된 채널의 메시지를 로컬 또는 클라우드 LLM으로 전달하고, Discord 안에서 설정을 관리할 수 있는 관리자 대시보드와 미니게임, 텍스트 기반 RAG를 제공합니다.

## 주요 기능

- **여러 LLM 백엔드 지원**: Ollama, OpenAI 호환 API, llama.cpp, vLLM, LM Studio, Cerebras, Groq를 같은 인터페이스로 사용합니다.
- **Cerebras·Groq 다중 키 failover**: API 키를 콤마로 구분해 등록하면 인증 오류, 요청 제한, 서버 오류, 네트워크 오류 발생 시 다음 키로 전환합니다. 잘못된 요청처럼 키 변경으로 해결할 수 없는 오류는 즉시 반환합니다.
- **Discord 관리자 대시보드**: 활성 채널, 프로바이더, 모델, 생성 파라미터, 타임아웃, 메모리, 페르소나, RAG 설정을 실행 중에 변경합니다.
- **대화 메모리와 순차 처리**: 채널별 대화 기록을 선택적으로 유지하며, LLM 요청은 `asyncio.Lock`으로 순서대로 처리합니다.
- **텍스트 RAG**: `config/knowledge`의 `.txt` 문서를 청크로 나누고 키워드 기반 검색 결과를 LLM 컨텍스트에 추가합니다. 관리자 대시보드에서 문서를 생성, 업로드, 편집, 삭제하거나 다시 색인할 수 있습니다.
- **미니게임과 재화 시스템**: 가입, 룰렛, 출석체크, 자산 확인, 랭킹, 가위바위보, 구걸, 지식 가르치기, 상점 명령을 제공합니다.
- **운영 상태 영속화**: 봇 설정, 게임 데이터, 아이템 데이터, RAG 문서는 `config` 볼륨에 저장됩니다.
- **긴 응답 분할**: Discord의 메시지 길이 제한에 맞춰 긴 답변을 여러 메시지로 나눠 전송합니다.

## 프로젝트 구조

```text
Danddobot/
├── .github/workflows/deploy.yml  # SSH 기반 자동 배포
├── config/
│   ├── channels.txt.example      # 허용 채널 목록 예시
│   ├── persona.txt.example       # 시스템 프롬프트 예시
│   └── knowledge/                # RAG 문서 저장 위치
├── src/
│   ├── admin/                    # 관리자·게임 대시보드 UI
│   ├── rag/                      # 문서 청킹과 키워드 검색
│   ├── bot.py                    # Discord 이벤트와 대화 처리
│   ├── bot_settings.py           # 런타임 설정 변경
│   ├── config.py                 # 환경 변수와 저장 상태 로딩
│   ├── db_manager.py             # 게임 데이터 저장
│   ├── game_commands.py          # 미니게임 슬래시 명령
│   ├── item_db_manager.py        # 상점 아이템 데이터 저장
│   ├── llm_client.py             # LLM 어댑터와 다중 키 failover
│   ├── main.py                   # 애플리케이션 진입점
│   └── state_manager.py          # 원자적 상태 파일 저장
├── tests/                        # LLM 설정·failover 테스트
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## 사전 준비

- Python 3.11 이상 또는 Docker와 Docker Compose
- Discord Bot Token
- 사용할 LLM 서버 또는 Cerebras/Groq API 키
- Discord Developer Portal에서 봇의 **Message Content Intent** 활성화
- 봇이 대상 채널에서 메시지를 읽고 보내며 슬래시 명령을 사용할 권한

## 설정

### 1. 설정 파일 생성

```bash
cp .env.example .env
cp config/persona.txt.example config/persona.txt
cp config/channels.txt.example config/channels.txt
```

`config/channels.txt`에는 봇이 대화에 응답할 채널 ID를 한 줄에 하나씩 입력합니다. 첫 번째 채널이 초기 활성 채널이 되며, 이후 관리자 대시보드에서 변경할 수 있습니다.

### 2. 필수 환경 변수

| 변수 | 설명 | 기본값 또는 예시 |
| --- | --- | --- |
| `DISCORD_TOKEN` | Discord Bot Token | 필수 |
| `LLM_PROVIDER` | `OLLAMA`, `OPENAI_COMPATIBLE`, `LLAMA_CPP`, `VLLM`, `LM_STUDIO`, `CEREBRAS`, `GROQ` | `OLLAMA` |
| `LLM_API_URL` | 기본 프로바이더 API 주소 | `http://local-llm:11434` |
| `LLM_MODEL` | 사용할 모델 ID | `llama3` |
| `LLM_TIMEOUT` | 응답 제한 시간(초). 0 이하는 무제한 | `300.0` |
| `PERSONA_FILE_PATH` | 시스템 프롬프트 파일 | `config/persona.txt` |
| `CHANNELS_FILE_PATH` | 허용 채널 목록 파일 | `config/channels.txt` |
| `ADMIN_CHANNEL_ID` | 관리자 대시보드 채널 ID. 비워두면 비활성화 | 선택 |
| `LOG_CHANNEL_ID` | 오류·디버그 로그 채널 ID | 선택 |

### 3. 프로바이더별 설정

관리자 대시보드에서 전환할 프로바이더는 `OLLAMA_API_URL`처럼 `<PROVIDER>_API_URL` 형식으로 등록합니다. Cerebras와 Groq는 기본 URL이 내장되어 있어 URL을 생략할 수 있습니다.

```env
OLLAMA_API_URL=http://local-llm:11434
# OPENAI_COMPATIBLE_API_URL=http://localhost:8000
# LLAMA_CPP_API_URL=http://localhost:8080
# VLLM_API_URL=http://vllm-container:8000
# LM_STUDIO_API_URL=http://localhost:1234

CEREBRAS_API_URL=https://api.cerebras.ai
CEREBRAS_API_KEY=key1,key2,key3

GROQ_API_URL=https://api.groq.com/openai
GROQ_API_KEY=key1,key2,key3
```

Cerebras와 Groq의 URL은 `/v1` 직전까지만 입력합니다. 클라이언트가 `/v1/chat/completions`와 `/v1/models`를 추가합니다.

### 4. RAG 설정

| 변수 | 설명 | 기본값 |
| --- | --- | --- |
| `RAG_ENABLED` | RAG 활성화 여부 (`TRUE`/`FALSE`) | `FALSE` |
| `RAG_KNOWLEDGE_DIR` | `.txt` 문서를 읽을 디렉터리 | `config/knowledge` |
| `RAG_TOP_K` | 검색할 상위 청크 수 | `3` |
| `RAG_MAX_CHARS` | LLM에 전달할 검색 결과의 최대 글자 수 | `1500` |
| `RAG_CHUNK_SIZE` | 문서 청크 최대 글자 수 | `500` |

`RAG_CHUNK_SIZE`가 `RAG_MAX_CHARS`보다 크면 애플리케이션이 자동으로 최대 글자 수에 맞춥니다.

## 실행

### Python으로 실행

```bash
python -m pip install -r requirements.txt
python -m src.main
```

### Docker Compose로 실행

Compose 설정은 `.env`를 읽고 로컬 `config` 디렉터리를 컨테이너의 `/app/config`에 마운트합니다. 먼저 외부 네트워크를 한 번 생성합니다.

```bash
docker network create danddobot-network
docker compose up --build -d
docker compose logs -f chatbot
```

이미 같은 이름의 네트워크가 있으면 첫 번째 명령은 생략합니다. `OLLAMA_API_URL=http://local-llm:11434`를 사용한다면 `local-llm` 컨테이너도 `danddobot-network`에 연결되어 있어야 합니다.

종료할 때는 다음 명령을 사용합니다.

```bash
docker compose down
```

## Discord 명령

현재 등록되는 전역 슬래시 명령은 다음과 같습니다. Discord의 전역 명령 동기화에는 시간이 걸릴 수 있습니다.

| 명령 | 설명 |
| --- | --- |
| `/가입` | 게임 계정을 만들고 가입 지원금을 받습니다. |
| `/룰렛` | 금액을 걸고 숫자 룰렛을 실행합니다. |
| `/출석체크` | 일일 보상과 연속 출석 보너스를 받습니다. |
| `/확인` | 보유 자산, 출석, 아이템을 확인합니다. |
| `/랭킹` | 자산 순위 상위 사용자를 확인합니다. |
| `/가위바위보` | 다른 사용자와 재화를 걸고 대결합니다. |
| `/구걸` | 쿨다운이 있는 모금 이벤트를 시작합니다. |
| `/가르치기` | 재화를 사용해 RAG 지식을 추가합니다. |
| `/상점` | 아이템 상점을 엽니다. 현재 일부 기능은 개발 중입니다. |

## 운영 데이터

다음 파일은 서버에서 생성·수정되는 데이터이므로 Git에서 추적하지 않습니다.

- `.env`
- `config/persona.txt`, `config/channels.txt`
- `config/state.json`, `config/state.json.tmp`
- `config/knowledge/*` (`*.example` 제외)
- `config/game_database.json`과 이전 DB 백업
- `config/item_database.json`

Docker Compose는 `./config:/app/config` 볼륨을 사용하므로 컨테이너를 다시 빌드해도 이 데이터는 호스트에 남습니다. 저장 데이터는 별도 백업 정책으로 관리하세요. 특히 배포 워크플로는 서버 체크아웃에 `git reset --hard`를 실행하므로 운영 데이터 파일을 다시 Git에 추가하지 않는 것이 중요합니다.

## 테스트

```bash
python -m unittest discover -s tests -v
python -m compileall -q src tests
```

현재 테스트는 Groq 설정 로딩, API 키 파싱, 키별 failover, 재시도하지 않아야 하는 오류, 전체 키 고갈, 관리자 런타임 전환을 로컬 HTTP 서버로 검증합니다.

## GitHub Actions 배포

`.github/workflows/deploy.yml`은 push 또는 수동 실행 시 SSH로 배포 서버에 접속해 해당 브랜치를 체크아웃하고 다음 명령으로 컨테이너를 다시 빌드합니다.

```bash
git fetch origin
git checkout <trigger-branch>
git reset --hard origin/<trigger-branch>
docker compose up --build -d
```

필요한 GitHub Actions secrets는 다음과 같습니다.

| Secret | 설명 |
| --- | --- |
| `SSH_HOST` | 배포 서버 주소 |
| `SSH_USERNAME` | 배포 전용 사용자 |
| `SSH_KEY` | 해당 사용자의 SSH 개인 키 |
| `SSH_PORT` | SSH 포트. 생략 시 22 |
| `PROJECT_PATH` | 서버의 저장소 경로 |

배포 사용자는 `PROJECT_PATH`에 쓰기 권한이 있고 Docker 명령을 실행할 수 있어야 합니다. 저장소 접근에는 읽기 전용 GitHub Deploy Key를 권장합니다.

> 현재 워크플로는 모든 브랜치의 push에 반응하고 SSH host key 검증을 비활성화합니다. 운영 환경에서는 배포 브랜치를 제한하고 서버의 `known_hosts`를 검증하도록 워크플로를 강화하는 편이 안전합니다. 또한 `docker compose up --build -d`는 컨테이너를 교체하므로 엄밀한 무중단 배포를 보장하지 않습니다.
