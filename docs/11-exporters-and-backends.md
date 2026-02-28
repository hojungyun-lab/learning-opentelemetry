# 📤 11. Exporters와 백엔드 (Exporters and Backends)

## 학습 목표

수집된 텔레메트리 데이터를 OTLP, Jaeger, Prometheus 등 실제 백엔드로 전송하는 Exporter를 설정하고, Docker로 백엔드를 구동하여 데이터를 시각화합니다.

---

## 핵심 개념

### Exporter의 역할

Exporter는 SDK가 수집한 데이터를 **특정 형식과 프로토콜로 변환하여 외부 시스템으로 전송**합니다. 애플리케이션 코드(계측 부분)를 수정하지 않고 Exporter만 교체하면 다른 백엔드로 데이터를 보낼 수 있습니다.

### OTLP (OpenTelemetry Protocol)

OTLP는 OpenTelemetry의 **표준 전송 프로토콜**입니다. 가능하면 OTLP를 사용하는 것이 권장됩니다.

| 전송 방식 | 기본 포트 | 특징 |
|----------|----------|------|
| OTLP/gRPC | 4317 | 고성능, 바이너리 직렬화 |
| OTLP/HTTP | 4318 | 방화벽/프록시 친화적, JSON/Protobuf |

---

## 실습

### 1단계: Jaeger로 Traces 전송

Jaeger를 Docker로 실행합니다:

```bash
docker run -d --name jaeger \
  -p 16686:16686 \
  -p 4317:4317 \
  -p 4318:4318 \
  jaegertracing/all-in-one:latest
```

- `16686`: Jaeger UI (웹 브라우저)
- `4317`: OTLP gRPC 수신
- `4318`: OTLP HTTP 수신

Jaeger로 데이터를 전송하는 앱을 작성합니다:

```python
# export_jaeger.py
# OTLP Exporter를 통해 Jaeger로 Traces 전송

import time
import random
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

resource = Resource.create({
    "service.name": "jaeger-demo",
    "service.version": "1.0.0",
    "deployment.environment": "development",
})

# OTLP gRPC Exporter → Jaeger
exporter = OTLPSpanExporter(
    endpoint="http://localhost:4317",
    insecure=True,  # TLS 비활성화 (개발용)
)

provider = TracerProvider(resource=resource)
provider.add_span_processor(BatchSpanProcessor(exporter))
trace.set_tracer_provider(provider)

tracer = trace.get_tracer(__name__)


def simulate_request(path: str):
    with tracer.start_as_current_span(
        f"GET {path}",
        kind=trace.SpanKind.SERVER,
    ) as span:
        span.set_attribute("http.request.method", "GET")
        span.set_attribute("url.path", path)

        # DB 조회 시뮬레이션
        with tracer.start_as_current_span("db.query") as db_span:
            db_span.set_attribute("db.system", "postgresql")
            db_span.set_attribute("db.operation.name", "SELECT")
            time.sleep(random.uniform(0.005, 0.05))

        # 캐시 확인 시뮬레이션
        with tracer.start_as_current_span("cache.check") as cache_span:
            cache_hit = random.choice([True, False])
            cache_span.set_attribute("cache.hit", cache_hit)
            if not cache_hit:
                cache_span.add_event("cache.miss")
                time.sleep(0.01)

        status_code = random.choice([200, 200, 200, 404, 500])
        span.set_attribute("http.response.status_code", status_code)

        if status_code >= 500:
            span.set_status(trace.StatusCode.ERROR, "Internal Server Error")


# 여러 요청 시뮬레이션
paths = ["/api/users", "/api/orders", "/api/products", "/api/payments"]
for _ in range(20):
    simulate_request(random.choice(paths))
    time.sleep(0.1)

provider.shutdown()
print("✅ Jaeger로 데이터 전송 완료. http://localhost:16686 에서 확인하세요.")
```

```bash
poetry run python export_jaeger.py
```

브라우저에서 http://localhost:16686 을 열고:
1. Service 드롭다운에서 `jaeger-demo` 선택
2. "Find Traces" 클릭
3. 개별 Trace를 클릭하여 Span 계층 구조 확인

### 2단계: Prometheus로 Metrics 전송

```bash
# Prometheus Exporter 패키지 설치
poetry add opentelemetry-exporter-prometheus prometheus-client
```

Prometheus Exporter는 **Pull 방식**으로 동작합니다. 앱이 `/metrics` 엔드포인트를 노출하면 Prometheus가 주기적으로 데이터를 수집합니다.

```python
# export_prometheus.py
# Prometheus Exporter를 통한 메트릭 노출

import time
import random
from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.resources import Resource
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from prometheus_client import start_http_server

resource = Resource.create({"service.name": "prometheus-demo"})

# PrometheusMetricReader: /metrics 엔드포인트 자동 생성
reader = PrometheusMetricReader()
provider = MeterProvider(resource=resource, metric_readers=[reader])
metrics.set_meter_provider(provider)

meter = metrics.get_meter(__name__)

# 계측기 생성
request_counter = meter.create_counter(
    "http_requests_total",
    description="Total HTTP requests",
)
request_duration = meter.create_histogram(
    "http_request_duration_seconds",
    description="HTTP request duration in seconds",
    unit="s",
)

# Prometheus가 스크랩할 HTTP 서버 시작 (포트 8000)
start_http_server(8000)
print("📊 Prometheus 메트릭 엔드포인트: http://localhost:8000/metrics")
print("메트릭을 생성 중입니다. Ctrl+C로 종료하세요.\n")

try:
    while True:
        method = random.choice(["GET", "POST"])
        route = random.choice(["/api/users", "/api/orders"])
        status = random.choice([200, 200, 200, 404, 500])

        request_counter.add(1, {
            "method": method,
            "route": route,
            "status": str(status),
        })

        duration = random.uniform(0.01, 0.5)
        request_duration.record(duration, {
            "method": method,
            "route": route,
        })

        time.sleep(0.5)

except KeyboardInterrupt:
    pass
```

실행 후 브라우저에서 `http://localhost:8000/metrics`를 열면 Prometheus 형식의 메트릭 데이터를 확인할 수 있습니다.

Prometheus를 Docker로 실행하여 데이터를 수집하도록 설정합니다:

`prometheus.yml` 파일을 생성합니다:

```yaml
# prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'otel-demo'
    static_configs:
      - targets: ['host.docker.internal:8000']
```

```bash
docker run -d --name prometheus \
  -p 9090:9090 \
  -v $(pwd)/prometheus.yml:/etc/prometheus/prometheus.yml \
  prom/prometheus:latest
```

http://localhost:9090 에서 Prometheus UI를 열고 `http_requests_total` 등의 메트릭을 조회할 수 있습니다.

### 3단계: 여러 Exporter 동시 사용

하나의 애플리케이션에서 여러 Exporter를 동시에 사용할 수 있습니다:

```python
# export_multiple.py
# 콘솔 + OTLP Exporter를 동시에 사용

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    SimpleSpanProcessor,
    ConsoleSpanExporter,
)
from opentelemetry.sdk.resources import Resource
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

resource = Resource.create({"service.name": "multi-export-demo"})
provider = TracerProvider(resource=resource)

# Exporter 1: 콘솔 출력 (디버그용)
provider.add_span_processor(
    SimpleSpanProcessor(ConsoleSpanExporter())
)

# Exporter 2: OTLP → Jaeger/Collector
provider.add_span_processor(
    BatchSpanProcessor(OTLPSpanExporter(
        endpoint="http://localhost:4317",
        insecure=True,
    ))
)

# 양쪽 모두에 데이터가 전송됨
trace.set_tracer_provider(provider)
```

---

## Exporter 선택 가이드

| 상황 | 권장 Exporter |
|------|-------------|
| 개발/디버깅 | `ConsoleSpanExporter`, `ConsoleMetricExporter` |
| Collector 사용 시 | `OTLPSpanExporter` (gRPC 또는 HTTP) |
| Jaeger 직접 전송 | `OTLPSpanExporter` (Jaeger가 OTLP 수신 지원) |
| Prometheus 연동 | `PrometheusMetricReader` (Pull 방식) |
| SaaS 벤더 사용 시 | 벤더 제공 Exporter 또는 OTLP (대부분 지원) |

---

## 정리 (Docker 컨테이너)

```bash
docker stop jaeger prometheus
docker rm jaeger prometheus
```

---

## 마무리

이번 단계에서 학습한 것:

- **OTLP Exporter**: gRPC/HTTP를 통해 Collector나 백엔드로 데이터 전송
- **Jaeger 연동**: Docker로 Jaeger 실행, Traces 시각화
- **Prometheus 연동**: Pull 방식의 메트릭 노출 및 수집
- **멀티 Exporter**: 여러 목적지로 동시 전송

**다음 단계**: [12. Collector 설정](12-collector-setup.md)에서 OpenTelemetry Collector를 Docker로 구성하여 중앙 집중식 데이터 처리 파이프라인을 구축합니다.
