# 🧪 17. 테스트와 디버깅 (Testing and Debugging)

## 학습 목표

InMemorySpanExporter를 사용하여 계측 코드를 단위 테스트하는 방법과, 텔레메트리 파이프라인의 문제를 진단하는 디버깅 전략을 학습합니다.

---

## 핵심 개념

### 왜 계측 코드를 테스트해야 하는가?

계측 코드도 프로덕션 코드의 일부입니다. 다음과 같은 상황을 방지하기 위해 테스트가 필요합니다:

- 리팩토링 후 Span이 누락되는 경우
- 잘못된 속성명이나 값이 기록되는 경우
- 부모-자식 Span 관계가 깨지는 경우
- 에러 상태가 올바르게 기록되지 않는 경우

### 테스트용 Exporter

| Exporter | 용도 |
|----------|------|
| `InMemorySpanExporter` | Span을 메모리에 저장 → 테스트에서 검증 |
| `ConsoleSpanExporter` | 콘솔 출력 → 눈으로 확인 |

---

## 실습

### 1단계: InMemorySpanExporter 기반 테스트

```bash
# pytest 설치
poetry add --group dev pytest
```

테스트 대상 코드 (`order_service.py`):

```python
# order_service.py
# 테스트 대상 비즈니스 로직

from opentelemetry import trace
from opentelemetry.trace import StatusCode

tracer = trace.get_tracer("order-service")


def create_order(user_id: str, items: list[dict]) -> dict:
    """주문 생성"""
    with tracer.start_as_current_span("create-order") as span:
        span.set_attribute("order.user_id", user_id)
        span.set_attribute("order.item_count", len(items))

        # 검증
        validate_items(items)

        # 총액 계산
        total = sum(item["price"] * item["qty"] for item in items)
        span.set_attribute("order.total", total)

        if total <= 0:
            span.set_status(StatusCode.ERROR, "총액이 0 이하")
            raise ValueError("총액이 0 이하입니다")

        span.add_event("order.created", {"order.total": total})
        return {"order_id": "ORD-001", "total": total, "status": "created"}


def validate_items(items: list[dict]):
    """주문 아이템 검증"""
    with tracer.start_as_current_span("validate-items") as span:
        if not items:
            span.set_status(StatusCode.ERROR, "아이템 없음")
            raise ValueError("주문 아이템이 비어있습니다")

        span.set_attribute("validation.item_count", len(items))
        span.add_event("validation.passed")
```

테스트 코드 (`test_order_service.py`):

```python
# test_order_service.py
# 계측 코드 단위 테스트

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory import InMemorySpanExporter
from opentelemetry.trace import StatusCode

from order_service import create_order


# --- 테스트 픽스처 ---

@pytest.fixture(autouse=True)
def setup_telemetry():
    """각 테스트 전에 새로운 TracerProvider 설정"""
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    yield exporter  # 테스트에 exporter 전달

    exporter.clear()
    provider.shutdown()


# --- 테스트 ---

def test_create_order_generates_spans(setup_telemetry):
    """주문 생성 시 올바른 Span이 생성되는지 검증"""
    exporter = setup_telemetry
    items = [{"price": 10000, "qty": 2}, {"price": 5000, "qty": 1}]

    result = create_order("user-42", items)

    # Span 목록 가져오기 (종료된 순서대로)
    spans = exporter.get_finished_spans()

    # 2개의 Span이 생성되어야 함: validate-items, create-order
    assert len(spans) == 2

    # Span 이름 확인
    span_names = [s.name for s in spans]
    assert "validate-items" in span_names
    assert "create-order" in span_names


def test_create_order_attributes(setup_telemetry):
    """Span 속성이 올바르게 기록되는지 검증"""
    exporter = setup_telemetry
    items = [{"price": 10000, "qty": 2}]

    create_order("user-42", items)

    spans = exporter.get_finished_spans()
    create_span = next(s for s in spans if s.name == "create-order")

    # 속성 검증
    assert create_span.attributes["order.user_id"] == "user-42"
    assert create_span.attributes["order.item_count"] == 1
    assert create_span.attributes["order.total"] == 20000


def test_create_order_events(setup_telemetry):
    """Span 이벤트가 올바르게 기록되는지 검증"""
    exporter = setup_telemetry
    items = [{"price": 5000, "qty": 3}]

    create_order("user-42", items)

    spans = exporter.get_finished_spans()
    create_span = next(s for s in spans if s.name == "create-order")

    # 이벤트 검증
    event_names = [e.name for e in create_span.events]
    assert "order.created" in event_names

    order_event = next(e for e in create_span.events if e.name == "order.created")
    assert order_event.attributes["order.total"] == 15000


def test_create_order_parent_child(setup_telemetry):
    """부모-자식 Span 관계 검증"""
    exporter = setup_telemetry
    items = [{"price": 10000, "qty": 1}]

    create_order("user-42", items)

    spans = exporter.get_finished_spans()
    create_span = next(s for s in spans if s.name == "create-order")
    validate_span = next(s for s in spans if s.name == "validate-items")

    # 같은 Trace에 속하는지 확인
    assert create_span.context.trace_id == validate_span.context.trace_id

    # validate-items의 부모가 create-order인지 확인
    assert validate_span.parent.span_id == create_span.context.span_id


def test_create_order_error_status(setup_telemetry):
    """에러 시 Span 상태가 ERROR로 설정되는지 검증"""
    exporter = setup_telemetry

    with pytest.raises(ValueError, match="비어있습니다"):
        create_order("user-42", [])

    spans = exporter.get_finished_spans()
    validate_span = next(s for s in spans if s.name == "validate-items")

    assert validate_span.status.status_code == StatusCode.ERROR
    assert "아이템 없음" in validate_span.status.description
```

```bash
poetry run pytest test_order_service.py -v
```

### 2단계: Metrics 테스트

```python
# test_metrics.py
# 메트릭 계측 코드 테스트

import pytest
from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader


@pytest.fixture
def metric_setup():
    reader = InMemoryMetricReader()
    provider = MeterProvider(metric_readers=[reader])
    metrics.set_meter_provider(provider)
    yield reader
    provider.shutdown()


def test_counter_increments(metric_setup):
    reader = metric_setup
    meter = metrics.get_meter("test")
    counter = meter.create_counter("test.counter")

    counter.add(1, {"operation": "create"})
    counter.add(3, {"operation": "create"})
    counter.add(1, {"operation": "delete"})

    # 메트릭 데이터 수집
    data = reader.get_metrics_data()
    metric_data = data.resource_metrics[0].scope_metrics[0].metrics[0]

    assert metric_data.name == "test.counter"

    # 데이터 포인트 확인
    points = list(metric_data.data.data_points)
    create_point = next(
        p for p in points if dict(p.attributes).get("operation") == "create"
    )
    assert create_point.value == 4  # 1 + 3
```

### 3단계: 디버깅 전략

#### 텔레메트리가 전송되지 않을 때

```python
# debug_checklist.py
# 텔레메트리 문제 진단 체크리스트

from opentelemetry import trace

# 1. TracerProvider가 설정되어 있는가?
provider = trace.get_tracer_provider()
print(f"현재 TracerProvider: {type(provider).__name__}")
# "ProxyTracerProvider"가 출력되면 SDK가 설정되지 않은 것

# 2. Span이 recording 상태인가?
tracer = trace.get_tracer("debug")
with tracer.start_as_current_span("test") as span:
    print(f"is_recording: {span.is_recording()}")
    # False이면 SDK 미설정 또는 Sampler가 거부한 것

# 3. OTEL_SDK_DISABLED 환경 변수 확인
import os
print(f"OTEL_SDK_DISABLED: {os.environ.get('OTEL_SDK_DISABLED', 'not set')}")
```

#### 환경 변수 기반 디버깅

```bash
# OTel 내부 로깅 레벨 변경
export OTEL_LOG_LEVEL=debug

# 콘솔 출력으로 전환하여 데이터 확인
export OTEL_TRACES_EXPORTER=console
export OTEL_METRICS_EXPORTER=console
export OTEL_LOGS_EXPORTER=console

# SDK를 완전히 비활성화 (성능 비교용)
export OTEL_SDK_DISABLED=true
```

#### Collector 연결 문제 진단

```bash
# Collector가 실행 중인지 확인
docker ps | grep otel-collector

# Collector 로그 확인
docker logs otel-collector 2>&1 | tail -50

# OTLP 엔드포인트 연결 테스트 (gRPC)
grpcurl -plaintext localhost:4317 list

# OTLP 엔드포인트 연결 테스트 (HTTP)
curl -v http://localhost:4318/v1/traces
```

#### Collector 자체 메트릭으로 진단

```yaml
# otel-collector-config.yml
service:
  telemetry:
    logs:
      level: debug          # 상세 로그
    metrics:
      address: 0.0.0.0:8888  # 내부 메트릭 노출
```

```bash
# Collector 내부 메트릭 확인
curl http://localhost:8888/metrics | grep otelcol

# 주요 지표:
# otelcol_receiver_accepted_spans — 수신된 Span 수
# otelcol_receiver_refused_spans — 거부된 Span 수
# otelcol_exporter_sent_spans — 전송된 Span 수
# otelcol_exporter_send_failed_spans — 전송 실패 Span 수
# otelcol_processor_batch_batch_send_size — 배치 크기
```

---

## 디버깅 순서 요약

```
1. SDK 설정 확인
   → TracerProvider가 ProxyTracerProvider가 아닌지?
   → span.is_recording()이 True인지?

2. Exporter 확인
   → ConsoleSpanExporter로 데이터가 출력되는지?
   → OTLP 엔드포인트가 올바른지?

3. 네트워크 확인
   → Collector가 실행 중인지?
   → 포트가 열려 있는지?
   → 방화벽/프록시 문제가 있는지?

4. Collector 확인
   → Collector 로그에 에러가 있는지?
   → Receiver/Processor/Exporter 설정이 올바른지?
   → 내부 메트릭에서 refused/failed 카운터가 증가하는지?

5. 백엔드 확인
   → Jaeger/Prometheus에서 서비스가 보이는지?
   → 데이터 기간 필터가 올바른지?
```

---

## 마무리

이번 단계에서 학습한 것:

- **InMemorySpanExporter**: 테스트에서 Span 생성, 속성, 이벤트, 관계, 상태를 검증
- **InMemoryMetricReader**: 메트릭 계측 코드 테스트
- **디버깅 체크리스트**: SDK 설정 → Exporter → 네트워크 → Collector → 백엔드
- **Collector 진단**: 내부 로그와 메트릭을 활용한 문제 분석

**축하합니다!** 이것으로 OpenTelemetry의 전체 학습 문서가 완료되었습니다. [examples/basic-app](../examples/basic-app/) 과 [examples/final-project](../examples/final-project/) 에서 지금까지 학습한 내용이 적용된 실전 프로젝트를 확인하세요.
