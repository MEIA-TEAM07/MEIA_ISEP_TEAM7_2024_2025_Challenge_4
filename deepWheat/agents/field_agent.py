import random
import asyncio
from spade.agent import Agent
from spade.message import Message
from utils.season import is_growth_season
from utils.logger import print_log, print_agent_header
from datetime import date
from spade.behaviour import CyclicBehaviour


class FieldAgent(Agent):
    class TriggerScanBehaviour(CyclicBehaviour):
        async def run(self):
            agent_name = self.agent.jid.user
            print_agent_header(agent_name)

            # Simulate sensor data
            field_name = "field_Summer_Wheat"
            humidity = random.uniform(30, 90)
            temperature = random.uniform(10, 40)
            wind_speed = random.uniform(5, 20)

            print_log(agent_name, f"🌡️ Simulated Sensor Data @ {field_name}:")
            print_log(agent_name, f"   Humidity: {humidity:.2f}%")
            print_log(agent_name, f"   Temperature: {temperature:.2f}°C")
            print_log(agent_name, f"   Wind Speed: {wind_speed:.2f} km/h")

            if is_growth_season(date.today()):
                print_log(agent_name, "🌱 Growth season detected — sending fertilization request.")
                msg = Message(to="central@localhost")
                msg.set_metadata("performative", "request")
                msg.set_metadata("ontology", "fertilization_request")
                msg.body = f"{field_name}|{wind_speed:.2f}"
                await self.send(msg)
                print_log(agent_name, "✅ FieldAgent: fertilization request sent.")
            elif humidity > 30 and temperature > 25:
                print_log(agent_name, "⚠️ Conditions suspicious — requesting disease monitoring scan.")
                msg = Message(to="central@localhost")
                msg.set_metadata("performative", "request")
                msg.set_metadata("ontology", "monitoring_request")
                msg.body = f"{field_name}|{wind_speed:.2f}"
                await self.send(msg)
                print_log(agent_name, "✅ FieldAgent: scan request sent.")
            else:
                print_log(agent_name, "✅ Conditions normal — no action taken.")
        
            print_log(agent_name, "🕒 Sleeping 10s before next scan...\n")    
            await asyncio.sleep(10)

    async def setup(self):
        print_log(self.jid.user, f"🌿 FieldAgent {self.jid} is online.")
        self.add_behaviour(self.TriggerScanBehaviour())