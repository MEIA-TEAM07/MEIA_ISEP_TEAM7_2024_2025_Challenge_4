import asyncio
from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
from spade.message import Message
from utils.logger import print_log, print_agent_header

class TreatmentDroneAgent(Agent):
    class ListenAndTreatBehaviour(CyclicBehaviour):
        async def on_start(self):
            print_agent_header(self.agent.jid.user)

        async def run(self):
            print_log(self.agent.jid.user, "💉 TreatmentDrone: Waiting for disease alerts...")
            msg = await self.receive(timeout=10)
            if msg and msg.metadata.get("ontology") == "disease_alert":
                field = msg.body
                print_log(self.agent.jid.user, f"🚨 Received treatment request for field: {field}")
                await self.apply_treatment(field)
            else:
                print_log(self.agent.jid.user, "🕒 No alerts received.")

        async def apply_treatment(self, field):
            print_log(self.agent.jid.user, f"🧭 Navigating to {field}...")
            await asyncio.sleep(2)

            print_log(self.agent.jid.user, f"💦 Applying pesticide at {field}...")
            await asyncio.sleep(2)

            print_log(self.agent.jid.user, f"✅ Treatment at {field} completed.")
            print_log(self.agent.jid.user, "🔋 Returning to base...")
            await asyncio.sleep(2)

    async def setup(self):
        print_log(self.jid.user, f"💉 TreatmentDroneAgent {self.jid} is online.")
        self.add_behaviour(self.ListenAndTreatBehaviour())