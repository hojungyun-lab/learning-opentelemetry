# 📋 OpenTelemetry Python 치트시트

> OpenTelemetry Python SDK 핵심 API와 패턴을 빠르게 참조할 수 있는 요약 카드입니다.

---

## 목차

- [패키지 설치](#패키지-설치)
- [Tracing](#tracing)
- [Metrics](#metrics)
- [Logs](#logs)
- [Context Propagation](#context-propagation)
- [Exporters](#exporters)
- [Collector 설정](#collector-설정)
- [자동 계측](#자동-계측)
- [Resource & Semantic Conventions](#resource--semantic-conventions)
- [Sampling](#sampling)
- [Baggage](#baggage)
- [테스트](#테스트)

---

## 패키지 설치

```bash
# 핵심 패키지
poetry add opentelemetry-api opentelemetry-sdk

# OTLP Exporter (gRPC / HTTP)
poetry add opentelemetry-exporter-otlp-proto-grpc
poetry add opentelemetry-exporter-otlp-proto-http

# 자동 계측
poetry add opentelemetry-distro opentelemetry-instrumentation

# 개별 계측 라이브러리 (필요한 것만)
poetry add opentelemetry-instrumentation-flask
poetry add opentelemetry-instrumentation-fastapi
poetry add opentelemetry-instrumentation-requests
poetry add opentelemetry-instrumentation-sqlalchemy
```

---

## Tracing

### TracerProvider 초기화

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
)
from opentelemetry.sdk.resources import Resource

# Resource: 이 서비스를 식별하는 메타데이터
resource = Resource.create({
    "service.name": "my-service",
    "service.version": "1.0.0",
    "deployment.environment": "production",
})

# Provider 생성 및 글로벌 등록
provider = TracerProvider(resource=resource)
provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
trace.set_tracer_provider(provider)

# Tracer 취득
tracer = trace.get_tracer(__name__)
```

### Span 생성

```python
# 기본 Span
with tracer.start_as_current_span("operation-name") as span:
    # 이 블록 안의 코드가 Span으로 기록됨
    result = do_work()

# 속성(Attributes) 추가
with tracer.start_as_current_span("db-query") as span:
    span.set_attribute("db.system", "postgresql")
    span.set_attribute("db.statement", "SELECT * FROM users")
    result = execute_query()

# 이벤트(Event) 기록
with tracer.start_as_current_span("process-order") as span:
    span.add_event("order.validated", {"order.id": "12345"})
    process(order)
    span.add_event("order.completed")

# 상태(Status) 설정
from opentelemetry.trace import StatusCode

with tracer.start_as_current_span("risky-operation") as span:
    try:
        result = risky_work()
        span.set_status(StatusCode.OK)
    except Exception as e:
        span.set_status(StatusCode.ERROR, str(e))
        span.record_exception(e)  # 예외 정보를 이벤트로 기록
        raise
```

### Span 종류(SpanKind)

```python
from opentelemetry.trace import SpanKind

# SERVER: HTTP 요청을 수신하는 서버
with tracer.start_as_current_span("handle-request", kind=SpanKind.SERVER):
    ...

# CLIENT: 외부 서비스로 요청을 보내는 클라이언트
with tracer.start_as_current_span("call-api", kind=SpanKind.CLIENT):
    ...

# PRODUCER: 메시지를 큐에 발행
with tracer.start_as_current_span("send-message", kind=SpanKind.PRODUCER):
    ...

# CONSUMER: 메시지를 큐에서 소비
with tracer.start_as_current_span("receive-message", kind=SpanKind.CONSUMER):
    ...

# INTERNAL: 내부 작업 (기본값)
with tracer.start_as_current_span("internal-calc", kind=SpanKind.INTERNAL):
    ...
```

### 중첩 Span (부모-자식 관계)

```python
# start_as_current_span은 자동으로 현재 Context의 Span을 부모로 설정
with tracer.start_as_current_span("parent-operation"):
    # parent-operation이 부모
    with tracer.start_as_current_span("child-step-1"):
        do_step_1()
    with tracer.start_as_current_span("child-step-2"):
        do_step_2()
```

---

## Metrics

### MeterProvider 초기화

```python
from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import (
    PeriodicExportingMetricReader,
    ConsoleMetricExporter,
)
from opentelemetry.sdk.resources import Resource

resource = Resource.create({"service.name": "my-service"})

reader = PeriodicExportingMetricReader(
    ConsoleMetricExporter(),
    export_interval_millis=10000,  # 10초마다 내보내기
)
provider = MeterProvider(resource=resource, metric_readers=[reader])
metrics.set_meter_provider(provider)

meter = metrics.get_meter(__name__)
```

### 동기 계측기 (Synchronous Instruments)

```python
# Counter — 단조 증가 값 (요청 수, 에러 수 등)
request_counter = meter.create_counter(
    name="http.server.request.count",
    description="수신된 HTTP 요청 수",
    unit="1",
)
request_counter.add(1, {"http.method": "GET", "http.route": "/api/items"})

# UpDownCounter — 증감 가능한 값 (활성 연결 수 등)
active_connections = meter.create_up_down_counter(
    name="http.server.active_connections",
    description="현재 활성 연결 수",
)
active_connections.add(1)   # 연결 시
active_connections.add(-1)  # 해제 시

# Histogram — 분포 측정 (응답 시간, 페이로드 크기 등)
request_duration = meter.create_histogram(
    name="http.server.request.duration",
    description="HTTP 요청 처리 시간",
    unit="ms",
)
request_duration.record(45.2, {"http.method": "GET", "http.status_code": 200})
```

### 비동기 계측기 (Observable / Asynchronous Instruments)

```python
import psutil

# Observable Gauge — 현재 값을 콜백으로 조회
def cpu_usage_callback(options):
    yield metrics.Observation(psutil.cpu_percent(), {})

meter.create_observable_gauge(
    name="system.cpu.utilization",
    callbacks=[cpu_usage_callback],
    description="CPU 사용률",
    unit="%",
)

# Observable Counter — 콜백으로 누적 값 조회
def bytes_sent_callback(options):
    net = psutil.net_io_counters()
    yield metrics.Observation(net.bytes_sent, {"direction": "sent"})

meter.create_observable_counter(
    name="system.network.bytes",
    callbacks=[bytes_sent_callback],
    unit="By",
)
```

### Views (메트릭 커스터마이징)

```python
from opentelemetry.sdk.metrics.view import View

# Histogram의 버킷 경계 변경
latency_view = View(
    instrument_name="http.server.request.duration",
    aggregation=ExplicitBucketHistogramAggregation(
        boundaries=[5, 10, 25, 50, 100, 250, 500, 1000]
    ),
)

# 특정 속성만 유지 (카디널리티 제어)
route_only_view = View(
    instrument_name="http.server.request.count",
    attribute_keys={"http.route"},  # http.method 등 다른 속성은 제거
)

provider = MeterProvider(
    resource=resource,
    metric_readers=[reader],
    views=[latency_view, route_only_view],
)
```

---

## Logs

### OTel Logs Bridge 설정

```python
import logging
from opentelemetry._logs import set_logger_provider
from opentelemetry.sdk._logs import LoggerProvider, LogRecord
from opentelemetry.sdk._logs.export import (
    BatchLogRecordProcessor,
    ConsoleLogExporter,
)
from opentelemetry.sdk.resources import Resource

resource = Resource.create({"service.name": "my-service"})

logger_provider = LoggerProvider(resource=resource)
logger_provider.add_log_record_processor(
    BatchLogRecordProcessor(ConsoleLogExporter())
)
set_logger_provider(logger_provider)

# Python 표준 logging에 OTel 핸들러 연결
from opentelemetry.sdk._logs import LoggingHandler

handler = LoggingHandler(
    level=logging.INFO,
    logger_provider=logger_provider,
)
logging.getLogger().addHandler(handler)

# 이제 일반 logging 호출이 OTel로 전달됨
logger = logging.getLogger(__name__)
logger.info("사용자가 로그인했습니다", extra={"user.id": "user-123"})
```

---

## Context Propagation

### 서비스 간 Context 전파 (HTTP)

```python
from opentelemetry.propagate import inject, extract
from opentelemetry import context
import requests

# --- 클라이언트 측: Context를 HTTP 헤더에 주입 ---
headers = {}
inject(headers)  # traceparent, tracestate 등 자동 주입
response = requests.get("http://other-service/api", headers=headers)

# --- 서버 측: HTTP 헤더에서 Context 추출 ---
from flask import request

ctx = extract(carrier=request.headers)
with tracer.start_as_current_span("handle", context=ctx):
    process_request()
```

### Propagator 설정

```python
from opentelemetry.propagate import set_global_textmap
from opentelemetry.propagators.composite import CompositeTextMapPropagator
from opentelemetry.propagators.b3 import B3MultiFormat

# W3C TraceContext(기본) + B3 동시 지원
set_global_textmap(CompositeTextMapPropagator([
    TraceContextTextMapPropagator(),
    B3MultiFormat(),
]))
```

---

## Exporters

### OTLP Exporter (gRPC)

```python
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter

# 기본 엔드포인트: localhost:4317
span_exporter = OTLPSpanExporter(endpoint="http://localhost:4317", insecure=True)
metric_exporter = OTLPMetricExporter(endpoint="http://localhost:4317", insecure=True)
```

### OTLP Exporter (HTTP/Protobuf)

```python
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter

# 기본 엔드포인트: localhost:4318
span_exporter = OTLPSpanExporter(endpoint="http://localhost:4318/v1/traces")
metric_exporter = OTLPMetricExporter(endpoint="http://localhost:4318/v1/metrics")
```

### Prometheus Exporter

```python
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from prometheus_client import start_http_server

# Prometheus가 스크랩할 /metrics 엔드포인트 노출 (포트 8000)
reader = PrometheusMetricReader()
provider = MeterProvider(resource=resource, metric_readers=[reader])
start_http_server(8000)
```

---

## Collector 설정

### 최소 구성 (otel-collector-config.yml)

```yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318

processors:
  batch:
    timeout: 5s
    send_batch_size: 1024

exporters:
  debug:
    verbosity: detailed
  otlp/jaeger:
    endpoint: jaeger:4317
    tls:
      insecure: true

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [batch]
      exporters: [debug, otlp/jaeger]
    metrics:
      receivers: [otlp]
      processors: [batch]
      exporters: [debug]
```

### Docker Compose로 Collector 실행

```yaml
# docker-compose.yml
services:
  otel-collector:
    image: otel/opentelemetry-collector-contrib:latest
    volumes:
      - ./otel-collector-config.yml:/etc/otelcol-contrib/config.yaml
    ports:
      - "4317:4317"   # gRPC
      - "4318:4318"   # HTTP
```

---

## 자동 계측

### CLI로 자동 계측 실행

```bash
# 계측 라이브러리 자동 설치
poetry run opentelemetry-bootstrap -a install

# 자동 계측으로 앱 실행
poetry run opentelemetry-instrument \
    --service_name my-service \
    --traces_exporter console \
    --metrics_exporter console \
    python app.py
```

### 환경 변수로 설정

```bash
export OTEL_SERVICE_NAME=my-service
export OTEL_TRACES_EXPORTER=otlp
export OTEL_METRICS_EXPORTER=otlp
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
export OTEL_PYTHON_LOGGING_AUTO_INSTRUMENTATION_ENABLED=true
```

---

## Resource & Semantic Conventions

### Resource 정의

```python
from opentelemetry.sdk.resources import Resource

resource = Resource.create({
    "service.name": "order-service",
    "service.version": "2.1.0",
    "service.namespace": "shop",
    "deployment.environment": "staging",
    "host.name": "server-01",
})
```

### 주요 Semantic Conventions (속성명)

```python
# HTTP 서버
"http.request.method"          # GET, POST, ...
"url.path"                     # /api/users
"http.response.status_code"    # 200, 404, 500
"server.address"               # example.com

# 데이터베이스
"db.system"                    # postgresql, mysql, redis
"db.namespace"                 # 데이터베이스 이름
"db.operation.name"            # SELECT, INSERT
"db.query.text"                # 실제 쿼리문

# 메시징
"messaging.system"             # kafka, rabbitmq
"messaging.destination.name"   # 토픽/큐 이름
"messaging.operation.type"     # publish, receive
```

---

## Sampling

```python
from opentelemetry.sdk.trace.sampling import (
    ALWAYS_ON,
    ALWAYS_OFF,
    TraceIdRatioBased,
    ParentBasedTraceIdRatio,
)

# 모든 Span 수집
provider = TracerProvider(sampler=ALWAYS_ON)

# 10%만 샘플링
provider = TracerProvider(sampler=TraceIdRatioBased(0.1))

# 부모 Span이 있으면 부모 결정을 따르고, 없으면 10% 샘플링
provider = TracerProvider(sampler=ParentBasedTraceIdRatio(0.1))

# 환경 변수로 설정
# OTEL_TRACES_SAMPLER=traceidratio
# OTEL_TRACES_SAMPLER_ARG=0.1
```

---

## Baggage

```python
from opentelemetry import baggage, context

# Baggage 설정 (현재 Context에 키-값 추가)
ctx = baggage.set_baggage("user.id", "user-42")
ctx = baggage.set_baggage("tenant.id", "acme-corp", context=ctx)

# 설정된 Context를 활성화
token = context.attach(ctx)

# Baggage 조회
user_id = baggage.get_baggage("user.id")  # "user-42"

# 모든 Baggage 조회
all_baggage = baggage.get_all()  # {"user.id": "user-42", "tenant.id": "acme-corp"}

# Context 복원
context.detach(token)
```

---

## 테스트

### InMemorySpanExporter로 Span 검증

```python
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export.in_memory import InMemorySpanExporter
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

# 테스트용 Provider 설정
exporter = InMemorySpanExporter()
provider = TracerProvider()
provider.add_span_processor(SimpleSpanProcessor(exporter))

tracer = provider.get_tracer("test")

# 테스트 대상 코드 실행
with tracer.start_as_current_span("test-operation") as span:
    span.set_attribute("key", "value")

# 검증
spans = exporter.get_finished_spans()
assert len(spans) == 1
assert spans[0].name == "test-operation"
assert spans[0].attributes["key"] == "value"

# 다음 테스트 전에 초기화
exporter.clear()
```

### 환경 변수 기반 디버깅

```bash
# 디버그 로깅 활성화
export OTEL_LOG_LEVEL=debug

# 콘솔 출력으로 전환 (문제 진단 시)
export OTEL_TRACES_EXPORTER=console
export OTEL_METRICS_EXPORTER=console

# SDK 비활성화 (성능 비교 시)
export OTEL_SDK_DISABLED=true
```
