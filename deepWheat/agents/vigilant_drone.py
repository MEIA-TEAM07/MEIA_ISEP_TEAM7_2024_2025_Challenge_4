import asyncio
import random
from spade.agent import Agent
from spade.behaviour import FSMBehaviour, State
from spade.message import Message
from spade.behaviour import CyclicBehaviour
from utils.battery import compute_battery_usage, drain_battery
from utils.logger import print_log, print_agent_header
from utils.field_map import shared_field_map
from config import (
    BATTERY_LOW_THRESHOLD,
    BATTERY_RECHARGE_STEP,
    RECHARGE_INTERVAL,
    FLIGHT_TIME,
    WIND_MIN,
    WIND_MAX,
    FIELD_AGENTS
)
from offboard import routing_service
from offboard.offboard_control import OffboardControl
from spade.template import Template

def field_id_to_agent(field_id):
    # Looks up the correct agent for a field
    for fa in FIELD_AGENTS:
        if fa["field_id"] == field_id:
            return fa["agent_jid"]
    return None

class VigilantDroneAgent(Agent):
    def __init__(self, jid, password, ros_node, id):
        super().__init__(jid, password)
        self.ros_node = ros_node
        self.id = id

    class VigilantFSM(FSMBehaviour):
        async def on_start(self):
            print_agent_header(self.agent.jid.user)
            print_log(self.agent.jid.user, "🚁 Vigilant Drone FSM starting...")

        async def on_end(self):
            print_log(self.agent.jid.user, "🛬 Vigilant Drone FSM finished.")

    class NegotiationBehaviour(CyclicBehaviour):
        async def run(self):
            msg = await self.receive(timeout=5)
            if msg:
                performative = msg.metadata.get("performative")
                ontology = msg.metadata.get("ontology")
                
                if performative == "cfp":
                    if self.agent.recharging:
                        print_log(self.agent.jid.user, f"🔌 Currently recharging — ignoring CFP.")
                        return
                    if self.agent.fsm.current_state != "IDLE":
                        print_log(self.agent.jid.user, f"🚁 Not in IDLE state — ignoring CFP.")
                        return
                    field_id = msg.body
                    proposal = Message(to="central@localhost")
                    proposal.set_metadata("performative", "proposal")
                    proposal.set_metadata("ontology", "monitoring_request")  # Fixed ontology
                    proposal.body = f"{self.agent.jid.user}|{self.agent.battery_level}|{self.agent.wind_speed:.2f}"
                    await self.send(proposal)
                    
                elif performative == "accept_proposal":
                    field_id = msg.body
                    fsm = self.agent.create_fsm()
                    self.agent.add_behaviour(fsm)
                    print(msg)
                    field_id, _ = msg.body.split("|")
                    self.agent.target_field = field_id
                    print(f"🔍 Target field set to: {self.agent.target_field}")
                    print_log(self.agent.jid.user, "🔥 Proposal accepted.")
                    
                elif performative == "reject_proposal":
                    print_log(self.agent.jid.user, "❌ Proposal rejected.")
                    
                # Handle registration acknowledgments
                elif performative == "confirm" and ontology == "registration_ack":
                    print_log(self.agent.jid.user, f"✅ Registration confirmed: {msg.body}")
                else:
                    try:
                        print(msg)
                        field_id, _ = msg.body.split("|")
                        self.agent.target_field = field_id
                        print(f"🔍 Target field set to: {self.agent.target_field}")
                    except Exception as e:
                        print_log(self.agent.jid.user, f"⚠️ Invalid message format. {e}")
                        return

    class Idle(State):
        async def run(self):
            if self.agent.target_field:
                self.set_next_state("NAVIGATE")
            else:
                self.set_next_state("IDLE")

    class NavigateToField(State):
        async def run(self):
            
            field_id = self.agent.target_field
            print(field_id)
            self.target_waypoints = shared_field_map.return_plant_locations_by_field(field_id)
            self.target_waypoints.insert(0, [0.0, 0.0, -1.3])
            self.target_waypoints = routing_service.find_shortest_path(self.target_waypoints)
            self.agent.offboard_control.scan(self.target_waypoints)
            print_log(self.agent.jid.user, f" Navigating to field: {field_id}")
            
            await asyncio.sleep(FLIGHT_TIME)
            self.agent.consume_battery(base_cost=5.0)
            if self.agent.battery_level < BATTERY_LOW_THRESHOLD:
                print_log(self.agent.jid.user, "❗ Battery too low to continue. Returning to base.")
                self.set_next_state("RETURN")
            else:
                self.set_next_state("SCAN")

    class ScanField(State):
        async def run(self):
            field_id = self.agent.target_field
            msg = await self.receive()
            if msg:
                print(msg)
                performative = msg.metadata.get("performative")
                ontology = msg.metadata.get("ontology")
                if performative == "inform" and ontology == "disease_alert":
                    body= msg.body
                    disease, x_str, y_str = body.split(", ")
                    x = float(x_str)
                    y = float(y_str)
                    pos = (x, y)
                    plant = shared_field_map.get_plant(field_id, pos)
                    status = plant["status"] if plant else "unknown"
                    being_treated = plant["being_treated"] if plant else False
                    try:
                        if status in ("healthy", "unknown") and not being_treated:
                            field_agent_jid = field_id_to_agent(field_id)
                            status = disease
                            if field_agent_jid:
                                print_log(self.agent.jid.user, f"🦠 Disease ({status}) detected at {field_id} {pos} — reporting to {field_agent_jid}")
                                msg = Message(to=field_agent_jid)
                                msg.set_metadata("performative", "inform")
                                msg.set_metadata("ontology", "disease_alert")
                                msg.body = f"{field_id}|{x},{y}|{status}"
                                print(msg)
                                await self.send(msg)
                    except Exception as e:
                        print_log(self.agent.jid.user, f"❗ Error reporting disease: {e}")

                elif performative == "inform" and ontology == "completed_scan":
                    print_log(self.agent.jid.user, "✅ Scan completed successfully.")
                    self.set_next_state("REPORT")

                # Report if there's a disease and it's not already being treated
             

            self.set_next_state("SCAN")

    class ReportFinding(State):
        async def run(self):
            self.set_next_state("RETURN")

    class ReturnToBase(State):
        async def run(self):
            print_log(f"{self.agent.jid.user}", "🔙 Returning to base...")
            self.set_next_state("IDLE")

    def consume_battery(self, base_cost=5.0):
        usage = compute_battery_usage(base_cost, self.wind_speed)
        self.battery_level = drain_battery(self.battery_level, usage)
        print_log(self.jid.user, f"🔋 Battery after flying: {self.battery_level:.2f}% (used {usage:.2f}%)")
    
    def create_fsm(self):
        fsm = self.VigilantFSM()
        fsm.agent = self
        fsm.add_state(name="IDLE", state=self.Idle(), initial=True)
        fsm.add_state(name="NAVIGATE", state=self.NavigateToField())
        fsm.add_state(name="SCAN", state=self.ScanField())
        fsm.add_state(name="REPORT", state=self.ReportFinding())
        fsm.add_state(name="RETURN", state=self.ReturnToBase())
        fsm.add_transition("IDLE", "NAVIGATE")
        fsm.add_transition("NAVIGATE", "SCAN")
        fsm.add_transition("SCAN", "SCAN")
        fsm.add_transition("SCAN", "REPORT")
        fsm.add_transition("REPORT", "RETURN")
        fsm.add_transition("RETURN", "IDLE")
        fsm.add_transition("IDLE", "IDLE")

        return fsm

    async def setup(self):
        await super().setup()
        try:
            self.tmpl = Template()
            self.tmpl.sender = str(self.jid)
            self.tmpl.metadata = {
                "performative": "inform",
                "ontology": "disease_alert"
            }
            self.tmpl2 = Template()
            self.tmpl2.sender = "central@localhost"
            
            self.recharging = False
            self.wind_speed = random.uniform(WIND_MIN, WIND_MAX)
            self.battery_level = 100.0
            print(f"🌬️ Wind Speed: {self.wind_speed:.2f} km/h")
            print(f"🔋 Initial Battery: {self.battery_level}%")
            print(f"🚁 VigilantDroneAgent {self.jid} is online.")
            
            self.fsm = self.create_fsm()
            self.add_behaviour(self.fsm, self.tmpl)
            self.add_behaviour(self.NegotiationBehaviour(), self.tmpl2)
            self.offboard_control = OffboardControl(self.ros_node, str(self.id), self.jid, self.fsm)
            self.loop = asyncio.get_event_loop()
            self.offboard_control.set_loop(self.loop)
            self.target_field = None
        except Exception as e:
            print(f"❗ Error during setup: {e}")