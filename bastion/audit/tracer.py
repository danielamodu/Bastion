"""
audit/tracer.py — Bastion distributed trace instrumentation.

Wraps Google Cloud Trace to produce a visible call chain for every
agent-to-agent interaction across the mesh.

Usage:
    from audit.tracer import BastionTracer

    with BastionTracer("risk_agent.assess_risk") as tracer:
        with tracer.span("registry.discover_agent") as span:
            span.add_label("capability", "fx_rate_lookup")
            result = discover_agent("fx_rate_lookup")

Each span lands in Cloud Trace under a single root trace ID so the
full chain is visible in one waterfall view.
"""

import datetime
import logging
import os
import random
import time
from contextlib import contextmanager
from typing import Optional

from google.cloud import trace_v2
from google.protobuf import timestamp_pb2

logger = logging.getLogger(__name__)

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "bastion-505622")


def _now_proto() -> timestamp_pb2.Timestamp:
    ts = timestamp_pb2.Timestamp()
    ts.FromDatetime(datetime.datetime.now(datetime.timezone.utc))
    return ts


def _new_id(bits: int = 128) -> str:
    """Generate a hex trace/span ID."""
    return f"{random.getrandbits(bits):032x}" if bits == 128 else f"{random.getrandbits(bits):016x}"


class ActiveSpan:
    """Context manager for a single Cloud Trace span."""

    def __init__(
        self,
        client: trace_v2.TraceServiceClient,
        trace_id: str,
        span_name: str,
        parent_span_id: Optional[str] = None,
    ):
        self._client = client
        self._trace_id = trace_id
        self._span_id = _new_id(64)
        self._span_name = span_name
        self._parent_span_id = parent_span_id
        self._start_time = _now_proto()
        self._labels: dict = {}
        self._status_message: Optional[str] = None

    def add_label(self, key: str, value: str):
        """Attach a key/value label to this span (visible in Trace UI)."""
        self._labels[key] = str(value)

    def set_status(self, message: str):
        self._status_message = message

    def _flush(self):
        end_time = _now_proto()
        resource_name = (
            f"projects/{PROJECT_ID}/traces/{self._trace_id}"
            f"/spans/{self._span_id}"
        )

        # Build attribute_map from collected labels
        all_attrs = dict(self._labels)
        if self._status_message:
            all_attrs["outcome"] = self._status_message

        attribute_map = {
            k: trace_v2.AttributeValue(
                string_value=trace_v2.TruncatableString(value=str(v)[:256])
            )
            for k, v in all_attrs.items()
        }

        span = trace_v2.Span(
            name=resource_name,
            display_name=trace_v2.TruncatableString(value=self._span_name[:128]),
            start_time=self._start_time,
            end_time=end_time,
            attributes=trace_v2.Span.Attributes(attribute_map=attribute_map),
        )
        if self._parent_span_id:
            span.parent_span_id = self._parent_span_id

        try:
            self._client.create_span(request=span)
            logger.info(
                "TRACE SPAN | trace=%s span=%s name=%s",
                self._trace_id[:8], self._span_id[:8], self._span_name,
            )
        except Exception as e:
            logger.warning("Trace flush failed (non-fatal): %s", e)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.add_label("error", str(exc_val)[:256])
            self.set_status("ERROR")
        self._flush()
        return False  # don't suppress exceptions


class BastionTracer:
    """
    Root tracer for a single agent operation.

    Creates one trace_id shared across all child spans so the full
    call chain appears as one waterfall in Cloud Trace.
    """

    def __init__(self, root_operation: str, correlation_id: Optional[str] = None):
        self._root_operation = root_operation
        self._trace_id = correlation_id or _new_id(128)
        self._client = trace_v2.TraceServiceClient()
        self._root_span: Optional[ActiveSpan] = None
        logger.info(
            "TRACE START | trace_id=%s operation=%s",
            self._trace_id, root_operation,
        )

    @property
    def trace_id(self) -> str:
        return self._trace_id

    def span(self, name: str) -> ActiveSpan:
        """Create a child span under the root trace."""
        parent_id = self._root_span._span_id if self._root_span else None
        return ActiveSpan(
            client=self._client,
            trace_id=self._trace_id,
            span_name=name,
            parent_span_id=parent_id,
        )

    def __enter__(self):
        self._root_span = ActiveSpan(
            client=self._client,
            trace_id=self._trace_id,
            span_name=self._root_operation,
        )
        self._root_span.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._root_span:
            if exc_type:
                self._root_span.add_label("error", str(exc_val)[:256])
                self._root_span.set_status("ERROR")
            else:
                self._root_span.set_status("OK")
            self._root_span._flush()
        logger.info(
            "TRACE END | trace_id=%s | view: https://console.cloud.google.com/traces/list?project=%s",
            self._trace_id, PROJECT_ID,
        )
        return False
