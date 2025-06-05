# deepWheat

**Precision Agriculture Multi-Agent System**

This project simulates a multi-agent system for precision agriculture using SPADE agents. Drones interact to monitor fields, detect diseases, and apply fertilizers or pesticides according to seasonal and environmental conditions.

---

## 🚀 Features
- Autonomous Payload Drones and Vigilant Drones
- Battery management with dynamic recharge
- Field condition simulation and disease alerts
- Seasonal behavior based on crop calendar
- Contract Net Protocol for task allocation
- Dynamic task prioritization and drone availability

---

## ⚙️ Project Structure
```
.
├── agents/              # SPADE agent definitions (Field, Central, Drones)
├── utils/               # Utility functions (logging, battery, negotiation, season)
├── config.py            # Global configuration variables
├── main.py              # Starts the simulation
└── README.md            # Project documentation
```

---

## 🧠 Agents

| Agent           | Responsibility                                              |
|----------------|--------------------------------------------------------------|
| CentralAgent   | Manages task assignment using ContractNetProtocol            |
| FieldAgent     | Simulates field data and generates requests                  |
| PayloadDrone   | Executes fertilization/pesticide tasks and manages battery   |
| VigilantDrone  | Monitors fields and detects disease                          |

---

## 🛠️ Environment Setup (Ubuntu 22.04)

### 1. Install dependencies
```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv -y
```

### 2. Create and activate virtual environment
```bash
python3 -m venv spade_env
source spade_env/bin/activate
```

### 3. Install SPADE (version 4.0.3) and other requirements
```bash
pip install spade==4.0.3
pip install -r requirements.txt
```

If `requirements.txt` doesn't exist, you can install manually:
```bash
pip install aioxmpp termcolor
```

---

## ▶️ Run the Simulation
```bash
python main.py
```
Then press **Q** and hit **Enter** to gracefully stop the simulation.

---

## 🔧 Configuration
All behavioral parameters are centralized in `config.py`:
- `BATTERY_LOW_THRESHOLD`, `BATTERY_RECHARGE_STEP`, `RECHARGE_INTERVAL`
- Seasonal window: `GROWTH_SEASON_START`, `GROWTH_SEASON_END`
- Wind range: `WIND_MIN`, `WIND_MAX`
- Task duration: `FLIGHT_TIME`, `APPLICATION_TIME`

---

## 📝 Notes
- Agents ignore tasks if recharging
- Battery is drained and recharged dynamically
- Seasonal logic controls fertilizer vs pesticide
- Agents compete for tasks; best proposal wins

---

## 📡 XMPP Server (Prosody)
Make sure Prosody is installed and running locally. Example:
```bash
sudo prosodyctl start
```
Create users for each agent using:
```bash
sudo prosodyctl adduser agent_name@localhost
```

---

## ✅ TODO
- [ ] Integrate ROS2 Humble and Gazebo for physical simulation