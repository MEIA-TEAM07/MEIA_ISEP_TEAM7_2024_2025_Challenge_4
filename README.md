# deepWheat

**Precision Agriculture Multi-Agent System**

This project simulates a sophisticated multi-agent system for precision agriculture using SPADE agents. Multiple autonomous drones collaborate to monitor wheat fields, detect diseases, and efficiently apply fertilizers or pesticides based on real-time environmental conditions and crop needs.

---

## 🚀 Key Features

### **Multi-Agent Coordination**
- **Contract Net Protocol** for optimal task allocation
- **Dynamic drone competition** based on battery levels and wind conditions
- **Parallel field operations** with intelligent request queuing
- **Real-time proposal evaluation** and task assignment

### **Smart Agriculture Operations**
- **Autonomous field monitoring** with disease detection
- **Precision fertilization** during growth seasons
- **Targeted pesticide application** for diseased plants
- **Weather-aware decision making** using OpenWeatherMap API

### **Intelligent Resource Management**
- **Dynamic battery management** with automatic recharging
- **Wind condition assessment** for optimal flight planning
- **Seasonal behavior adaptation** based on crop calendar
- **Load balancing** across multiple drone agents

---

## 🏗️ System Architecture

### **Agent Hierarchy**
```
CentralAgent (Coordinator)
├── Contract Net Protocol Manager
├── Request Queue Management
└── Drone Fleet Coordination
    ├── PayloadDrone Fleet (3 drones)
    │   ├── Fertilization Operations
    │   ├── Pesticide Application
    │   └── Battery Management
    ├── VigilantDrone Fleet (2 drones)
    │   ├── Field Monitoring
    │   ├── Disease Detection
    │   └── Plant Scanning
    └── FieldAgent Network (2 fields)
        ├── Weather Monitoring
        ├── Crop Status Tracking
        └── Request Generation
```

### **Communication Flow**
1. **Field Agents** monitor weather and crop conditions
2. **Fertilization requests** sent during growth season
3. **CentralAgent** broadcasts CFP (Call for Proposals)
4. **All available drones** submit competitive proposals
5. **Best proposal wins** based on battery + wind scoring
6. **Parallel operations** with automatic request queuing
7. **Disease alerts** trigger targeted treatment requests

---

## 📁 Project Structure
```
deepWheat/
├── agents/
│   ├── central_agent.py     # Contract Net Protocol coordinator
│   ├── field_agent.py       # Field monitoring and requests
│   ├── payload_drone.py     # Fertilization/pesticide operations
│   └── vigilant_drone.py    # Disease detection and monitoring
├── utils/
│   ├── battery.py           # Battery usage calculations
│   ├── field_map.py         # Shared field state management
│   ├── logger.py            # Color-coded logging system
│   ├── negotiation.py       # Proposal evaluation logic
│   ├── season.py            # Growth season detection
│   └── weather.py           # OpenWeatherMap integration
├── config.py                # System configuration
├── main.py                  # Simulation launcher
└── README.md               # This file
```

---

## 🤖 Agent Specifications

### **CentralAgent** - System Coordinator
- **Responsibilities**: Task assignment, drone coordination, request queuing
- **Protocol**: Contract Net Protocol with FSM-based state management
- **Features**: Dynamic proposal evaluation, parallel request processing
- **Drone Fleet**: Manages 3 payload drones + 2 vigilant drones

### **FieldAgent** - Field Management
- **Responsibilities**: Weather monitoring, crop status, fertilization requests
- **Data Sources**: OpenWeatherMap API, growth season calendar
- **Features**: Daily initialization, treatment tracking, completion monitoring
- **Coverage**: Each agent manages one 2x5 grid field (10 plants)

### **PayloadDroneAgent** - Operations Execution
- **Responsibilities**: Fertilization, pesticide application, battery management
- **Features**: Proposal generation, task execution, automatic recharging
- **Operations**: Full-field fertilization, targeted plant treatment
- **Fleet Size**: 3 drones competing for tasks

### **VigilantDroneAgent** - Monitoring & Detection
- **Responsibilities**: Field scanning, disease detection, alert generation
- **Features**: Grid-based plant scanning, disease reporting, battery management
- **Coverage**: Plant-by-plant monitoring with position tracking
- **Fleet Size**: 2 drones for field surveillance

---

## 🛠️ Environment Setup

### **System Requirements**
- Ubuntu 22.04 LTS (recommended)
- Python 3.8+
- Prosody XMPP Server
- OpenWeatherMap API key

### **1. Install System Dependencies**
```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv prosody -y
```

### **2. Setup Virtual Environment**
```bash
python3 -m venv spade_env
source spade_env/bin/activate
```

### **3. Install Python Dependencies**
```bash
pip install spade==4.0.3 requests aioxmpp termcolor
```

### **4. Configure Prosody XMPP Server**
```bash
# Start Prosody service
sudo systemctl start prosody
sudo systemctl enable prosody

# Create agent accounts
sudo prosodyctl adduser central@localhost
sudo prosodyctl adduser field1@localhost
sudo prosodyctl adduser field2@localhost
sudo prosodyctl adduser payload1@localhost
sudo prosodyctl adduser payload2@localhost
sudo prosodyctl adduser payload3@localhost
sudo prosodyctl adduser vigilant1@localhost
sudo prosodyctl adduser vigilant2@localhost
```

### **5. Configure Weather API**
Update `config.py` with your OpenWeatherMap API key:
```python
WEATHER_API_KEY = "your_api_key_here"
WEATHER_LAT = 41.1496  # Your latitude
WEATHER_LON = -8.6109  # Your longitude
```

---

## ▶️ Running the Simulation

### **Start the System**
```bash
python main.py
```

### **Expected Output**
```
🚁 Managing 2 vigilant drones and 3 payload drones
📤 Sending CFP for fertilization_request: field_1|3.09 to 3 payload drones
📊 Proposal from payload1: Battery=100.0%, Wind=10.58km/h, Score=0.65
📊 Proposal from payload2: Battery=100.0%, Wind=10.12km/h, Score=0.66
📊 Proposal from payload3: Battery=100.0%, Wind=8.98km/h, Score=0.70
🏆 Best proposal: payload3 (score: 0.70)
✅ Assigned fertilization_request to payload3
```

### **Stop the Simulation**
Press **Q** and hit **Enter** for graceful shutdown.

---

## ⚙️ Configuration Options

### **Battery Management**
```python
BATTERY_LOW_THRESHOLD = 45      # Recharge below 45%
BATTERY_RECHARGE_STEP = 20      # Recharge 20% per interval
RECHARGE_INTERVAL = 1           # 1 second per recharge step
```

### **Seasonal Behavior**
```python
GROWTH_SEASON_START = (3, 15)   # March 15
GROWTH_SEASON_END = (6, 15)     # June 15
DEFAULT_CROP_TYPE = "spring"    # Spring wheat
```

### **Environmental Conditions**
```python
WIND_MIN = 5                    # Minimum wind speed (km/h)
WIND_MAX = 15                   # Maximum wind speed (km/h)
FLIGHT_TIME = 2                 # Flight time between positions (seconds)
APPLICATION_TIME = 2            # Application time per plant (seconds)
```

### **Field Configuration**
```python
FIELD_ROWS = 2                  # Grid rows per field
FIELD_COLS = 5                  # Grid columns per field

# Predefined diseased plants
DISEASED_PLANTS = {
    "field_1": [(0, 1, "white_stripe"), (1, 3, "brown_rust")],
    "field_2": [(1, 2, "yellow_rust"), (0, 4, "septoria")]
}
```

---

## 🔬 System Behavior

### **Contract Net Protocol Flow**
1. **Field Agent** detects fertilization need
2. **Central Agent** broadcasts CFP to all payload drones
3. **Available drones** submit proposals with battery/wind data
4. **Proposals evaluated** using scoring algorithm: `battery_score - wind_penalty`
5. **Best drone selected** and assigned the task
6. **Other drones rejected** and remain available for future tasks

### **Proposal Evaluation Algorithm**
```python
def evaluate_proposal(battery_level, wind_speed):
    battery_score = battery_level / 100.0  # Normalize to 0-1
    wind_penalty = wind_speed / 30.0       # Assume max wind 30km/h
    return battery_score - wind_penalty    # Higher score = better drone
```

### **Disease Detection Workflow**
1. **Vigilant Drone** scans field grid systematically
2. **Disease detected** at specific plant coordinates
3. **Field Agent** receives disease alert with position
4. **Treatment request** sent if plant not already being treated
5. **Payload Drone** applies pesticide to specific plant
6. **Treatment completion** reported back to Field Agent

---

## 📊 Monitoring & Logging

### **Color-Coded Logging**
- **🔵 Central Agent**: Blue - Coordination and task assignment
- **🟢 Vigilant Drones**: Green - Monitoring and detection
- **🔴 Payload Drones**: Red - Operations and battery status
- **🟡 Field Agents**: Yellow - Field conditions and requests

### **Key Metrics Tracked**
- Drone battery levels and recharge cycles
- Wind conditions and flight efficiency
- Task completion rates and timing
- Proposal scores and selection rationale
- Disease detection and treatment effectiveness

---

## 🔄 Extensibility

### **Adding More Drones**
Simply update the range in `main.py`:
```python
payload_drones = [
    PayloadDroneAgent(f"payload{i}@localhost", "admin1234")
    for i in range(1, 5)  # Creates payload1 through payload4
]
```

### **Adding More Fields**
Update `config.py`:
```python
FIELD_AGENTS = [
    {"agent_jid": "field1@localhost", "field_id": "field_1"},
    {"agent_jid": "field2@localhost", "field_id": "field_2"},
    {"agent_jid": "field3@localhost", "field_id": "field_3"}  # New field
]
```

### **Custom Disease Types**
Add new diseases to `DISEASED_PLANTS` configuration:
```python
DISEASED_PLANTS = {
    "field_1": [(0, 1, "powdery_mildew"), (1, 3, "leaf_spot")],
    # ... additional disease configurations
}
```

---

## 🚀 Future Enhancements

### **Planned Features**
- [ ] **ROS2 Integration** for physical drone simulation
- [ ] **Gazebo 3D Environment** for realistic field visualization
- [ ] **Machine Learning** for disease prediction
- [ ] **IoT Sensor Integration** for real-time field data
- [ ] **Mobile Dashboard** for monitoring and control

### **Research Applications**
- Multi-agent coordination algorithms
- Precision agriculture optimization
- Autonomous vehicle fleet management
- Environmental monitoring systems
- Supply chain and logistics optimization

---

## 📜 License

This project is developed for research and educational purposes in precision agriculture and multi-agent systems.

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit issues, feature requests, or pull requests to improve the deepWheat system.

---

**deepWheat** - *Autonomous Multi-Agent Precision Agriculture* 🌾🚁