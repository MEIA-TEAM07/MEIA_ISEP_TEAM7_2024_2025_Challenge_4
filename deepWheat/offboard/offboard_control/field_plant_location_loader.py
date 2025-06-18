import os, csv

fields_files = {
    #'field1': 'field1_plant_locations.csv'
    'field1': 'field1_plant_locations_test.csv'
}

def return_plant_locations_by_field(field_name):
    csv_name = fields_files.get(field_name)
    if csv_name is None:
        raise ValueError(f"No CSV configured for field '{field_name}'")

    base_dir = os.path.dirname(__file__)  
    fullpath = os.path.join(base_dir, csv_name)

    waypoints = []
    try:
        with open(fullpath, 'r') as f:
            reader = csv.reader(f)
            for row in reader:
                if not row or row[0].startswith('#'):
                    continue
                x, y, z = map(float, row)
                waypoints.append([x, y, z])
    except Exception as e:
        raise RuntimeError(f"Error reading '{fullpath}': {e}")
    return waypoints
