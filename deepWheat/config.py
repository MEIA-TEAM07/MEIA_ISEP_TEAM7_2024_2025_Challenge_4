# config.py

BATTERY_LOW_THRESHOLD = 45
BATTERY_CRITICAL_THRESHOLD = 25
BATTERY_RECHARGE_STEP = 20
RECHARGE_INTERVAL = 1
RECHARGE_LOG = True

GROWTH_SEASON_START = (3, 15)  # March 15
GROWTH_SEASON_END = (7, 5)     # July 5
DEFAULT_CROP_TYPE = "spring"

WIND_MIN = 5
WIND_MAX = 15
FLIGHT_TIME = 2
APPLICATION_TIME = 2

PROPOSAL_TIMEOUT     = 0.5    # seconds to wait for proposals
RECEIVE_TIMEOUT      = 1    # seconds to wait for message reception

# Grid size for all fields (can be made per-field if needed)
FIELD_ROWS = 2
FIELD_COLS = 5

# Field and disease mapping
FIELDS = [
    {"field_id": "field_1", "rows": FIELD_ROWS, "cols": FIELD_COLS},
    {"field_id": "field_2", "rows": FIELD_ROWS, "cols": FIELD_COLS}
]

# Map agent JIDs to fields
FIELD_AGENT_ASSIGNMENT = {
    "field_1": "field1@localhost",
    "field_2": "field2@localhost",
}
FIELD_AGENTS = [
    {"agent_jid": "field1@localhost", "field_id": "field_1"},
    {"agent_jid": "field2@localhost", "field_id": "field_2"},
    {"agent_jid": "field3@localhost", "field_id": "field_3"}
]

TYPE_DRONE_PAYLOAD = "payload_drone"
TYPE_DRONE_VIGILANT = "vigilant_drone"

# SPADE settings

# ALL ONTOLOGIES
ONTOLOGY                                = "ontology" 
ONTOLOGY_DRONE_REGISTRATION             = "drone_registration"
ONTOLOGY_DRONE_REGISTRATION_ACK         = "registration_ack"
ONTOLOGY_PESTICIDE                      = "pesticide_request"
ONTOLOGY_TREATMENT                      = "treatment_request"
ONTOLOGY_FERTILIZATION                  = "fertilization_request"
ONTOLOGY_DISEASE_ALERT                  = "disease_alert"
LIST_OF_REQUEST_ONTOLOGIES              = ["monitoring_request", "fertilization_request", "treatment_request","pesticide_request"]
REQUEST_ONTOLOGIES                      = [
                                        "monitoring_request",
                                        "fertilization_request",
                                        "treatment_request",
                                        ]

# ALL PERFORMATIVES 
PERFORMATIVE               = "performative"
PERFORMATIVE_REGISTER      = "register"
PERFORMATIVE_CONFIRM       = "confirm"
PERFORMATIVE_CFP           = "cfp"
PERFORMATIVE_AFFIRM        = "affirm"
PERFORMATIVE_PROPOSAL      = "proposal"
PERFORMATIVE_ACCEPT        = "accept_proposal"
PERFORMATIVE_REJECT        = "reject_proposal"
PERFORMATIVE_INFORM        = "inform"

# STATE MACHINE
STATE_WAIT                 = "WAIT"
STATE_COLLECT_PROPOSALS    = "COLLECT_PROPOSALS"
STATE_CFP                  = "SEND_CFP"
STATE_IDLE                 = "IDLE"
STATE_NAVIGATE             = "NAVIGATE"
STATE_SCAN                 = "SCAN"
STATE_COLLECT_PROPOSALS    = "COLLECT_PROPOSALS"

# Weather settings
WEATHER_API_KEY = "bcbf7b4cabfaa6fa5678dc5c5ada8a96"
WEATHER_LAT = 41.1496
WEATHER_LON = -8.6109
WEATHER_UPDATE_INTERVAL = 600

OFF_SET_DRONES = [
    {"drone_id": "1", "offset": [-3.0, 7.0]},
    {"drone_id": "2", "offset": [-3.0, -7.0]},
    {"drone_id": "3", "offset": [-6.0, 7.0]},
    {"drone_id": "4", "offset": [-6.0, -7.0]},
]
