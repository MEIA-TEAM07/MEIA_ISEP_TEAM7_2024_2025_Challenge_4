import random
from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
from spade.message import Message
from utils.logger import print_log, print_agent_header

class CentralAgent(Agent):
    class RequestRouterBehaviour(CyclicBehaviour):
        async def on_start(self):
            print_agent_header(self.agent.jid.user)

        async def run(self):
            print_log(self.agent.jid.user, "🏢 CentralAgent: waiting for field requests...")
            msg = await self.receive(timeout=10)
            if msg and msg.metadata.get("ontology") == "monitoring_request":
                field_data = msg.body
                print_log(self.agent.jid.user, f"📩 Central received scan request: {field_data}")

                # Forward to available drone (random choice for now)
                drone = random.choice(["vigilant1@localhost", "vigilant2@localhost"])
                forward_msg = Message(to=drone)
                forward_msg.set_metadata("performative", "request")
                forward_msg.set_metadata("ontology", "monitoring_request")
                forward_msg.body = field_data
                await self.send(forward_msg)
                print_log(self.agent.jid.user, f"📤 Task sent to {drone}")
            else:
                print_log(self.agent.jid.user, "🕒 No new tasks.")

    async def setup(self):
        print_log(self.jid.user, f"🏢 CentralAgent {self.jid} is online.")
        self.add_behaviour(self.RequestRouterBehaviour())