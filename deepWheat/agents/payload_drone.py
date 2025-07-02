import asyncio
import random
from datetime import datetime
import re

from attrs import field
from offboard.offboard_control import OffboardControl
from spade.agent import Agent
from offboard import routing_service
from spade.message import Message
from spade.template import Template


from utils.logger import print_log, print_agent_header
from utils.battery import compute_battery_usage, drain_battery
from utils.season import is_growth_season
from utils.field_map import shared_field_map
from spade.behaviour import CyclicBehaviour, FSMBehaviour, State
from config import (ONTOLOGY_DRONE_REGISTRATION_ACK, ONTOLOGY_FERTILIZATION, ONTOLOGY_TREATMENT, PERFORMATIVE_ACCEPT, PERFORMATIVE_CFP,
                    PERFORMATIVE_CONFIRM, PERFORMATIVE_INFORM, PERFORMATIVE_REJECT, ONTOLOGY_DISEASE_ALERT, ONTOLOGY, PERFORMATIVE,
                    PERFORMATIVE_PROPOSAL, LIST_OF_REQUEST_ONTOLOGIES, WIND_MAX, WIND_MIN ,ONTOLOGY_PESTICIDE)

class PayloadDroneAgent(Agent):
    def __init__(self, jid, password, ros, id):
        super().__init__(jid, password)
        self.ros_node = ros
        self.id = id
        self.flag = False
        self.flag_work = False

    class BatteryHandler(CyclicBehaviour):
        async def run(self):
            msg = await self.receive(timeout=5)
            if msg:

                performative = msg.metadata.get(PERFORMATIVE)
                ontology = msg.metadata.get(ONTOLOGY)

                if performative == PERFORMATIVE_INFORM and ontology  == "battery_alert":
                    proposal = Message(to="central@localhost")
                    proposal.set_metadata(PERFORMATIVE, PERFORMATIVE_INFORM)
                    proposal.set_metadata(ONTOLOGY, ontology)
                    proposal.body = f"{self.agent.jid.user}|{self.agent.offboard_control.battery_level}"
                    print_log(self.agent.jid.user, f"Battery proposal: {proposal}")
                    await self.send(proposal)
                elif performative == PERFORMATIVE_INFORM and ontology == "charge_permission":
                    print_log(self.agent.jid.user, f"Permissão de carregamento")
                    self.agent.offboard_control.receive_charger_available()
                elif performative == PERFORMATIVE_INFORM and ontology == "battery_charged":
                    inform = Message(to="central@localhost")
                    inform.set_metadata(PERFORMATIVE, PERFORMATIVE_INFORM)
                    inform.set_metadata(ONTOLOGY, ontology)
                    inform.body = f"{self.agent.jid.user}|{self.agent.offboard_control.battery_level}"
                    print_log(self.agent.jid.user, f"BATERIA CARREGADA: {inform}")
                    await self.send(inform)
                else:
                    print(f"{self.agent.jid}: BatteryHandler received message: {msg}")
                    return
    
 
    class TaskHandler(CyclicBehaviour):
        async def run(self):
            msg = await self.receive(timeout=5)
            
            if msg:

                performative = msg.metadata.get(PERFORMATIVE)
                ontology = msg.metadata.get(ONTOLOGY)
                
                if self.agent.flag_work == True and ontology not in ["completed_fertilize", "completed_fungicide"] :
                    return

                if performative == PERFORMATIVE_CFP and ontology in LIST_OF_REQUEST_ONTOLOGIES:
                    while self.agent.payload != None or self.agent.target_field != None:
                        await asyncio.sleep(0.1)
                    field_info = msg.body
                    print_log(self.agent.jid.user, f"📩 Received CFP for {ontology} at {field_info}")

                    # Respond with proposal
                    proposal = Message(to=str(msg.sender))
                    proposal.set_metadata(PERFORMATIVE, PERFORMATIVE_PROPOSAL)
                    proposal.set_metadata(ONTOLOGY, ontology)
                    proposal.body = f"{self.agent.jid.user}|{self.agent.offboard_control.battery_level}|{self.agent.wind_speed:.2f}"
                    print_log(self.agent.jid.user, f"Proposal: {proposal}")
                    await self.send(proposal)
                    print_log(self.agent.jid.user, f"📤 Sent proposal for {ontology} at {field_info} by {self.agent.jid.user}")

                elif performative == PERFORMATIVE_ACCEPT and ontology in LIST_OF_REQUEST_ONTOLOGIES:
                    while self.agent.payload != None or self.agent.target_field != None:
                        await asyncio.sleep(0.1)
                    field_info = msg.body
                    print_log(self.agent.jid.user, f"✅ Proposal accepted for {ontology} at {field_info}")
                    if ontology == ONTOLOGY_FERTILIZATION:
                        field_id = field_info.split("|")[0]
                        self.agent.target_field = field_id
                        self.agent.payload = "fertilizer"
                    elif ontology == ONTOLOGY_TREATMENT or ONTOLOGY_PESTICIDE:
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
                elif performative == PERFORMATIVE_INFORM and ontology == "completed_fungicide":
                    self.agent.flag = True
                    mail = re.sub(r'_(\d+)$', r'\1@localhost', self.agent.target_field)
                    position = self.agent.target_position[0]
                    fi_msg = Message(to=mail)
                    fi_msg.set_metadata("performative", "inform")
                    fi_msg.set_metadata("ontology", "completed_fungicide")
                    fi_msg.body = f"{self.agent.target_field}|{position}"  
                    print_log(self.agent.jid.user, f"MESSSAGE FOR FIELD {mail}: {fi_msg}")
                    await self.send(fi_msg)
                elif performative == PERFORMATIVE_INFORM and ontology == "completed_fertilize":
                    print_log(self.agent.jid.user, f"Received completed fertilization message")
                    self.agent.flag = True
                    mail = re.sub(r'_(\d+)$', r'\1@localhost', self.agent.target_field)
                    fi_msg = Message(to=mail)
                    fi_msg.set_metadata("performative", "inform")
                    fi_msg.set_metadata("ontology", "completed_fertilize")
                    fi_msg.body = f"{self.agent.target_field}"  
                    print_log(self.agent.jid.user, f"MESSSAGE FOR FIELD {mail}: {fi_msg}")
                    await self.send(fi_msg)
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
                self.agent.flag_work = True

                msg = Message(to="central@localhost")               # receiver
                msg.set_metadata("ontology", "drone_status_update") # match your ontology
                msg.set_metadata("performative", "inform")          # match your performative
                msg.body = f"{self.agent.jid}|unavailable"               # same body format
                await self.send(msg)    
                self.set_next_state("NAVIGATE")
            else:
                await asyncio.sleep(3)  # Idle polling
                self.set_next_state("IDLE")

    class NavigateToField(State):
        async def run(self):
            try:
                if self.agent.payload == 'treatment':
                    print_log(self.agent.jid.user, f"DRONE ID {str(self.agent.id)}")
                    field_id = self.agent.target_field
                    if self.agent.target_position:
                        target= self.agent.target_position[0]
                        self.target_position = list(map(float, target.split(",")))
                        flying_altitude = -2.3
                        self.target_position.append(flying_altitude)
                        self.target_waypoints = shared_field_map.return_plant_locations_by_field(field_id, flying_altitude)

                        self.initial_position = [self.agent.offboard_control.current_x, self.agent.offboard_control.current_y, flying_altitude]
                        self.target_waypoints = routing_service.find_shortest_fungicide_path(self.target_waypoints, self.target_position, self.initial_position)
                        self.agent.offboard_control.apply_fungicide(self.target_waypoints)
                        self.set_next_state("TREAT")
                    else:
                        print_log(self.agent.jid.user, f"🛬 No waypoint set for field {field_id} — returning to idle.")
                        self.set_next_state("IDLE")
                elif self.agent.payload == 'fertilizer':
                    field_id = self.agent.target_field
                    flying_altitude = -3.3
                    self.target_waypoints = shared_field_map.return_plant_locations_by_field(field_id, flying_altitude)
                    self.target_waypoints = routing_service.find_shortest_zigzag_path(self.target_waypoints,[self.agent.offboard_control.current_x, self.agent.offboard_control.current_y, flying_altitude])
                    self.target_waypoints.pop(0)
                    self.agent.offboard_control.fertilize(self.target_waypoints)
                    print_log(self.agent.jid.user, f"🧭 Navigating to field {field_id} with payload {self.agent.payload}")
                    self.set_next_state("FERTILIZE")
                else:
                    self.set_next_state("IDLE")
            except Exception as e:
                print(e)        

    class Fertilize(State):
        async def run(self):
            field_id = self.agent.target_field
            print_log(self.agent.jid.user, f"🌾 Starting full field fertilization for {field_id}")
            while self.agent.flag != True:
                await asyncio.sleep(1)
            print_log(self.agent.jid.user, f"✅ Fertilization complete at {field_id}")
            self.agent.flag = False
            self.set_next_state("RETURN")

    class Treat(State):
        async def run(self):
            field_id = self.agent.target_field
            print_log(self.agent.jid.user, f"🧪 Applying pesticide at {field_id}")
            while self.agent.flag != True:
                await asyncio.sleep(1)
            print_log(self.agent.jid.user, f"✅ Treatment complete at {field_id}")
            self.agent.flag = False
            self.set_next_state("RETURN")

    class Return(State):
        async def run(self):
            print_log(self.agent.jid.user, "🏠 Returning to base for recharge or next assignment...")
            self.agent.target_field = None
            self.agent.target_position = None
            self.agent.waypoint = None
            self.agent.payload = None
            self.agent.flag_work = False

            msg = Message(to="central@localhost")               # receiver
            msg.set_metadata("ontology", "drone_status_update") # match your ontology
            msg.set_metadata("performative", "inform")          # match your performative
            msg.body = f"{self.agent.jid}|available"               # same body format
            await self.send(msg)    

            self.set_next_state("IDLE")

    def create_fsm(self):
        fsm = self.PayloadFSM()
        fsm.agent = self
        fsm.add_state(name="IDLE", state=self.Idle(), initial=True)
        fsm.add_state(name="NAVIGATE", state=self.NavigateToField())
        fsm.add_state(name="TREAT", state=self.Treat())
        fsm.add_state(name="FERTILIZE", state=self.Fertilize())
        fsm.add_state(name="RETURN", state=self.Return())
        fsm.add_transition("IDLE", "NAVIGATE")
        fsm.add_transition("NAVIGATE", "TREAT")
        fsm.add_transition("NAVIGATE", "FERTILIZE")
        fsm.add_transition("NAVIGATE", "IDLE")
        fsm.add_transition("TREAT", "RETURN")
        fsm.add_transition("FERTILIZE", "RETURN")
        fsm.add_transition("RETURN", "IDLE")
        fsm.add_transition("IDLE", "IDLE")
        return fsm

    async def setup(self):

        try:
            await super().setup()
            self.fsm = self.create_fsm()
            self.add_behaviour(self.fsm)

            self.offboard_control = OffboardControl(self.ros_node, str(self.id), self.jid, self.fsm)
            self.loop = asyncio.get_event_loop()
            self.offboard_control.set_loop(self.loop)        
            self.wind_speed = random.uniform(WIND_MIN, WIND_MAX)
            self.target_position = None
            self.waypoint = None
            self.target_field = None
            self.payload = None

            print_agent_header(self.jid.user)
            print_log(self.jid.user, f"{self.jid} is online.")
            print_log(self.jid.user, f"🔧 Default payload set to: {self.payload}")
            print_log(self.jid.user, f"🚁 PayloadDrone: Waiting for tasks... Current payload: {self.payload}")


            # Assumindo que PERFORMATIVE_INFORM, ONTOLOGY, etc. já estão definidos

            # Templates individuais
            t_alert = Template()
            t_alert.set_metadata(PERFORMATIVE, PERFORMATIVE_INFORM)
            t_alert.set_metadata(ONTOLOGY, "battery_alert")

            t_permission = Template()
            t_permission.set_metadata(PERFORMATIVE, PERFORMATIVE_INFORM)
            t_permission.set_metadata(ONTOLOGY, "charge_permission")

            t_charged = Template()
            t_charged.set_metadata(PERFORMATIVE, PERFORMATIVE_INFORM)
            t_charged.set_metadata(ONTOLOGY, "battery_charged")

            # Combina com OR para criar um único filtro
            battery_template = t_alert | t_permission | t_charged

            # Depois, ao registar o behaviour:
            self.add_behaviour(self.BatteryHandler(), battery_template)

            self.add_behaviour(self.TaskHandler())
        except Exception as e:
            print_log(self.jid.user, f"❗ Error during setup: {e}")