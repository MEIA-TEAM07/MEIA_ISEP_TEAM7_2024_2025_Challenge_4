import asyncio
import random
from spade.agent import Agent
from spade.behaviour import FSMBehaviour, State
from spade.message import Message
from utils.battery import compute_battery_usage, drain_battery

class VigilantDroneAgent(Agent):
    class VigilantFSM(FSMBehaviour):
        async def on_start(self):
            print("🚁 Vigilant Drone FSM starting...")

        async def on_end(self):
            print("🛬 Vigilant Drone FSM finished.")

    class Idle(State):
        async def run(self):
            print("🕒 IDLE: Waiting for monitoring request...")
            msg = await self.receive(timeout=10)
            if msg:
                try:
                    field_name, wind_str = msg.body.split("|")
                    self.set("target_field", field_name)
                    self.wind_speed = float(wind_str)
                    print(f"🌬️ Wind updated from field: {self.wind_speed:.2f} km/h")
                except ValueError:
                    print("⚠️ Invalid message format.")
                    self.set_next_state("IDLE")
                    return
                self.set_next_state("NAVIGATE")
            else:
                self.set_next_state("IDLE")

    class NavigateToField(State):
        async def run(self):
            field = self.get("target_field")
            print(f"🧭 Navigating to field: {field}")
            await asyncio.sleep(2)  # Simulate travel time
            self.agent.consume_battery(base_cost=5.0)
           
            if self.agent.battery_level < 15:
                print("❗ Battery too low to continue. Returning to base.")
                self.set_next_state("RETURN")
            else:
                self.set_next_state("SCAN")

    class ScanField(State):
        async def run(self):
            print("🔍 Scanning field...")
            await asyncio.sleep(2)
            disease_found = random.random() > 0.5
            self.set("disease_found", disease_found)
            self.set_next_state("REPORT")

    class ReportFinding(State):
        async def run(self):
            if self.get("disease_found"):
                print("🦠 Disease detected! Notifying Treatment Drone...")
                msg = Message(to="treatment1@localhost")  # update if needed
                msg.set_metadata("performative", "inform")
                msg.set_metadata("ontology", "disease_alert")
                msg.body = f"Disease found at field {self.get('target_field')}"
                await self.send(msg)
            else:
                print("✅ No disease detected.")
            self.set_next_state("RETURN")

    class ReturnToBase(State):
        async def run(self):
            print("🔋 Returning to base...")
            await asyncio.sleep(2)

            if self.agent.battery_level < 20:
                print("⚡ Low battery detected. Starting recharge...")
                while self.agent.battery_level < 100:
                    await asyncio.sleep(1)
                    self.agent.battery_level = min(100.0, self.agent.battery_level + 20)
                    print(f"🔌 Recharging... Battery at {self.agent.battery_level:.2f}%")
                print("✅ Recharge complete. Drone is ready.")
            else:
                print(f"🔋 Battery is at {self.agent.battery_level:.2f}% — no recharge needed.")

            self.set_next_state("IDLE")

    def consume_battery(self, base_cost=5.0):
        usage = compute_battery_usage(base_cost, self.wind_speed)
        self.battery_level = drain_battery(self.battery_level, usage)
        print(f"🔋 Battery after flying: {self.battery_level:.2f}% (used {usage:.2f}%)")

    async def setup(self):
        self.wind_speed = 5 + 10 * random.random()  # e.g., 5–15 km/h
        self.battery_level = 100.0

        print(f"🌬️ Wind Speed: {self.wind_speed:.2f} km/h")
        print(f"🔋 Initial Battery: {self.battery_level}%")

        print(f"🚁 VigilantDroneAgent {self.jid} is online.")
        fsm = self.VigilantFSM()
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
        fsm.add_transition("IDLE", "IDLE")  # if no message received

        self.add_behaviour(fsm)