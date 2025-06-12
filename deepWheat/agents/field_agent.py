import asyncio
from spade.agent import Agent
from spade.message import Message
from utils.season import is_growth_season
from utils.logger import print_log, print_agent_header
from utils.weather import get_current_weather
from datetime import date
from spade.behaviour import CyclicBehaviour
from config import (
    FIELD_ROWS,
    FIELD_COLS,
)

class FieldAgent(Agent):
    def __init__(self, jid, password, field_id):
        super().__init__(jid, password)
        self.field_id = field_id
        self.rows = FIELD_ROWS
        self.cols = FIELD_COLS
        self.memory = self.initialize_field_memory(field_id, self.rows, self.cols)
        self.initialized_today = False  # Track if we've done initial setup today
        
    def initialize_field_memory(self, field_id, rows, cols):
        # Per-plant data + per-field fertilization date + monitoring date
        memory = {}
        for x in range(rows):
            for y in range(cols):
                memory[(field_id, x, y)] = {
                    "diseased": False,
                    "being_treated": False,
                }
        memory["last_fertilized_date"] = None
        memory["last_init_date"] = None  # Track when we last did initialization
        memory["last_monitoring_date"] = None  # Track when we last requested monitoring
        return memory

    class FieldBehaviour(CyclicBehaviour):
        async def request_weekly_monitoring(self, field_id, wind_speed):
            """Request vigilant drone monitoring (weekly) - called from within behavior"""
            msg = Message(to="central@localhost")
            msg.set_metadata("performative", "request")
            msg.set_metadata("ontology", "monitoring_request")
            msg.body = f"{field_id}|{wind_speed:.2f}"
            await self.send(msg)  # Use self.send from behavior, not self.agent.send
            print_log(self.agent.jid.user, f"📤 Weekly monitoring request sent for {field_id}")

        async def run(self):
            agent_name = self.agent.jid.user
            field_id = self.agent.field_id
            today = date.today()

            # Only do the full initialization once per day
            if not self.agent.initialized_today or self.agent.memory.get("last_init_date") != today:
                print_agent_header(agent_name)
                weather = get_current_weather()
                humidity = weather["humidity"]
                temperature = weather["temperature"]
                wind_speed = weather["wind_speed"]

                print_log(agent_name, f"🌡️ Daily Weather Report @ {field_id}:")
                print_log(agent_name, f"   Humidity: {humidity:.2f}%")
                print_log(agent_name, f"   Temperature: {temperature:.2f}°C")
                print_log(agent_name, f"   Wind Speed: {wind_speed:.2f} km/h")

                # FERTILIZATION CHECK - ONLY ONE request per field per day
                if is_growth_season(today):
                    if self.agent.memory["last_fertilized_date"] != today:
                        print_log(agent_name, f"🌱 Growth season active - fertilization needed for {field_id}")
                        msg = Message(to="central@localhost")
                        msg.set_metadata("performative", "request")
                        msg.set_metadata("ontology", "fertilization_request")
                        msg.body = f"{field_id}|{wind_speed:.2f}"
                        await self.send(msg)
                        print_log(agent_name, f"📤 Fertilization request sent for {field_id}")
                        # Don't update last_fertilized_date here - wait for completion
                    else:
                        print_log(agent_name, f"✅ {field_id} already fertilized today")
                else:
                    print_log(agent_name, f"❄️ Outside growth season - no fertilization needed")

                # WEEKLY MONITORING CHECK - Request vigilant drone monitoring
                last_monitoring = self.agent.memory.get("last_monitoring_date")
                
                if last_monitoring is None:
                    # First time - always request monitoring
                    print_log(agent_name, f"🔍 First monitoring request for {field_id}")
                    await self.request_weekly_monitoring(field_id, wind_speed)  # Call behavior method
                    self.agent.memory["last_monitoring_date"] = today
                else:
                    # Check if a week has passed since last monitoring
                    days_since_monitoring = (today - last_monitoring).days
                    if days_since_monitoring >= 7:
                        print_log(agent_name, f"🔍 Weekly monitoring needed for {field_id} (last: {days_since_monitoring} days ago)")
                        await self.request_weekly_monitoring(field_id, wind_speed)  # Call behavior method
                        self.agent.memory["last_monitoring_date"] = today
                    else:
                        print_log(agent_name, f"🔍 Monitoring up to date for {field_id} (last: {days_since_monitoring} days ago)")

                # Mark as initialized for today
                self.agent.initialized_today = True
                self.agent.memory["last_init_date"] = today
                print_log(agent_name, f"🎯 Daily initialization complete for {field_id}")

            # Always handle incoming messages (disease alerts, completion notifications)
            msg = await self.receive(timeout=1)
            message_count = 0
            while msg and message_count < 10:  # Limit to prevent infinite loops
                message_count += 1
                ontology = msg.metadata.get("ontology")
                
                if ontology == "disease_alert":
                    field, xy, disease = msg.body.split("|")
                    x, y = map(int, xy.split(","))
                    mem = self.agent.memory[(field, x, y)]
                    
                    if mem["diseased"]:
                        if mem["being_treated"]:
                            print_log(agent_name, f"❗ Already treating disease @ {field} ({x},{y}). Ignoring duplicate alert.")
                        else:
                            print_log(agent_name, f"🚨 Untreated disease @ {field} ({x},{y}) - requesting treatment")
                            await self.request_treatment(field, x, y, disease)
                            mem["being_treated"] = True
                    else:
                        print_log(agent_name, f"🦠 NEW disease detected @ {field} ({x},{y}): {disease}")
                        mem["diseased"] = True
                        await self.request_treatment(field, x, y, disease)
                        mem["being_treated"] = True

                elif ontology == "treatment_assigned":
                    field, xy, _ = msg.body.split("|")
                    x, y = map(int, xy.split(","))
                    mem = self.agent.memory[(field, x, y)]
                    print_log(agent_name, f"✅ Treatment assigned for {field} ({x},{y})")
                    mem["being_treated"] = True
                    
                elif ontology == "treatment_complete":
                    field, xy, _ = msg.body.split("|")
                    x, y = map(int, xy.split(","))
                    mem = self.agent.memory[(field, x, y)]
                    print_log(agent_name, f"🎉 Treatment COMPLETE @ {field} ({x},{y}) - plant is healthy!")
                    mem["being_treated"] = False
                    mem["diseased"] = False
                    
                elif ontology == "fertilization_complete":
                    field, xy, _ = msg.body.split("|")
                    x, y = map(int, xy.split(","))
                    print_log(agent_name, f"🌱 Fertilization complete @ {field} ({x},{y})")
                    
                    # Update last fertilized date when we get first fertilization complete message
                    if self.agent.memory["last_fertilized_date"] != today:
                        self.agent.memory["last_fertilized_date"] = today
                        print_log(agent_name, f"📅 Marking {field_id} as fertilized for {today}")
                        
                else:
                    print_log(agent_name, f"⚠️ Unknown message ontology: {ontology}")
                
                # Get next message with shorter timeout
                msg = await self.receive(timeout=0.1)

            # Reset daily initialization flag at midnight (simplified check)
            current_date = date.today()
            if self.agent.memory.get("last_init_date") != current_date:
                self.agent.initialized_today = False

            # Sleep before next cycle - shorter sleep for more responsive message handling
            await asyncio.sleep(30)  # Check every 30 seconds instead of 10

        async def request_treatment(self, field, x, y, disease):
            """Send treatment request to central agent"""
            msg = Message(to="central@localhost")
            msg.set_metadata("performative", "request")
            msg.set_metadata("ontology", "treatment_request")
            msg.body = f"{field}|{x},{y}|{disease}"
            await self.send(msg)
            print_log(self.agent.jid.user, f"📤 Treatment request sent for {field} ({x},{y}): {disease}")

    async def setup(self):
        agent_name = self.jid.user
        self.field_id = getattr(self, 'field_id', None)
        self.rows = FIELD_ROWS
        self.cols = FIELD_COLS
        self.memory = self.initialize_field_memory(self.field_id, self.rows, self.cols)
        self.initialized_today = False
        
        print_log(agent_name, f"🌿 FieldAgent {self.jid} is online and managing {self.field_id}")
        print_log(agent_name, f"📋 Managing {self.rows}x{self.cols} grid = {self.rows * self.cols} plants")
        
        self.add_behaviour(self.FieldBehaviour())