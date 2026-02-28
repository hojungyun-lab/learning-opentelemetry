# 📈 07. Metrics 심화 (Metrics Advanced)

## 학습 목표

비동기(Observable) 계측기를 사용하여 시스템 상태를 주기적으로 수집하고, Views를 활용하여 메트릭의 집계 방식과 속성을 커스터마이징합니다.

---

## 핵심 개념

### 비동기 계측기 (Observable Instruments)

동기 계측기가 "코드 흐름 속에서 값을 기록"하는 방식이라면, 비동기 계측기는 **SDK가 주기적으로 콜백 함수를 호출**하여 현재 값을 수집하는 방식입니다.

| 비동기 계측기 | 용도 | 콜백 반환값 |
|--------------|------|------------|
| Observable Gauge | 측정 시점의 현재 값 | 현재 CPU 사용률, 온도 |
| Observable Counter | 누적되는 외부 카운터 | 시스템에서 집계된 전송 바이트 |
| Observable UpDownCounter | 증감하는 외부 값 | 프로세스 메모리, 스레드 수 |

**사용 시점**: 값이 외부 시스템(OS, 라이브러리 등)에 의해 관리되고, 필요 시 현재 값을 조회할 수 있을 때 사용합니다.

### Views

Views는 SDK 수준에서 메트릭의 **집계 방식, 포함할 속성, 이름** 등을 변경할 수 있는 도구입니다. 계측 코드를 수정하지 않고도 메트릭의 동작을 조정할 수 있습니다.

---

## 실습

### 1단계: Observable Gauge (시스템 모니터링)

```bash
# psutil 설치 (시스템 정보 조회)
poetry add psutil
```

`metrics_observable.py` 파일을 생성합니다:

```python
# metrics_observable.py
# Observable 계측기를 사용한 시스템 리소스 모니터링

import time
import psutil
from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import (
    ConsoleMetricExporter,
    PeriodicExportingMetricReader,
)
from opentelemetry.sdk.resources import Resource

resource = Resource.create({"service.name": "observable-demo"})
reader = PeriodicExportingMetricReader(
    ConsoleMetricExporter(),
    export_interval_millis=5000,
)
provider = MeterProvider(resource=resource, metric_readers=[reader])
metrics.set_meter_provider(provider)

meter = metrics.get_meter(__name__)


# --- Observable Gauge: 현재 값을 콜백으로 조회 ---

def cpu_usage_callback(options):
    """CPU 사용률을 반환하는 콜백"""
    # SDK가 주기적으로 이 함수를 호출
    # Observation(값, 속성) 형태로 반환
    usage = psutil.cpu_percent(interval=None)
    yield metrics.Observation(usage, {"cpu": "total"})

    # CPU 코어별 사용률도 반환 가능
    per_cpu = psutil.cpu_percent(interval=None, percpu=True)
    for i, cpu_pct in enumerate(per_cpu):
        yield metrics.Observation(cpu_pct, {"cpu": f"core-{i}"})


def memory_usage_callback(options):
    """메모리 사용률을 반환하는 콜백"""
    mem = psutil.virtual_memory()
    yield metrics.Observation(mem.percent, {"type": "used_percent"})
    yield metrics.Observation(mem.available / (1024 ** 3), {"type": "available_gb"})


meter.create_observable_gauge(
    name="system.cpu.utilization",
    callbacks=[cpu_usage_callback],
    description="CPU 사용률",
    unit="%",
)

meter.create_observable_gauge(
    name="system.memory.utilization",
    callbacks=[memory_usage_callback],
    description="메모리 사용 상태",
)


# --- Observable Counter: 누적값을 콜백으로 조회 ---

def network_bytes_callback(options):
    """네트워크 입출력 누적 바이트를 반환"""
    net = psutil.net_io_counters()
    yield metrics.Observation(net.bytes_sent, {"direction": "sent"})
    yield metrics.Observation(net.bytes_recv, {"direction": "received"})


meter.create_observable_counter(
    name="system.network.io",
    callbacks=[network_bytes_callback],
    description="네트워크 입출력 누적 바이트",
    unit="By",
)


# --- Observable UpDownCounter: 증감하는 외부 값 ---

def thread_count_callback(options):
    """현재 프로세스의 스레드 수를 반환"""
    import threading
    yield metrics.Observation(threading.active_count(), {})


meter.create_observable_up_down_counter(
    name="process.thread.count",
    callbacks=[thread_count_callback],
    description="현재 활성 스레드 수",
    unit="1",
)


print("5초마다 시스템 메트릭이 수집됩니다. Ctrl+C로 종료하세요.\n")
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    provider.shutdown()
```

```bash
poetry run python metrics_observable.py
```

### 2단계: Views를 사용한 메트릭 커스터마이징

```python
# metrics_views.py
# Views를 사용한 메트릭 집계 방식 변경

import time
import random
from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import (
    ConsoleMetricExporter,
    PeriodicExportingMetricReader,
)
from opentelemetry.sdk.metrics.view import View
from opentelemetry.sdk.metrics.aggregation import (
    ExplicitBucketHistogramAggregation,
    DropAggregation,
)
from opentelemetry.sdk.resources import Resource

resource = Resource.create({"service.name": "views-demo"})

# --- View 정의 ---

# View 1: Histogram의 버킷 경계 변경
# 기본 버킷(0,5,10,25,...,10000)을 애플리케이션에 맞게 조정
latency_view = View(
    instrument_name="http.server.request.duration",
    aggregation=ExplicitBucketHistogramAggregation(
        boundaries=[10, 25, 50, 100, 250, 500, 1000, 2500, 5000],
    ),
)

# View 2: 특정 속성만 유지 (카디널리티 제어)
# → http.route만 남기고 나머지 속성(method, status 등) 제거
# → 속성 조합이 줄어들어 백엔드 부하 감소
route_only_view = View(
    instrument_name="http.server.request.count",
    attribute_keys={"http.route"},  # 이 속성만 유지
)

# View 3: 특정 메트릭 완전히 비활성화
# → 개발용 메트릭을 운영에서 제거할 때 유용
drop_debug_view = View(
    instrument_name="debug.*",      # 와일드카드 패턴
    aggregation=DropAggregation(),   # 데이터 수집하지 않음
)

# View 4: 메트릭 이름 변경
rename_view = View(
    instrument_name="app.request.count",
    name="http.requests.total",  # Prometheus 네이밍 컨벤션에 맞게 변경
)

# --- MeterProvider에 Views 적용 ---
reader = PeriodicExportingMetricReader(
    ConsoleMetricExporter(),
    export_interval_millis=5000,
)

provider = MeterProvider(
    resource=resource,
    metric_readers=[reader],
    views=[latency_view, route_only_view, drop_debug_view, rename_view],
)
metrics.set_meter_provider(provider)

meter = metrics.get_meter(__name__)

# 계측기 생성
request_counter = meter.create_counter("http.server.request.count")
request_duration = meter.create_histogram(
    "http.server.request.duration", unit="ms",
)
debug_counter = meter.create_counter("debug.verbose.metric")
app_counter = meter.create_counter("app.request.count")

print("5초마다 메트릭이 출력됩니다. Ctrl+C로 종료하세요.\n")

try:
    for i in range(20):
        route = random.choice(["/api/users", "/api/orders"])
        method = random.choice(["GET", "POST"])

        # request_counter: route_only_view가 적용되어 http.route만 기록됨
        request_counter.add(1, {
            "http.request.method": method,
            "http.route": route,
            "http.response.status_code": 200,
        })

        # request_duration: latency_view의 커스텀 버킷이 적용됨
        request_duration.record(random.uniform(5, 3000), {
            "http.route": route,
        })

        # debug_counter: drop_debug_view에 의해 수집되지 않음
        debug_counter.add(1)

        # app_counter: rename_view에 의해 "http.requests.total"로 출력됨
        app_counter.add(1, {"http.route": route})

        time.sleep(0.5)

except KeyboardInterrupt:
    pass
finally:
    provider.shutdown()
```

### 3단계: Exemplars (Trace-Metric 연결)

Exemplars는 메트릭 데이터 포인트에 **해당 시점의 Trace ID를 연결**하는 기능입니다. "이 메트릭 급등이 발생한 시점의 구체적인 요청을 추적"할 수 있게 합니다.

```python
# metrics_exemplars.py
# Metrics와 Traces를 Exemplars로 연결

import time
import random
from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import (
    ConsoleMetricExporter,
    PeriodicExportingMetricReader,
)
from opentelemetry.sdk.resources import Resource

resource = Resource.create({"service.name": "exemplars-demo"})

# Tracing 설정
tracer_provider = TracerProvider(resource=resource)
tracer_provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
trace.set_tracer_provider(tracer_provider)
tracer = trace.get_tracer(__name__)

# Metrics 설정
reader = PeriodicExportingMetricReader(
    ConsoleMetricExporter(),
    export_interval_millis=5000,
)
meter_provider = MeterProvider(resource=resource, metric_readers=[reader])
metrics.set_meter_provider(meter_provider)
meter = metrics.get_meter(__name__)

request_duration = meter.create_histogram(
    "http.server.request.duration",
    unit="ms",
)

# Trace 안에서 Metric을 기록하면 Exemplar가 자동으로 연결됨
for i in range(10):
    with tracer.start_as_current_span(f"request-{i}") as span:
        duration = random.uniform(10, 1000)
        # 현재 Span의 Context가 활성화되어 있으므로
        # 이 메트릭 기록에 해당 Trace/Span ID가 Exemplar로 자동 첨부됨
        request_duration.record(duration, {"http.route": "/api/data"})
    time.sleep(0.3)

tracer_provider.shutdown()
meter_provider.shutdown()
```

---

## Metrics 속성(Labels) 설계 지침

### 카디널리티 주의

속성 값의 고유한 조합 수를 **카디널리티(Cardinality)**라고 합니다. 카디널리티가 높으면 메모리 사용량과 백엔드 저장 비용이 급증합니다.

```python
# ❌ 높은 카디널리티 — 사용자 ID를 속성에 넣으면 수백만 개의 시계열 생성
counter.add(1, {"user.id": "user-12345"})

# ✅ 낮은 카디널리티 — 제한된 값의 속성만 사용
counter.add(1, {"http.method": "GET", "http.route": "/api/users"})
```

### 속성 설계 원칙

1. **속성 값은 유한한 집합**이어야 합니다 (예: HTTP 메서드, 상태 코드, 라우트)
2. **고유 ID**(사용자 ID, 요청 ID 등)는 속성에 넣지 않습니다 → Traces에서 추적
3. **Views의 `attribute_keys`**를 사용하여 필요한 속성만 유지합니다

---

## 마무리

이번 단계에서 학습한 것:

- **Observable 계측기**: 콜백 기반으로 시스템 상태를 주기적으로 수집
- **Views**: 버킷 경계 변경, 속성 필터링, 메트릭 비활성화, 이름 변경
- **Exemplars**: Metric과 Trace 간의 연결
- **카디널리티 관리**: 속성 설계 시 성능 고려사항

**다음 단계**: [08. Logs 연동](08-logs-integration.md)에서 Python의 표준 logging 모듈과 OpenTelemetry Logs Bridge를 연동하는 방법을 학습합니다.
