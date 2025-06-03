import asyncio
from agents.vigilant_drone import VigilantDroneAgent
from agents.field_agent import FieldAgent
from agents.payload_drone import PayloadDroneAgent
from agents.central_agent import CentralAgent

async def main():
    drones = [
        VigilantDroneAgent(f"vigilant{i}@localhost", "admin1234")
        for i in range(1, 3)  # creates vigilant1 and vigilant2
    ]
    field = FieldAgent("field1@localhost", "admin1234")
    payload = PayloadDroneAgent("payload1@localhost", "admin1234")
    central = CentralAgent("central@localhost", "admin1234")

    # Start all agents
    await payload.start()
    await central.start()
    await field.start()
    for drone in drones:
        await drone.start()

    print("✅ All agents started")
    await asyncio.sleep(30)  # give them time to interact

    for drone in drones:
        await drone.stop()
    print("🛑 All agents stopped")

if __name__ == "__main__":
    asyncio.run(main())