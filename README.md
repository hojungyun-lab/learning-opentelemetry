# 📡 Learning OpenTelemetry

OpenTelemetry(이하 OTel)를 **처음부터 실전까지** 단계별로 학습할 수 있는 종합 가이드 레포지토리입니다.

## 이 가이드의 특징

- **단계별 구성**: 환경 설정부터 마이크로서비스 분산 추적까지 18단계로 구성
- **실습 중심**: 모든 개념을 실제 동작하는 코드와 함께 설명
- **실전 프로젝트 포함**: 기초 데모 앱과 멀티 서비스 최종 프로젝트 제공
- **현업 기준**: OpenTelemetry Python SDK 1.39.x 기반의 모범 사례 적용

## 사전 요구사항

- Python 3.12 이상
- Docker & Docker Compose
- Poetry (Python 패키지 관리)
- 기본적인 Python 웹 개발 경험 (Flask 또는 FastAPI)

## 프로젝트 구조

```text
.
├── README.md                 # 프로젝트 소개 및 학습 목차
├── CHEATSHEET.md             # 핵심 API 빠른 참조 카드
├── assets/                   # 다이어그램 이미지
│   └── images/
├── docs/                     # 단계별 학습 문서
│   ├── 00-environment-setup.md
│   ├── 01-observability-fundamentals.md
│   ├── ...
│   └── 17-testing-and-debugging.md
└── examples/                 # 데모 프로젝트
    ├── basic-app/            # Flask 기초 계측 앱
    └── final-project/        # FastAPI 마이크로서비스 통합 프로젝트
```

## 🚀 시작하기

### 1. 환경 확인

```bash
# Python 버전 확인 (3.12 이상)
python3 --version

# Poetry 설치 확인
poetry --version

# Docker 확인
docker --version
docker compose version
```

> Poetry가 설치되어 있지 않다면: `curl -sSL https://install.python-poetry.org | python3 -`

### 2. 학습용 빈 프로젝트 생성

학습 문서를 따라가며 직접 코드를 작성해 볼 빈 프로젝트를 생성합니다.

```bash
# 새 디렉터리 생성 및 이동
mkdir my-otel-practice && cd my-otel-practice

# Poetry로 프로젝트 초기화
poetry init --name my-otel-practice --python "^3.12" --no-interaction

# OpenTelemetry 기본 패키지 설치
poetry add opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp
```

### 3. 완성된 예제 실행해 보기

#### basic-app (기초 데모)

```bash
cd examples/basic-app
poetry install
poetry run python app.py

# 다른 터미널에서 요청 전송
curl http://localhost:5050/items
curl http://localhost:5050/items/1
```

콘솔에 출력되는 Span 데이터를 확인할 수 있습니다.

#### final-project (실전 마이크로서비스)

```bash
cd examples/final-project
docker compose up --build

# 다른 터미널에서 요청 전송
curl http://localhost:8001/orders
curl http://localhost:8002/inventory
```

- Jaeger UI: http://localhost:16686 — 분산 트레이스 시각화
- Prometheus UI: http://localhost:9090 — 메트릭 조회

---

## 📚 학습 목차 (커리큘럼)

### 기초 단계

| # | 주제 | 핵심 내용 |
|---|------|-----------|
| 00 | [환경 설정](docs/00-environment-setup.md) | Python, Poetry, Docker 환경 구성 및 OTel 패키지 설치 |
| 01 | [Observability 기초](docs/01-observability-fundamentals.md) | Observability의 정의, Traces·Metrics·Logs 세 가지 신호 |
| 02 | [OpenTelemetry 아키텍처](docs/02-opentelemetry-architecture.md) | API / SDK / Exporter / Collector 계층 구조 |

### Traces & Context

| # | 주제 | 핵심 내용 |
|---|------|-----------|
| 03 | [Traces 기초](docs/03-traces-basics.md) | TracerProvider 설정, 첫 Span 생성, ConsoleSpanExporter |
| 04 | [Spans 심화](docs/04-spans-in-depth.md) | Span 속성, 이벤트, 상태 코드, 중첩 Span 구조 |
| 05 | [Context Propagation](docs/05-context-propagation.md) | Context 개념, W3C TraceContext, 서비스 간 전파 |

### Metrics & Logs

| # | 주제 | 핵심 내용 |
|---|------|-----------|
| 06 | [Metrics 기초](docs/06-metrics-basics.md) | MeterProvider, Counter, Histogram 기본 사용법 |
| 07 | [Metrics 심화](docs/07-metrics-advanced.md) | UpDownCounter, Observable 계측기, Views 설정 |
| 08 | [Logs 연동](docs/08-logs-integration.md) | Python logging 모듈과 OTel Logs Bridge 통합 |

### 계측 (Instrumentation)

| # | 주제 | 핵심 내용 |
|---|------|-----------|
| 09 | [자동 계측](docs/09-auto-instrumentation.md) | opentelemetry-instrument CLI, Flask/Requests 자동 계측 |
| 10 | [수동 계측](docs/10-manual-instrumentation.md) | 커스텀 Span, 메트릭, 속성 추가 실전 패턴 |

### 백엔드 & Collector

| # | 주제 | 핵심 내용 |
|---|------|-----------|
| 11 | [Exporters와 백엔드](docs/11-exporters-and-backends.md) | OTLP, Jaeger, Prometheus Exporter 설정 |
| 12 | [Collector 설정](docs/12-collector-setup.md) | OTel Collector 아키텍처와 Docker 기반 구동 |
| 13 | [Collector 파이프라인](docs/13-collector-pipelines.md) | Receiver → Processor → Exporter 구성 |

### 고급 & 실전

| # | 주제 | 핵심 내용 |
|---|------|-----------|
| 14 | [Sampling 전략](docs/14-sampling-strategies.md) | AlwaysOn, TraceIdRatio, ParentBased, Tail Sampling |
| 15 | [Resource와 Semantic Conventions](docs/15-resource-and-semantic-conventions.md) | Resource 속성 정의, 표준 속성 네이밍 규칙 |
| 16 | [Baggage와 Correlation](docs/16-baggage-and-correlation.md) | Baggage API, 서비스 간 메타데이터 전파 |
| 17 | [테스트와 디버깅](docs/17-testing-and-debugging.md) | InMemorySpanExporter, 계측 코드 테스트 전략 |

---

## 📋 빠른 참조

핵심 API와 패턴을 한눈에 확인하려면 → [CHEATSHEET.md](CHEATSHEET.md)

---

## 참고 자료

- [OpenTelemetry 공식 문서](https://opentelemetry.io/docs/)
- [OpenTelemetry Python GitHub](https://github.com/open-telemetry/opentelemetry-python)
- [OpenTelemetry Python Contrib](https://github.com/open-telemetry/opentelemetry-python-contrib)
- [W3C Trace Context 표준](https://www.w3.org/TR/trace-context/)
