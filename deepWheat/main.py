import asyncio
import threading
from agents.vigilant_drone import VigilantDroneAgent
from agents.field_agent import FieldAgent
from agents.payload_drone import PayloadDroneAgent
from agents.central_agent import CentralAgent
from config import FIELD_AGENTS

stop_event = threading.Event()

def wait_for_q():
    print("🕹️ Press 'Q' then Enter to stop the simulation.")
    while True:
        if input().strip().upper() == "Q":
            stop_event.set()
            break

async def main():
    drones = [
        VigilantDroneAgent(f"vigilant{i}@localhost", "admin1234")
        for i in range(1, 3)  # creates vigilant1 and vigilant2
    ]
    payload_drones = [
        PayloadDroneAgent(f"payload{i}@localhost", "admin1234")
        for i in range(1, 4)  # creates payload1, payload2, and payload3
    ]

    field_agents = [
        FieldAgent(cfg["agent_jid"], "admin1234", cfg["field_id"])
        for cfg in FIELD_AGENTS
    ]   
    central = CentralAgent("central@localhost", "admin1234")

    # Start all agents in the original simple way
    await central.start()

    for drone in drones:
        await drone.start()
        
    for payload_drone in payload_drones:
        await payload_drone.start()

    for field_agent in field_agents:
        await field_agent.start()

    print("✅ All agents started")

    thread = threading.Thread(target=wait_for_q)
    thread.start()

    while not stop_event.is_set():
        await asyncio.sleep(1)

    # Graceful shutdown
    for field_agent in field_agents:
        await field_agent.stop()

    for payload_drone in payload_drones:
        await payload_drone.stop()

    await central.stop()

    for drone in drones:
        await drone.stop()
    
    thread.join()
    print("🛑 All agents stopped")

if __name__ == "__main__":
    asyncio.run(main())