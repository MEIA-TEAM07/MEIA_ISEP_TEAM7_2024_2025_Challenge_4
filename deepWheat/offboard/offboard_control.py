import threading
import time
from rclpy.node import Node
from offboard import disease_classification_service
from spade.message import Message
import asyncio
from spade.behaviour import FSMBehaviour
from offboard.offboard_signal import OffboardSignal
from offboard.offboard_ros_messenger import OffboardRosMessenger
from utils.logger import print_log
from config import OFF_SET_DRONES

class OffboardControl:
    def __init__(self, node: Node, drone_id, agent_jid, behaviour: FSMBehaviour):
        try:
            self.drone_id = drone_id
            self.has_signal = False
            self.node = node
            self.agent_jid = agent_jid
            self.behaviour = behaviour
            self.flying_altitude = -1.3
            self.charging_intentions = []
            self.payload_level = 0
            self.payload_recharge_rate = 20
            self.payload_type = None
            self.payload_usage_fertilize = 0.8
            self.payload_usage_fungicide = 0.8
            self.task_status_on_hold = False
            self.counterdown = 0
            self.charging_counter = 0
            self.battery_flag = False
            self.t_start = self.node.get_clock().now().nanoseconds
            self.was_on_hold = False
            self.is_ready_to_charge = False
            
            # State
            self.task = None
            self.task_on_hold = None
            self.image_counter = 0
            self.latest_image = None
            self.reset_variables()
            self.battery_level = 100.0
            self.first_call = True
            x = 0
            y = 0
            for offset in OFF_SET_DRONES:
                if offset["drone_id"] == drone_id:
                    x, y = offset['offset']

            self.idle_waypoint = [x, y, self.flying_altitude]
            self.charging_station_waypoint = [0.0, 7.0, self.flying_altitude]
            self.battery_recharge_rate = 20
            if self.drone_id == '1' or self.drone_id == '2':
                self.battery_usage = 0.02
            else:
                self.battery_usage = 0.06
            self.low_battery_threshold = 30.0
            self.idle_count = 0
            self.turned_on = True
            self.current_x = 0.0
            self.current_y = 0.0
            self.current_z = 100.0
            self.first_count = True
            self.waypoint_reached = False

            self.offboard_ros_messenger = OffboardRosMessenger(self, node,drone_id)
            self.offboard_signal = OffboardSignal(drone_id, interval=0.01)

            self.unlocked = threading.Lock()
            
        except Exception as e:
            print(f"Error initializing OffboardControl: {e}")


    def set_loop(self, loop):
        self.loop = loop

    def base_task(self, waypoints, waypoint_index, task_type):
        self.reset_variables()
        self.target_waypoints = waypoints
        self.current_waypoint_index = waypoint_index
        self.task = task_type
        self.task_on_hold = task_type
        self.turned_on = True

        if(self.first_call):
            self.first_call = False
            self.scan_timer = self.node.create_timer(0.1, self.offboard_callback)

    def scan(self, waypoints, waypoint_index=0):
        self.update_flying_altitude(waypoints[1][2])
        self.base_task(waypoints, waypoint_index, 'scan')

    def apply_fungicide(self, waypoints, waypoint_index=0):
        self.update_flying_altitude(waypoints[1][2])
        self.base_task(waypoints, waypoint_index, 'fungicide')

    def fertilize(self, waypoints, waypoint_index=0):
        self.update_flying_altitude(waypoints[1][2])
        waypoints = self.adjust_waypoints_for_fertilization(waypoints)
        
        self.base_task(waypoints, waypoint_index, 'fertilize')

    def offboard_callback(self):
        try:
            if self.task != 'recharge' and self.task != 'idle':
                self.task_on_hold = self.task
            self.count += 1
            t = self.node.get_clock().now().nanoseconds
            if self.battery_flag == True:
                self.task = 'recharge'
            if self.turned_on == False and self.task != 'recharge':
                if self.has_signal == True:
                    self.offboard_signal.stop()
                    self.has_signal = False
                return
            if self.task_on_hold == 'scan':
                self.manage_battery()
            else:
                self.manage_payload_and_battery()
            
            if self.battery_level <= 0.0:
                if self.has_signal == True:
                    try:
                        print(f"Killed signal for {self.agent_jid} because battery depleted {self.agent_jid}")
                        self.offboard_signal.stop()
                        self.has_signal = False
                    except Exception as e:
                        print(f"{self.agent_jid} eu tentei matar uma merda que não devia. Erro: {e}" )
                return
            if self.task == 'scan':
                self.scan_callback(t)
                return
            elif self.task == 'fungicide' or self.task == 'fertilize':
                self.fungicide_fertilize_callback(t, self.task)
                return
            elif self.task == 'recharge':
                self.charging_callback(t)
                return
            elif self.task == 'idle':
                self.idle_callback(t)
                return

        except Exception as e:
            print(f"Error in offboard callback: {e}")

    def scan_callback(self, t):
        self.offboard_ros_messenger.set_gimbal_pos()

        tookoff = self.takeoff(t)
            
        if tookoff == True:
            if self.unlocked.locked() == False:
                self.follow_scan_path(t)

                if self.waypoint_reached == True:
                    if self.image_processing_started == False:
                        asyncio.run_coroutine_threadsafe(self.process_image(), self.loop)
                        self.image_processing_started = True

                    is_last_waypoint = self.current_waypoint_index >= len(self.target_waypoints) - 1
                    if self.unlocked.locked() == False:
                        if is_last_waypoint == True:
                            self.send_task_complete('scan')

    def charging_callback(self, t):
        if self.drone_id == '4':
            print(f"{self.agent_jid}: Run3: Task: {self.task}, Task on hold: {self.task_on_hold}, is_ready_to_charge: {self.is_ready_to_charge}")
        if self.is_ready_to_charge == False:
            self.is_ready_to_charge = self.follow_charging_path(t)
        return
    
    def fungicide_fertilize_callback(self, t, task_type):
        tookoff = self.takeoff(t)
        if tookoff == True:
            if task_type == 'fungicide':
                self.fungicide_path(t)
            else:
                self.fertilize_path(t)
            is_last_waypoint = self.current_waypoint_index >= len(self.target_waypoints) - 1
            if is_last_waypoint == True and self.waypoint_reached:
                self.send_task_complete(task_type)

    def idle_callback(self, t):
        is_in_waypoint = self.is_in_waypoint(self.idle_waypoint)
        if(self.idle_count < 7 and self.has_signal == True):
            tookoff = self.takeoff(t)
            if tookoff == True:
                self.offboard_ros_messenger.publish_setpoint(t,self.idle_waypoint)
            if is_in_waypoint:
                print(f"T({self.node.get_clock().now().nanoseconds - self.t_start}): {self.agent_jid} somei 1 idle_count {self.idle_count}")
                self.idle_count += 1
        else:
            if self.has_signal == True:
                try:
                    self.idle_count = 0
                    print(f"T({self.node.get_clock().now().nanoseconds - self.t_start}): {self.agent_jid} idle_count {self.idle_count}")
                    print(f"Matei no idle_callback um processo signal para {self.agent_jid}")
                    self.offboard_signal.stop()
                    self.has_signal = False
                except Exception as e:
                    print(f"{self.agent_jid} eu tentei matar uma merda que não devia. Erro: {e}" )
            self.turned_on = False
        

    def arm_and_set_offboard_mode(self, t):
        # self.offboard_ros_messenger.publish_off_board_mode(t)
        if self.has_signal == False:
            self.count = 0
            print(f"{self.agent_jid} vai iniciar o processo de arm e offboard")
            self.turned_on = True
            self.offboard_signal.start()
            self.has_signal = True

    async def process_image(self):

        if self.latest_image is None:
            print_log(self.agent_jid.user, "No access to image")
            return
        with self.unlocked:
        
            img = self.latest_image
            h, w = img.shape[:2]
            top    = int(0.3 * h)
            bottom = int(0.7 * h)
            left   = int(0.4 * w)
            right  = int(0.6 * w)
            cropped = img[top:bottom, left:right]

            # 2) Classify the cropped center
            label = disease_classification_service.classify_from_array(cropped)
            if label != 'Healthy':
                print_log(self.agent_jid.user, f'Disease Detected: {label}')

            try:
                if label != 'Healthy':
                    msg = Message(to=str(self.agent_jid))
                    msg.set_metadata("performative", "inform")
                    msg.set_metadata("ontology", "disease_alert")
                    msg.body = f"{label}, {self.target_waypoints[self.current_waypoint_index][0]}, {self.target_waypoints[self.current_waypoint_index][1]}"
                    await self.behaviour.send(msg)
            except Exception as e:
                print(f"Error sending message to agent: {e}")
    
    def send_task_complete(self, task_string):
        self.task = 'idle'
        self.target_waypoints = []
        self.current_waypoint_index = 0
        msg = Message(to=str(self.agent_jid))
        msg.set_metadata("performative", "inform")
        msg.set_metadata("ontology", f"completed_{task_string}")
        msg.body = "Completed"
        print_log(self.agent_jid.user, f"Offboard: Task Completed {msg}")
        asyncio.run_coroutine_threadsafe(self.behaviour.send(msg), self.loop)
        return
    
    def follow_scan_path(self, t):
        is_last_waypoint = self.current_waypoint_index >= len(self.target_waypoints) - 1
        with self.unlocked:
            if self.waypoint_reached == True:
                if is_last_waypoint == False:
                    self.waypoint_reached = False
                    self.image_processing_started = False
                    self.waypoint_counter = 0
                    self.current_waypoint_index += 1
                else:
                    self.image_processing_started = False
                    self.waypoint_reached = False
            else:
                wp = self.target_waypoints[self.current_waypoint_index]
                x_diff, y_diff, z_diff = self.calculate_distance_to_point(wp)

                if (x_diff < 0.03 and y_diff < 0.03):
                    if self.waypoint_counter >= 3:
                        self.waypoint_reached = True
                    self.waypoint_counter += 1
                else:
                    self.waypoint_counter = 0

                self.offboard_ros_messenger.publish_setpoint(t, self.target_waypoints[self.current_waypoint_index])

    def fungicide_path(self, t):
        is_last_waypoint = self.current_waypoint_index >= len(self.target_waypoints) - 1
        if self.waypoint_reached == True:
            if is_last_waypoint == False:
                self.waypoint_reached = False
                self.waypoint_counter = 0
                self.current_waypoint_index += 1
        else:
            wp = self.target_waypoints[self.current_waypoint_index]
            x_diff, y_diff, z_diff = self.calculate_distance_to_point(wp)

            if self.current_waypoint_index > 0:
                self.payload_level -= self.payload_usage_fungicide
                if self.payload_level <= 0.0:
                    self.payload_level = 0.0

            if (x_diff < 0.1 and y_diff < 0.1):
                if self.waypoint_counter >= 3:
                    self.waypoint_reached = True
                self.waypoint_counter += 1
            else:
                self.waypoint_counter = 0

            self.offboard_ros_messenger.publish_setpoint(t, self.target_waypoints[self.current_waypoint_index])

    def fertilize_path(self, t):
        even_index = self.current_waypoint_index % 2 == 0
        if self.task_status_on_hold == True and even_index == False:
            self.current_waypoint_index -= 1
            if self.current_waypoint_index < 0:
                self.current_waypoint_index = 0
        self.task_status_on_hold = False
            
        is_last_waypoint = self.current_waypoint_index >= len(self.target_waypoints) - 1

        if self.waypoint_reached:
            self.was_on_hold = False
            if not is_last_waypoint:
                self.waypoint_reached = False
                self.waypoint_counter = 0
                self.current_waypoint_index += 1
        else:
            wp = self.target_waypoints[self.current_waypoint_index]
            x_diff, y_diff, z_diff = self.calculate_distance_to_point(wp)

            if x_diff < 0.15 and y_diff < 1.5:
                if even_index:
                    if self.waypoint_counter >= 1:
                        self.waypoint_reached = True
                        print_log(self.agent_jid.user, f"Applying fertilizer. Current payload charge {self.payload_level:.0f}%")
                    self.waypoint_counter += 1
                else:
                    self.waypoint_reached = True
            else:
                if even_index == False:
                    if self.was_on_hold == False:
                        self.payload_level -= self.payload_usage_fertilize

                self.waypoint_counter = 0

            self.offboard_ros_messenger.publish_setpoint(t, self.target_waypoints[self.current_waypoint_index])



    def follow_charging_path(self, t):
        if self.is_in_charging_waypoint():
            if self.first_count == True:
                self.first_count = False
                return True
            self.first_count = False
            if self.charging_counter < 3:
                self.charging_counter += 1
                self.offboard_ros_messenger.publish_setpoint(t, self.charging_station_waypoint)
                return False
            elif self.counterdown <3 :
                self.counterdown  += 1
                self.offboard_ros_messenger.publish_setpoint(t,[self.charging_station_waypoint[0], self.charging_station_waypoint[1], -1.0])
                return False
            else:
                self.is_ready_to_charge = True
                if self.has_signal == True:
                    try: 
                        print(f"Matei no charging_path( um processo signal para {self.agent_jid}")
                        self.offboard_signal.stop()
                        self.has_signal = False
                    except Exception as e: 
                        print(f"{self.agent_jid} eu tentei matar uma merda que não devia. Erro: {e}" )
                return True
        if self.first_count == True:
            print(f"T({self.node.get_clock().now().nanoseconds - self.t_start}): First count for {self.agent_jid} is True")
            self.count = 0
        self.first_count = False
        tookoff = self.takeoff(t)
        if self.drone_id == '4':
            print(f"{self.agent_jid}: Run4: tookoff: {tookoff}")
        if tookoff == True:
            self.offboard_ros_messenger.publish_setpoint(t, self.charging_station_waypoint)
        return False


    def manage_battery(self):
        if self.is_in_charging_position() == True:
            self.battery_level = self.battery_level + self.battery_recharge_rate
            if self.battery_level >= 100.0:
                self.battery_level = 100.0
                if self.task == 'recharge':
                    print_log(self.agent_jid.user, "Battery Fully Recharged.")
                    self.already_charged()
                    self.change_from_recharge_to_task_on_hold()
        else:
            self.battery_level = self.battery_level - self.battery_usage
            if self.battery_level <= 0:
                self.battery_level = 0
            if self.count % 100 == 0:
                print_log(self.agent_jid.user, f"Current Battery Charge: {self.battery_level:.0f}%")
            if self.low_battery_threshold >= self.battery_level:
                if self.task != 'recharge':
                    print_log(self.agent_jid.user, "Battery low, heading to charging station")
                    self.send_charing_intention()

    def manage_payload_and_battery(self):
        if self.is_in_charging_position() == True:
            self.battery_level = self.battery_level + self.battery_recharge_rate
            if self.battery_level >= 100.0:
                self.battery_level = 100.0

            if self.task_on_hold != self.payload_type:
                if self.payload_type == None:
                    self.charging_intentions.append("payload")
                    self.change_task_to_recharge()
                    print_log(self.agent_jid.user, "Started filling payload")
                    self.payload_level = 0
                else:
                    print_log(self.agent_jid.user, "Swapping payload")
                self.payload_type = self.task_on_hold

            if self.payload_type != None:
                self.payload_level = self.payload_level + self.payload_recharge_rate
                if self.payload_level >= 100.0:
                    self.payload_level = 100.0
                battery_fulfilled = ("battery" in self.charging_intentions and self.battery_level >= 100.0)  or ("battery" not in self.charging_intentions)
                payload_fulfilled = ("payload" in self.charging_intentions and self.payload_level >= 100.0) or ("payload" not in self.charging_intentions)
                if battery_fulfilled and payload_fulfilled and self.task == 'recharge':
                    if(self.battery_level >= 100):
                        print_log(self.agent_jid.user, "Battery Fully Recharged")
                    if(self.payload_level >= 100):
                        print_log(self.agent_jid.user, "Payload Filled")
                    self.already_charged()
                    self.change_from_recharge_to_task_on_hold()
        else:
            self.battery_level = self.battery_level - self.battery_usage
            if self.battery_level <= 0:
                self.battery_level = 0
            if self.payload_level <= 0:
                self.payload_level = 0

            has_low_battery = self.low_battery_threshold >= self.battery_level
            has_payload_empty = self.payload_level <= 0
            if self.count % 100 == 0:
                print_log(self.agent_jid.user, f"Current Battery Charge: {self.battery_level:.0f}%, Current Payload Charge: {self.payload_level:.0f}%")

            has_to_change_payload = False
            if self.task != self.payload_type and self.task != 'idle' and self.task != 'recharge':
                has_to_change_payload = True

            if  has_payload_empty or has_low_battery or has_to_change_payload:
                if self.task != 'recharge':
                    self.charging_intentions = []
                    if has_payload_empty == True:
                        print_log(self.agent_jid.user, "Payload empty, heading to charging station.")
                        self.charging_intentions.append('payload')
                    elif has_low_battery == True:
                        self.charging_intentions.append('battery')
                        print_log(self.agent_jid.user, "Battery low, heading to charging station.")
                    elif has_to_change_payload == True:
                        self.charging_intentions.append('payload')
                        print_log(self.agent_jid.user, "Heading to charging station to swap payload.")
                    self.send_charing_intention()

    def set_variables_for_activity(self):
        self.count = 0
        self.waypoint_counter = 0
        self.armed = False
        self.altitude_reached = False
        self.charging_intentions = []
        
    def reset_variables(self):
        self.count = 0
        self.waypoint_counter = 0
        self.armed = False
        self.altitude_reached = False
        self.current_waypoint_index = 0
        self.waypoint_index_on_hold = 0
        self.charging_counter = 0
        self.counterdown = 0
        self.image_processing_started = False
        self.idle_count = 0
        self.charging_intentions = []

    def calculate_distance_to_point(self, point):
        x_diff = point[0] - self.current_x
        y_diff = point[1] - self.current_y
        z_diff = abs(point[2]) - abs(self.current_z)
        return abs(x_diff), abs(y_diff), z_diff
    
    def is_in_charging_position(self):
        x_diff, y_diff, z_diff = self.calculate_distance_to_point([self.charging_station_waypoint[0], self.charging_station_waypoint[1], -0.78])
        return x_diff < 0.2 and y_diff < 0.2 and abs(z_diff) < 0.12
    
    def change_from_recharge_to_task_on_hold(self):
        self.is_ready_to_charge = False
        self.charging_counter = 0
        self.counterdown = 0
        self.task = self.task_on_hold
        if self.task != 'idle':
            self.set_variables_for_activity()
        else:
            self.reset_variables()

    def change_task_to_recharge(self):
        self.waypoint_counter = 0
        if self.task != 'recharge':
            if self.task == 'fertilize':
                self.task_status_on_hold = True
                self.was_on_hold = True
            if self.task != 'idle':
                self.task_on_hold = self.task
        self.task = 'recharge'

    def is_in_charging_waypoint(self):
        return self.is_in_waypoint(self.charging_station_waypoint, 0.3)
    
    def takeoff(self, t):
        self.arm_and_set_offboard_mode(t)
        _, _, z_diff = self.calculate_distance_to_point([0, 0, self.flying_altitude])
        if z_diff > 0.1:
           self.offboard_ros_messenger.publish_setpoint(t, [self.current_x, self.current_y, self.flying_altitude - 0.1])
           return False
        else:
            return True
        
    def is_in_waypoint(self, waypoint, diff = 0.2):
        x_diff, y_diff, z_diff = self.calculate_distance_to_point(waypoint)
        return x_diff < diff and y_diff < diff
    
    def adjust_waypoints_for_fertilization(self, waypoints):
        adjusted = waypoints.copy()
        for i in range(1, len(waypoints), 2):
            prev = waypoints[i-1]
            curr = waypoints[i]
            if prev[1] > curr[1]:
                adjusted[i] = [curr[0], curr[1] - 1.5, curr[2]]
            else:
                adjusted[i] = [curr[0], curr[1] + 1.5, curr[2]]
        return adjusted
    
    def update_flying_altitude(self, new_altitude):
        self.flying_altitude = new_altitude
        self.idle_waypoint[2] = self.flying_altitude
        self.charging_station_waypoint[2] = self.flying_altitude

    def send_charing_intention(self):
        if self.task != 'idle':
            self.task_on_hold = self.task
        self.task = 'idle'
        msg = Message(to=str(self.agent_jid))
        msg.set_metadata("performative", "inform")
        msg.set_metadata("ontology", f"battery_alert")
        msg.body = "I want to charge"
        print_log(self.agent_jid.user, f"Sent battery alert{msg}")
        asyncio.run_coroutine_threadsafe(self.behaviour.send(msg), self.loop)

    def already_charged(self):
        self.is_ready_to_charge = False
        self.battery_flag = False
        msg = Message(to=str(self.agent_jid))
        msg.set_metadata("performative", "inform")
        msg.set_metadata("ontology", f"battery_charged")
        msg.body = "I'm charged"
        asyncio.run_coroutine_threadsafe(self.behaviour.send(msg), self.loop)


    def receive_charger_available(self):
        self.turned_on = True
        print(f"{self.agent_jid} fui chamado em receive_charger_available Task: {self.task}, Task on hold: {self.task_on_hold}")
        self.count = 0
        #self.task = self.task_on_hold
        self.battery_flag = True
        self.change_task_to_recharge()
