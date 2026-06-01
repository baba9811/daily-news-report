# Daily News Report

AI 기반 일일 뉴스 브리핑 및 트레이딩 리포트 시스템.
과거 추천 성과를 추적하며 스스로 학습하고 개선합니다.

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/Python-3.11+-3776ab.svg)](https://www.python.org)
[![Next.js](https://img.shields.io/badge/Next.js-15-000000.svg)](https://nextjs.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com)

바쁜 아침, 뉴스와 시장을 직접 확인할 시간이 부족할 때를 위해 만들었습니다.
매일 아침 AI가 국내 뉴스, 해외 뉴스, 트레이딩 리포트 세 가지 파이프라인을 자동 실행해서
웹 검색 기반 뉴스 브리핑과 시장 분석 리포트를 이메일로 보내줍니다.

[Features](#features) · [Getting Started](#getting-started) · [Dashboard](#dashboard) · [Architecture](#architecture) · [Contributing](#contributing)

<br/>

<img src="docs/assets/dashboard-screenshot.png" alt="Daily News Report Dashboard" width="720" />

---

<a id="features"></a>

## Features

### Triple Pipeline

| Pipeline | Schedule | 설명 |
|----------|----------|-------------|
| **해외 뉴스 브리핑** | 07:00 KST | 세계 정치, 글로벌 경제, 기술, 과학, 기후, 분쟁, 문화 등 7개 카테고리 해외 뉴스 |
| **국내 뉴스 브리핑** | 07:15 KST | 정치, 경제, 사회, 기술, 문화, 국제, 오늘의 일정 등 7개 카테고리 국내 뉴스 |
| **트레이딩 리포트** | 07:30 KST | 뉴스 기반 인과관계 분석 + 한국/미국 시장 트레이딩 추천 |

### Highlights

- **AI 뉴스 분석** — 20건 이상의 웹 검색으로 국내외 뉴스를 심층 분석
- **트레이딩 리포트** — 인과관계 분석 (뉴스 → 직접 영향 → 파생 효과 → 투자 기회)
- **Dual Market** — 한국 (KOSPI/KOSDAQ) + 미국 (NYSE/NASDAQ) 주식 추천
- **실시간 시세** — yfinance로 주요 지수/환율/원자재를 사전 수집
- **Self-Improving Retrospective** — 과거 추천 성과를 추적하고, 성공/실패 패턴을 다음 추천에 반영
- **HTML Email** — 다크 모드, 카드 기반, Gmail 호환 리포트
- **Web Dashboard** — 성과 차트, 추천 이력, 주간 회고를 시각적으로 확인
- **Scheduler** — macOS (launchd) + Linux/WSL2 (cron), `make dev`로 한번에 실행
- **Multi-Language** — 한국어, 영어, 일본어 (`REPORT_LANGUAGE`)

<details>
<summary><b>Features (English)</b></summary>

- **AI News Analysis** — 20+ web searches for in-depth news analysis
- **Triple Pipeline** — Global news (07:00) → Korean news (07:15) → Trading report (07:30)
- **Causal Chain Analysis** — News → Direct Impact → Derived Effects → Investment Opportunities
- **Dual Market Coverage** — Korean (KOSPI/KOSDAQ) + US (NYSE/NASDAQ)
- **Real-Time Market Data** — Pre-fetches indices, FX rates, and commodities via yfinance
- **Self-Improving Retrospective** — Tracks outcomes, analyzes patterns, feeds learnings into future reports
- **Professional HTML Email** — Dark mode, card-based, Gmail-compatible
- **Web Dashboard** — Performance charts, recommendation history, weekly retrospective
- **Integrated Scheduler** — macOS (launchd) + Linux/WSL2 (cron)
- **Multi-Language** — Korean, English, Japanese reports

</details>

<a id="getting-started"></a>

## Getting Started

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- Node.js 20+ & [Yarn Berry](https://yarnpkg.com/) (v4+)
- [Docker](https://docs.docker.com/get-docker/) (Multica 운영 콘솔 self-host 스택 구동용)
- Gmail 계정 + [앱 비밀번호](https://myaccount.google.com/apppasswords)

### 1. Clone & Configure

```bash
git clone https://github.com/baba9811/daily-news-report.git
cd daily-news-report

cp .env.example .env
```

`.env` 파일을 열고 인증 정보를 입력하세요:

```bash
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password        # Gmail 앱 비밀번호 (16자리)
EMAIL_FROM=your-email@gmail.com
EMAIL_TO=["recipient@email.com"]
```

### 2. Install

```bash
make setup
```

Python 의존성(`uv sync`), 프론트엔드 의존성(`yarn install`), DB 초기화를 한번에 수행합니다.

### 3. Run

```bash
# 전체 실행 (Multica 스택 + 백엔드 + 프론트엔드 + 3개 스케줄러)
make dev
# Multica:  http://localhost:3001  (운영 콘솔, /multica 페이지에 임베드)
# Backend:  http://localhost:8000
# Frontend: http://localhost:3000
# Ctrl+C로 전체 종료 (Multica 컨테이너 포함, 데이터 볼륨은 보존)

# 파이프라인 수동 실행
make run              # 트레이딩 리포트
make run-news         # 한국 뉴스 브리핑
make run-global-news  # 해외 뉴스 브리핑
```

`make dev`는 시작 시 `docker compose`로 Multica self-host 스택(postgres + backend + web)을
자동 기동하고 헬스 체크가 통과할 때까지 대기합니다. Docker 데몬이 꺼져 있으면 경고만 출력하고
네이티브 서버는 그대로 실행됩니다(graceful degradation). Multica 스택만 따로 제어하려면:

```bash
make multica-up       # 스택 기동 + 헬스 대기
make multica-status   # 컨테이너 상태 + 백엔드 헬스 프로브
make multica-stop     # 컨테이너 정지 (데이터/볼륨 보존, 빠른 재기동)
make multica-down     # 컨테이너 제거 (데이터 볼륨은 보존)
make multica-logs     # 스택 로그 tail
```

#### Multica 로그인

Multica 운영 콘솔(`http://localhost:3001`, `/multica` 페이지에 임베드)은 **비밀번호가 없는
이메일 인증코드(passwordless)** 방식으로 로그인합니다. 동작 방식은 `APP_ENV` 값에 따라 다릅니다.

**기본값 (`APP_ENV=production`)** — 로그인 화면에서 이메일을 입력하면 6자리 인증코드가 발급됩니다.
이메일 발송 키(`RESEND_API_KEY`)가 없으면 코드는 백엔드 컨테이너 로그로 출력됩니다:

```bash
# 코드 요청 후 로그에서 확인
docker logs --since 30s multica-backend-1 2>&1 | grep "Verification code"
```

한 번 로그인하면 세션(JWT)이 **30일** 유지되므로, 그동안은 코드를 다시 입력할 필요가 없습니다.

**로컬 개발 — 고정 코드 (선택)** — 코드를 매번 로그에서 찾기 번거로우면, 루프백 전용 로컬
스택에 한해 고정 코드를 쓸 수 있습니다. 스택은 `127.0.0.1`에만 바인딩되어 외부에 노출되지 않습니다.
gitignore되는 [`.multica/.env`](.multica/.env)에 다음 두 줄을 설정하세요(시크릿이라 커밋되지 않습니다):

```dotenv
# 고정 코드는 APP_ENV가 production이 아닐 때만 동작합니다.
APP_ENV=dev
MULTICA_DEV_VERIFICATION_CODE=000000
```

이후 백엔드를 재기동하면(`make multica-up` 또는 `docker compose -f docker-compose.multica.yml
--env-file .multica/.env up -d backend`) 아무 이메일 + `000000`으로 로그인됩니다. `ALLOW_SIGNUP=true`
이므로 새 이메일은 자동으로 계정이 생성됩니다.

> [!WARNING]
> 고정 코드와 `APP_ENV=dev`는 **루프백 전용 로컬 환경에서만** 안전합니다. 이 스택을 외부에
> 노출할 경우 반드시 `APP_ENV=production`으로 되돌리세요 — production에서는 고정 코드가 자동으로
> 무시됩니다.

자동화(아웃바운드 이슈 생성 등)는 사람 로그인이 아니라 루트 `.env`의 `MULTICA_API_TOKEN`과
`MULTICA_WORKSPACE_ID`로 동작하며, 이 값은 `bash scripts/multica-bootstrap.sh`로 발급합니다.

#### 워크스페이스 멤버 추가 (사람 합류)

로그인은 누구나 본인 이메일로 할 수 있지만, 그 계정이 카운슬 워크스페이스(`Daily Scheduler
Council`)의 이슈/데이터를 보려면 **멤버로 합류**해야 합니다. 봇 계정이 워크스페이스 owner이므로,
봇의 PAT로 **초대**를 생성하고 사람이 **수락**하는 공식 흐름을 씁니다(DB 직접 조작 없음):

```bash
make multica-add-member EMAIL=you@example.com ROLE=admin   # ROLE 생략 시 admin
# 또는: bash scripts/multica-add-member.sh you@example.com admin
```

이 명령은 `POST /api/workspaces/{id}/members`로 **대기(pending) 초대**를 생성합니다(아직 로그인하지
않은 이메일도 미리 초대 가능, 7일 만료). 이후:

1. 초대받은 사람이 `http://localhost:3001`에 그 이메일로 **로그인**합니다.
2. Multica 화면에서 **대기 중인 초대를 수락**하면 멤버가 되고 카운슬 워크스페이스가 보입니다.

`ROLE`은 `admin`(이슈·설정 관리 가능) 또는 `member`를 받습니다. 이미 멤버인 이메일에 다시 실행하면
멱등하게 "already a member"로 통과합니다.

#### Multica API 확인 / 사용법

Multica self-host 백엔드는 `http://localhost:8080`(루트 `.env`의 `MULTICA_BASE_URL`)에서 REST API를
제공합니다. **OpenAPI/Swagger 문서는 노출되지 않으므로**, 엔드포인트와 허용 메서드는 `OPTIONS`의
`Allow` 헤더로 직접 확인합니다. 인증은 사람 로그인(JWT)이 아니라 봇 PAT로 하며, 모든 요청에 두 헤더가
필요합니다 — `Authorization: Bearer $MULTICA_API_TOKEN`, `X-Workspace-ID: $MULTICA_WORKSPACE_ID`.
두 값은 `bash scripts/multica-bootstrap.sh`가 루트 `.env`에 기록합니다(시크릿이라 커밋되지 않음).

```bash
# .env에서 자격증명 로드 (토큰을 화면에 출력하지 않음)
TOKEN=$(grep '^MULTICA_API_TOKEN=' .env | cut -d= -f2)
WS=$(grep '^MULTICA_WORKSPACE_ID=' .env | cut -d= -f2)
AUTH=(-H "Authorization: Bearer $TOKEN" -H "X-Workspace-ID: $WS")

# 허용 메서드 탐지 (OpenAPI가 없으므로 OPTIONS의 Allow 헤더로 확인)
curl -s -i -X OPTIONS "${AUTH[@]}" http://localhost:8080/api/agents       | grep -i '^allow'  # GET, POST
curl -s -i -X OPTIONS "${AUTH[@]}" http://localhost:8080/api/agents/<ID>  | grep -i '^allow'  # GET, PUT

# 카운슬 에이전트 목록 (이름 -> 모델)
curl -s "${AUTH[@]}" http://localhost:8080/api/agents \
  | python3 -c 'import sys,json
for a in json.load(sys.stdin): print(a["name"], "->", a["model"])'

# provider -> 온라인 런타임 매핑 확인
curl -s "${AUTH[@]}" http://localhost:8080/api/runtimes | python3 -m json.tool
```

주요 엔드포인트:

| 엔드포인트 | 메서드 | 용도 |
|---|---|---|
| `/api/runtimes` | GET | claude/codex 런타임 온라인 여부 |
| `/api/agents` | GET, POST | 에이전트 목록 / 생성 |
| `/api/agents/{id}` | GET, **PUT** | 단건 조회 / **수정(전체 교체)** |
| `/api/squads`, `/api/squads/{id}/members` | GET, POST | 스쿼드 / 멤버 |
| `/api/skills` | GET, POST | 워크스페이스 스킬 |

> [!NOTE]
> 에이전트 수정은 **`PUT`(전체 교체)**입니다 — `PATCH`는 없습니다. 모델만 바꿀 때도
> `name / description / instructions / runtime_id / model / visibility`를 함께 보내야 나머지 필드가
> 비워지지 않습니다.

**카운슬 (재)등록 / 모델 재배치** — 워크스페이스에 보이는 에이전트 + "Investment Council" 스쿼드 +
리포트 스킬은 다음 한 줄로 등록합니다:

```bash
make multica-register-agents   # = python3 scripts/multica-register-agents.py
```

스크립트는 **멱등**합니다: 없는 것만 만들고, 이미 있으면 모델이 스펙과 다를 때 `PUT`으로 **재배치**
합니다(예: 과거 all-opus → 현재 tier). 모델 tier는 원본인 [`role_registry.py`](backend/src/daily_scheduler/infrastructure/adapters/council/role_registry.py)를
미러링합니다 — **opus**는 Bull/Bear 토론 + PM 합성, **sonnet**은 리서치/분석, **haiku**는 기술적
readout/발행, 교차검증 레이어(Judge/Trader/Risk/Perf)는 **Codex/GPT-5.5**.

### 4. Scheduler 관리

<table>
<tr><th></th><th>macOS (launchd)</th><th>Linux / WSL2 (cron)</th></tr>
<tr><td><b>Trading Report</b></td><td>

```bash
make scheduler-install
make scheduler-status
make scheduler-start
make scheduler-stop
make scheduler-uninstall
```

</td><td>

```bash
make scheduler-linux-install
make scheduler-linux-status
make scheduler-linux-start
make scheduler-linux-stop
make scheduler-linux-uninstall
```

</td></tr>
<tr><td><b>Korean News</b></td><td>

```bash
make news-scheduler-install
make news-scheduler-status
make news-scheduler-start
```

</td><td>

```bash
make news-scheduler-linux-install
make news-scheduler-linux-status
make news-scheduler-linux-start
```

</td></tr>
<tr><td><b>Global News</b></td><td>

```bash
make global-news-scheduler-install
make global-news-scheduler-status
make global-news-scheduler-start
```

</td><td>

```bash
make global-news-scheduler-linux-install
make global-news-scheduler-linux-status
make global-news-scheduler-linux-start
```

</td></tr>
</table>

스케줄 시간 변경은 `.env`에서 수정 후 install을 다시 실행하면 됩니다:

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `SCHEDULE_TIME` | `07:30` | 트레이딩 리포트 (KST) |
| `NEWS_SCHEDULE_TIME` | `07:15` | 한국 뉴스 브리핑 (KST) |
| `GLOBAL_NEWS_SCHEDULE_TIME` | `07:00` | 해외 뉴스 브리핑 (KST) |

<a id="dashboard"></a>

## Dashboard

`http://localhost:3000` 에서 확인할 수 있습니다:

| Page | 설명 |
|------|------|
| **Dashboard** | 오늘의 리포트 요약, 활성 추천, 주요 지표 |
| **Reports** | 일일/주간/뉴스 리포트 열람 (검색 + 페이지네이션) |
| **Performance** | 승률, P&L 타임시리즈 차트, 섹터별 성과 분석 |
| **Retrospective** | 주간 종합 회고, 전략 조정 제안 |
| **Settings** | 이메일, AI 모델, 언어 설정, 시스템 상태 확인 |

<a id="architecture"></a>

## Architecture

```mermaid
graph TB
    subgraph Scheduler["Scheduler (launchd / cron)"]
        S1[07:00 Global News] --> R1[run_global_news.sh]
        S2[07:15 Korean News] --> R2[run_news.sh]
        S3[07:30 Trading Report] --> R3[run_daily.sh]
    end

    subgraph Backend["Backend (Python + FastAPI)"]
        R1 --> GN[Global News Pipeline]
        R2 --> KN[Korean News Pipeline]
        R3 --> O[Trading Pipeline]

        GN --> C1[AI 분석<br/>해외 뉴스 검색]
        KN --> C2[AI 분석<br/>국내 뉴스 검색]

        O --> CK[Check Recommendations<br/>만료 + 목표가/손절가]
        O --> UP[Update Prices<br/>yfinance]
        O --> RT[Build Retrospective<br/>성과 추적]
        O --> MD[Fetch Market Data<br/>지수/환율/원자재]
        O --> SC[Screen Stocks<br/>펀더멘털 + 기술적 분석]
        O --> C3[AI 분석<br/>뉴스 검색 + 리포트 생성]

        C1 --> PR[Parser + Save]
        C2 --> PR
        C3 --> PR
        PR --> E[Email<br/>Gmail SMTP]
        PR --> DB[(SQLite)]
    end

    subgraph Frontend["Frontend (Next.js + Tailwind)"]
        D[Dashboard]
        RP[Reports]
        PF[Performance]
        RS[Retrospective]
        ST[Settings]
    end

    Frontend -->|REST API| Backend
```

백엔드는 [Hexagonal Architecture](https://alistair.cockburn.us/hexagonal-architecture/) (Ports & Adapters) 패턴을 따릅니다:

```
backend/src/daily_scheduler/
├── domain/           # Entity, Port (interface) — 순수 비즈니스 로직
├── application/      # Use case (pipeline, retrospective, market data)
├── infrastructure/   # Adapter (yfinance, AI, SMTP, SQLAlchemy)
├── entrypoints/      # API route (FastAPI), CLI command (Typer)
├── templates/        # Jinja2 prompt template
└── constants.py      # Tunable defaults (timeout, expiry 등)
```

## Retrospective System

Self-improving feedback loop가 매일 실행됩니다:

```
1. 모든 활성 추천의 현재가를 조회
2. 목표가/손절가 도달 여부 자동 체크 → P&L 계산
3. 30일 통계 생성: 승률, 섹터별 성과, 전략별(DAY/SWING) 비교
4. 실시간 시세 수집 (지수, 환율, 원자재)
5. 모든 context를 AI prompt에 주입
6. AI가 뉴스 검색 → 인과관계 분석 → 파생효과 분석 → 추천 생성
7. 새 추천 → 다음날 성과 추적 → feedback loop 반복
```

**Weekly Retrospective (매주 월요일)**:
- 전주 전체 추천 성과 종합 분석
- 섹터별/전략별 승률 비교
- 전략 조정 제안 및 교훈 도출

## Project Structure

```
daily-news-report/
├── backend/                 # Python backend (FastAPI + Hexagonal Architecture)
│   ├── src/daily_scheduler/
│   │   ├── domain/          # Entity, Port (interface)
│   │   ├── application/     # Use case (pipeline, retrospective, market data)
│   │   ├── infrastructure/  # Adapter (yfinance, AI, SMTP, SQLAlchemy)
│   │   ├── entrypoints/     # API route, CLI command
│   │   ├── templates/       # Jinja2 prompt template (korean_news, global_news, daily_report)
│   │   └── constants.py     # Tunable defaults
│   ├── tests/               # pytest unit + integration test
│   ├── alembic/             # DB migration
│   └── pyproject.toml       # uv project config
├── frontend/                # Next.js 15 (App Router + Tailwind CSS + Recharts)
│   └── src/app/             # Pages: Dashboard, Reports, Performance, Retrospective, Settings
├── scheduler/               # Scheduler config
│   ├── install.sh           # macOS launchd (Trading Report)
│   ├── install-news.sh      # macOS launchd (Korean News)
│   ├── install-global-news.sh  # macOS launchd (Global News)
│   ├── install-*-linux.sh   # Linux/WSL2 cron
│   └── run_*.sh             # Pipeline execution wrapper
├── .env.example             # Environment variable template
├── Makefile                 # 50+ convenience commands
├── SPEC.md                  # 76 verifiable behavior specs
└── DISCLAIMER.md            # Financial data & AI disclaimer
```

## Configuration

### Environment Variables (`.env`) — Secrets & environment-specific

| Variable | 설명 | Default |
|----------|------|---------|
| `SMTP_HOST` | SMTP server host | `smtp.gmail.com` |
| `SMTP_PORT` | SMTP port | `587` |
| `SMTP_USER` | Gmail 주소 | — |
| `SMTP_PASSWORD` | Gmail 앱 비밀번호 | — |
| `EMAIL_TO` | 수신자 (JSON array) | — |
| `CLAUDE_CLI_PATH` | AI CLI binary path | `claude` |
| `CLAUDE_MODEL` | AI model (opus / sonnet / haiku) | `opus` |
| `REPORT_LANGUAGE` | 리포트 언어 (`ko`, `en`, `ja`) | `ko` |
| `TIMEZONE` | IANA timezone | `Asia/Seoul` |
| `SCHEDULE_TIME` | 트레이딩 리포트 시간 KST (HH:MM) | `07:30` |
| `NEWS_SCHEDULE_TIME` | 한국 뉴스 브리핑 시간 KST (HH:MM) | `07:15` |
| `GLOBAL_NEWS_SCHEDULE_TIME` | 해외 뉴스 브리핑 시간 KST (HH:MM) | `07:00` |
| `DATABASE_URL` | SQLite DB path | `sqlite:///data/daily_scheduler.db` |

### Application Constants (`constants.py`) — Tunable defaults

| Constant | 설명 | Default |
|----------|------|---------|
| `CLAUDE_TIMEOUT_SECONDS` | AI call timeout | `1200` |
| `CLAUDE_RETRY_COUNT` | Retry count on failure | `2` |
| `DAY_TRADE_EXPIRY_DAYS` | DAY trade auto-expiry | `1` |
| `SWING_TRADE_EXPIRY_DAYS` | SWING trade auto-expiry | `14` |
| `RETROSPECTIVE_LOOKBACK_DAYS` | Retrospective lookback period | `30` |

## Tech Stack

| Layer | Technologies |
|-------|-------------|
| **Backend** | Python 3.11+, FastAPI, SQLAlchemy, SQLite, Alembic, Pydantic, Jinja2, aiosmtplib |
| **Frontend** | Next.js 15, React 19, TypeScript 5.7, Tailwind CSS 4, Recharts, TanStack Query |
| **AI** | Claude (Anthropic) |
| **Market Data** | yfinance (Yahoo Finance) |
| **Scheduler** | macOS launchd, Linux cron |
| **Package Manager** | uv (Python), Yarn Berry v4 (Frontend) |
| **Code Quality** | ruff, pylint, pyrefly, mypy, ESLint, oxlint, pytest, Playwright |

## Disclaimer

> **이 소프트웨어는 교육 및 연구 목적으로만 제공됩니다.**
> AI가 생성한 트레이딩 추천은 투자 조언이 아니며, 금융 손실에 대한 책임은 사용자에게 있습니다.
> 자세한 내용은 [DISCLAIMER.md](DISCLAIMER.md)를 참조하세요.

금융 데이터는 [yfinance](https://github.com/ranaroussi/yfinance)를 통해 수집됩니다. [Yahoo Finance 이용약관](https://legal.yahoo.com/us/en/yahoo/terms/product-atos/apitnc/index.html)을 준수해야 합니다.

<a id="contributing"></a>

## Contributing

버그 리포트, 기능 제안, 코드 기여 모두 환영합니다.
[CONTRIBUTING.md](CONTRIBUTING.md)를 참조해 주세요.

## Security

보안 취약점을 발견하셨다면 [SECURITY.md](SECURITY.md)를 참조하세요.

## License

[Apache License 2.0](LICENSE)

<!--
  GitHub Topics (Settings → Topics):
  ai, trading, stock-market, daily-report, news-briefing, fastapi, nextjs,
  python, typescript, kospi, nasdaq, retrospective, email-automation,
  hexagonal-architecture, yfinance, global-news
-->
