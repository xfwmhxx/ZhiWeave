from prometheus_client import Counter, Histogram

HTTP_REQUESTS = Counter(
    "zhiweave_http_requests_total",
    "HTTP requests handled by the API",
    ("method", "path", "status"),
)
HTTP_DURATION = Histogram(
    "zhiweave_http_request_duration_seconds",
    "HTTP request duration",
    ("method", "path"),
)
