import threading
from rclpy.node import Node
from offboard import disease_classification_service
from spade.message import Message
import asyncio
from spade.behaviour import FSMBehaviour
from offboard.offboard_ros_messenger import OffboardRosMessenger
from utils.logger import print_log


class OffboardControl:
    def __init__(self, node: Node, drone_id, agent_jid, behaviour: FSMBehaviour):
        try:
            self.node = node
            self.agent_jid = agent_jid
            self.behaviour = behaviour
            self.flying_altitude = -1.3

            # State
            self.task = None
            self.task_on_hold = None
            self.image_counter = 0
            self.latest_image = None
            self.reset_variables()
            self.battery_level = 100.0
            self.first_call = True
            self.idle_waypoint = [-3.0, 7.0, self.flying_altitude]
            self.charging_station_waypoint = [0.0, 7.0, self.flying_altitude]
            self.battery_recharge_rate = 0.7
            self.battery_usage = 0.06
            self.low_battery_threshold = 30.0
            self.idle_count = 0
            self.turned_on = True
            self.current_x = 0.0
            self.current_y = 0.0
            self.current_z = 100.0

            self.offboard_ros_messenger = OffboardRosMessenger(self, node,drone_id)

            self.unlocked = threading.Lock()
        except Exception as e:
            print(f"Error initializing OffboardControl: {e}")


    def set_loop(self, loop):
        self.loop = loop

    def scan(self, waypoints, waypoint_index=0):
        self.reset_variables()
        self.target_waypoints = waypoints
        self.current_waypoint_index = waypoint_index
        self.task = 'scan'
        self.turned_on = True

        if(self.first_call):
            self.first_call = False
            self.scan_timer = self.node.create_timer(0.1, self.offboard_callback)

    def offboard_callback(self):
        try:
            self.count += 1
            t = self.node.get_clock().now().nanoseconds

            if self.turned_on == False:
                return
            
            self.manage_battery()

            if self.battery_level <= 0.0:
                print("Battery depleted")
                return

            if self.task == 'scan':
                self.scan_callback(t)
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

        self.arm_and_set_offboard_mode(t)

        if self.mode_set and not self.gimbal_pointed:
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
                            self.send_scan_complete()

    def charging_callback(self, t):
        is_ready_to_charge = self.follow_charging_path(t)
        if is_ready_to_charge == False:
            self.arm_and_set_offboard_mode(t)
        return

    def idle_callback(self, t):
        is_in_waypoint = self.is_in_waypoint(self.idle_waypoint)
        if(self.idle_count < 5):
            self.arm_and_set_offboard_mode(t)
            tookoff = self.takeoff(t)
            if tookoff == True:
                self.offboard_ros_messenger.publish_setpoint(t,self.idle_waypoint)
            if is_in_waypoint:
                self.idle_count += 1
        else:
            self.turned_on = False
        

    def arm_and_set_offboard_mode(self, t):
        self.offboard_ros_messenger.publish_off_board_mode(t)

        if self.count == 1 and not self.armed:
            self.offboard_ros_messenger.arm(t)
            self.armed = True
        if self.count == 16 and not self.mode_set:
            self.offboard_ros_messenger.set_offboard_mode(t)
            self.mode_set = True
            print_log(self.agent_jid.user, "Ready for Takeoff")

    async def process_image(self):

        if self.latest_image is None:
            print('No image')
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
    
    def send_scan_complete(self):
        self.task = 'idle'
        self.target_waypoints = []
        self.current_waypoint_index = 0
        msg = Message(to=str(self.agent_jid))
        msg.set_metadata("performative", "inform")
        msg.set_metadata("ontology", "completed_scan")
        msg.body = "Completed"
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
                    if self.waypoint_counter >= 10:
                        self.waypoint_reached = True
                    self.waypoint_counter += 1
                else:
                    self.waypoint_counter = 0

                self.offboard_ros_messenger.publish_setpoint(t, self.target_waypoints[self.current_waypoint_index])

    def follow_charging_path(self, t):
        if self.is_in_charging_waypoint():
            if self.charging_counter < 10:
                self.charging_counter += 1
                self.offboard_ros_messenger.publish_setpoint(t, self.charging_station_waypoint)
                return False
            else:
                return True
            
        self.offboard_ros_messenger.publish_setpoint(t, self.charging_station_waypoint)
        return False


    def manage_battery(self):
        if self.is_in_charging_position() == True:
            self.battery_level = self.battery_level + self.battery_recharge_rate
            if self.battery_level >= 100.0:
                self.battery_level = 100.0
                if self.task == 'recharge':
                    print_log(self.agent_jid.user, "Battery Fully Recharged.")
                    self.change_from_recharge_to_task_on_hold()
        else:
            self.battery_level = self.battery_level - self.battery_usage
            if self.battery_level <= 0:
                self.battery_level = 0
            if self.count % 100 == 0:
                print_log(self.agent_jid.user, f"Current Battery Charge: {self.battery_level:.2f}%")
            if self.low_battery_threshold >= self.battery_level:
                if self.task != 'recharge':
                    print_log(self.agent_jid.user, "Battery low, heading to charging station")
                    self.change_task_to_recharge()

    def set_variables_for_activity(self):
        self.count = 0
        self.waypoint_counter = 0
        self.mode_set = False
        self.armed = False
        self.altitude_reached = False
        self.waypoint_reached = 0
        self.gimbal_pointed = False

        
    def reset_variables(self):
        self.count = 0
        self.waypoint_counter = 0
        self.mode_set = False
        self.armed = False
        self.altitude_reached = False
        self.waypoint_reached = False
        self.current_waypoint_index = 0
        self.gimbal_pointed = False
        self.waypoint_index_on_hold = 0
        self.charging_counter = 0
        self.image_processing_started = False
        self.idle_count = 0

    def calculate_distance_to_point(self, point):
        x_diff = point[0] - self.current_x
        y_diff = point[1] - self.current_y
        z_diff = abs(point[2]) - abs(self.current_z)
        return abs(x_diff), abs(y_diff), z_diff
    
    def is_in_charging_position(self):
        x_diff, y_diff, z_diff = self.calculate_distance_to_point([self.charging_station_waypoint[0], self.charging_station_waypoint[1], -0.78])
        return x_diff < 0.2 and y_diff < 0.2 and abs(z_diff) < 0.12
    
    def change_from_recharge_to_task_on_hold(self):
        self.charging_counter = 0
        self.task = self.task_on_hold
        if self.task == 'scan':
            self.set_variables_for_activity()
        elif self.task == 'idle':
            self.reset_variables()

    def change_task_to_recharge(self):
        self.waypoint_counter = 0
        self.task_on_hold = self.task
        self.task = 'recharge'

    def is_in_charging_waypoint(self):
        return self.is_in_waypoint(self.charging_station_waypoint)
    
    def takeoff(self, t):
        _, _, z_diff = self.calculate_distance_to_point([0, 0, self.flying_altitude])
        if z_diff > 0.1:
           self.offboard_ros_messenger.publish_setpoint(t, [self.current_x, self.current_y, self.flying_altitude - 0.1])
           return False
        else:
            return True
        
    def is_in_waypoint(self, waypoint):
        x_diff, y_diff, z_diff = self.calculate_distance_to_point(waypoint)
        return x_diff < 0.2 and y_diff < 0.2