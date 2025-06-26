import asyncio
import random
from datetime import datetime

from attrs import field
from offboard.offboard_control import OffboardControl
from spade.agent import Agent
from offboard import routing_service
from spade.message import Message

from utils.logger import print_log, print_agent_header
from utils.battery import compute_battery_usage, drain_battery
from utils.season import is_growth_season
from utils.field_map import shared_field_map
from spade.behaviour import CyclicBehaviour, FSMBehaviour, State
from config import (BATTERY_LOW_THRESHOLD, BATTERY_RECHARGE_STEP, ONTOLOGY_DRONE_REGISTRATION_ACK, ONTOLOGY_FERTILIZATION, ONTOLOGY_TREATMENT, PERFORMATIVE_ACCEPT, PERFORMATIVE_CFP, 
                    PERFORMATIVE_CONFIRM, PERFORMATIVE_INFORM, PERFORMATIVE_REJECT, RECHARGE_INTERVAL, FLIGHT_TIME, APPLICATION_TIME, WIND_MIN, WIND_MAX, FIELD_ROWS, 
                    FIELD_COLS, FIELD_AGENT_ASSIGNMENT, ONTOLOGY_FERTILIZATION_REQUEST, ONTOLOGY_PESTICIDE_REQUEST, ONTOLOGY_DISEASE_ALERT, 
                    ONTOLOGY, PERFORMATIVE, PERFORMATIVE_PROPOSAL, LIST_OF_REQUEST_ONTOLOGIES)

class PayloadDroneAgent(Agent):
    def __init__(self, jid, password, ros):
        super().__init__(jid, password)
        self.ros_node = ros

    class TaskHandler(CyclicBehaviour):
        async def run(self):
            msg = await self.receive(timeout=5)
            if msg:
                performative = msg.metadata.get(PERFORMATIVE)
                ontology = msg.metadata.get(ONTOLOGY)

                if performative == PERFORMATIVE_CFP and ontology in LIST_OF_REQUEST_ONTOLOGIES:

                    field_info = msg.body
                    print_log(self.agent.jid.user, f"📩 Received CFP for {ontology} at {field_info}")

                    # Respond with proposal
                    proposal = Message(to=str(msg.sender))
                    proposal.set_metadata(PERFORMATIVE, PERFORMATIVE_PROPOSAL)
                    proposal.set_metadata(ONTOLOGY, ontology)
                    proposal.body = f"{self.agent.jid.user}|{self.agent.battery_level}|{self.agent.wind_speed:.2f}"
                    await self.send(proposal)
                    print_log(self.agent.jid.user, f"📤 Sent proposal for {ontology} at {field_info}")

                elif performative == PERFORMATIVE_ACCEPT and ontology in LIST_OF_REQUEST_ONTOLOGIES:
                    field_info = msg.body
                    print_log(self.agent.jid.user, f"✅ Proposal accepted for {ontology} at {field_info}")
                    if ontology == ONTOLOGY_FERTILIZATION:
                        field_id = field_info.split("|")[0]
                        self.agent.target_field = field_id
                        self.agent.payload = "fertilizer"
                    elif ontology == ONTOLOGY_TREATMENT:
                        x,y = field_info.split("|")[1:]
                        field_id = field_info.split("|")[0]
                        self.agent.target_field = field_id
                        self.agent.target_position = (x, y)
                        self.agent.payload = "treatment"

                elif performative == PERFORMATIVE_REJECT:
                    print_log(self.agent.jid.user, f"❌ Proposal rejected: {msg.body}")

                # Handle registration acknowledgments
                elif performative == PERFORMATIVE_CONFIRM and ontology == ONTOLOGY_DRONE_REGISTRATION_ACK:
                    print_log(self.agent.jid.user, f"✅ Registration confirmed: {msg.body}")

                elif performative == PERFORMATIVE_INFORM and ontology == ONTOLOGY_DISEASE_ALERT:
                    # Not used for this agent but kept for compatibility
                    print_log(self.agent.jid.user, f"🦠 Alert received: {msg.body}")

                else:
                    print_log(self.agent.jid.user, f"⚠️ Unknown message received: {msg.metadata}, body: {msg.body}")

    class PayloadFSM(FSMBehaviour):
        async def on_start(self):
            print_agent_header(self.agent.jid.user)
            print_log(self.agent.jid.user, "🚁 Vigilant Drone FSM starting...")

        async def on_end(self):
            print_log(self.agent.jid.user, "🛬 Vigilant Drone FSM finished.")

    class Idle(State):
        async def run(self):
            # Wait for a task assignment
            if self.agent.target_field:
                print_log(self.agent.jid.user, f"🚀 Task assigned: {self.agent.target_field} ({self.agent.payload})")
                self.set_next_state("NAVIGATE")
            else:
                await asyncio.sleep(3)  # Idle polling
                self.set_next_state("IDLE")

    class NavigateToField(State):
        async def run(self):
            if self.agent.payload == 'treatment':
                field_id = self.agent.target_field
                print(field_id)
                if self.agent.waypoint:
                    self.target_waypoints = self.agent.waypoint 
                    self.agent.waypoint = None 
                    self.agent.offboard_control.apply_fungicide(self.target_waypoints)
                    print_log(self.agent.jid.user, f"🧭 Navigating to field {field_id} with payload {self.agent.payload}")
                    self.set_next_state("TREAT")
                else:
                    print_log(self.agent.jid.user, f"🛬 No waypoint set for field {field_id} — returning to idle.")
                    self.set_next_state("IDLE")
            elif self.agent.payload == 'fertilize':
                field_id = self.agent.target_field
                print(field_id)
                self.target_waypoints = shared_field_map.return_plant_locations_by_field(field_id)
                print(self.target_waypoints)
                self.target_waypoints = routing_service.find_shortest_zigzag_path(self.target_waypoints,[self.agent.offboard_control.current_x, self.agent.offboard_control.current_y, self.agent.offboard_control.flying_altitude])
                self.target_waypoints.pop(0)
                self.agent.offboard_control.fertilize(self.target_waypoints)
                print_log(self.agent.jid.user, f"🧭 Navigating to field {field_id} with payload {self.agent.payload}")
                self.set_next_state("FERTILIZE")
            else:
                self.set_next_state("IDLE")

    class Fertilize(State):
        async def run(self):
            field_id = self.agent.target_field
            print_log(self.agent.jid.user, f"🌾 Starting full field fertilization for {field_id}")
            msg = await self.receive()
            if msg:
                print(msg)
                performative = msg.metadata.get("performative")
                ontology = msg.metadata.get("ontology")
                if performative == "inform" and ontology == "fertilization_complete":
                    print_log(self.agent.jid.user, f"✅ Fertilization complete for {field_id}")
            self.set_next_state("RETURN")

    class Treat(State):
        async def run(self):
            field_id = self.agent.target_field
            print_log(self.agent.jid.user, f"🧪 Applying pesticide at {field_id}")
            msg = await self.receive()
            if msg:
                print(msg)
                performative = msg.metadata.get("performative")
                ontology = msg.metadata.get("ontology")
                if performative == "inform" and ontology == "treatment_complete":
                    print_log(self.agent.jid.user, f"✅ Treatment complete at {field_id}")
            self.set_next_state("RETURN")

    class Return(State):
        async def run(self):
            print_log(self.agent.jid.user, "🏠 Returning to base for recharge or next assignment...")
            self.agent.target_field = None
            self.agent.target_position = None
            self.agent.waypoint = None
            self.agent.payload = None
            self.set_next_state("IDLE")

    def create_fsm(self):
        fsm = self.VigilantFSM()
        fsm.agent = self
        fsm.add_state(name="IDLE", state=self.Idle(), initial=True)
        fsm.add_state(name="NAVIGATE", state=self.NavigateToField())
        fsm.add_state(name="TREAT", state=self.Treat())
        fsm.add_state(name="FERTILIZE", state=self.Fertilize())
        fsm.add_state(name="RETURN", state=self.Return())
        fsm.add_transition("IDLE", "NAVIGATE")
        fsm.add_transition("NAVIGATE", "TREAT")
        fsm.add_transition("NAVIGATE", "FERTILIZE")
        fsm.add_transition("TREAT", "RETURN")
        fsm.add_transition("FERTILIZE", "RETURN")
        fsm.add_transition("RETURN", "IDLE")
        fsm.add_transition("IDLE", "IDLE")
        return fsm

    async def setup(self):
        await super().setup()
        


        self.fsm = self.create_fsm()
        self.add_behaviour(self.fsm, self.tmpl)

        self.offboard_control = OffboardControl(self.ros_node, str(self.id), self.jid, self.fsm)
        self.loop = asyncio.get_event_loop()
        self.offboard_control.set_loop(self.loop)        

        self.agent.target_position = None
        self.waypoint = None
        self.target_field = None
        self.payload = None

        print_agent_header(self.jid.user)
        print_log(self.jid.user, f"{self.jid} is online.")
        print_log(self.jid.user, f"🔧 Default payload set to: {self.payload}")
        print_log(self.jid.user, f"🚁 PayloadDrone: Waiting for tasks... Current payload: {self.payload}")



        self.add_behaviour(self.TaskHandler())