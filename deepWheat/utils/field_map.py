# utils/field_map.py

import threading
from config import DISEASED_PLANTS

class FieldMap:
    def __init__(self, rows=2, cols=5):
        self.rows = rows
        self.cols = cols
        self.lock = threading.Lock()
        self.fields = {}  # field_id -> map

        for field_id in DISEASED_PLANTS.keys():
            # Each cell: {"plant_id": ..., "status": ..., "being_treated": ...}
            self.fields[field_id] = {
                (x, y): {
                    "plant_id": f"{field_id}_plant_{x}_{y}",
                    "status": "healthy",
                    "being_treated": False,
                }
                for x in range(rows) for y in range(cols)
            }
            # Mark diseased plants
            for (x, y, disease) in DISEASED_PLANTS[field_id]:
                self.fields[field_id][(x, y)]["status"] = disease

    def get_plant(self, field_id, pos):
        with self.lock:
            return self.fields.get(field_id, {}).get(pos, None)

    def set_status(self, field_id, pos, status):
        with self.lock:
            if pos in self.fields.get(field_id, {}):
                self.fields[field_id][pos]["status"] = status

    def set_treatment(self, field_id, pos, value=True):
        with self.lock:
            if pos in self.fields.get(field_id, {}):
                self.fields[field_id][pos]["being_treated"] = value

    def is_being_treated(self, field_id, pos):
        with self.lock:
            return self.fields.get(field_id, {}).get(pos, {}).get("being_treated", False)

    def already_diseased(self, field_id, pos):
        with self.lock:
            status = self.fields.get(field_id, {}).get(pos, {}).get("status", "")
            return status != "healthy"

    def print_map(self, field_id):
        with self.lock:
            print(f"Field: {field_id}")
            for x in range(self.rows):
                row = []
                for y in range(self.cols):
                    cell = self.fields[field_id][(x, y)]
                    s = cell["status"][0].upper()
                    t = "*" if cell["being_treated"] else " "
                    row.append(f"{s}{t}")
                print(" ".join(row))
            print()

shared_field_map = FieldMap(rows=2, cols=5)