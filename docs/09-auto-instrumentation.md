# 🤖 09. 자동 계측 (Auto-Instrumentation)

## 학습 목표

`opentelemetry-instrument` CLI를 사용하여 코드 수정 없이 Flask, requests 등 라이브러리를 자동으로 계측하는 방법을 익힙니다.

---

## 핵심 개념

### 자동 계측이란?

자동 계측(Auto-Instrumentation)은 **애플리케이션 코드를 수정하지 않고** 프레임워크와 라이브러리의 텔레메트리 데이터를 자동으로 수집하는 방식입니다.

- Flask의 HTTP 요청 수신 시 자동으로 Span 생성
- requests 라이브러리로 HTTP 요청 전송 시 자동으로 Context 전파
- SQLAlchemy 쿼리 실행 시 자동으로 DB Span 기록

### 동작 원리

자동 계측은 **몽키 패칭(Monkey Patching)** 기법을 사용합니다. 라이브러리의 핵심 함수를 런타임에 OTel 계측 코드로 감싸는 방식입니다.

```
원래 함수 호출:
  flask.Flask.wsgi_app() → 비즈니스 로직

자동 계측 후:
  flask.Flask.wsgi_app() → [OTel: Span 생성 + Context 추출] → 비즈니스 로직 → [OTel: Span 종료]
```

### 필요 패키지

```
opentelemetry-distro       ← 자동 계측 메타 패키지
opentelemetry-instrumentation   ← 계측 라이브러리 검색/설치 도구
opentelemetry-instrumentation-flask   ← Flask 전용 계측
opentelemetry-instrumentation-requests ← requests 전용 계측
```

---

## 실습

### 1단계: 패키지 설치

```bash
# 자동 계측 핵심 패키지
poetry add opentelemetry-distro opentelemetry-instrumentation

# Flask와 requests 계측 라이브러리 (개별 설치)
poetry add opentelemetry-instrumentation-flask
poetry add opentelemetry-instrumentation-requests

# 또는 opentelemetry-bootstrap으로 자동 검색 및 설치
# 프로젝트에 설치된 라이브러리를 스캔하여 호환 계측 패키지를 자동 설치
poetry run opentelemetry-bootstrap -a install
```

### 2단계: 계측 대상 앱 준비

어떤 OTel 코드도 포함하지 않은 순수한 Flask 앱을 준비합니다.

`auto_app.py` 파일을 생성합니다:

```python
# auto_app.py
# OTel 코드가 전혀 없는 순수 Flask 앱

import requests
from flask import Flask, jsonify

app = Flask(__name__)


@app.route("/")
def index():
    return jsonify({"message": "Hello from auto-instrumented app!"})


@app.route("/users")
def get_users():
    # 외부 API 호출 (httpbin.org)
    response = requests.get("https://httpbin.org/json")
    return jsonify({
        "source": "external-api",
        "data": response.json(),
    })


@app.route("/users/<user_id>")
def get_user(user_id):
    return jsonify({"id": user_id, "name": "Alice"})


@app.route("/error")
def trigger_error():
    raise ValueError("의도적으로 발생시킨 에러")


if __name__ == "__main__":
    app.run(port=5000, debug=False)
```

### 3단계: 자동 계측으로 실행

```bash
# opentelemetry-instrument CLI로 앱 실행
# → OTel 코드 없이도 Flask, requests가 자동 계측됨
poetry run opentelemetry-instrument \
    --service_name auto-demo \
    --traces_exporter console \
    --metrics_exporter console \
    --logs_exporter console \
    python auto_app.py
```

다른 터미널에서 요청을 보냅니다:

```bash
curl http://localhost:5000/
curl http://localhost:5000/users
curl http://localhost:5000/users/42
curl http://localhost:5000/error
```

앱이 실행 중인 터미널에서 출력을 확인합니다:

- **`GET /`**: Flask SERVER Span이 자동 생성
- **`GET /users`**: Flask SERVER Span + requests CLIENT Span이 생성되고 Context가 전파
- **`GET /error`**: Span에 ERROR 상태와 예외 정보가 자동 기록

### 4단계: 환경 변수로 설정

CLI 인자 대신 환경 변수로 설정할 수 있습니다:

```bash
# 서비스 식별
export OTEL_SERVICE_NAME=auto-demo
export OTEL_RESOURCE_ATTRIBUTES="deployment.environment=staging,service.version=1.0.0"

# Exporter 설정
export OTEL_TRACES_EXPORTER=otlp
export OTEL_METRICS_EXPORTER=otlp
export OTEL_LOGS_EXPORTER=otlp

# OTLP 엔드포인트 (Collector 주소)
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317

# Python logging 자동 계측
export OTEL_PYTHON_LOGGING_AUTO_INSTRUMENTATION_ENABLED=true

# 실행
poetry run opentelemetry-instrument python auto_app.py
```

### 5단계: 프로그래밍 방식 자동 계측

CLI 대신 코드 내에서 자동 계측을 활성화할 수도 있습니다:

```python
# auto_programmatic.py
# 코드에서 자동 계측 활성화

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, BatchSpanProcessor
from opentelemetry.sdk.resources import Resource

# 먼저 TracerProvider 설정
resource = Resource.create({"service.name": "programmatic-auto-demo"})
provider = TracerProvider(resource=resource)
provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
trace.set_tracer_provider(provider)

# 그 다음 자동 계측 활성화
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor

# Flask 앱이 생성되기 전에 호출
FlaskInstrumentor().instrument()
RequestsInstrumentor().instrument()

# 이후 Flask 앱 정의
from flask import Flask, jsonify
import requests

app = Flask(__name__)

@app.route("/")
def index():
    return jsonify({"status": "ok"})

@app.route("/external")
def call_external():
    # requests 자동 계측: Context 주입 + CLIENT Span 생성
    resp = requests.get("https://httpbin.org/get")
    return jsonify(resp.json())

if __name__ == "__main__":
    app.run(port=5000)
```

---

## 주요 자동 계측 라이브러리

| 라이브러리 | 계측 패키지 | 자동 생성 동작 |
|-----------|------------|---------------|
| Flask | `opentelemetry-instrumentation-flask` | SERVER Span, 요청/응답 속성 |
| FastAPI | `opentelemetry-instrumentation-fastapi` | SERVER Span, 요청/응답 속성 |
| Django | `opentelemetry-instrumentation-django` | SERVER Span, 미들웨어 추적 |
| requests | `opentelemetry-instrumentation-requests` | CLIENT Span, Context 주입 |
| httpx | `opentelemetry-instrumentation-httpx` | CLIENT Span, Context 주입 |
| SQLAlchemy | `opentelemetry-instrumentation-sqlalchemy` | DB Span, 쿼리 기록 |
| psycopg2 | `opentelemetry-instrumentation-psycopg2` | DB Span, PostgreSQL 쿼리 |
| Redis | `opentelemetry-instrumentation-redis` | DB Span, Redis 명령어 |
| Celery | `opentelemetry-instrumentation-celery` | PRODUCER/CONSUMER Span |

전체 목록: [OpenTelemetry Python Contrib](https://github.com/open-telemetry/opentelemetry-python-contrib/tree/main/instrumentation)

---

## 자동 계측 vs. 수동 계측

| 항목 | 자동 계측 | 수동 계측 |
|------|----------|----------|
| 코드 수정 | 불필요 | 필요 |
| 적용 범위 | 프레임워크/라이브러리 수준 | 비즈니스 로직 수준 |
| 세밀한 제어 | 제한적 | 완전한 제어 |
| 도입 비용 | 매우 낮음 | 높음 |
| 권장 조합 | **자동 + 수동을 함께 사용** ||

실무에서는 **자동 계측으로 프레임워크 수준의 기본 데이터를 수집**하고, **수동 계측으로 비즈니스 로직의 세부 정보를 추가**하는 것이 일반적입니다.

---

## 마무리

이번 단계에서 학습한 것:

- `opentelemetry-instrument` CLI를 통한 제로 코드 계측
- 환경 변수 기반 설정 (`OTEL_SERVICE_NAME`, `OTEL_TRACES_EXPORTER` 등)
- 프로그래밍 방식의 자동 계측 (`FlaskInstrumentor().instrument()`)
- 주요 Python 라이브러리별 자동 계측 패키지

**다음 단계**: [10. 수동 계측](10-manual-instrumentation.md)에서 자동 계측과 함께 사용하는 커스텀 Span, 메트릭, 속성 추가 패턴을 학습합니다.
