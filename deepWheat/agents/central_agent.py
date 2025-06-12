from spade.agent import Agent
from spade.behaviour import FSMBehaviour, State, CyclicBehaviour
from spade.message import Message
from utils.logger import print_log, print_agent_header
from utils.negotiation import evaluate_proposal
import asyncio
from collections import deque

class CentralAgent(Agent):
    class DroneRegistration(CyclicBehaviour):
        """Handles drone registration and deregistration"""
        async def run(self):
            msg = await self.receive(timeout=1)
            if msg:
                ontology = msg.metadata.get("ontology")
                performative = msg.metadata.get("performative")
                
                if ontology == "drone_registration":
                    if performative == "register":
                        # Handle drone registration
                        try:
                            drone_type, drone_jid = msg.body.split("|")
                            drone_jid_str = str(drone_jid).split("/")[0]  # Clean JID format
                            
                            if drone_type == "payload_drone":
                                if drone_jid_str not in self.agent.payload_drones:
                                    self.agent.payload_drones.append(drone_jid_str)
                                    print_log(self.agent.jid.user, f"✅ Registered payload drone: {drone_jid_str}")
                            elif drone_type == "vigilant_drone":
                                if drone_jid_str not in self.agent.vigilant_drones:
                                    self.agent.vigilant_drones.append(drone_jid_str)
                                    print_log(self.agent.jid.user, f"✅ Registered vigilant drone: {drone_jid_str}")
                                    
                            # Send acknowledgment
                            ack = Message(to=str(msg.sender))
                            ack.set_metadata("performative", "confirm")
                            ack.set_metadata("ontology", "registration_ack")
                            ack.body = f"Registration successful for {drone_type}"
                            await self.send(ack)
                            
                        except Exception as e:
                            print_log(self.agent.jid.user, f"⚠️ Registration error: {e}")
                    
                    elif performative == "deregister":
                        # Handle drone deregistration (for graceful shutdowns)
                        try:
                            drone_type, drone_jid = msg.body.split("|")
                            drone_jid_str = str(drone_jid).split("/")[0]
                            
                            if drone_type == "payload_drone" and drone_jid_str in self.agent.payload_drones:
                                self.agent.payload_drones.remove(drone_jid_str)
                                print_log(self.agent.jid.user, f"❌ Deregistered payload drone: {drone_jid_str}")
                            elif drone_type == "vigilant_drone" and drone_jid_str in self.agent.vigilant_drones:
                                self.agent.vigilant_drones.remove(drone_jid_str)
                                print_log(self.agent.jid.user, f"❌ Deregistered vigilant drone: {drone_jid_str}")
                                
                        except Exception as e:
                            print_log(self.agent.jid.user, f"⚠️ Deregistration error: {e}")

    class ContractNetManager(FSMBehaviour):
        async def on_start(self):
            print_agent_header(self.agent.jid.user)
            print_log(self.agent.jid.user, "🧠 Starting ContractNetManager...")
            # Initialize request queue
            self.agent.request_queue = deque()
            self.agent.processing_request = False

        async def on_end(self):
            print_log(self.agent.jid.user, "✅ Contract negotiation finished.")

    class WaitRequest(State):
        async def run(self):
            while True:  # Keep looping until we find work or need to transition
                # First priority: check if we have queued requests and we're not currently processing
                if self.agent.request_queue and not self.agent.processing_request:
                    print_log(self.agent.jid.user, f"📋 Processing queued request ({len(self.agent.request_queue)} in queue)")
                    request_data = self.agent.request_queue.popleft()
                    self.set("ontology", request_data["ontology"])
                    self.set("field_data", request_data["field_data"])
                    self.set("field_agent", request_data["field_agent"])
                    self.agent.processing_request = True
                    self.set_next_state("SEND_CFP")
                    return

                # If we're currently processing, just wait and check queue again
                if self.agent.processing_request:
                    print_log(self.agent.jid.user, "⏳ Currently processing request, waiting...")
                    await asyncio.sleep(1)  # Short wait before checking queue again
                    continue

                # If no queued requests and not processing, wait for new messages
                print_log(self.agent.jid.user, "📥 Waiting for field requests...")
                msg = await self.receive(timeout=2)  # Shorter timeout for more responsive queue checking
                
                if msg:
                    ontology = msg.metadata.get("ontology")
                    # Accept monitoring, fertilization, and treatment requests
                    if ontology in ["monitoring_request", "fertilization_request", "treatment_request"]:
                        request_data = {
                            "ontology": ontology,
                            "field_data": msg.body,
                            "field_agent": str(msg.sender)
                        }
                        
                        if self.agent.processing_request:
                            # Currently processing, add to queue
                            self.agent.request_queue.append(request_data)
                            print_log(self.agent.jid.user, f"📋 Request queued: {ontology} (queue size: {len(self.agent.request_queue)})")
                            # Continue the loop to keep checking
                            continue
                        else:
                            # Not processing, handle immediately
                            self.set("ontology", ontology)
                            self.set("field_data", msg.body)
                            self.set("field_agent", str(msg.sender))
                            self.agent.processing_request = True
                            self.set_next_state("SEND_CFP")
                            return
                    else:
                        print_log(self.agent.jid.user, f"⚠️ Unknown request: {ontology}")
                        # Continue the loop
                        continue
                else:
                    # Timeout occurred - this is normal, just continue the loop to check queue again
                    print_log(self.agent.jid.user, "🕒 No new messages, checking queue...")
                    continue

    class SendCFP(State):
        async def run(self):
            ontology = self.get("ontology")
            field_data = self.get("field_data")
            
            # Decide which drones to send CFP to
            if ontology == "monitoring_request":
                drones = self.agent.vigilant_drones
                drone_type = "vigilant"
            else:  # fertilization_request or treatment_request
                drones = self.agent.payload_drones
                drone_type = "payload"

            if not drones:
                print_log(self.agent.jid.user, f"⚠️ No {drone_type} drones available for {ontology}")
                self.agent.processing_request = False
                self.set_next_state("WAIT")
                return

            print_log(self.agent.jid.user, f"📤 Sending CFP for {ontology}: {field_data} to {len(drones)} {drone_type} drones")
            
            # Send CFP to ALL appropriate drones
            cfp_messages = []
            for drone in drones:
                cfp = Message(to=drone)
                cfp.set_metadata("performative", "cfp")
                # Use the right ontology for drones
                if ontology == "treatment_request":
                    cfp.set_metadata("ontology", "pesticide_request")
                else:
                    cfp.set_metadata("ontology", ontology)
                cfp.body = field_data
                cfp_messages.append(cfp)

            # Send all CFPs
            for cfp in cfp_messages:
                await self.send(cfp)
                print_log(self.agent.jid.user, f"📤 CFP sent to {cfp.to}")

            self.agent.proposals = []
            self.agent.responders = drones
            self.set_next_state("COLLECT_PROPOSALS")

    class CollectProposals(State):
        async def run(self):
            ontology = self.get("ontology")
            print_log(self.agent.jid.user, f"📨 Collecting proposals for {ontology}...")
            
            start = asyncio.get_event_loop().time()
            proposal_timeout = 8  # Increased timeout for better collection
            
            while asyncio.get_event_loop().time() - start < proposal_timeout:
                msg = await self.receive(timeout=1)
                if msg:
                    performative = msg.metadata.get("performative")
                    msg_ontology = msg.metadata.get("ontology")
                    
                    if performative == "proposal":
                        # Handle proposal messages as before
                        sender = str(msg.sender).split("/")[0]
                        try:
                            drone_name, battery, wind = msg.body.split("|")
                            score = evaluate_proposal(float(battery), float(wind))
                            print_log(self.agent.jid.user, f"📊 Proposal from {drone_name}: Battery={battery}%, Wind={wind}km/h, Score={score:.2f}")
                            self.agent.proposals.append((sender, score, msg.body, drone_name))
                        except Exception as e:
                            print_log(self.agent.jid.user, f"⚠️ Malformed proposal from {sender}: {e}")
                    
                    elif msg_ontology in ["monitoring_request", "fertilization_request", "treatment_request"]:
                        # Queue new field requests that arrive while collecting proposals
                        request_data = {
                            "ontology": msg_ontology,
                            "field_data": msg.body,
                            "field_agent": str(msg.sender)
                        }
                        self.agent.request_queue.append(request_data)
                        print_log(self.agent.jid.user, f"📋 Request queued while collecting proposals: {msg_ontology} (queue size: {len(self.agent.request_queue)})")

            print_log(self.agent.jid.user, f"📋 Collected {len(self.agent.proposals)} proposals from {len(self.agent.responders)} drones")

            if self.agent.proposals:
                # Sort proposals by score (best first)
                self.agent.proposals.sort(key=lambda p: p[1], reverse=True)
                best_drone = self.agent.proposals[0]
                
                print_log(self.agent.jid.user, f"🏆 Best proposal: {best_drone[3]} (score: {best_drone[1]:.2f})")
                
                # Send acceptance to best drone
                decision = Message(to=best_drone[0])
                decision.set_metadata("performative", "accept_proposal")
                # Use correct ontology for drone accept
                if ontology == "treatment_request":
                    decision.set_metadata("ontology", "pesticide_request")
                else:
                    decision.set_metadata("ontology", ontology)
                decision.body = self.get("field_data")
                await self.send(decision)
                print_log(self.agent.jid.user, f"✅ Assigned {ontology} to {best_drone[3]}")

                # Notify FieldAgent when a treatment is assigned
                if ontology == "treatment_request":
                    field_agent_jid = self.get("field_agent")
                    fa_msg = Message(to=field_agent_jid)
                    fa_msg.set_metadata("performative", "inform")
                    fa_msg.set_metadata("ontology", "treatment_assigned")
                    fa_msg.body = self.get("field_data")  # Pass field, coords, disease
                    await self.send(fa_msg)

                # Send rejections to other responders
                rejected_count = 0
                for responder in self.agent.responders:
                    if responder != best_drone[0]:
                        rejection = Message(to=responder)
                        rejection.set_metadata("performative", "reject_proposal")
                        rejection.set_metadata("ontology", ontology if ontology != "treatment_request" else "pesticide_request")
                        rejection.body = "Better proposal selected."
                        await self.send(rejection)
                        rejected_count += 1
                
                print_log(self.agent.jid.user, f"❌ Sent rejections to {rejected_count} drones")
            else:
                print_log(self.agent.jid.user, "⚠️ No proposals received. All drones might be busy or recharging.")

            # Mark processing as complete
            self.agent.processing_request = False
            self.set_next_state("WAIT")

    # central_agent.py - Go back to the simple working approach with all bug fixes:

    async def setup(self):
        # Hardcoded drone lists (simple and reliable)
        self.vigilant_drones = ["vigilant1@localhost", "vigilant2@localhost"]
        self.payload_drones = ["payload1@localhost", "payload2@localhost", "payload3@localhost"]  # All 3 drones
        
        # Initialize request processing state
        self.request_queue = deque()
        self.processing_request = False

        print_agent_header(self.jid.user)
        print_log(self.jid.user, f"{self.jid} is online.")
        print_log(self.jid.user, f"🚁 Managing {len(self.vigilant_drones)} vigilant drones and {len(self.payload_drones)} payload drones")

        # Add contract net FSM with ALL necessary transitions
        fsm = self.ContractNetManager()
        fsm.add_state(name="WAIT", state=self.WaitRequest(), initial=True)
        fsm.add_state(name="SEND_CFP", state=self.SendCFP())
        fsm.add_state(name="COLLECT_PROPOSALS", state=self.CollectProposals())

        # All transitions (including the critical missing one)
        fsm.add_transition("WAIT", "SEND_CFP")
        fsm.add_transition("SEND_CFP", "COLLECT_PROPOSALS")
        fsm.add_transition("SEND_CFP", "WAIT")  # ← This was the original bug!
        fsm.add_transition("COLLECT_PROPOSALS", "WAIT")
        fsm.add_transition("WAIT", "WAIT")

        self.add_behaviour(fsm)