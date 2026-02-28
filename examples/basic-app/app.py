# app.py
# OpenTelemetry 기초 데모 — Flask REST API + Traces + Metrics
#
# 이 앱은 다음을 시연합니다:
# 1. TracerProvider와 MeterProvider 초기화
# 2. Flask 자동 계측 (HTTP 요청 Span 자동 생성)
# 3. 수동 Span 생성 (비즈니스 로직 추적)
# 4. Counter와 Histogram 메트릭

import os
import time
import random
from flask import Flask, jsonify, request

from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
)
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import (
    ConsoleMetricExporter,
    PeriodicExportingMetricReader,
)
from opentelemetry.sdk.resources import Resource
from opentelemetry.trace import StatusCode
from opentelemetry.instrumentation.flask import FlaskInstrumentor


# ============================================================
# 1. OTel 초기화
# ============================================================

resource = Resource.create({
    "service.name": "basic-demo-app",
    "service.version": "1.0.0",
    "deployment.environment": "development",
})

# --- Tracing ---
tracer_provider = TracerProvider(resource=resource)

# 환경 변수 OTEL_EXPORTER_ENDPOINT가 있으면 OTLP, 없으면 Console
otlp_endpoint = os.environ.get("OTEL_EXPORTER_ENDPOINT")
if otlp_endpoint:
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
        OTLPSpanExporter,
    )
    span_exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
    print(f"📡 Traces → OTLP ({otlp_endpoint})")
else:
    span_exporter = ConsoleSpanExporter()
    print("📡 Traces → Console")

tracer_provider.add_span_processor(BatchSpanProcessor(span_exporter))
trace.set_tracer_provider(tracer_provider)
tracer = trace.get_tracer("basic-app")

# --- Metrics ---
metric_reader = PeriodicExportingMetricReader(
    ConsoleMetricExporter(),
    export_interval_millis=10000,  # 10초마다 출력
)
meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
metrics.set_meter_provider(meter_provider)
meter = metrics.get_meter("basic-app")

# 비즈니스 메트릭 정의
item_counter = meter.create_counter(
    "app.items.created",
    description="생성된 아이템 수",
    unit="1",
)
request_duration = meter.create_histogram(
    "app.request.duration",
    description="비즈니스 로직 처리 시간",
    unit="ms",
)


# ============================================================
# 2. Flask 앱
# ============================================================

app = Flask(__name__)

# Flask 자동 계측: 모든 요청에 대해 SERVER Span이 자동 생성됨
FlaskInstrumentor().instrument_app(app)

# 인메모리 데이터 저장소
items_db: dict[int, dict] = {
    1: {"id": 1, "name": "키보드", "price": 85000},
    2: {"id": 2, "name": "마우스", "price": 45000},
    3: {"id": 3, "name": "모니터", "price": 350000},
}
next_id = 4


@app.route("/items", methods=["GET"])
def list_items():
    """아이템 목록 조회"""
    # Flask 자동 계측이 이미 SERVER Span을 생성하고 있으므로
    # 비즈니스 로직에 대한 수동 Span만 추가
    with tracer.start_as_current_span("query-items") as span:
        span.set_attribute("items.count", len(items_db))
        # 약간의 지연 시뮬레이션 (DB 조회)
        time.sleep(random.uniform(0.005, 0.02))
        return jsonify({"items": list(items_db.values())})


@app.route("/items/<int:item_id>", methods=["GET"])
def get_item(item_id: int):
    """개별 아이템 조회"""
    with tracer.start_as_current_span("get-item") as span:
        span.set_attribute("item.id", item_id)

        item = items_db.get(item_id)
        if not item:
            span.set_status(StatusCode.ERROR, f"아이템 {item_id} 없음")
            span.set_attribute("http.response.status_code", 404)
            return jsonify({"error": f"아이템 {item_id}을(를) 찾을 수 없습니다"}), 404

        return jsonify(item)


@app.route("/items", methods=["POST"])
def create_item():
    """아이템 생성"""
    global next_id
    start_time = time.time()

    data = request.get_json()
    if not data or "name" not in data or "price" not in data:
        return jsonify({"error": "name과 price가 필요합니다"}), 400

    with tracer.start_as_current_span("create-item") as span:
        # 입력 검증
        with tracer.start_as_current_span("validate-input") as val_span:
            val_span.set_attribute("input.name", data["name"])
            val_span.set_attribute("input.price", data["price"])

            if data["price"] <= 0:
                val_span.set_status(StatusCode.ERROR, "가격은 0보다 커야 합니다")
                return jsonify({"error": "가격은 0보다 커야 합니다"}), 400

            val_span.add_event("validation.passed")

        # 아이템 저장
        with tracer.start_as_current_span("save-item") as save_span:
            item = {"id": next_id, "name": data["name"], "price": data["price"]}
            items_db[next_id] = item
            save_span.set_attribute("item.id", next_id)
            save_span.add_event("item.saved", {"item.id": next_id})
            next_id += 1
            time.sleep(random.uniform(0.005, 0.015))  # DB 쓰기 시뮬레이션

        span.set_attribute("item.id", item["id"])
        span.set_attribute("item.name", item["name"])

    # 메트릭 기록
    item_counter.add(1, {"item.category": "general"})
    duration_ms = (time.time() - start_time) * 1000
    request_duration.record(duration_ms, {"operation": "create_item"})

    return jsonify(item), 201


@app.route("/items/<int:item_id>", methods=["DELETE"])
def delete_item(item_id: int):
    """아이템 삭제"""
    with tracer.start_as_current_span("delete-item") as span:
        span.set_attribute("item.id", item_id)

        if item_id not in items_db:
            span.set_status(StatusCode.ERROR, f"아이템 {item_id} 없음")
            return jsonify({"error": f"아이템 {item_id}을(를) 찾을 수 없습니다"}), 404

        deleted = items_db.pop(item_id)
        span.add_event("item.deleted", {"item.name": deleted["name"]})
        return jsonify({"message": f"아이템 '{deleted['name']}'이(가) 삭제되었습니다"})


@app.route("/health")
def health():
    """헬스 체크 (보통 트레이싱에서 제외)"""
    return jsonify({"status": "healthy"})


# ============================================================
# 3. 실행
# ============================================================

if __name__ == "__main__":
    print("\n🚀 Basic Demo App 시작")
    print("   GET  http://localhost:5050/items")
    print("   GET  http://localhost:5050/items/<id>")
    print("   POST http://localhost:5050/items")
    print("   DEL  http://localhost:5050/items/<id>")
    print()

    try:
        app.run(host="0.0.0.0", port=5000, debug=False)
    finally:
        tracer_provider.shutdown()
        meter_provider.shutdown()
