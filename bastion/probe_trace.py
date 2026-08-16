"""Quick probe: can we write a Cloud Trace span on bastion-505622?"""
from google.cloud import trace_v2
from google.protobuf import timestamp_pb2
import datetime

client = trace_v2.TraceServiceClient()
project = "bastion-505622"
parent = f"projects/{project}"

now = datetime.datetime.utcnow()
ts = timestamp_pb2.Timestamp()
ts.FromDatetime(now)

span = trace_v2.Span(
    name=f"{parent}/traces/aaaabbbbcccc00001111222233334444/spans/1111222233334444",
    display_name=trace_v2.TruncatableString(value="bastion-billing-test"),
    start_time=ts,
    end_time=ts,
)

try:
    client.create_span(request=span)
    print("TRACE_WRITE_OK — billing NOT blocked")
except Exception as e:
    print(f"TRACE_WRITE_FAILED: {e}")
