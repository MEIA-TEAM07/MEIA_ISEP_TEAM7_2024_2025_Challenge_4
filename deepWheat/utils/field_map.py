# utils/field_map.py

import threading
import csv
import os
from pathlib import Path
# Define a mapping of field names to their CSV files

class FieldMap:
    """
    A class to manage field maps and plant locations.
    This class reads field definitions from a CSV file and provides methods
    to access plant information by field ID and coordinates.
    It is thread-safe for concurrent access.
    """
    def __init__(self, csv_path):


        self.lock = threading.Lock()
        # fields: field_id -> {(x, y): cell_info}
        self.fields = {}

        # Read map definitions from CSV
        with open(csv_path, newline='') as csvfile:
            reader = csv.reader(csvfile)
            for row in reader:
                # Expecting CSV columns: field_id, x, y
                field_id = row[0]
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
    
    def get_field(self, field_id):
        """
        Return the entire field data for a given field ID.
        """
        with self.lock:
            return self.fields.get(field_id, {})


    def return_plant_locations_by_field(self, field_id, flying_altitude = -1.3):
        """
        Return list of [x, y, z] waypoints for a given field name,
        using the already-loaded self.fields data. Z is fixed at -1.3.
        """

        with self.lock:
            coords = self.fields.get(field_id)
            if coords is None:
                raise ValueError(f"No data loaded for field ID {field_id}")

            # Build waypoints with fixed z coordinate -1.3
            waypoints = [[x, y, flying_altitude] for (x, y) in coords.keys()]
        return waypoints

base_dir = Path(__file__).resolve().parent.parent  # adjust as needed
csv_path = base_dir / "data" / "field_map.csv"

shared_field_map = FieldMap(str(csv_path))