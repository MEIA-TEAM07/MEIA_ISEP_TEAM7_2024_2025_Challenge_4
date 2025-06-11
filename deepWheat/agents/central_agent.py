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
                # Accept monitoring, fertilization, and treatment requests
                if ontology in ["monitoring_request", "fertilization_request", "treatment_request"]:
                    self.set("ontology", ontology)
                    self.set("field_data", msg.body)
                    # Store which agent requested (for treatment/fertilizer feedback)
                    self.set("field_agent", str(msg.sender))
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
            # Decide which drones to send CFP to
            if ontology == "monitoring_request":
                drones = self.agent.vigilant_drones
            else:  # fertilization_request or treatment_request
                drones = self.agent.payload_drones

            print_log(self.agent.jid.user, f"📤 Sending CFP for {ontology}: {field_data}")
            for drone in drones:
                cfp = Message(to=drone)
                cfp.set_metadata("performative", "cfp")
                # Use the right ontology for drones
                if ontology == "treatment_request":
                    cfp.set_metadata("ontology", "pesticide_request")
                else:
                    cfp.set_metadata("ontology", ontology)
                cfp.body = field_data
                await self.send(cfp)

            self.agent.proposals = []
            self.agent.responders = drones
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
                    try:
                        drone_name, battery, wind = msg.body.split("|")
                        score = evaluate_proposal(float(battery), float(wind))
                        print_log(self.agent.jid.user, f"Score: {score} for Drone {drone_name}")
                        self.agent.proposals.append((sender, score, msg.body))
                    except Exception as e:
                        print_log(self.agent.jid.user, f"⚠️ Malformed proposal from {sender}: {e}")

            if self.agent.proposals:
                best_drone = max(self.agent.proposals, key=lambda p: p[1])
                decision = Message(to=best_drone[0])
                decision.set_metadata("performative", "accept_proposal")
                # Use correct ontology for drone accept
                if ontology == "treatment_request":
                    decision.set_metadata("ontology", "pesticide_request")
                else:
                    decision.set_metadata("ontology", ontology)
                decision.body = self.get("field_data")
                await self.send(decision)
                print_log(self.agent.jid.user, f"✅ Assigned {ontology} to {best_drone[0]}")

                # Notify FieldAgent when a treatment is assigned
                if ontology == "treatment_request":
                    field_agent_jid = self.get("field_agent")
                    fa_msg = Message(to=field_agent_jid)
                    fa_msg.set_metadata("performative", "inform")
                    fa_msg.set_metadata("ontology", "treatment_assigned")
                    fa_msg.body = self.get("field_data")  # Pass field, coords, disease
                    await self.send(fa_msg)

                # Send rejections to other responders
                for responder in self.agent.responders:
                    if responder != best_drone[0]:
                        rejection = Message(to=responder)
                        rejection.set_metadata("performative", "reject_proposal")
                        rejection.set_metadata("ontology", ontology if ontology != "treatment_request" else "pesticide_request")
                        rejection.body = "Better proposal selected."
                        await self.send(rejection)
            else:
                print_log(self.agent.jid.user, "⚠️ No proposals received. Waiting for recharging agents.")

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
        fsm.add_transition("WAIT", "WAIT")

        self.add_behaviour(fsm)