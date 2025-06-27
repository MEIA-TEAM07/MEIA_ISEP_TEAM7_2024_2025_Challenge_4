from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp
import numpy as np
import math

def find_shortest_path(waypoints):
    # 2) Build a 3D Euclidean distance matrix
        n = len(waypoints)
        dist_matrix = [[0]*n for _ in range(n)]
        for i in range(n):
            xi, yi, zi = waypoints[i]
            for j in range(n):
                xj, yj, zj = waypoints[j]
                dx, dy, dz = xi - xj, yi - yj, zi - zj
                dist_matrix[i][j] = int(np.sqrt(dx*dx + dy*dy + dz*dz))  # use sqrt instead of hypot


        # 3) Zero out “return to depot” so it becomes an open path
        for i in range(n):
            dist_matrix[i][0] = 0

        # 4) Set up OR-Tools routing solver
        manager = pywrapcp.RoutingIndexManager(n, 1, 0)  # one vehicle, depot=0
        routing = pywrapcp.RoutingModel(manager)

        def distance_callback(from_index, to_index):
            frm = manager.IndexToNode(from_index)
            to = manager.IndexToNode(to_index)
            return dist_matrix[frm][to]

        transit_idx = routing.RegisterTransitCallback(distance_callback)
        routing.SetArcCostEvaluatorOfAllVehicles(transit_idx)

        search_params = pywrapcp.DefaultRoutingSearchParameters()
        search_params.first_solution_strategy = (
            routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
        )

        solution = routing.SolveWithParameters(search_params)
        route = []
        index = routing.Start(0)
        while not routing.IsEnd(index):
            route.append(manager.IndexToNode(index))
            index = solution.Value(routing.NextVar(index))

        # 5) Reorder waypoints according to 'route'
        waypoints = [waypoints[i] for i in route]

        return waypoints

def find_corners_of_field(waypoints):

    min_x = min(wp[0] for wp in waypoints)
    max_x = max(wp[0] for wp in waypoints)
    min_y = min(wp[1] for wp in waypoints)
    max_y = max(wp[1] for wp in waypoints)

    corners = []
    for x, y in [(min_x, min_y), (min_x, max_y), (max_x, min_y), (max_x, max_y)]:
        for wp in waypoints:
            if abs(wp[0] - x) < 1e-6 and abs(wp[1] - y) < 1e-6:
                corners.append(wp)
                break

    return corners

def find_closest_corner(point, corners):
    closest = None
    min_dist = float('inf')
    for corner in corners:
        dist = math.sqrt((point[0] - corner[0])**2 + (point[1] - corner[1])**2)
        if dist < min_dist:
            min_dist = dist
            closest = corner
    return closest

def get_all_lane_extreme_points(waypoints):
    xs = sorted(set([wp[0] for wp in waypoints]))
    points = []
    for x in xs:
        lane_points = [wp for wp in waypoints if abs(wp[0] - x) < 1e-6]
        if lane_points:
            points.append(max(lane_points, key=lambda wp: wp[1]))
            points.append(min(lane_points, key=lambda wp: wp[1]))
    return points


def find_shortest_zigzag_path(waypoints, start_point):
    waypoints = get_all_lane_extreme_points(waypoints)

    xs = sorted(set([wp[0] for wp in waypoints]))
    ys = sorted(set([wp[1] for wp in waypoints]))
    
    corners = find_corners_of_field(waypoints)
    start = find_closest_corner(start_point, corners)
    path = [start]
    x_order = xs if abs(start[0] - xs[0]) < abs(start[0] - xs[-1]) else xs[::-1]
    y_order_even = ys if abs(start[1] - ys[0]) < abs(start[1] - ys[-1]) else ys[::-1]
    y_order_odd = y_order_even[::-1]

    for i, x in enumerate(x_order):
        y_order = y_order_even if i % 2 == 0 else y_order_odd
        for y in y_order:
            matches = [wp for wp in waypoints if abs(wp[0] - x) < 1e-6 and abs(wp[1] - y) < 1e-6]
            if matches and matches[0] not in path:
                path.append(matches[0])
    return path

def find_shortest_fungicide_path(waypoints, point, initial_position):
    waypoints = get_adjacent_points(waypoints, point)
    waypoints.insert(0, initial_position)
    waypoints = find_shortest_path(waypoints)
    waypoints.pop(0)
    return waypoints

def get_adjacent_points(points, point):
    x, y, z = point
    same_z = [p for p in points if p[2] == z and p != point]
    result = [point]
    
    north = [p for p in same_z if p[0]==x and p[1]>y]
    if north:
        result.append(min(north, key=lambda p: p[1]-y))

    south = [p for p in same_z if p[0]==x and p[1]<y]
    if south:
        result.append(max(south, key=lambda p: p[1]-y))

    east = [p for p in same_z if p[1]==y and p[0]>x]
    if east:
        
        result.append(min(east, key=lambda p: p[0]-x))
    west = [p for p in same_z if p[1]==y and p[0]<x]
    if west:
        result.append(max(west, key=lambda p: p[0]-x))
    return result
