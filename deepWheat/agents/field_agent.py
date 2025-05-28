import asyncio
import random
from spade.agent import Agent
from spade.behaviour import OneShotBehaviour
from spade.message import Message

class FieldAgent(Agent):
    class TriggerScanBehaviour(OneShotBehaviour):
        async def run(self):
            # Simulate sensor data
            field_name = "field_3"
            humidity = random.uniform(30, 90)
            temperature = random.uniform(10, 40)
            wind_speed = random.uniform(5, 20)

            print(f"🌡️ Simulated Sensor Data @ {field_name}:")
            print(f"   Humidity: {humidity:.2f}%")
            print(f"   Temperature: {temperature:.2f}°C")
            print(f"   Wind Speed: {wind_speed:.2f} km/h")

            # Define trigger logic
            if humidity > 30 and temperature > 25:
                print("⚠️ Conditions suspicious — requesting drone scan.")
                msg = Message(to="central@localhost")
                msg.set_metadata("performative", "request")
                msg.set_metadata("ontology", "monitoring_request")
                msg.body = f"{field_name}|{wind_speed:.2f}"
                await self.send(msg)
                print("✅ FieldAgent: scan request sent.")
            else:
                print("✅ Conditions normal — no scan requested.")

    async def setup(self):
        print(f"🌿 FieldAgent {self.jid} is online.")
        self.add_behaviour(self.TriggerScanBehaviour())