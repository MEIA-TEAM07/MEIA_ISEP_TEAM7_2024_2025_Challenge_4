import asyncio
from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
from spade.message import Message


class TreatmentDroneAgent(Agent):
    class ListenAndTreatBehaviour(CyclicBehaviour):
        async def run(self):
            print("💉 TreatmentDrone: Waiting for disease alerts...")
            msg = await self.receive(timeout=10)
            if msg and msg.metadata.get("ontology") == "disease_alert":
                field = msg.body
                print(f"🚨 Received treatment request for field: {field}")
                await self.apply_treatment(field)
            else:
                print("🕒 No alerts received.")

        async def apply_treatment(self, field):
            print(f"🧭 Navigating to {field}...")
            await asyncio.sleep(2)

            print(f"💦 Applying pesticide at {field}...")
            await asyncio.sleep(2)

            print(f"✅ Treatment at {field} completed.")
            print("🔋 Returning to base...")
            await asyncio.sleep(2)

    async def setup(self):
        print(f"💉 TreatmentDroneAgent {self.jid} is online.")
        self.add_behaviour(self.ListenAndTreatBehaviour())