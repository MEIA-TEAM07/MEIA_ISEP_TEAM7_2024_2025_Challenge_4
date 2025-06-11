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

def field_id_to_agent(field_id):
    # Looks up the correct agent for a field
    for fa in FIELD_AGENTS:
        if fa["field_id"] == field_id:
            return fa["agent_jid"]
    return None

class VigilantDroneAgent(Agent):
    class VigilantFSM(FSMBehaviour):
        async def on_start(self):
            print_agent_header(self.agent.jid.user)
            print_log(self.agent.jid.user, "🚁 Vigilant Drone FSM starting...")

        async def on_end(self):
            print_log(self.agent.jid.user, "🛬 Vigilant Drone FSM finished.")

    class NegotiationBehaviour(CyclicBehaviour):
        async def run(self):
            msg = await self.receive(timeout=5)
            if msg and msg.metadata.get("performative") == "cfp":
                if self.agent.recharging:
                    print_log(self.agent.jid.user, f"🔌 Currently recharging — ignoring CFP.")
                    return
                field_id = msg.body
                proposal = Message(to="central@localhost")
                proposal.set_metadata("performative", "proposal")
                proposal.set_metadata("ontology", "monitoring_task")
                proposal.body = f"{self.agent.jid.user}|{self.agent.battery_level}|{self.agent.wind_speed:.2f}"
                await self.send(proposal)
            elif msg and msg.metadata.get("performative") == "accept_proposal":
                field_id = msg.body
                fsm = self.agent.create_fsm(field_id)
                self.agent.add_behaviour(fsm)
                print_log(self.agent.jid.user, "🔥 Proposal accepted.")
            elif msg and msg.metadata.get("performative") == "reject_proposal":
                print_log(self.agent.jid.user, "❌ Proposal rejected.")

    class Idle(State):
        async def run(self):
            print_log(self.agent.jid.user, "🕒 IDLE: Waiting for monitoring request...")
            msg = await self.receive(timeout=10)
            if msg:
                try:
                    field_id, wind_str = msg.body.split("|")
                    self.set("target_field", field_id)
                    self.wind_speed = float(wind_str)
                    print_log(self.agent.jid.user, f"🌬️ Wind updated from field: {self.wind_speed:.2f} km/h")
                except ValueError:
                    print_log(self.agent.jid.user, "⚠️ Invalid message format.")
                    self.set_next_state("IDLE")
                    return
                self.set_next_state("NAVIGATE")
            else:
                self.set_next_state("IDLE")

    class NavigateToField(State):
        async def run(self):
            field_id = self.get("target_field")
            print_log(self.agent.jid.user, f"🧭 Navigating to field: {field_id}")
            await asyncio.sleep(FLIGHT_TIME)
            self.agent.consume_battery(base_cost=5.0)
            if self.agent.battery_level < BATTERY_LOW_THRESHOLD:
                print_log(self.agent.jid.user, "❗ Battery too low to continue. Returning to base.")
                self.set_next_state("RETURN")
            else:
                self.set_next_state("SCAN")

    class ScanField(State):
        async def run(self):
            field_id = self.get("target_field")
            print_log(self.agent.jid.user, f"🔍 Scanning field: {field_id}")
            detected = False
            # Get dimensions dynamically
            rows, cols = shared_field_map.rows, shared_field_map.cols

            for x in range(rows):
                for y in range(cols):
                    pos = (x, y)
                    await asyncio.sleep(FLIGHT_TIME)  # Simulate drone movement

                    plant = shared_field_map.get_plant(pos, field=field_id)
                    status = plant["status"] if plant else "unknown"
                    being_treated = plant["being_treated"] if plant else False

                    log_str = f"👁️  Scanning {field_id}@{pos}: Status={status}, Treated={being_treated}"
                    print_log(self.agent.jid.user, log_str)

                    # Report if there's a disease and it's not already being treated
                    if status not in ("healthy", "unknown") and not being_treated:
                        field_agent_jid = field_id_to_agent(field_id)
                        if field_agent_jid:
                            print_log(self.agent.jid.user, f"🦠 Disease ({status}) detected at {field_id} {pos} — reporting to {field_agent_jid}")
                            msg = Message(to=field_agent_jid)
                            msg.set_metadata("performative", "inform")
                            msg.set_metadata("ontology", "disease_alert")
                            msg.body = f"{field_id}|{x},{y}|{status}"
                            await self.send(msg)
                        detected = True

            self.set("disease_found", detected)
            self.set_next_state("REPORT")

    class ReportFinding(State):
        async def run(self):
            if self.get("disease_found"):
                print_log(self.agent.jid.user, "🦠 At least one disease reported to FieldAgent.")
            else:
                print_log(self.agent.jid.user, "✅ No disease detected.")
            self.set_next_state("RETURN")

    class ReturnToBase(State):
        async def run(self):
            print_log(self.agent.jid.user, "🔋 Returning to base...")
            await asyncio.sleep(FLIGHT_TIME)
            if self.agent.battery_level < BATTERY_LOW_THRESHOLD:
                print_log(self.agent.jid.user, "⚡ Low battery detected. Starting recharge...")
                self.agent.recharging = True
                while self.agent.battery_level < 100:
                    await asyncio.sleep(RECHARGE_INTERVAL)
                    self.agent.battery_level = min(100.0, self.agent.battery_level + BATTERY_RECHARGE_STEP)
                    print_log(self.agent.jid.user, f"🔌 Recharging... Battery at {self.agent.battery_level:.2f}%")
                self.agent.recharging = False
                print_log(self.agent.jid.user, "✅ Recharge complete. Drone is ready.")
            else:
                print_log(self.agent.jid.user, f"🔋 Battery is at {self.agent.battery_level:.2f}% — no recharge needed.")
            self.set_next_state("IDLE")

    def consume_battery(self, base_cost=5.0):
        usage = compute_battery_usage(base_cost, self.wind_speed)
        self.battery_level = drain_battery(self.battery_level, usage)
        print_log(self.jid.user, f"🔋 Battery after flying: {self.battery_level:.2f}% (used {usage:.2f}%)")
    
    def create_fsm(self, field_id=None):
        fsm = self.VigilantFSM()
        fsm.agent = self
        fsm.add_state(name="IDLE", state=self.Idle(), initial=True)
        fsm.add_state(name="NAVIGATE", state=self.NavigateToField())
        fsm.add_state(name="SCAN", state=self.ScanField())
        fsm.add_state(name="REPORT", state=self.ReportFinding())
        fsm.add_state(name="RETURN", state=self.ReturnToBase())
        fsm.add_transition("IDLE", "NAVIGATE")
        fsm.add_transition("NAVIGATE", "SCAN")
        fsm.add_transition("SCAN", "REPORT")
        fsm.add_transition("REPORT", "RETURN")
        fsm.add_transition("RETURN", "IDLE")
        fsm.add_transition("IDLE", "IDLE")
        if field_id:
            fsm.set("target_field", field_id)
        return fsm

    async def setup(self):
        self.recharging = False
        self.wind_speed = random.uniform(WIND_MIN, WIND_MAX)
        self.battery_level = 100.0
        print(f"🌬️ Wind Speed: {self.wind_speed:.2f} km/h")
        print(f"🔋 Initial Battery: {self.battery_level}%")
        print(f"🚁 VigilantDroneAgent {self.jid} is online.")
        fsm = self.create_fsm()
        self.add_behaviour(fsm)
        self.add_behaviour(self.NegotiationBehaviour())