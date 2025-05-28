
# 🌾 deepWheat - Multi-Agent Drone Monitoring System

**deepWheat** is a prototype platform developed as part of a SMAGIA reinforcement learning project. It simulates a collaborative system of drones and field agents to monitor and treat wheat crops for diseases using the SPADE multi-agent framework.

---

## 🧠 Overview

This simulation consists of four types of agents:

1. **FieldAgent**
   - Simulates environmental sensors (humidity, temperature, wind).
   - Requests drone scans based on threshold anomalies.

2. **VigilantDroneAgent**
   - Receives scan tasks and navigates to fields.
   - Scans for wheat diseases and notifies the treatment drone if needed.
   - Considers wind impact on battery usage and automatically recharges if battery is low.

3. **TreatmentDroneAgent**
   - Responds to disease alerts from VigilantDroneAgent.
   - Navigates to the affected field and simulates pesticide application.

4. **CentralAgent**
   - Dispatches vigilant drones to fields based on FieldAgent requests.
   - Coordinates multiple vigilant drones dynamically.

---

## 📁 Project Structure

```
deepWheat/
├── agents/
│   ├── __init__.py
│   ├── central_agent.py
│   ├── field_agent.py
│   ├── treatment_drone.py
│   └── vigilant_drone.py
├── utils/
│   ├── __init__.py
│   └── battery.py
├── main.py
├── config.py
├── requirements.txt
└── README.md
```

---

## 📦 Installation

1. Clone the project:

```bash
git clone https://github.com/your-org/deepWheat.git
cd deepWheat
```

2. Create and activate a virtual environment:

```bash
python3 -m venv spade_env
source spade_env/bin/activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

---

## 🛰️ Prosody Setup

1. Install Prosody:

```bash
brew tap prosody/prosody
brew install prosody
```

2. Start Prosody:

```bash
sudo prosodyctl start
```

3. Create the required XMPP users:

```bash
sudo prosodyctl adduser central@localhost
sudo prosodyctl adduser vigilant1@localhost
sudo prosodyctl adduser vigilant2@localhost
sudo prosodyctl adduser treatment1@localhost
sudo prosodyctl adduser field1@localhost
```

---

## 🚀 Running the System

```bash
python main.py
```

You’ll see logs for:

- Agent registration and activation
- Simulated environmental conditions
- Battery usage & recharge behavior
- Communication between agents
- Drone actions (scan, detect, treat)

---

## 📋 Notes

- Drones consume more battery with higher wind speeds.
- Vigilant drones only recharge if battery < 20%.
- Central agent dynamically assigns available drones to tasks.
- Random conditions and disease detection are used to simulate variability.

---
