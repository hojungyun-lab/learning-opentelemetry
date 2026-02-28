# 📊 06. Metrics 기초 (Metrics Basics)

## 학습 목표

MeterProvider를 설정하고, 동기 계측기(Counter, Histogram)를 사용하여 기본적인 메트릭 데이터를 수집하는 방법을 익힙니다.

---

## 핵심 개념

### Metrics란?

Metrics(메트릭)는 **시간에 따른 수치 데이터**를 수집하는 신호입니다. Traces가 개별 요청의 흐름을 추적하는 반면, Metrics는 시스템의 전반적인 상태와 추세를 파악하는 데 집중합니다.

- "초당 몇 건의 요청이 처리되는가?" → **Counter**
- "요청 응답 시간의 분포는 어떠한가?" → **Histogram**
- "현재 활성 연결 수는 몇 개인가?" → **UpDownCounter / Gauge**

### MeterProvider → Meter → Instrument

Traces의 TracerProvider → Tracer → Span 구조와 동일한 패턴입니다:

```
MeterProvider (전역 설정: Resource, MetricReader, Views)
    │
    └── get_meter("my-module") → Meter 인스턴스
            ├── create_counter("request.count")     → Counter
            ├── create_histogram("request.duration") → Histogram
            └── create_up_down_counter("active.conn") → UpDownCounter
```

### 계측기(Instrument)의 종류

| 계측기 | 동기/비동기 | 단조성 | 사용 예시 |
|--------|-----------|--------|----------|
| Counter | 동기 | 단조 증가 | 요청 수, 에러 수, 전송 바이트 |
| UpDownCounter | 동기 | 증감 가능 | 활성 연결 수, 큐 길이 |
| Histogram | 동기 | 해당 없음 | 응답 시간, 페이로드 크기 |
| Observable Counter | 비동기 | 단조 증가 | 시스템 누적 값 (CPU 시간 등) |
| Observable UpDownCounter | 비동기 | 증감 가능 | 프로세스 메모리 사용량 |
| Observable Gauge | 비동기 | 해당 없음 | 현재 CPU 사용률, 온도 |

**동기 vs. 비동기**:
- **동기 계측기**: 코드 내에서 직접 값을 기록 (`counter.add(1)`)
- **비동기 계측기(Observable)**: 콜백 함수를 등록하면 SDK가 주기적으로 호출하여 값을 수집

이번 문서에서는 동기 계측기(Counter, Histogram, UpDownCounter)를 다루고, 비동기 계측기는 [07. Metrics 심화](07-metrics-advanced.md)에서 다룹니다.

### MetricReader와 내보내기 주기

Traces에서는 SpanProcessor가 Span을 Exporter로 전달했지만, Metrics에서는 **MetricReader**가 이 역할을 합니다.

```python
# PeriodicExportingMetricReader: 일정 간격으로 메트릭 데이터를 수집하여 Exporter로 전달
reader = PeriodicExportingMetricReader(
    exporter,
    export_interval_millis=10000,  # 10초마다 수집 및 내보내기
)
```

---

## 실습

### 1단계: MeterProvider 설정과 Counter

`metrics_counter.py` 파일을 생성합니다:

```python
# metrics_counter.py
# Counter를 사용한 요청 수 집계

import time
import random
from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import (
    ConsoleMetricExporter,
    PeriodicExportingMetricReader,
)
from opentelemetry.sdk.resources import Resource

# 1. Resource 설정
resource = Resource.create({
    "service.name": "metrics-counter-demo",
})

# 2. MetricReader 생성
#    ConsoleMetricExporter: 콘솔에 메트릭 출력
#    export_interval_millis: 5초마다 수집 및 출력
reader = PeriodicExportingMetricReader(
    ConsoleMetricExporter(),
    export_interval_millis=5000,
)

# 3. MeterProvider 생성 및 글로벌 등록
provider = MeterProvider(resource=resource, metric_readers=[reader])
metrics.set_meter_provider(provider)

# 4. Meter 취득
meter = metrics.get_meter(__name__)

# 5. Counter 생성
#    name: 메트릭 식별자 (네임스페이스.대상.측정 형식 권장)
#    unit: 측정 단위 ("1"은 횟수를 의미)
request_counter = meter.create_counter(
    name="http.server.request.count",
    description="수신된 HTTP 요청 수",
    unit="1",
)

error_counter = meter.create_counter(
    name="http.server.error.count",
    description="HTTP 에러 응답 수",
    unit="1",
)

# 6. Counter 사용: .add()로 값 증가
#    두 번째 인자는 속성(labels) — 메트릭을 분류하는 태그
methods = ["GET", "POST", "PUT", "DELETE"]
routes = ["/api/users", "/api/orders", "/api/products"]

print("5초마다 메트릭이 콘솔에 출력됩니다. Ctrl+C로 종료하세요.\n")

try:
    for i in range(30):
        method = random.choice(methods)
        route = random.choice(routes)
        status = random.choice([200, 200, 200, 200, 404, 500])

        # 모든 요청을 카운트
        request_counter.add(1, {
            "http.request.method": method,
            "http.route": route,
            "http.response.status_code": status,
        })

        # 에러 응답만 별도 카운트
        if status >= 400:
            error_counter.add(1, {
                "http.response.status_code": status,
                "http.route": route,
            })

        time.sleep(0.5)

except KeyboardInterrupt:
    pass
finally:
    provider.shutdown()
```

```bash
poetry run python metrics_counter.py
```

5초마다 콘솔에 Counter 데이터가 출력됩니다. 속성 조합별로 값이 집계되는 것을 확인합니다.

### 2단계: Histogram (분포 측정)

```python
# metrics_histogram.py
# Histogram을 사용한 응답 시간 분포 측정

import time
import random
from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import (
    ConsoleMetricExporter,
    PeriodicExportingMetricReader,
)
from opentelemetry.sdk.resources import Resource

resource = Resource.create({"service.name": "metrics-histogram-demo"})
reader = PeriodicExportingMetricReader(
    ConsoleMetricExporter(),
    export_interval_millis=5000,
)
provider = MeterProvider(resource=resource, metric_readers=[reader])
metrics.set_meter_provider(provider)

meter = metrics.get_meter(__name__)

# Histogram 생성
# → 기록된 값들의 분포(버킷), 합계, 개수, 최소/최대를 자동 계산
request_duration = meter.create_histogram(
    name="http.server.request.duration",
    description="HTTP 요청 처리 시간",
    unit="ms",
)

payload_size = meter.create_histogram(
    name="http.server.response.body.size",
    description="HTTP 응답 본문 크기",
    unit="By",  # Bytes
)

print("5초마다 메트릭이 콘솔에 출력됩니다. Ctrl+C로 종료하세요.\n")

try:
    for i in range(30):
        # 응답 시간 시뮬레이션 (5ms ~ 500ms)
        duration = random.uniform(5, 500)
        method = random.choice(["GET", "POST"])
        route = random.choice(["/api/users", "/api/orders"])

        # .record()로 값 기록
        request_duration.record(duration, {
            "http.request.method": method,
            "http.route": route,
        })

        # 응답 크기 시뮬레이션
        size = random.randint(100, 10000)
        payload_size.record(size, {
            "http.route": route,
        })

        time.sleep(0.5)

except KeyboardInterrupt:
    pass
finally:
    provider.shutdown()
```

출력에서 Histogram의 **버킷(bucket) 분포**를 확인합니다. 기본 버킷 경계는 `[0, 5, 10, 25, 50, 75, 100, 250, 500, 750, 1000, 2500, 5000, 7500, 10000]`입니다.

### 3단계: UpDownCounter (증감 카운터)

```python
# metrics_updown.py
# UpDownCounter를 사용한 활성 리소스 추적

import time
import random
from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import (
    ConsoleMetricExporter,
    PeriodicExportingMetricReader,
)
from opentelemetry.sdk.resources import Resource

resource = Resource.create({"service.name": "metrics-updown-demo"})
reader = PeriodicExportingMetricReader(
    ConsoleMetricExporter(),
    export_interval_millis=5000,
)
provider = MeterProvider(resource=resource, metric_readers=[reader])
metrics.set_meter_provider(provider)

meter = metrics.get_meter(__name__)

# UpDownCounter: 증가와 감소가 모두 가능
active_requests = meter.create_up_down_counter(
    name="http.server.active_requests",
    description="현재 처리 중인 HTTP 요청 수",
    unit="1",
)

queue_size = meter.create_up_down_counter(
    name="task.queue.size",
    description="작업 큐에 대기 중인 작업 수",
    unit="1",
)

print("5초마다 메트릭이 콘솔에 출력됩니다. Ctrl+C로 종료하세요.\n")

try:
    for i in range(20):
        # 요청 시작 (증가)
        active_requests.add(1, {"http.request.method": "GET"})
        time.sleep(0.1)

        # 큐에 작업 추가
        queue_size.add(random.randint(1, 5))

        # 요청 완료 (감소)
        active_requests.add(-1, {"http.request.method": "GET"})

        # 큐에서 작업 처리 완료
        queue_size.add(-random.randint(0, 3))

        time.sleep(0.5)

except KeyboardInterrupt:
    pass
finally:
    provider.shutdown()
```

---

## 계측기 선택 가이드

```
"무엇을 측정하려는가?"

1. 누적 횟수 (항상 증가) → Counter
   예: 총 요청 수, 총 에러 수, 처리된 바이트 수

2. 현재 값 (증감 가능) → UpDownCounter
   예: 활성 연결 수, 큐 대기 작업 수

3. 값의 분포 → Histogram
   예: 응답 시간, 페이로드 크기, 배치 처리 건수

4. 외부 시스템의 현재 상태 → Observable Gauge (07장)
   예: CPU 사용률, 메모리 사용량, 디스크 공간
```

---

## 마무리

이번 단계에서 학습한 것:

- MeterProvider → Meter → Instrument 구조
- **Counter**: 단조 증가하는 누적 값 측정
- **Histogram**: 값의 분포 측정 (버킷 기반)
- **UpDownCounter**: 증감 가능한 현재 값 추적
- 속성(labels)을 통한 메트릭 분류

**다음 단계**: [07. Metrics 심화](07-metrics-advanced.md)에서 비동기(Observable) 계측기와 Views를 사용한 메트릭 커스터마이징을 다룹니다.
