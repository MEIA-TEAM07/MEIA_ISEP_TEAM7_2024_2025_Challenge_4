import asyncio
from spade.agent import Agent
from spade.message import Message
from utils.season import is_growth_season
from utils.logger import print_log, print_agent_header
from utils.weather import get_current_weather
from datetime import date
from spade.behaviour import CyclicBehaviour
from config import (
    FIELD_AGENT_ASSIGNMENT,
    FIELD_ROWS,
    FIELD_COLS,
)
import time

class FieldAgent(Agent):
    def initialize_field_memory(self, field_id, rows, cols):
        # Track per-plant status: disease, being_treated, last_fertilized
        memory = {}
        for x in range(rows):
            for y in range(cols):
                memory[(field_id, x, y)] = {
                    "diseased": False,
                    "being_treated": False,
                    "last_fertilized_date": None
                }
        return memory

    class FieldBehaviour(CyclicBehaviour):
        async def run(self):
            agent_name = self.agent.jid.user
            print_agent_header(agent_name)
            field_id = self.agent.field_id
            weather = get_current_weather()
            humidity = weather["humidity"]
            temperature = weather["temperature"]
            wind_speed = weather["wind_speed"]

            print_log(agent_name, f"🌡️ Weather @ {field_id}:")
            print_log(agent_name, f"   Humidity: {humidity:.2f}%")
            print_log(agent_name, f"   Temperature: {temperature:.2f}°C")
            print_log(agent_name, f"   Wind Speed: {wind_speed:.2f} km/h")

            today = date.today()

            # FERTILIZER LOGIC (one request per coordinate/day)
            if is_growth_season(today):
                for x in range(self.agent.rows):
                    for y in range(self.agent.cols):
                        mem = self.agent.memory[(field_id, x, y)]
                        if mem["last_fertilized_date"] != today:
                            print_log(agent_name, f"🌱 Fertilization needed @ {field_id} ({x},{y}) — sending request.")
                            msg = Message(to="central@localhost")
                            msg.set_metadata("performative", "request")
                            msg.set_metadata("ontology", "fertilization_request")
                            msg.body = f"{field_id}|{x},{y}|{wind_speed:.2f}"
                            await self.send(msg)
                            # Set immediately to prevent duplicate requests
                            mem["last_fertilized_date"] = today

            # Wait for monitoring (simulate periodic check)
            print_log(agent_name, "🕒 Sleeping 10s before next scan...\n")
            await asyncio.sleep(100)

            # Handle incoming messages
            msg = await self.receive(timeout=1)
            while msg:
                ontology = msg.metadata.get("ontology")
                if ontology == "disease_alert":
                    field, xy, disease = msg.body.split("|")
                    x, y = map(int, xy.split(","))
                    mem = self.agent.memory[(field, x, y)]
                    if mem["diseased"]:
                        if mem["being_treated"]:
                            print_log(agent_name, f"❗ Already being treated: {field} ({x},{y}). Ignoring alert.")
                        else:
                            print_log(agent_name, f"🚨 Disease found @ {field} ({x},{y}) again, requesting treatment.")
                            self.request_treatment(field, x, y, disease)
                            mem["being_treated"] = True
                    else:
                        print_log(agent_name, f"🦠 New disease @ {field} ({x},{y}). Requesting treatment.")
                        mem["diseased"] = True
                        self.request_treatment(field, x, y, disease)
                        mem["being_treated"] = True

                elif ontology == "treatment_assigned":
                    field, xy, _ = msg.body.split("|")
                    x, y = map(int, xy.split(","))
                    mem = self.agent.memory[(field, x, y)]
                    print_log(agent_name, f"✅ Treatment assigned at {field} ({x},{y})")
                    mem["being_treated"] = True
                elif ontology == "treatment_complete":
                    field, xy, _ = msg.body.split("|")
                    x, y = map(int, xy.split(","))
                    mem = self.agent.memory[(field, x, y)]
                    print_log(agent_name, f"🎉 Treatment complete at {field} ({x},{y})")
                    mem["being_treated"] = False
                    mem["diseased"] = False
                elif ontology == "fertilization_complete":
                    field, xy, _ = msg.body.split("|")
                    x, y = map(int, xy.split(","))
                    mem = self.agent.memory[(field, x, y)]
                    print_log(agent_name, f"🎉 Fertilization complete at {field} ({x},{y})")
                    # Optionally, add a field here to mark as fertilized if you want to track it further.
                else:
                    print_log(agent_name, f"⚠️ Unknown message: {ontology}")
                msg = await self.receive(timeout=0.5)

        def request_treatment(self, field, x, y, disease):
            msg = Message(to="central@localhost")
            msg.set_metadata("performative", "request")
            msg.set_metadata("ontology", "treatment_request")
            msg.body = f"{field}|{x},{y}|{disease}"
            asyncio.create_task(self.send(msg))

    async def setup(self):
        # Decide which field this agent manages
        agent_name = self.jid.user
        self.field_id = FIELD_AGENT_ASSIGNMENT.get(agent_name, "field_1")
        self.rows = FIELD_ROWS
        self.cols = FIELD_COLS
        self.memory = self.initialize_field_memory(self.field_id, self.rows, self.cols)
        print_log(agent_name, f"🌿 FieldAgent {self.jid} is online and manages {self.field_id}.")
        self.add_behaviour(self.FieldBehaviour())