# PX4 WebSocket C2 Communication Script

This script provides WebSocket-based Command and Control (C2) communication for PX4 SITL drones using the format `{topic:xxx,payload:{xxx}}`.

## Features

- **WebSocket Communication**: Real-time bidirectional communication
- **MAVLink Integration**: Direct connection to PX4 via MAVLink
- **Multiple Commands**: Arm, disarm, takeoff, land, RTL, waypoint navigation, velocity control, position control, flight mode changes, mission upload/execution, and status requests
- **Error Handling**: Comprehensive error handling and response feedback
- **Colored Logging**: Easy-to-read colored console output

## Installation

1. Install dependencies:
```bash
pip install -r requirements_c2.txt
```

## Usage

### 1. Start PX4 SITL

First, start PX4 SITL with MAVLink communication enabled:

```bash
# From the PX4 root directory
make px4_sitl gazebo
```

### 2. Start the C2 Script

```bash
python3 px4_websocket_c2.py <websocket_url> <mavlink_connection>
```

**Examples:**
```bash
# Connect to local WebSocket server and PX4 via TCP
python3 px4_websocket_c2.py ws://localhost:8080 tcp:localhost:5760

# Connect to remote WebSocket server and PX4 via UDP
python3 px4_websocket_c2.py ws://192.168.1.100:8080 udp:192.168.1.100:14550
```

### 3. Test with WebSocket Server (Optional)

For testing, you can use the included test server:

```bash
# Start test server on port 8080
python3 websocket_test_server.py 8080

# In another terminal, connect the C2 script
python3 px4_websocket_c2.py ws://localhost:8080 tcp:localhost:5760
```

## Supported Commands

### Basic Flight Commands

#### Arm/Disarm
```json
{
  "topic": "arm",
  "payload": {}
}
```

```json
{
  "topic": "disarm",
  "payload": {}
}
```

#### Takeoff/Land
```json
{
  "topic": "takeoff",
  "payload": {"altitude": 10.0}
}
```

```json
{
  "topic": "land",
  "payload": {}
}
```

#### Return to Launch
```json
{
  "topic": "rtl",
  "payload": {}
}
```

### Navigation Commands

#### Waypoint Navigation
```json
{
  "topic": "waypoint",
  "payload": {
    "lat": 47.397742,
    "lon": 8.545594,
    "alt": 10.0
  }
}
```

#### Velocity Control
```json
{
  "topic": "velocity",
  "payload": {
    "vx": 2.0,
    "vy": 0.0,
    "vz": 0.0
  }
}
```

#### Position Control
```json
{
  "topic": "position",
  "payload": {
    "x": 10.0,
    "y": 5.0,
    "z": -5.0
  }
}
```

### Mission Commands

#### Upload and Start Mission
```json
{
  "topic": "mission",
  "payload": {
    "mission_file": "scout/missions/example.plan"
  }
}
```

#### Start Current Mission
```json
{
  "topic": "mission",
  "payload": {}
}
```

### System Commands

#### Change Flight Mode
```json
{
  "topic": "mode",
  "payload": {
    "mode": "AUTO"
  }
}
```

#### Get Status
```json
{
  "topic": "status",
  "payload": {}
}
```

## Response Format

All commands receive responses in the format:

```json
{
  "topic": "command_response",
  "payload": {
    "success": true,
    "timestamp": 1234567890.123,
    "message": "Command executed successfully",
    "additional_data": "..."
  }
}
```

## Error Handling

If a command fails, the response will include:

```json
{
  "topic": "command_response",
  "payload": {
    "success": false,
    "timestamp": 1234567890.123,
    "error": "Error description"
  }
}
```

## MAVLink Connection Types

The script supports various MAVLink connection types:

- **TCP**: `tcp:localhost:5760`
- **UDP**: `udp:192.168.1.100:14550`
- **Serial**: `serial:/dev/ttyUSB0:921600`
- **SITL**: `tcp:localhost:5760` (default for SITL)

## WebSocket URL Formats

- **Local**: `ws://localhost:8080`
- **Remote**: `ws://192.168.1.100:8080`
- **Secure**: `wss://example.com:443`

## Troubleshooting

### Common Issues

1. **Connection Failed**: Ensure PX4 SITL is running and the MAVLink connection string is correct
2. **WebSocket Connection Failed**: Check if the WebSocket server is running and accessible
3. **Command Timeout**: Some commands may take time to execute, check the PX4 logs for details

### Debug Mode

For more detailed logging, modify the logging level in the script:

```python
logging.basicConfig(
    level=logging.DEBUG,  # Change from INFO to DEBUG
    format='%(asctime)s - %(levelname)s - %(message)s'
)
```

## Security Considerations

- Use secure WebSocket connections (WSS) in production
- Implement authentication for WebSocket connections
- Validate all incoming commands
- Use firewall rules to restrict access

## Integration Examples

### JavaScript Client
```javascript
const ws = new WebSocket('ws://localhost:8080');

ws.onopen = function() {
    // Send arm command
    ws.send(JSON.stringify({
        topic: 'arm',
        payload: {}
    }));
};

ws.onmessage = function(event) {
    const response = JSON.parse(event.data);
    console.log('Response:', response);
};
```

### Python Client
```python
import websockets
import json
import asyncio

async def send_command():
    async with websockets.connect('ws://localhost:8080') as websocket:
        command = {
            "topic": "takeoff",
            "payload": {"altitude": 15.0}
        }
        await websocket.send(json.dumps(command))
        response = await websocket.recv()
        print(f"Response: {response}")

asyncio.run(send_command())
```

## License

This script is part of the PX4 Scout project and follows the same licensing terms.
