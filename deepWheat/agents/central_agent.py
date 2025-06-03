from spade.agent import Agent
from spade.behaviour import FSMBehaviour, State
from spade.message import Message
from utils.logger import print_log, print_agent_header
from utils.negotiation import evaluate_proposal
import asyncio

class CentralAgent(Agent):
    class ContractNetManager(FSMBehaviour):
        async def on_start(self):
            print_agent_header(self.agent.jid.user)
            print_log(self.agent.jid.user, "🧠 Starting ContractNetManager...")

        async def on_end(self):
            print_log(self.agent.jid.user, "✅ Contract negotiation finished.")

    class WaitRequest(State):
        async def run(self):
            print_log(self.agent.jid.user, "📥 Waiting for field requests...")
            msg = await self.receive(timeout=10)
            if msg:
                ontology = msg.metadata.get("ontology")
                if ontology in ["monitoring_request", "fertilization_request"]:
                    self.set("ontology", ontology)
                    self.set("field_data", msg.body)
                    self.set_next_state("SEND_CFP")
                else:
                    print_log(self.agent.jid.user, f"⚠️ Unknown request: {ontology}")
                    self.set_next_state("WAIT")
            else:
                print_log(self.agent.jid.user, "🕒 No new tasks.")
                self.set_next_state("WAIT")

    class SendCFP(State):
        async def run(self):
            ontology = self.get("ontology")
            field_data = self.get("field_data")
            drones = self.agent.vigilant_drones if ontology == "monitoring_request" else self.agent.payload_drones

            print_log(self.agent.jid.user, f"📤 Sending CFP for {ontology}: {field_data}")
            for drone in drones:
                cfp = Message(to=drone)
                cfp.set_metadata("performative", "cfp")
                cfp.set_metadata("ontology", ontology)
                cfp.body = field_data
                await self.send(cfp)

            self.agent.proposals = []
            self.set_next_state("COLLECT_PROPOSALS")

    class CollectProposals(State):
        async def run(self):
            ontology = self.get("ontology")
            print_log(self.agent.jid.user, "📨 Collecting proposals...")
            start = asyncio.get_event_loop().time()
            while asyncio.get_event_loop().time() - start < 5:
                msg = await self.receive(timeout=1)
                if msg and msg.metadata.get("performative") == "proposal":
                    sender = str(msg.sender).split("/")[0]
                    drone_name, battery, wind = msg.body.split("|")
                    score = evaluate_proposal(float(battery), float(wind))
                    self.agent.proposals.append((sender, score, msg.body))

            if self.agent.proposals:
                best_drone = max(self.agent.proposals, key=lambda p: p[1])
                decision = Message(to=best_drone[0])
                decision.set_metadata("performative", "accept_proposal")
                decision.set_metadata("ontology", ontology)
                decision.body = self.get("field_data")
                await self.send(decision)
                print_log(self.agent.jid.user, f"✅ Assigned {ontology} to {best_drone[0]}")
            else:
                print_log(self.agent.jid.user, "⚠️ No proposals received.")

            self.set_next_state("WAIT")

    async def setup(self):
        self.vigilant_drones = ["vigilant1@localhost", "vigilant2@localhost"]
        self.payload_drones = ["payload1@localhost", "payload2@localhost"]

        print_agent_header(self.jid.user)
        print_log(self.jid.user, f"{self.jid} is online.")

        fsm = self.ContractNetManager()
        fsm.add_state(name="WAIT", state=self.WaitRequest(), initial=True)
        fsm.add_state(name="SEND_CFP", state=self.SendCFP())
        fsm.add_state(name="COLLECT_PROPOSALS", state=self.CollectProposals())

        fsm.add_transition("WAIT", "SEND_CFP")
        fsm.add_transition("SEND_CFP", "COLLECT_PROPOSALS")
        fsm.add_transition("COLLECT_PROPOSALS", "WAIT")

        self.add_behaviour(fsm)