"""MQTT test publisher for Senquip Home Assistant integration.

Publishes JSON telemetry payloads to an MQTT broker, simulating one or more
Senquip QUAD-C2 devices.  Each publish stream runs independently with its own
topic, scenario file, and interval — so you can simulate a generator reporting
every 5 s while the main engine reports every 10 s.

Usage examples:

    # Single device
    python publisher.py --publish senquip/GEN001/data:scenarios/can1_generator.json:5

    # Multiple devices at different intervals
    python publisher.py \\
        --publish senquip/GEN001/data:scenarios/can1_generator.json:5 \\
        --publish senquip/MAIN001/data:scenarios/can2_man_engine.json:10

    # Single-shot publish (once per stream, then exit)
    python publisher.py --once --publish senquip/test/data:scenarios/dual_device.json:0

    # With sensor randomisation
    python publisher.py --randomize --publish senquip/test/data:scenarios/can2_man_engine.json:5

Environment variable fallbacks (used when no --publish args are given):
    MQTT_HOST          default localhost
    MQTT_PORT          default 1883
    MQTT_USERNAME      optional
    MQTT_PASSWORD      optional
    PUBLISH_STREAMS    comma-separated topic:file:interval entries
"""

import argparse
import asyncio
import copy
import json
import logging
import os
import random
import sys
import time

import paho.mqtt.client as mqtt

log = logging.getLogger("senquip-publisher")

# ---------------------------------------------------------------------------
# Sensor randomisation
# ---------------------------------------------------------------------------

RANDOMISE_RULES: dict[str, tuple[float, float, float]] = {
    # key: (stddev, min_clamp, max_clamp)
    "vsys": (0.05, 3.8, 4.5),
    "vin": (0.3, 20.0, 30.0),
    "ambient": (1.5, 15.0, 60.0),
    "accel_x": (0.02, -2.0, 2.0),
    "accel_y": (0.02, -2.0, 2.0),
    "accel_z": (0.02, -2.0, 2.0),
    "wifi_rssi": (2.0, -90.0, 0.0),
}


def randomise_sensors(device: dict) -> None:
    """Add small Gaussian noise to analog sensor values in-place."""
    for key, (stddev, lo, hi) in RANDOMISE_RULES.items():
        if key in device and isinstance(device[key], (int, float)):
            noisy = device[key] + random.gauss(0, stddev)
            device[key] = round(max(lo, min(hi, noisy)), 2)


# ---------------------------------------------------------------------------
# Scenario loading
# ---------------------------------------------------------------------------


def load_scenario(path: str) -> list | dict:
    """Load a JSON scenario file and return its contents."""
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, (list, dict)):
        raise ValueError(f"Scenario must be a JSON object or array, got {type(data).__name__}")
    log.info("Loaded scenario %s (%s)", path, "array" if isinstance(data, list) else "object")
    return data


# ---------------------------------------------------------------------------
# Publish stream
# ---------------------------------------------------------------------------


class PublishStream:
    """One independent publish loop: topic + scenario + interval."""

    def __init__(
        self,
        topic: str,
        scenario_path: str,
        interval: float,
        randomize: bool = False,
    ):
        self.topic = topic
        self.interval = interval
        self.randomize = randomize
        self.base_payload = load_scenario(scenario_path)
        self.iteration = 0
        self.base_ts = time.time()

    def next_payload(self) -> list | dict:
        """Return payload with updated timestamps and optional randomisation."""
        payload = copy.deepcopy(self.base_payload)
        devices = payload if isinstance(payload, list) else [payload]

        now = self.base_ts + (self.iteration * self.interval)
        for device in devices:
            device["ts"] = round(now, 1)
            device["time"] = int(now)
            if self.randomize:
                randomise_sensors(device)

        self.iteration += 1
        return payload


# ---------------------------------------------------------------------------
# MQTT helpers
# ---------------------------------------------------------------------------


def create_client(
    host: str,
    port: int,
    username: str | None = None,
    password: str | None = None,
) -> mqtt.Client:
    """Create and connect an MQTT v5 client using paho-mqtt v2 API."""
    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"senquip-publisher-{os.getpid()}",
    )
    if username:
        client.username_pw_set(username, password)
    client.connect(host, port, keepalive=60)
    client.loop_start()
    log.info("Connected to MQTT broker %s:%d", host, port)
    return client


# ---------------------------------------------------------------------------
# Async publish loops
# ---------------------------------------------------------------------------


async def run_stream(client: mqtt.Client, stream: PublishStream) -> None:
    """Publish one stream's payload on its interval forever."""
    while True:
        payload = stream.next_payload()
        msg = json.dumps(payload)
        client.publish(stream.topic, msg, qos=0)
        log.info(
            "[%s] Published iteration %d (%d bytes)",
            stream.topic,
            stream.iteration,
            len(msg),
        )
        await asyncio.sleep(stream.interval)


async def run_once(client: mqtt.Client, streams: list[PublishStream]) -> None:
    """Publish each stream exactly once, then return."""
    for stream in streams:
        payload = stream.next_payload()
        msg = json.dumps(payload)
        client.publish(stream.topic, msg, qos=0)
        log.info("[%s] Published once (%d bytes)", stream.topic, len(msg))
    # Brief pause to let paho flush the messages
    await asyncio.sleep(0.5)


async def run_continuous(client: mqtt.Client, streams: list[PublishStream]) -> None:
    """Run all publish streams concurrently until interrupted."""
    tasks = [asyncio.create_task(run_stream(client, s)) for s in streams]
    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        pass


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_stream_spec(spec: str) -> tuple[str, str, float]:
    """Parse a 'topic:file:interval' string."""
    parts = spec.split(":")
    if len(parts) != 3:
        raise argparse.ArgumentTypeError(
            f"Expected topic:file:interval, got {spec!r}"
        )
    topic, filepath, interval_str = parts
    try:
        interval = float(interval_str)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"Interval must be a number, got {interval_str!r}"
        )
    if interval < 0:
        raise argparse.ArgumentTypeError("Interval must be >= 0")
    return topic, filepath, interval


def build_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Senquip MQTT test publisher",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("MQTT_HOST", "localhost"),
        help="MQTT broker host (env: MQTT_HOST, default: localhost)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("MQTT_PORT", "1883")),
        help="MQTT broker port (env: MQTT_PORT, default: 1883)",
    )
    parser.add_argument(
        "--username",
        default=os.environ.get("MQTT_USERNAME"),
        help="MQTT username (env: MQTT_USERNAME)",
    )
    parser.add_argument(
        "--password",
        default=os.environ.get("MQTT_PASSWORD"),
        help="MQTT password (env: MQTT_PASSWORD)",
    )
    parser.add_argument(
        "--publish",
        action="append",
        metavar="TOPIC:FILE:INTERVAL",
        help="Publish stream as topic:scenario_file:interval_seconds (repeatable)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Publish each stream once, then exit",
    )
    parser.add_argument(
        "--randomize",
        action="store_true",
        help="Add random variance to analog sensor values",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable debug logging",
    )
    return parser.parse_args()


def main() -> None:
    args = build_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-5s %(message)s",
        datefmt="%H:%M:%S",
    )

    # Resolve publish streams from --publish args or PUBLISH_STREAMS env var
    specs: list[str] = args.publish or []
    if not specs:
        env_streams = os.environ.get("PUBLISH_STREAMS", "")
        if env_streams:
            specs = [s.strip() for s in env_streams.split(",") if s.strip()]

    if not specs:
        log.error(
            "No publish streams configured. Use --publish or set PUBLISH_STREAMS env var."
        )
        sys.exit(1)

    streams: list[PublishStream] = []
    for spec in specs:
        topic, filepath, interval = parse_stream_spec(spec)
        streams.append(
            PublishStream(topic, filepath, interval, randomize=args.randomize)
        )

    log.info("Configured %d publish stream(s):", len(streams))
    for s in streams:
        log.info("  %s → %s every %.1fs", s.topic, "scenario", s.interval)

    client = create_client(args.host, args.port, args.username, args.password)

    try:
        if args.once:
            asyncio.run(run_once(client, streams))
        else:
            asyncio.run(run_continuous(client, streams))
    except KeyboardInterrupt:
        log.info("Interrupted — shutting down")
    finally:
        client.loop_stop()
        client.disconnect()
        log.info("Disconnected from broker")


if __name__ == "__main__":
    main()
