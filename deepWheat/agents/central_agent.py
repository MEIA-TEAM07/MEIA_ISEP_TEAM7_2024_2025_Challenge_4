from spade.agent import Agent
from spade.behaviour import FSMBehaviour, State, CyclicBehaviour
from spade.message import Message
from spade.template import Template
from utils.logger import print_log, print_agent_header
from utils.negotiation import evaluate_proposal
import asyncio
from collections import deque
import threading
from config import (ONTOLOGY_DRONE_REGISTRATION_ACK, STATE_WAIT, STATE_COLLECT_PROPOSALS, STATE_CFP, PROPOSAL_TIMEOUT, RECEIVE_TIMEOUT, 
                    PERFORMATIVE, PERFORMATIVE_PROPOSAL, ONTOLOGY, ONTOLOGY_PESTICIDE, LIST_OF_REQUEST_ONTOLOGIES,
                    ONTOLOGY_DRONE_REGISTRATION, PERFORMATIVE_REGISTER, PERFORMATIVE_CONFIRM, TYPE_DRONE_PAYLOAD, TYPE_DRONE_VIGILANT,)

class CentralAgent(Agent):

    def __init__(self, jid, password):
        super().__init__(jid, password)
        self.vigilant_drones = []
        self.payload_drones = []
        self.available_drones = ["vigilant1@localhost", "payload1@localhost"]  # All drones are initially available
        self.request_queue = deque()
        
        self.reqlock = threading.Lock()
        self.dlock = threading.Lock()

    def pop_request(self):
        with self.reqlock:
            if self.request_queue:
                return self.request_queue.popleft()
            return None
        
    def add_request(self, request_data):
        with self.reqlock:
            self.request_queue.append(request_data)

    def drone_available(self, drone_jid):
        with self.dlock:
            if drone_jid not in self.available_drones and drone_jid in self.vigilant_drones and drone_jid in self.payload_drones:
                self.available_drones.append(drone_jid)
                print_log(self.jid.user, f"✅ Drone available: {drone_jid.split('.')[0]}")
            elif drone_jid not in self.vigilant_drones and drone_jid not in self.payload_drones:
                print_log(self.jid.user, f"⚠️ Drone not registered: {drone_jid.split('.')[0]}")
            elif drone_jid in self.available_drones:
                print_log(self.jid.user, f"⚠️ Drone already marked as available: {drone_jid.split('.')[0]}")

    def drone_unavailable(self, drone_jid):
        with self.dlock:
            if drone_jid in self.available_drones and drone_jid in self.vigilant_drones and drone_jid in self.payload_drones:
                self.available_drones.remove(drone_jid)
                print_log(self.jid.user, f"❌ Drone unavailable: {drone_jid.split('.')[0]}")
            elif drone_jid not in self.vigilant_drones and drone_jid not in self.payload_drones:
                print_log(self.jid.user, f"⚠️ Drone not registered: {drone_jid.split('.')[0]}")
            elif drone_jid not in self.available_drones:
                print_log(self.jid.user, f"⚠️ Drone already marked as unavailable: {drone_jid.split('.')[0]}")


    class DroneRegistration(CyclicBehaviour):
        """Handles drone registration and deregistration"""
        async def run(self):
            msg = await self.receive(timeout=1)
            if msg:
                ontology = msg.metadata.get(ONTOLOGY)
                performative = msg.metadata.get(PERFORMATIVE)

                if ontology == ONTOLOGY_DRONE_REGISTRATION:
                    if performative == PERFORMATIVE_REGISTER:
                        # Handle drone registration
                        try:
                            drone_type, drone_jid = msg.body.split("|")
                            drone_jid_str = str(drone_jid).split("/")[0]  # Clean JID format
                            
                            if drone_type == TYPE_DRONE_PAYLOAD:
                                if drone_jid_str not in self.agent.payload_drones:
                                    self.agent.payload_drones.append(drone_jid_str)
                                    print_log(self.agent.jid.user, f"✅ Registered payload drone: {drone_jid_str}")
                            elif drone_type == TYPE_DRONE_VIGILANT:
                                if drone_jid_str not in self.agent.vigilant_drones:
                                    self.agent.vigilant_drones.append(drone_jid_str)
                                    print_log(self.agent.jid.user, f"✅ Registered vigilant drone: {drone_jid_str}")
                                    
                            # Send acknowledgment
                            ack = Message(to=str(msg.sender))
                            ack.set_metadata(PERFORMATIVE, PERFORMATIVE_CONFIRM)
                            ack.set_metadata(ONTOLOGY, ONTOLOGY_DRONE_REGISTRATION_ACK)
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

    class RequestReception(CyclicBehaviour):
        async def run(self):
            msg = await self.receive()
            if msg:
                ontology = msg.metadata.get(ONTOLOGY)
                # Accept monitoring, fertilization, and treatment requests
                if ontology in LIST_OF_REQUEST_ONTOLOGIES:
                    request_data = {
                        "ontology": ontology,
                        "field_data": msg.body,
                        "field_agent": str(msg.sender)
                    }
                    self.agent.add_request(request_data)
                    print_log(self.agent.jid.user, f"📋 Received {ontology} from {msg.sender}: {msg.body}")
                else:
                    print_log(self.agent.jid.user, f"⚠️ Unknown request ontology: {ontology}")

    class DroneStatusUpdate(CyclicBehaviour):
        async def run(self):
            msg = await self.receive()
            if msg:
                if msg.sender: 
                    drone_jid = str(msg.sender)
                    if msg.metadata.get("ontology") == "drone_status_update" and msg.metadata.get("performative") == "inform":
                        status = msg.body
                        print_log(self.agent.jid.user, f"📊 Drone status update from {drone_jid.split('.')[0]}: {status}")
                        # Here you could implement logic to handle drone status updates
                        # For example, update internal state or notify field agents
                        if status == "available":
                            self.agent.drone_available(drone_jid)
                        elif status == "unavailable":
                            self.agent.drone_unavailable(drone_jid)
                else:
                    print_log(self.agent.jid.user, "⚠️ Received drone status update without sender JID. Ignoring.")


    class ContractNetManager(FSMBehaviour):
        async def on_start(self):
            print_agent_header(self.agent.jid.user)
            print_log(self.agent.jid.user, "🧠 Starting ContractNetManager...")
            # Initialize request queue
            self.agent.request_queue = deque()
        async def on_end(self):
            print_log(self.agent.jid.user, "✅ Contract negotiation finished.")

    class WaitRequest(State):
        async def run(self):
            if self.agent.request_queue:
                self.set_next_state(STATE_CFP)
                return
            else:
                self.set_next_state(STATE_WAIT)

    class SendCFP(State):
        async def run(self):
            print_log(self.agent.jid.user, f"📋 Processing queued request ({len(self.agent.request_queue)} in queue)")
            request_data = self.agent.pop_request()
            if not request_data:
                print_log(self.agent.jid.user, "⚠️ No request data found. Returning to WAIT state.")
                self.set_next_state(STATE_WAIT)
                return
            self.ontology = request_data[ONTOLOGY]
            field_data = request_data["field_data"]
            field_agent = request_data["field_agent"]
            drones = []
            # Get available drones based on ontology
            if self.ontology == "monitoring_request":
                drones = self.agent.vigilant_drones
                drone_type = "vigilant"
                if any(drone in self.agent.available_drones for drone in drones):
                    print_log(self.agent.jid.user, f"📦 Found available {drone_type} drones for {self.ontology}")
                    await self.send_cfp(self.ontology, field_data, drones)
                    return
                else:
                    print_log(self.agent.jid.user, f"⚠️ No available {drone_type} drones for {self.ontology}. Cannot process monitoring request.")
                    self.agent.add_request(request_data)
                    self.set_next_state(STATE_WAIT)
                    return
            elif self.ontology == "fertilization_request":
                drones = self.agent.payload_drones
                drone_type = "payload"
                if any(drone in self.agent.available_drones for drone in drones):
                    print_log(self.agent.jid.user, f"📦 Found available {drone_type} drones for {self.ontology}")
                    await self.send_cfp(self.ontology, field_data, drones)   
                    return
                else:
                    print_log(self.agent.jid.user, f"⚠️ No available {drone_type} drones for {self.ontology}. Cannot process fertilization request.")
                    self.agent.add_request(request_data)
                    self.set_next_state(STATE_WAIT)
                    return
            elif self.ontology == "treatment_request":
                drones = self.agent.payload_drones
                drone_type = "payload"
                if any(drone in self.agent.available_drones for drone in drones):
                    print_log(self.agent.jid.user, f"📦 Found available {drone_type} drones for {self.ontology}")
                    await self.send_cfp(self.ontology, field_data, drones)
                    return
                else:
                    print_log(self.agent.jid.user, f"⚠️ No available {drone_type} drones for {self.ontology}. Cannot process treatment request.")
                    self.agent.add_request(request_data)
                    self.set_next_state(STATE_WAIT)
                    return
            else:
                print_log(self.agent.jid.user, f"⚠️ Unknown request ontology: {self.ontology}")
                self.set_next_state(STATE_WAIT)
                return
            
        async def send_cfp(self, ontology, field_data, drones):
            for drone in drones:
                cfp = Message(to=drone)
                cfp.set_metadata("performative", "cfp")
                cfp.set_metadata("ontology", ontology)
                cfp.body = field_data 
                await self.send(cfp)
                print_log(self.agent.jid.user, f"📤 Sent CFP to {drone.split('.')[0]} for {ontology} in field {field_data}")
            self.agent.responders = drones
            self.agent.proposals = []
            
            self.set("ontology", ontology)
            self.set("field_data", field_data)

            self.set_next_state(STATE_COLLECT_PROPOSALS)
            return

    class CollectProposals(State):
        async def run(self):
            self.ontology = self.get("ontology")
            print_log(self.agent.jid.user, f"📨 Collecting proposals for {self.ontology}...")
            
            start = asyncio.get_event_loop().time()
            
            while asyncio.get_event_loop().time() - start < PROPOSAL_TIMEOUT:
                msg = await self.receive()
                if msg:
                    performative = msg.metadata.get(PERFORMATIVE)
                    msg_ontology = msg.metadata.get(ONTOLOGY)

                    if performative == PERFORMATIVE_PROPOSAL:
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
                        self.agent.add_request(request_data)
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
                if self.ontology == "treatment_request":
                    decision.set_metadata("ontology", "pesticide_request")
                else:
                    decision.set_metadata("ontology", self.ontology)
                decision.body = self.get("field_data")
                await self.send(decision)
                print_log(self.agent.jid.user, f"✅ Assigned {self.ontology} to {best_drone[3]}")

                # Notify FieldAgent when a treatment is assigned
                if self.ontology == "treatment_request":
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
                        rejection.set_metadata("ontology", self.ontology if self.ontology != "treatment_request" else "pesticide_request")
                        rejection.body = "Better proposal selected."
                        await self.send(rejection)
                        rejected_count += 1
                
                print_log(self.agent.jid.user, f"❌ Sent rejections to {rejected_count} drones")
            else:
                print_log(self.agent.jid.user, "⚠️ No proposals received. All drones might be busy or recharging.")

            # Mark processing as complete
            self.set_next_state(STATE_WAIT)

    # central_agent.py - Go back to the simple working approach with all bug fixes:

    async def setup(self):

        self.tmplRegistration = Template()
        self.tmplStatusUpdate = Template()
        self.tmplRequest = Template()
        self.tmplProposal = Template()

        self.tmplRegistration.set_metadata("ontology", "drone_registration")
        self.tmplStatusUpdate.set_metadata("ontology", "drone_status_update")
        self.tmplRequest.set_metadata("performative", "request")
        # Templates para cada ontology
        ontologies = ["monitoring_request", "fertilization_request",
                      "treatment_request", "pesticide_request"]
        tmpl_onts = [Template().set_metadata("ontology", ont) or Template() for ont in ontologies]

        # Templates para cada performative
        tmpl_cfp   = Template(); tmpl_cfp.set_metadata("performative", "cfp")
        tmpl_prop  = Template(); tmpl_prop.set_metadata("performative", "proposal")

        # Combinações
        any_ontology = tmpl_onts[0] | tmpl_onts[1] | tmpl_onts[2] | tmpl_onts[3]
        any_perf     = tmpl_cfp | tmpl_prop

        self.combined_tmpl = any_ontology & any_perf
        self.combined_tmpl2 = any_ontology & self.tmplRequest
        
        #self.add_behaviour(self.DroneRegistration(), template=self.tmplRegistration)
        self.add_behaviour(self.DroneStatusUpdate(), self.tmplStatusUpdate)
        self.add_behaviour(self.RequestReception(), self.combined_tmpl2)

        # Hardcoded drone lists (simple and reliable)
        self.vigilant_drones = ["vigilant1@localhost", "vigilant2@localhost"]
        self.payload_drones = ["payload1@localhost", "payload2@localhost", "payload3@localhost"]  # All 3 drones
        
        # Initialize request processing state
        self.request_queue = deque()

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

        self.add_behaviour(fsm, self.combined_tmpl)