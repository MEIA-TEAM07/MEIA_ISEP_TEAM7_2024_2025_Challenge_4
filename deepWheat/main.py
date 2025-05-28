import asyncio
from agents.vigilant_drone import VigilantDroneAgent
from agents.field_agent import FieldAgent
from agents.treatment_drone import TreatmentDroneAgent
from agents.central_agent import CentralAgent

async def main():
    drones = [
        VigilantDroneAgent(f"vigilant{i}@localhost", "admin1234")
        for i in range(1, 3)  # creates vigilant1 and vigilant2
    ]
    field = FieldAgent("field1@localhost", "admin1234")
    treatment = TreatmentDroneAgent("treatment1@localhost", "admin1234")
    central = CentralAgent("central@localhost", "admin1234")

    # Start all agents

    await central.start()
    for drone in drones:
        await drone.start()
    await field.start()
    await treatment.start()

    print("✅ All agents started")
    await asyncio.sleep(30)  # give them time to interact

    await field.stop()
    await treatment.stop()
    await central.stop()
    for drone in drones:
        await drone.stop()
    print("🛑 All agents stopped")

if __name__ == "__main__":
    asyncio.run(main())