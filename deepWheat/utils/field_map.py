# utils/field_map.py

import threading
import csv

class FieldMap:
    def __init__(self, csv_path):
        self.lock = threading.Lock()
        # fields: field_id -> {(x, y): cell_info}
        self.fields = {}

        # Read map definitions from CSV
        with open(csv_path, newline='') as csvfile:
            reader = csv.reader(csvfile)
            for row in reader:
                # Expecting CSV columns: field_id, x, y
                field_id = int(row[0])
                x, y = float(row[1]), float(row[2])

                # Initialize field dict on first encounter
                if field_id not in self.fields:
                    self.fields[field_id] = {}

                # Create default plant cell
                self.fields[field_id][(x, y)] = {
                    'plant_id': f"{field_id}_plant_{x}_{y}",
                    'status': 'healthy',
                    'being_treated': False,
                }

    def get_plant(self, field_id, pos):
        with self.lock:
            return self.fields.get(field_id, {}).get(pos)
      
shared_field_map = FieldMap("deepWheat/data/field_map.csv")