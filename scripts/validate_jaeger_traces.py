#!/usr/bin/env python3
"""
Validate Jaeger trace collection.

This script:
1. Makes a request to the KTRDR API
2. Waits for traces to be processed
3. Queries Jaeger API to verify traces were received
4. Prints trace details

Usage:
    python scripts/validate_jaeger_traces.py
    python scripts/validate_jaeger_traces.py --jaeger-url http://localhost:16686
"""

import argparse
import sys
import time

import httpx


def main():
    parser = argparse.ArgumentParser(description="Validate Jaeger trace collection")
    parser.add_argument(
        "--jaeger-url",
        default="http://localhost:16686",
        help="Jaeger UI URL (default: http://localhost:16686)",
    )
    parser.add_argument(
        "--api-url",
        default="http://localhost:8000",
        help="KTRDR API URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--wait-seconds",
        type=int,
        default=2,
        help="Seconds to wait for trace processing (default: 2)",
    )
    args = parser.parse_args()

    print("=" * 70)
    print("Jaeger Trace Validation")
    print("=" * 70)

    # Step 1: Make API request
    print(f"\n1. Making request to {args.api_url}...")
    try:
        response = httpx.get(f"{args.api_url}/")
        print(f"   ✅ API responded with status {response.status_code}")
    except httpx.RequestError as e:
        print(f"   ❌ Failed to reach API: {e}")
        return 1

    # Step 2: Wait for trace processing
    print(f"\n2. Waiting {args.wait_seconds} seconds for trace processing...")
    time.sleep(args.wait_seconds)

    # Step 3: Check Jaeger services
    print(f"\n3. Querying Jaeger at {args.jaeger_url}...")
    try:
        services_response = httpx.get(f"{args.jaeger_url}/api/services")
        services_response.raise_for_status()
        services = services_response.json()

        if "data" not in services:
            print("   ❌ No services found in Jaeger")
            return 1

        print(f"   ✅ Found {len(services['data'])} service(s)")
        for service in services["data"]:
            print(f"      - {service}")

        if "ktrdr-api" not in services["data"]:
            print("\n   ❌ ktrdr-api service not found in Jaeger!")
            print("      Possible causes:")
            print("      - Backend not configured with OTLP_ENDPOINT")
            print("      - Jaeger not receiving traces")
            print("      - Need to restart backend after Jaeger startup")
            return 1

        print("\n   ✅ ktrdr-api service found in Jaeger!")

    except httpx.RequestError as e:
        print(f"   ❌ Failed to reach Jaeger: {e}")
        print("      Make sure Jaeger is running (docker-compose up jaeger)")
        return 1

    # Step 4: Query traces
    print("\n4. Fetching recent traces for ktrdr-api...")
    try:
        traces_response = httpx.get(
            f"{args.jaeger_url}/api/traces",
            params={"service": "ktrdr-api", "limit": 5},
        )
        traces_response.raise_for_status()
        traces_data = traces_response.json()

        if "data" not in traces_data or len(traces_data["data"]) == 0:
            print("   ❌ No traces found for ktrdr-api")
            return 1

        trace_count = len(traces_data["data"])
        print(f"   ✅ Found {trace_count} trace(s)")

        # Display first trace details
        first_trace = traces_data["data"][0]
        print("\n   First trace details:")
        print(f"      Trace ID: {first_trace['traceID']}")
        print(f"      Spans: {len(first_trace['spans'])}")

        # Display span details
        for i, span in enumerate(first_trace["spans"][:3], 1):
            print(f"\n      Span {i}:")
            print(f"         Operation: {span['operationName']}")
            print(f"         Span ID: {span['spanID']}")
            print(f"         Duration: {span['duration'] / 1000:.2f}ms")

            # Show important tags
            tags = {tag["key"]: tag["value"] for tag in span["tags"]}
            if "http.method" in tags:
                print(f"         HTTP Method: {tags['http.method']}")
            if "http.url" in tags:
                print(f"         HTTP URL: {tags['http.url']}")
            if "http.status_code" in tags:
                print(f"         HTTP Status: {tags['http.status_code']}")

    except httpx.RequestError as e:
        print(f"   ❌ Failed to fetch traces: {e}")
        return 1

    # Success
    print("\n" + "=" * 70)
    print("✅ Validation successful!")
    print(f"   View traces in Jaeger UI: {args.jaeger_url}")
    print("=" * 70 + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
