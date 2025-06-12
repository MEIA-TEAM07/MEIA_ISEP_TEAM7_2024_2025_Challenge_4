import asyncio
import random
from datetime import datetime
from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
from spade.message import Message

from utils.logger import print_log, print_agent_header
from utils.battery import compute_battery_usage, drain_battery
from utils.season import is_growth_season
from utils.field_map import shared_field_map
from config import (
    BATTERY_LOW_THRESHOLD,
    BATTERY_RECHARGE_STEP,
    RECHARGE_INTERVAL,
    FLIGHT_TIME,
    APPLICATION_TIME,
    WIND_MIN,
    WIND_MAX,
    FIELD_ROWS,
    FIELD_COLS,
    FIELD_AGENT_ASSIGNMENT,
)

class PayloadDroneAgent(Agent):
    class TaskHandler(CyclicBehaviour):
        async def run(self):
            msg = await self.receive(timeout=5)
            if msg:
                performative = msg.metadata.get("performative")
                ontology = msg.metadata.get("ontology")

                if performative == "cfp" and ontology in {"fertilization_request", "pesticide_request"}:
                    if self.agent.recharging:
                        print_log(self.agent.jid.user, f"🔌 Currently recharging — ignoring CFP.")
                        return

                    field_info = msg.body
                    print_log(self.agent.jid.user, f"📩 Received CFP for {ontology} at {field_info}")

                    # Respond with proposal
                    proposal = Message(to=str(msg.sender))
                    proposal.set_metadata("performative", "proposal")
                    proposal.set_metadata("ontology", ontology)
                    proposal.body = f"{self.agent.jid.user}|{self.agent.battery_level}|{self.agent.wind_speed:.2f}"
                    await self.send(proposal)
                    print_log(self.agent.jid.user, f"📤 Sent proposal for {ontology} at {field_info}")

                elif performative == "accept_proposal" and ontology in {"fertilization_request", "pesticide_request"}:
                    field_info = msg.body
                    print_log(self.agent.jid.user, f"✅ Proposal accepted for {ontology} at {field_info}")
                    # Call execute_task, which returns a list of msgs to send
                    messages = await self.agent.execute_task(field_info, ontology)
                    for m in messages:
                        await self.send(m)

                elif performative == "inform" and ontology == "disease_alert":
                    # Not used for this agent but kept for compatibility
                    print_log(self.agent.jid.user, f"🦠 Alert received: {msg.body}")

                elif performative == "reject_proposal":
                    print_log(self.agent.jid.user, f"❌ Proposal rejected: {msg.body}")

                # Handle registration acknowledgments
                elif performative == "confirm" and ontology == "registration_ack":
                    print_log(self.agent.jid.user, f"✅ Registration confirmed: {msg.body}")

                else:
                    print_log(self.agent.jid.user, f"⚠️ Unknown message received: {msg.metadata}, body: {msg.body}")

    async def execute_task(self, field_info, ontology):
        """
        Returns: List of Message objects to send after completion
        """
        messages_to_send = []
        # Parse field_id and position from field_info
        if "|" in field_info:
            field_id, xy_rest = field_info.split("|", 1)
            # xy_rest can be "1,2" or "1,2|wind" (ignore wind if present)
            xy = xy_rest.split("|")[0]
        else:
            field_id = field_info
            xy = None

        field_agent_jid = FIELD_AGENT_ASSIGNMENT.get(field_id, "field1@localhost")

        # FERTILIZATION: iterate over all plants in field
        if ontology == "fertilization_request":
            print_log(self.jid.user, f"🌾 Starting full field fertilization for {field_id}")
            for x in range(FIELD_ROWS):
                for y in range(FIELD_COLS):
                    pos = (x, y)
                    plant = shared_field_map.get_plant(field_id, pos)
                    op_str = f"{field_id} {x},{y}"
                    print_log(self.jid.user, f"🧭 Navigating to {op_str} with fertilizer...")
                    await asyncio.sleep(FLIGHT_TIME)
                    self.consume_battery(base_cost=5.0)
                    print_log(self.jid.user, f"🧪 Applying fertilizer at {op_str}...")
                    await asyncio.sleep(APPLICATION_TIME)
                    self.consume_battery(base_cost=3.0)
                    print_log(self.jid.user, f"✅ Fertilization complete at {op_str}")
                    # Notify field agent for each plant
                    msg = Message(to=field_agent_jid)
                    msg.set_metadata("performative", "inform")
                    msg.set_metadata("ontology", "fertilization_complete")
                    msg.body = f"{field_id}|{x},{y}|fertilizer"
                    messages_to_send.append(msg)

                    if self.battery_level < BATTERY_LOW_THRESHOLD:
                        await self.recharge()
        # PESTICIDE: treat only the specific plant (x, y)
        elif ontology == "pesticide_request" and xy:
            x, y = map(int, xy.split(","))
            pos = (x, y)
            op_str = f"{field_id} {x},{y}"
            print_log(self.jid.user, f"🧭 Navigating to {op_str} with pesticide...")
            await asyncio.sleep(FLIGHT_TIME)
            self.consume_battery(base_cost=5.0)
            print_log(self.jid.user, f"🧪 Applying pesticide at {op_str}...")
            await asyncio.sleep(APPLICATION_TIME)
            self.consume_battery(base_cost=3.0)
            print_log(self.jid.user, f"✅ Treatment complete at {op_str}")
            msg = Message(to=field_agent_jid)
            msg.set_metadata("performative", "inform")
            msg.set_metadata("ontology", "treatment_complete")
            msg.body = f"{field_id}|{x},{y}|pesticide"
            messages_to_send.append(msg)

            if self.battery_level < BATTERY_LOW_THRESHOLD:
                await self.recharge()
        else:
            print_log(self.jid.user, f"⚠️ Unknown task execution call: {ontology} {field_info}")

        return messages_to_send

    async def recharge(self):
        print_log(self.jid.user, "🔋 Battery low — returning to base...")
        await asyncio.sleep(FLIGHT_TIME)
        self.consume_battery(base_cost=5.0)
        print_log(self.jid.user, "🔌 Recharging battery at base...")
        self.recharging = True
        while self.battery_level < 100:
            await asyncio.sleep(RECHARGE_INTERVAL)
            self.battery_level = min(100.0, self.battery_level + BATTERY_RECHARGE_STEP)
            print_log(self.jid.user, f"🔌 Recharging... Battery at {self.battery_level:.2f}%")
        self.recharging = False
        print_log(self.jid.user, f"🔋 Battery fully recharged: {self.battery_level:.2f}%")

    def consume_battery(self, base_cost=5.0):
        usage = compute_battery_usage(base_cost, self.wind_speed)
        self.battery_level = drain_battery(self.battery_level, usage)
        print_log(self.jid.user, f"🔋 Battery after operation: {self.battery_level:.2f}% (used {usage:.2f}%)")

    async def setup(self):
        await super().setup()
        
        self.recharging = False
        self.wind_speed = random.uniform(WIND_MIN, WIND_MAX)
        self.battery_level = 100.0

        if is_growth_season(datetime.now().date()):
            self.payload = "fertilizer"
        else:
            self.payload = "pesticide"

        print_agent_header(self.jid.user)
        print_log(self.jid.user, f"{self.jid} is online.")
        print_log(self.jid.user, f"🔧 Default payload set to: {self.payload}")
        print_log(self.jid.user, f"🚁 PayloadDrone: Waiting for tasks... Current payload: {self.payload}")

        self.add_behaviour(self.TaskHandler())