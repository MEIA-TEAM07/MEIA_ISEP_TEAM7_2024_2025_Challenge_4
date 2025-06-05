import asyncio
import random
from spade.agent import Agent
from spade.behaviour import FSMBehaviour, State
from spade.message import Message
from utils.battery import compute_battery_usage, drain_battery
from utils.logger import print_log, print_agent_header
from spade.behaviour import CyclicBehaviour
from config import BATTERY_LOW_THRESHOLD, RECHARGE_INTERVAL, BATTERY_RECHARGE_STEP

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
                
                field = msg.body
                # Send proposal back
                proposal = Message(to="central@localhost")
                proposal.set_metadata("performative", "proposal")
                proposal.set_metadata("ontology", "monitoring_task")
                body = f"{self.agent.jid.user}|{self.agent.battery_level}|{self.agent.wind_speed:.2f}"
                proposal.body = body
                await self.send(proposal)

            elif msg and msg.metadata.get("performative") == "accept_proposal":
                field = msg.body
                fsm = self.agent.create_fsm(field)
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
                    field_name, wind_str = msg.body.split("|")
                    self.set("target_field", field_name)
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
            field = self.get("target_field")
            print_log(self.agent.jid.user, f"🧭 Navigating to field: {field}")
            await asyncio.sleep(2)  # Simulate travel time
            self.agent.consume_battery(base_cost=5.0)
           
            if self.agent.battery_level < BATTERY_LOW_THRESHOLD:
                print_log(self.agent.jid.user, "❗ Battery too low to continue. Returning to base.")
                self.set_next_state("RETURN")
            else:
                self.set_next_state("SCAN")

    class ScanField(State):
        async def run(self):
            print_log(self.agent.jid.user, "🔍 Scanning field...")
            await asyncio.sleep(2)
            disease_found = random.random() > 0.5
            self.set("disease_found", disease_found)
            self.set_next_state("REPORT")

    class ReportFinding(State):
        async def run(self):
            if self.get("disease_found"):
                print_log(self.agent.jid.user, "🦠 Disease detected! Notifying Payload Drone...")
                msg = Message(to="payload1@localhost")  # update if needed
                msg.set_metadata("performative", "inform")
                msg.set_metadata("ontology", "disease_alert")
                msg.body = f"Disease found at field {self.get('target_field')}"
                await self.send(msg)
            else:
                print_log(self.agent.jid.user, "✅ No disease detected.")
            self.set_next_state("RETURN")

    class ReturnToBase(State):
        async def run(self):
            print_log(self.agent.jid.user, "🔋 Returning to base...")
            await asyncio.sleep(2)

            if self.agent.battery_level < BATTERY_LOW_THRESHOLD:
                print_log(self.agent.jid.user, "⚡ Low battery detected. Starting recharge...")
                self.agent.recharging = True
                while self.battery_level < 100:
                    await asyncio.sleep(RECHARGE_INTERVAL)
                    self.battery_level = min(100.0, self.battery_level + BATTERY_RECHARGE_STEP)
                    print_log(self.jid.user, f"🔌 Recharging... Battery at {self.battery_level:.2f}%")
                self.agent.recharging = False
                print_log(self.agent.jid.user, "✅ Recharge complete. Drone is ready.")
            else:
                print_log(self.agent.jid.user, f"🔋 Battery is at {self.agent.battery_level:.2f}% — no recharge needed.")
            self.set_next_state("IDLE")

    def consume_battery(self, base_cost=5.0):
        usage = compute_battery_usage(base_cost, self.wind_speed)
        self.battery_level = drain_battery(self.battery_level, usage)
        print_log(self.jid.user, f"🔋 Battery after flying: {self.battery_level:.2f}% (used {usage:.2f}%)")
    
    def create_fsm(self, field_data=None):
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
        fsm.add_transition("IDLE", "IDLE")  # fallback

        if field_data:
            fsm.set("target_field", field_data)

        return fsm

    async def setup(self):
        self.recharging = False
        self.wind_speed = 5 + 10 * random.random()  # e.g., 5–15 km/h
        self.battery_level = 100.0

        print(f"🌬️ Wind Speed: {self.wind_speed:.2f} km/h")
        print(f"🔋 Initial Battery: {self.battery_level}%")

        print(f"🚁 VigilantDroneAgent {self.jid} is online.")
      
        fsm = self.create_fsm()        
        self.add_behaviour(fsm)
        self.add_behaviour(self.NegotiationBehaviour())