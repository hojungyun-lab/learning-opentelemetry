# 🔍 04. Spans 심화 (Spans In-Depth)

## 학습 목표

Span의 속성(Attributes), 이벤트(Events), 상태(Status), SpanKind를 활용하여 풍부한 계측 데이터를 기록하는 방법을 익힙니다.

---

## 핵심 개념

### Span을 풍부하게 만드는 요소

Span은 단순히 "시작과 끝"만 기록하는 것이 아닙니다. 다음 요소를 추가하면 문제 분석 시 필요한 맥락을 빠르게 파악할 수 있습니다.

| 요소 | 용도 | 예시 |
|------|------|------|
| Attributes | 키-값 메타데이터 | `http.method=GET`, `db.system=postgresql` |
| Events | Span 내에서 발생한 시점별 이벤트 | `"cache.miss"`, `"retry.attempt"` |
| Status | 작업의 성공/실패 상태 | `OK`, `ERROR` |
| SpanKind | Span의 역할 유형 | `SERVER`, `CLIENT`, `INTERNAL` |
| Exception | 예외 정보 기록 | 스택 트레이스, 에러 메시지 |

---

## 실습

### 1단계: Attributes (속성)

`span_attributes.py` 파일을 생성합니다:

```python
# span_attributes.py
# Span에 속성을 추가하여 맥락 정보를 기록

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor
from opentelemetry.sdk.resources import Resource

resource = Resource.create({"service.name": "span-attributes-demo"})
provider = TracerProvider(resource=resource)
provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
trace.set_tracer_provider(provider)

tracer = trace.get_tracer(__name__)


def handle_request(method: str, path: str, user_id: str):
    with tracer.start_as_current_span("handle-http-request") as span:
        # 문자열 속성
        span.set_attribute("http.request.method", method)
        span.set_attribute("url.path", path)
        span.set_attribute("user.id", user_id)

        # 정수 속성
        span.set_attribute("http.response.status_code", 200)

        # 불리언 속성
        span.set_attribute("http.response.from_cache", False)

        # 리스트 속성 (동일 타입의 요소만 가능)
        span.set_attribute("http.response.header.content_type", ["application/json"])

        # 비즈니스 로직
        result = {"items": [1, 2, 3]}

        # 응답 관련 속성
        span.set_attribute("response.item_count", len(result["items"]))

        return result


# 생성 시점에 속성을 전달할 수도 있음
with tracer.start_as_current_span(
    "batch-operation",
    attributes={"batch.size": 100, "batch.type": "daily"},
) as span:
    span.set_attribute("batch.processed", 98)
    span.set_attribute("batch.failed", 2)


handle_request("GET", "/api/items", "user-42")
provider.shutdown()
```

**속성 값으로 허용되는 타입**:
- `str`, `bool`, `int`, `float`
- 위 타입의 동일 타입 리스트: `list[str]`, `list[int]` 등

### 2단계: Events (이벤트)

이벤트는 Span의 수명 동안 특정 시점에 발생한 사건을 기록합니다. 속성과 달리 **타임스탬프**가 함께 기록됩니다.

`span_events.py` 파일을 생성합니다:

```python
# span_events.py
# Span 내에서 시점별 이벤트를 기록

import time
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor
from opentelemetry.sdk.resources import Resource

resource = Resource.create({"service.name": "span-events-demo"})
provider = TracerProvider(resource=resource)
provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
trace.set_tracer_provider(provider)

tracer = trace.get_tracer(__name__)


def process_order(order_id: str, items: list[str]):
    with tracer.start_as_current_span("process-order") as span:
        span.set_attribute("order.id", order_id)

        # 이벤트 1: 주문 검증 시작
        span.add_event("order.validation.started", {
            "order.item_count": len(items),
        })
        time.sleep(0.02)  # 검증 시뮬레이션

        # 이벤트 2: 검증 완료
        span.add_event("order.validation.completed", {
            "validation.result": "passed",
        })

        # 이벤트 3: 결제 처리
        span.add_event("payment.processing", {
            "payment.method": "credit_card",
            "payment.amount": 15000,
        })
        time.sleep(0.03)

        # 이벤트 4: 주문 확정
        span.add_event("order.confirmed", {
            "order.estimated_delivery": "2024-03-20",
        })


process_order("ORD-001", ["item-a", "item-b", "item-c"])
provider.shutdown()
```

출력에서 각 이벤트에 타임스탬프가 기록되어 있는 것을 확인합니다. 이벤트 간 시간 차이를 통해 각 단계의 소요 시간을 파악할 수 있습니다.

### 3단계: Status와 Exception

```python
# span_status.py
# Span의 상태 코드와 예외 기록

from opentelemetry import trace
from opentelemetry.trace import StatusCode
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor
from opentelemetry.sdk.resources import Resource

resource = Resource.create({"service.name": "span-status-demo"})
provider = TracerProvider(resource=resource)
provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
trace.set_tracer_provider(provider)

tracer = trace.get_tracer(__name__)


# --- StatusCode 종류 ---
# UNSET: 기본값. 에러가 아님을 의미하지만 명시적 성공도 아님
# OK:    명시적으로 성공을 표시 (일반적으로 설정하지 않아도 됨)
# ERROR: 에러 발생을 표시


def successful_operation():
    """성공적인 작업"""
    with tracer.start_as_current_span("successful-op") as span:
        result = 42
        # OK를 명시적으로 설정 (선택 사항)
        span.set_status(StatusCode.OK, "처리 완료")
        return result


def failed_operation():
    """실패하는 작업 — 예외 기록 포함"""
    with tracer.start_as_current_span("failed-op") as span:
        try:
            # 의도적으로 에러 발생
            result = 1 / 0
        except ZeroDivisionError as e:
            # 1. 상태를 ERROR로 설정
            span.set_status(StatusCode.ERROR, str(e))

            # 2. 예외 정보를 이벤트로 기록 (스택 트레이스 포함)
            span.record_exception(e)

            # 3. 필요 시 추가 속성
            span.set_attribute("error.type", type(e).__name__)

            # 예외를 상위로 전파할지 여부는 비즈니스 로직에 따라 결정
            # raise  # 전파하려면 주석 해제


def partial_failure():
    """부분 실패 — 일부 아이템만 처리 실패"""
    with tracer.start_as_current_span("batch-process") as span:
        items = ["a", "b", "c", "d", "e"]
        failed_items = []

        for item in items:
            try:
                if item == "c":
                    raise ValueError(f"'{item}' 처리 불가")
                # 정상 처리
            except ValueError as e:
                failed_items.append(item)
                # 개별 실패를 이벤트로 기록
                span.add_event("item.processing_failed", {
                    "item.id": item,
                    "error.message": str(e),
                })

        if failed_items:
            span.set_status(
                StatusCode.ERROR,
                f"{len(failed_items)}개 아이템 처리 실패",
            )
            span.set_attribute("batch.failed_items", failed_items)
        else:
            span.set_status(StatusCode.OK)

        span.set_attribute("batch.total", len(items))
        span.set_attribute("batch.success", len(items) - len(failed_items))


successful_operation()
failed_operation()
partial_failure()
provider.shutdown()
```

### 4단계: SpanKind

SpanKind는 Span이 분산 시스템에서 어떤 역할을 하는지 나타냅니다. 시각화 도구(Jaeger 등)가 Span 간 관계를 정확히 표시하는 데 사용됩니다.

```python
# span_kind.py
# SpanKind를 사용한 역할 구분

import time
from opentelemetry import trace
from opentelemetry.trace import SpanKind
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor
from opentelemetry.sdk.resources import Resource

resource = Resource.create({"service.name": "span-kind-demo"})
provider = TracerProvider(resource=resource)
provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
trace.set_tracer_provider(provider)

tracer = trace.get_tracer(__name__)


def simulate_http_server():
    """HTTP 서버 측 핸들러"""
    # SERVER: 외부로부터 요청을 수신하여 처리
    with tracer.start_as_current_span(
        "GET /api/orders",
        kind=SpanKind.SERVER,
        attributes={
            "http.request.method": "GET",
            "url.path": "/api/orders",
        },
    ) as span:
        # 내부 처리 로직
        orders = fetch_from_database()

        # 외부 서비스 호출
        payment_status = call_payment_service()

        span.set_attribute("http.response.status_code", 200)
        return orders


def fetch_from_database():
    """내부 DB 조회"""
    # INTERNAL: 프로세스 내부의 작업 (기본값)
    with tracer.start_as_current_span(
        "db.query",
        kind=SpanKind.INTERNAL,
    ) as span:
        span.set_attribute("db.system", "postgresql")
        span.set_attribute("db.operation.name", "SELECT")
        time.sleep(0.01)
        return [{"id": 1, "total": 10000}]


def call_payment_service():
    """외부 결제 서비스 호출"""
    # CLIENT: 외부 서비스로 요청을 전송
    with tracer.start_as_current_span(
        "POST payment-service/verify",
        kind=SpanKind.CLIENT,
        attributes={
            "http.request.method": "POST",
            "server.address": "payment-service",
            "server.port": 8080,
        },
    ) as span:
        time.sleep(0.02)
        span.set_attribute("http.response.status_code", 200)
        return "verified"


simulate_http_server()
provider.shutdown()
```

**SpanKind 요약:**

| SpanKind | 설명 | 사용 시점 |
|----------|------|----------|
| `INTERNAL` | 프로세스 내부 작업 (기본값) | 내부 함수 호출, 비즈니스 로직 |
| `SERVER` | 외부 요청을 수신하여 처리 | HTTP 서버 핸들러, gRPC 서버 |
| `CLIENT` | 외부 서비스로 요청 전송 | HTTP 클라이언트, DB 클라이언트 |
| `PRODUCER` | 메시지를 큐에 발행 | Kafka Producer, RabbitMQ Publisher |
| `CONSUMER` | 메시지를 큐에서 소비 | Kafka Consumer, RabbitMQ Subscriber |

---

## 실전 패턴: 함수 데코레이터로 계측 간소화

반복되는 Span 생성 코드를 데코레이터로 추출하는 패턴입니다:

```python
# decorators.py
import functools
from opentelemetry import trace

tracer = trace.get_tracer(__name__)


def traced(span_name: str = None, attributes: dict = None):
    """함수를 자동으로 Span으로 감싸는 데코레이터"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            name = span_name or func.__qualname__
            with tracer.start_as_current_span(name) as span:
                if attributes:
                    for key, value in attributes.items():
                        span.set_attribute(key, value)
                try:
                    result = func(*args, **kwargs)
                    return result
                except Exception as e:
                    span.set_status(trace.StatusCode.ERROR, str(e))
                    span.record_exception(e)
                    raise
        return wrapper
    return decorator


# 사용 예시
@traced("validate-user-input")
def validate_input(data: dict):
    if "email" not in data:
        raise ValueError("이메일 필수")
    return True


@traced(attributes={"component": "repository"})
def find_user_by_id(user_id: str):
    # 함수명(find_user_by_id)이 Span 이름으로 사용됨
    return {"id": user_id, "name": "Alice"}
```

---

## 마무리

이번 단계에서 학습한 것:

- **Attributes**: 키-값 메타데이터로 Span에 맥락 추가
- **Events**: 타임스탬프와 함께 Span 내 시점별 사건 기록
- **Status/Exception**: 에러 상태 표시 및 예외 정보 기록
- **SpanKind**: 분산 시스템에서의 역할 구분 (`SERVER`, `CLIENT`, `PRODUCER`, `CONSUMER`)
- **데코레이터 패턴**: 반복적인 계측 코드를 간소화

**다음 단계**: [05. Context Propagation](05-context-propagation.md)에서 서비스 간에 어떻게 Trace를 연결하는지, Context가 무엇이고 어떻게 전파되는지를 살펴봅니다.
