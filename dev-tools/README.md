# Senquip Dev Tools

Development environment for the Senquip Home Assistant integration.
Includes a full Home Assistant instance, MQTT broker, and test data publisher —
all wired together and loading the integration from the working tree.

## Quick Start

```bash
cd dev-tools
docker compose up
```

This starts:

- **Home Assistant** at [http://localhost:8123](http://localhost:8123) — with the
  Senquip integration mounted from `custom_components/senquip/` (read-only)
- **Mosquitto** MQTT broker on port 1883
- **Test publisher** sending two devices to separate topics every 5s:
  - `HE8EV12LF` → `senquip/HE8EV12LF/data`
  - `HD2EKH27F` → `senquip/HD2EKH27F/data`

### First-Time HA Setup

1. Open [http://localhost:8123](http://localhost:8123) and create an owner account
2. Go to **Settings > Devices & Services > Add Integration**
3. Add the **MQTT** integration — set broker to `mosquitto`, port `1883`
4. Add the **Senquip Telemetry** integration — enter topic `senquip/HE8EV12LF/data`
5. Wait for device discovery (the publisher is already sending data)
6. Configure active CAN ports (protocol + optional profiles) and select signals
7. Repeat step 4-6 for the second device on topic `senquip/HD2EKH27F/data`

Changes to the integration source code are picked up on HA restart —
just `docker compose restart homeassistant`.

## Multi-Device Simulation

Simulate two devices at different intervals by overriding `PUBLISH_STREAMS`:

```bash
PUBLISH_STREAMS="senquip/GEN001/data:scenarios/can1_generator.json:5,senquip/MAIN001/data:scenarios/can2_man_engine.json:10" \
  docker compose up
```

GEN001 publishes every 5s, MAIN001 every 10s — each on its own topic.

## Usage Examples

```bash
# Single scenario, custom interval
PUBLISH_STREAMS="senquip/test/data:scenarios/can2_man_engine.json:2" \
  docker compose up

# Publish once and exit
docker compose run --rm publisher \
  python publisher.py --once --publish senquip/test/data:scenarios/minimal.json:0

# Enable sensor value randomisation
docker compose run --rm publisher \
  python publisher.py --randomize \
  --publish senquip/test/data:scenarios/can2_man_engine.json:5

# Connect to external broker (no Mosquitto container needed)
docker compose run --rm publisher \
  python publisher.py --host 192.168.1.50 --port 1883 \
  --publish senquip/test/data:scenarios/device_he8ev12lf.json:5
```

## Standalone (No Docker)

```bash
cd dev-tools/mqtt-publisher
pip install -r requirements.txt

# Single stream
python publisher.py --publish senquip/test/data:scenarios/can2_man_engine.json:5

# Multiple streams
python publisher.py \
  --publish senquip/GEN001/data:scenarios/can1_generator.json:5 \
  --publish senquip/MAIN001/data:scenarios/can2_man_engine.json:10

# Custom broker
python publisher.py --host 192.168.1.50 --port 1883 \
  --publish senquip/test/data:scenarios/device_he8ev12lf.json:5

# Single shot
python publisher.py --once --publish senquip/test/data:scenarios/minimal.json:0
```

## Scenarios

Each scenario is a **single device JSON object** (not an array). Real devices publish separately to their own topics.

| File | Description |
| ---- | ----------- |
| `device_he8ev12lf.json` | HE8EV12LF device — full CAN1+CAN2 data with events (from example.md) |
| `device_hd2ekh27f.json` | HD2EKH27F device — CAN2 only with custom parameters (from example.md) |
| `can1_generator.json` | CAN1 only — Cummins QSB4.5 generator (40 frames, standard J1939) |
| `can2_man_engine.json` | CAN2 only — MAN D2862 main engine (16 frames, use `man_d2862.json` profile with J1939 protocol) |
| `minimal.json` | Bare minimum device — no CAN data, just internal sensors |
| `with_events.json` | Device with events array for event entity testing |
| `dm1_faults.json` | DM1 diagnostic faults on both CAN1 (LE) and CAN2 (BE) |

## Configuration

### `--publish` Format

Each `--publish` argument (or `PUBLISH_STREAMS` entry) follows the format:

```
topic:scenario_file:interval_seconds
```

- **topic** — MQTT topic to publish to
- **scenario_file** — Path to JSON scenario file
- **interval_seconds** — Seconds between publishes

### Environment Variables

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `MQTT_HOST` | `localhost` | MQTT broker hostname |
| `MQTT_PORT` | `1883` | MQTT broker port |
| `MQTT_USERNAME` | _(none)_ | MQTT username |
| `MQTT_PASSWORD` | _(none)_ | MQTT password |
| `PUBLISH_STREAMS` | _(none)_ | Comma-separated `topic:file:interval` entries |

### CLI Arguments

```
--host HOST          MQTT broker host
--port PORT          MQTT broker port
--username USER      MQTT username
--password PASS      MQTT password
--publish T:F:I      Publish stream (repeatable)
--once               Publish each stream once, then exit
--randomize          Add random variance to analog sensor values
-v, --verbose        Debug logging
```

## Home Assistant Container

The `homeassistant` service mounts `custom_components/senquip/` read-only into
the container at `/config/custom_components/senquip/`. This means:

- Code changes are reflected immediately on HA restart
- No need to copy files or rebuild the container
- HA config (automations, dashboards, integrations) persists in the `ha_config` volume

```bash
# Restart HA after code changes
docker compose restart homeassistant

# View HA logs
docker compose logs -f homeassistant

# Reset HA config (start fresh)
docker compose down -v && docker compose up
```

### Connecting to an External Broker

If you already have an MQTT broker running elsewhere, you can skip the Mosquitto
container and just run HA + publisher pointed at your broker:

```bash
docker compose up homeassistant
# Then configure MQTT in HA to point to your external broker
```

## Adding New Scenarios

1. Copy an existing scenario JSON file
2. Modify `deviceid`, sensor values, CAN frames as needed
3. Save to the `scenarios/` directory
4. Reference it in `PUBLISH_STREAMS` or `--publish`

Scenario files use the exact same JSON format the integration expects from MQTT —
either a single device object `{...}` or an array of devices `[{...}, {...}]`.
