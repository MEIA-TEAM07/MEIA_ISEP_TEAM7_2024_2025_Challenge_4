import asyncio
import threading
import sys
from agents.vigilant_drone import VigilantDroneAgent
from agents.field_agent import FieldAgent
from agents.payload_drone import PayloadDroneAgent
from agents.central_agent import CentralAgent

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
        for i in range(1, 3)  # creates payload1 and payload2
    ]
    field = FieldAgent("field1@localhost", "admin1234")
    #payload = PayloadDroneAgent("payload1@localhost", "admin1234")
    central = CentralAgent("central@localhost", "admin1234")

    # Start all agents
    await central.start()

    for drone in drones:
        await drone.start()
        
    for payload_drone in payload_drones:
        await payload_drone.start()

    #await payload.start()
    await field.start()

    print("✅ All agents started")
    thread = threading.Thread(target=wait_for_q)
    thread.start()

    while not stop_event.is_set():
        await asyncio.sleep(1)

    # ... graceful shutdown ...
    await field.stop()

    for payload_drone in payload_drones:
        await payload_drone.stop()

    await central.stop()

    for drone in drones:
        await drone.stop()
    
    thread.join()
    print("🛑 All agents stopped")

if __name__ == "__main__":
    asyncio.run(main())