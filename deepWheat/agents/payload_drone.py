import asyncio
import random
from datetime import datetime
from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
from spade.message import Message

from utils.logger import print_log, print_agent_header
from utils.battery import compute_battery_usage, drain_battery
from utils.season import is_growth_season
from config import (
    BATTERY_LOW_THRESHOLD,
    BATTERY_RECHARGE_STEP,
    RECHARGE_INTERVAL,
    FLIGHT_TIME,
    APPLICATION_TIME,
    WIND_MIN,
    WIND_MAX
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
                    
                    field = msg.body
                    print_log(self.agent.jid.user, f"📩 Received CFP for {ontology} at {field}")

                    # Respond with proposal
                    proposal = Message(to=str(msg.sender))
                    proposal.set_metadata("performative", "proposal")
                    proposal.set_metadata("ontology", ontology)
                    proposal.body = f"{self.agent.jid.user}|{self.agent.battery_level}|{self.agent.wind_speed:.2f}"
                    await self.send(proposal)
                    print_log(self.agent.jid.user, f"📤 Sent proposal for {ontology} at {field}")

                elif performative == "accept_proposal" and ontology in {"fertilization_request", "pesticide_request"}:
                    field = msg.body
                    print_log(self.agent.jid.user, f"✅ Proposal accepted for {ontology} at {field}")
                    await self.agent.execute_task(field, ontology)

                elif performative == "inform" and ontology == "disease_alert":
                    field = msg.body.split("field")[-1].strip()
                    print_log(self.agent.jid.user, f"🦠 Alert received — switching to pesticide for field {field}")
                    await self.agent.execute_task(f"field {field}", "pesticide_request")

                else:
                    print_log(self.agent.jid.user, f"⚠️ Unknown message received: {msg.metadata}, body: {msg.body}")

    async def execute_task(self, field, ontology):
        operation = "fertilizer" if ontology == "fertilization_request" else "pesticide"
        print_log(self.jid.user, f"🧭 Navigating to {field} with {operation}...")
        await asyncio.sleep(FLIGHT_TIME)
        self.consume_battery(base_cost=5.0)

        print_log(self.jid.user, f"🧪 Applying {operation} at {field}...")
        await asyncio.sleep(APPLICATION_TIME)
        self.consume_battery(base_cost=3.0)

        print_log(self.jid.user, f"✅ {operation.capitalize()} application complete.")
        await asyncio.sleep(1)

        if self.battery_level < BATTERY_LOW_THRESHOLD:
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
        else:
            print_log(self.jid.user, f"🔋 Battery OK ({self.battery_level:.2f}%) — staying in the field.")

    def consume_battery(self, base_cost=5.0):
        usage = compute_battery_usage(base_cost, self.wind_speed)
        self.battery_level = drain_battery(self.battery_level, usage)
        print_log(self.jid.user, f"🔋 Battery after operation: {self.battery_level:.2f}% (used {usage:.2f}%)")

    async def setup(self):
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