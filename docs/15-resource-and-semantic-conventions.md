# 🏷️ 15. Resource와 Semantic Conventions

## 학습 목표

Resource 속성을 통해 서비스를 식별하는 방법과, Semantic Conventions(표준 속성 네이밍 규칙)을 적용하여 일관된 텔레메트리 데이터를 생성하는 방법을 학습합니다.

---

## 핵심 개념

### Resource란?

Resource는 텔레메트리 데이터를 **생성하는 주체(서비스, 프로세스, 호스트 등)에 대한 메타데이터**입니다. 모든 Span, Metric, Log에 공통으로 첨부되어 "이 데이터가 어디서 왔는가?"를 식별합니다.

```python
from opentelemetry.sdk.resources import Resource

resource = Resource.create({
    "service.name": "order-service",        # 필수: 서비스 이름
    "service.version": "2.1.0",             # 서비스 버전
    "service.namespace": "e-commerce",      # 서비스 그룹
    "deployment.environment": "production", # 배포 환경
    "host.name": "prod-server-01",          # 호스트명
})
```

### Semantic Conventions란?

Semantic Conventions는 OpenTelemetry에서 정의한 **표준 속성 이름과 값의 규칙**입니다. 서로 다른 팀, 서비스, 언어에서 생성된 텔레메트리 데이터가 **일관된 형식**을 갖도록 합니다.

예를 들어 HTTP 메서드를 기록할 때:
```python
# ❌ 팀마다 다른 이름을 사용하면
span.set_attribute("method", "GET")          # 팀 A
span.set_attribute("http_method", "GET")     # 팀 B
span.set_attribute("request.method", "GET")  # 팀 C

# ✅ Semantic Conventions를 따르면 모두 동일
span.set_attribute("http.request.method", "GET")  # 표준
```

표준화된 속성을 사용하면:
- 백엔드 도구(Jaeger, Grafana 등)가 속성을 자동 인식하여 시각화
- 팀 간 데이터 비교 가능
- Collector의 Processor가 일관되게 데이터를 가공 가능

---

## 실습

### 1단계: Resource 설정 패턴

```python
# resource_demo.py
# 다양한 Resource 설정 방법

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor
from opentelemetry.sdk.resources import Resource, OTELResourceDetector

# --- 방법 1: 딕셔너리로 직접 생성 ---
resource = Resource.create({
    "service.name": "user-service",
    "service.version": "3.2.1",
    "service.namespace": "backend",
    "deployment.environment": "staging",
})

# --- 방법 2: Resource 병합 ---
# 기본 Resource (process, OS 정보 등)에 커스텀 속성 추가
base_resource = Resource.create({
    "service.name": "user-service",
})
custom_resource = Resource.create({
    "team.name": "platform",
    "team.slack": "#platform-alerts",
})
# merge()는 새 Resource를 반환 (충돌 시 other가 우선)
merged_resource = base_resource.merge(custom_resource)

# --- 방법 3: 환경 변수로 설정 ---
# export OTEL_SERVICE_NAME=user-service
# export OTEL_RESOURCE_ATTRIBUTES=service.version=3.2.1,deployment.environment=staging

# 환경 변수 Resource는 코드의 Resource와 자동 병합됨
# 같은 키가 있으면 코드의 값이 우선

provider = TracerProvider(resource=merged_resource)
provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
trace.set_tracer_provider(provider)

tracer = trace.get_tracer(__name__)

with tracer.start_as_current_span("test") as span:
    print("Resource 속성:")
    for key, value in merged_resource.attributes.items():
        print(f"  {key}: {value}")

provider.shutdown()
```

### 2단계: 주요 Semantic Conventions

#### HTTP 관련

```python
# HTTP Server (요청 수신 측)
span.set_attribute("http.request.method", "GET")      # 요청 메서드
span.set_attribute("url.path", "/api/users")           # 경로
span.set_attribute("url.query", "page=1&limit=20")     # 쿼리 스트링
span.set_attribute("url.scheme", "https")              # 스킴
span.set_attribute("http.response.status_code", 200)   # 응답 코드
span.set_attribute("http.route", "/api/users/:id")     # 라우트 패턴
span.set_attribute("server.address", "api.example.com") # 서버 주소
span.set_attribute("server.port", 443)                  # 서버 포트
span.set_attribute("network.protocol.version", "1.1")   # HTTP 버전
span.set_attribute("user_agent.original", "Mozilla/5.0...") # User-Agent

# HTTP Client (요청 전송 측)
span.set_attribute("http.request.method", "POST")
span.set_attribute("server.address", "payment-api.example.com")
span.set_attribute("server.port", 443)
```

#### 데이터베이스 관련

```python
span.set_attribute("db.system", "postgresql")           # DB 종류
span.set_attribute("db.namespace", "myapp")             # 데이터베이스 이름
span.set_attribute("db.operation.name", "SELECT")       # 작업 유형
span.set_attribute("db.query.text", "SELECT * FROM users WHERE id = $1")
span.set_attribute("server.address", "db.example.com")  # DB 호스트
span.set_attribute("server.port", 5432)                 # DB 포트
```

#### 메시징 관련

```python
span.set_attribute("messaging.system", "kafka")             # 메시지 시스템
span.set_attribute("messaging.destination.name", "orders")   # 토픽/큐 이름
span.set_attribute("messaging.operation.type", "publish")    # publish/receive
span.set_attribute("messaging.message.id", "msg-123")        # 메시지 ID
span.set_attribute("messaging.kafka.consumer.group", "order-processors")
```

#### 서비스 Resource 관련

```python
# 필수
resource.set_attribute("service.name", "order-service")

# 권장
resource.set_attribute("service.version", "2.1.0")
resource.set_attribute("service.namespace", "e-commerce")
resource.set_attribute("deployment.environment", "production")

# 호스트 정보
resource.set_attribute("host.name", "prod-01")
resource.set_attribute("host.type", "n2-standard-4")

# 컨테이너/클라우드
resource.set_attribute("container.name", "order-svc-abc123")
resource.set_attribute("k8s.namespace.name", "production")
resource.set_attribute("k8s.pod.name", "order-svc-abc123-xyz")
resource.set_attribute("cloud.provider", "gcp")
resource.set_attribute("cloud.region", "asia-northeast3")
```

### 3단계: Semantic Conventions를 적용한 실전 계측

```python
# semantic_app.py
# Semantic Conventions를 적용한 계측 예시

import time
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.trace import SpanKind, StatusCode

resource = Resource.create({
    "service.name": "order-service",
    "service.version": "2.1.0",
    "service.namespace": "e-commerce",
    "deployment.environment": "production",
})

provider = TracerProvider(resource=resource)
provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
trace.set_tracer_provider(provider)
tracer = trace.get_tracer("order-service", "2.1.0")


def handle_create_order():
    """HTTP Server Span — Semantic Conventions 적용"""
    with tracer.start_as_current_span(
        "POST /api/orders",
        kind=SpanKind.SERVER,
        attributes={
            "http.request.method": "POST",
            "url.path": "/api/orders",
            "url.scheme": "https",
            "http.route": "/api/orders",
            "server.address": "api.example.com",
            "server.port": 443,
        },
    ) as span:
        # DB 조회
        query_database()

        # 외부 서비스 호출
        call_payment_api()

        span.set_attribute("http.response.status_code", 201)


def query_database():
    """DB Span — Semantic Conventions 적용"""
    with tracer.start_as_current_span(
        "SELECT orders",
        kind=SpanKind.CLIENT,
        attributes={
            "db.system": "postgresql",
            "db.namespace": "ecommerce",
            "db.operation.name": "SELECT",
            "db.query.text": "SELECT * FROM orders WHERE user_id = $1",
            "server.address": "db.internal",
            "server.port": 5432,
        },
    ):
        time.sleep(0.01)


def call_payment_api():
    """HTTP Client Span — Semantic Conventions 적용"""
    with tracer.start_as_current_span(
        "POST payment-api/charge",
        kind=SpanKind.CLIENT,
        attributes={
            "http.request.method": "POST",
            "server.address": "payment.example.com",
            "server.port": 443,
            "url.path": "/api/v2/charge",
        },
    ) as span:
        time.sleep(0.02)
        span.set_attribute("http.response.status_code", 200)


handle_create_order()
provider.shutdown()
```

---

## Semantic Conventions 참조

공식 Semantic Conventions 문서:
- [HTTP](https://opentelemetry.io/docs/specs/semconv/http/)
- [Database](https://opentelemetry.io/docs/specs/semconv/database/)
- [Messaging](https://opentelemetry.io/docs/specs/semconv/messaging/)
- [RPC](https://opentelemetry.io/docs/specs/semconv/rpc/)
- [Resource](https://opentelemetry.io/docs/specs/semconv/resource/)

---

## 마무리

이번 단계에서 학습한 것:

- **Resource**: 서비스 식별 메타데이터 (이름, 버전, 환경)
- **Semantic Conventions**: 표준 속성명으로 일관된 데이터 생성
- **주요 도메인별 속성**: HTTP, Database, Messaging, Resource
- **병합 패턴**: 여러 소스의 Resource를 합치는 방법

**다음 단계**: [16. Baggage와 Correlation](16-baggage-and-correlation.md)에서 서비스 간에 커스텀 메타데이터를 전파하는 Baggage API를 학습합니다.
