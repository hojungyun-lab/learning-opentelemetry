# 🛠️ 00. 환경 설정 (Environment Setup)

## 학습 목표

Python, Poetry, Docker 기반의 OpenTelemetry 개발 환경을 구성하고, 기본 패키지가 정상적으로 설치되었는지 확인합니다.

---

## 핵심 개념

### 왜 별도의 환경 설정이 필요한가?

OpenTelemetry는 여러 패키지로 구성된 생태계입니다. 핵심 API와 SDK 이외에도 Exporter, 자동 계측 라이브러리 등 목적에 따라 다양한 패키지를 조합해서 사용합니다. Poetry를 통해 이 의존성을 체계적으로 관리하면 프로젝트 간 충돌 없이 안정적으로 개발할 수 있습니다.

### OpenTelemetry Python 패키지 구조

```
opentelemetry-api          ← API 인터페이스 (추상화 계층)
opentelemetry-sdk          ← SDK 구현체 (실제 동작)
opentelemetry-exporter-*   ← 텔레메트리 데이터 내보내기 (OTLP, Jaeger 등)
opentelemetry-instrumentation-*  ← 라이브러리별 자동 계측
```

- **API 패키지**: 텔레메트리 데이터를 생성하는 인터페이스만 정의합니다. 라이브러리 개발자가 주로 의존합니다.
- **SDK 패키지**: API의 구현체로, 실제로 데이터를 수집·처리·내보내기합니다. 애플리케이션 개발자가 설정합니다.
- **이 분리가 존재하는 이유**: 라이브러리는 가벼운 API에만 의존하고, 최종 애플리케이션에서 SDK 구현체를 선택할 수 있게 됩니다.

---

## 실습

### 1단계: 사전 도구 확인

```bash
# Python 버전 확인 (3.12 이상 권장)
python3 --version

# Poetry 설치 확인
poetry --version
# 미설치 시: curl -sSL https://install.python-poetry.org | python3 -

# Docker 확인 (후반부 실습에서 사용)
docker --version
docker compose version
```

### 2단계: 프로젝트 초기화

```bash
# 학습용 디렉터리 생성
mkdir otel-practice && cd otel-practice

# Poetry 프로젝트 초기화
poetry init \
  --name otel-practice \
  --python "^3.12" \
  --no-interaction

# 가상 환경을 프로젝트 내부에 생성 (선택 사항이지만 권장)
poetry config virtualenvs.in-project true
```

### 3단계: OpenTelemetry 패키지 설치

```bash
# 핵심 패키지: API + SDK
poetry add opentelemetry-api opentelemetry-sdk

# 콘솔 출력용 (학습 초기에 사용)
# SDK에 포함되어 있으므로 별도 설치 불필요

# OTLP Exporter (Collector 연동 시 사용, 나중에 설치해도 됨)
poetry add opentelemetry-exporter-otlp-proto-grpc
```

### 4단계: 설치 확인

`verify_setup.py` 파일을 생성합니다:

```python
# verify_setup.py
# OpenTelemetry 패키지가 정상 설치되었는지 확인하는 스크립트

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor

# TracerProvider 설정
provider = TracerProvider()
# SimpleSpanProcessor: 즉시 내보내기 (개발용, 운영에서는 BatchSpanProcessor 사용)
provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
trace.set_tracer_provider(provider)

# Tracer 생성
tracer = trace.get_tracer("setup-verify")

# 테스트 Span 생성
with tracer.start_as_current_span("hello-opentelemetry") as span:
    span.set_attribute("setup.status", "success")
    print("✅ OpenTelemetry 설정이 정상적으로 완료되었습니다.")

# Provider 종료 (버퍼에 남은 데이터 내보내기)
provider.shutdown()
```

실행:

```bash
poetry run python verify_setup.py
```

**예상 출력:** 콘솔에 Span 데이터(JSON 형식)가 출력되며 `hello-opentelemetry`라는 이름의 Span을 확인할 수 있습니다.

```json
{
    "name": "hello-opentelemetry",
    "context": {
        "trace_id": "0x...",
        "span_id": "0x..."
    },
    "attributes": {
        "setup.status": "success"
    },
    "status": {
        "status_code": "UNSET"
    }
}
```

### 5단계: pyproject.toml 확인

설치가 완료되면 `pyproject.toml`에 다음과 같은 의존성이 기록됩니다:

```toml
[tool.poetry.dependencies]
python = "^3.12"
opentelemetry-api = "^1.39.0"
opentelemetry-sdk = "^1.39.0"
opentelemetry-exporter-otlp-proto-grpc = "^1.39.0"
```

---

## Docker 환경 준비 (선택)

후반부 실습에서는 Jaeger, Prometheus, OTel Collector를 Docker로 실행합니다. 미리 이미지를 다운로드해 두면 편리합니다:

```bash
# Jaeger (트레이싱 백엔드)
docker pull jaegertracing/all-in-one:latest

# OpenTelemetry Collector
docker pull otel/opentelemetry-collector-contrib:latest

# Prometheus (메트릭 백엔드)
docker pull prom/prometheus:latest
```

---

## 마무리

이번 단계에서 완료한 것:

- Python, Poetry, Docker 환경 확인
- OpenTelemetry 핵심 패키지(`opentelemetry-api`, `opentelemetry-sdk`) 설치
- 간단한 Span 생성으로 설치 검증

**다음 단계**: [01. Observability 기초](01-observability-fundamentals.md)에서 OpenTelemetry가 해결하려는 문제, 즉 Observability가 무엇이고 왜 필요한지를 살펴봅니다.
