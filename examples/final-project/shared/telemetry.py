# shared/telemetry.py
# 공유 텔레메트리 초기화 모듈
#
# 여러 서비스에서 공통으로 사용하는 OTel 설정을 모듈화합니다.
# 각 서비스는 이 모듈을 import하여 일관된 설정을 적용합니다.

import os
from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter


def init_telemetry(service_name: str, service_version: str = "1.0.0"):
    """
    OpenTelemetry TracerProvider와 MeterProvider를 초기화합니다.

    Args:
        service_name: 서비스 식별 이름 (예: "order-service")
        service_version: 서비스 버전

    Returns:
        tuple[TracerProvider, MeterProvider]
    """
    # OTLP 엔드포인트 (Collector 주소)
    otlp_endpoint = os.environ.get(
        "OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317"
    )

    # Resource: 서비스 식별 메타데이터
    resource = Resource.create({
        "service.name": service_name,
        "service.version": service_version,
        "deployment.environment": os.environ.get("DEPLOYMENT_ENV", "development"),
    })

    # --- Tracing ---
    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(
        BatchSpanProcessor(
            OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
        )
    )
    trace.set_tracer_provider(tracer_provider)

    # --- Metrics ---
    metric_reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(endpoint=otlp_endpoint, insecure=True),
        export_interval_millis=15000,
    )
    meter_provider = MeterProvider(
        resource=resource,
        metric_readers=[metric_reader],
    )
    metrics.set_meter_provider(meter_provider)

    return tracer_provider, meter_provider


def get_tracer(name: str) -> trace.Tracer:
    """모듈별 Tracer를 반환합니다."""
    return trace.get_tracer(name)


def get_meter(name: str) -> metrics.Meter:
    """모듈별 Meter를 반환합니다."""
    return metrics.get_meter(name)
