# ✋ 10. 수동 계측 (Manual Instrumentation)

## 학습 목표

자동 계측과 병행하여, 비즈니스 로직에 커스텀 Span과 메트릭을 추가하는 실전 패턴을 익힙니다.

---

## 핵심 개념

### 왜 수동 계측이 필요한가?

자동 계측은 프레임워크 레벨의 데이터(HTTP 요청, DB 쿼리 등)를 수집하지만, **비즈니스 로직의 세부 정보**는 수집하지 못합니다.

```
자동 계측이 생성하는 Span:
  GET /api/orders (200, 340ms)

수동 계측을 추가한 결과:
  GET /api/orders (200, 340ms)
  ├── validate-order (15ms)          ← 수동
  │   └── check-inventory (8ms)     ← 수동
  ├── calculate-shipping (25ms)      ← 수동
  └── db.query (30ms)                ← 자동 (SQLAlchemy)
```

수동 계측을 통해 다음을 추가할 수 있습니다:
- 비즈니스 로직의 개별 단계를 Span으로 분리
- 주문 금액, 상품 수 등 비즈니스 속성 기록
- 비즈니스 메트릭 (주문 건수, 결제 금액 분포 등)

---

## 실습

### 1단계: 자동 + 수동 계측 통합

```bash
poetry add flask opentelemetry-instrumentation-flask opentelemetry-sdk
```

`manual_app.py` 파일을 생성합니다:

```python
# manual_app.py
# 자동 계측(Flask) + 수동 계측(비즈니스 로직) 통합

import time
import random
from flask import Flask, jsonify, request

from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import (
    ConsoleMetricExporter,
    PeriodicExportingMetricReader,
)
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.trace import StatusCode

# --- OTel 초기화 ---
resource = Resource.create({
    "service.name": "order-service",
    "service.version": "2.0.0",
})

# Tracing
tracer_provider = TracerProvider(resource=resource)
tracer_provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
trace.set_tracer_provider(tracer_provider)
tracer = trace.get_tracer("order-service.api")

# Metrics
metric_reader = PeriodicExportingMetricReader(
    ConsoleMetricExporter(),
    export_interval_millis=10000,
)
meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
metrics.set_meter_provider(meter_provider)
meter = metrics.get_meter("order-service.api")

# 비즈니스 메트릭 정의
order_counter = meter.create_counter(
    "orders.created.count",
    description="생성된 주문 수",
)
order_amount = meter.create_histogram(
    "orders.amount",
    description="주문 금액 분포",
    unit="KRW",
)
order_processing_time = meter.create_histogram(
    "orders.processing.duration",
    description="주문 처리 시간",
    unit="ms",
)

# --- Flask 앱 ---
app = Flask(__name__)
FlaskInstrumentor().instrument_app(app)  # Flask 자동 계측


@app.route("/orders", methods=["POST"])
def create_order():
    """주문 생성 엔드포인트 — 수동 계측 추가"""
    start = time.time()

    data = request.get_json() or {
        "items": [
            {"id": "ITEM-001", "name": "노트북", "price": 1200000, "qty": 1},
            {"id": "ITEM-002", "name": "마우스", "price": 50000, "qty": 2},
        ],
        "user_id": "user-42",
    }

    # 현재 Span 가져오기 (Flask 자동 계측이 생성한 Span)
    current_span = trace.get_current_span()
    current_span.set_attribute("order.user_id", data["user_id"])
    current_span.set_attribute("order.item_count", len(data["items"]))

    try:
        # 비즈니스 로직: 수동 Span으로 각 단계 추적
        order = validate_order(data)
        total = calculate_total(order)
        process_payment(data["user_id"], total)

        # 비즈니스 메트릭 기록
        order_counter.add(1, {
            "order.status": "success",
            "payment.method": "credit_card",
        })
        order_amount.record(total, {"currency": "KRW"})

        duration_ms = (time.time() - start) * 1000
        order_processing_time.record(duration_ms)

        return jsonify({"order_id": "ORD-001", "total": total, "status": "created"})

    except Exception as e:
        order_counter.add(1, {"order.status": "failed"})
        current_span.set_status(StatusCode.ERROR, str(e))
        current_span.record_exception(e)
        return jsonify({"error": str(e)}), 400


def validate_order(data: dict) -> dict:
    """주문 유효성 검증"""
    with tracer.start_as_current_span("validate-order") as span:
        span.set_attribute("order.user_id", data["user_id"])

        # 재고 확인
        with tracer.start_as_current_span("check-inventory") as inv_span:
            for item in data["items"]:
                inv_span.add_event("inventory.check", {
                    "item.id": item["id"],
                    "item.qty": item["qty"],
                })
            time.sleep(0.01)  # DB 조회 시뮬레이션

        # 사용자 검증
        with tracer.start_as_current_span("verify-user") as user_span:
            user_span.set_attribute("user.id", data["user_id"])
            time.sleep(0.005)

        return data


def calculate_total(order: dict) -> int:
    """주문 총액 계산"""
    with tracer.start_as_current_span("calculate-total") as span:
        total = sum(item["price"] * item["qty"] for item in order["items"])
        span.set_attribute("order.total", total)
        span.set_attribute("order.currency", "KRW")

        # 할인 적용 시뮬레이션
        discount = random.choice([0, 5, 10])
        if discount > 0:
            span.add_event("discount.applied", {"discount.percent": discount})
            total = int(total * (1 - discount / 100))

        return total


def process_payment(user_id: str, amount: int):
    """결제 처리"""
    with tracer.start_as_current_span(
        "process-payment",
        kind=trace.SpanKind.CLIENT,  # 외부 결제 서비스 호출
    ) as span:
        span.set_attribute("payment.user_id", user_id)
        span.set_attribute("payment.amount", amount)
        span.set_attribute("payment.method", "credit_card")
        time.sleep(0.03)  # 결제 API 호출 시뮬레이션
        span.add_event("payment.authorized")


@app.route("/orders", methods=["GET"])
def list_orders():
    """주문 목록 조회"""
    with tracer.start_as_current_span("query-orders") as span:
        span.set_attribute("query.limit", 10)
        time.sleep(0.01)
        orders = [{"id": f"ORD-{i:03d}", "total": random.randint(10000, 500000)} for i in range(1, 4)]

    return jsonify({"orders": orders})


if __name__ == "__main__":
    app.run(port=5000, debug=False)
```

```bash
poetry run python manual_app.py

# 다른 터미널에서:
curl -X POST http://localhost:5000/orders \
  -H "Content-Type: application/json" \
  -d '{"items": [{"id":"A1","name":"키보드","price":80000,"qty":1}], "user_id":"user-1"}'

curl http://localhost:5000/orders
```

### 2단계: 재사용 가능한 텔레메트리 모듈

실전에서는 OTel 초기화를 별도 모듈로 분리합니다:

```python
# telemetry.py
# 재사용 가능한 OTel 초기화 모듈

from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter


def setup_telemetry(
    service_name: str,
    service_version: str = "0.0.0",
    otlp_endpoint: str = "http://localhost:4317",
) -> tuple[TracerProvider, MeterProvider]:
    """OTel TracerProvider와 MeterProvider를 초기화하고 반환"""

    resource = Resource.create({
        "service.name": service_name,
        "service.version": service_version,
    })

    # Tracing
    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(
            endpoint=otlp_endpoint,
            insecure=True,
        ))
    )
    trace.set_tracer_provider(tracer_provider)

    # Metrics
    metric_reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(
            endpoint=otlp_endpoint,
            insecure=True,
        ),
        export_interval_millis=15000,
    )
    meter_provider = MeterProvider(
        resource=resource,
        metric_readers=[metric_reader],
    )
    metrics.set_meter_provider(meter_provider)

    return tracer_provider, meter_provider


def get_tracer(module_name: str) -> trace.Tracer:
    """모듈별 Tracer 반환"""
    return trace.get_tracer(module_name)


def get_meter(module_name: str) -> metrics.Meter:
    """모듈별 Meter 반환"""
    return metrics.get_meter(module_name)
```

사용 예시:

```python
# main.py
from telemetry import setup_telemetry, get_tracer, get_meter

# 앱 시작 시 한 번 호출
tracer_provider, meter_provider = setup_telemetry(
    service_name="my-service",
    service_version="1.2.0",
)

# 각 모듈에서
tracer = get_tracer(__name__)
meter = get_meter(__name__)
```

### 3단계: 계측 설계 지침

```python
# --- 어떤 것을 Span으로 만들어야 하는가? ---

# ✅ Span으로 만들 가치가 있는 것:
# - 외부 서비스 호출 (API, DB, 메시지 큐)
# - 비즈니스 로직의 주요 단계 (주문 검증, 결제 처리)
# - 시간이 걸리는 연산 (데이터 변환, 파일 처리)
# - 조건 분기가 있는 로직 (캐시 히트/미스)

# ❌ Span으로 만들 필요가 없는 것:
# - 단순한 getter/setter
# - 인메모리 연산 (< 1ms)
# - 너무 자주 호출되는 유틸리티 함수

# --- 어떤 것을 Metric으로 만들어야 하는가? ---

# ✅ Counter: 발생 횟수가 중요한 것
order_created = meter.create_counter("orders.created")
login_failed = meter.create_counter("auth.login.failed")

# ✅ Histogram: 분포가 중요한 것
response_time = meter.create_histogram("http.response.duration", unit="ms")
batch_size = meter.create_histogram("batch.size")

# ✅ UpDownCounter: 현재 값의 변화가 중요한 것
active_sessions = meter.create_up_down_counter("sessions.active")
```

---

## 마무리

이번 단계에서 학습한 것:

- 자동 계측(프레임워크 수준)과 수동 계측(비즈니스 로직 수준)의 통합
- 비즈니스 메트릭(주문 수, 금액 분포 등) 정의 및 기록
- 재사용 가능한 `telemetry.py` 초기화 모듈 패턴
- Span과 Metric의 계측 범위 설계 지침

**다음 단계**: [11. Exporters와 백엔드](11-exporters-and-backends.md)에서 수집된 데이터를 Jaeger, Prometheus 등 실제 백엔드로 전송하는 방법을 학습합니다.
