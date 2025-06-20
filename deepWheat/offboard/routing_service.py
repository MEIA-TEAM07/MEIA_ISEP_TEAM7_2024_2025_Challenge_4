from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp
import numpy as np

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