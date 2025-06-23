from rclpy.node import Node
from px4_msgs.msg import (
    OffboardControlMode,
    TrajectorySetpoint,
    VehicleCommand,
    VehicleLocalPosition,
)
from std_msgs.msg import Float64
from sensor_msgs.msg import Image
from cv_bridge import CvBridge, CvBridgeError
from rclpy.qos import QoSProfile, ReliabilityPolicy
from offboard import disease_classification_service
from spade.message import Message
from spade.agent import Agent
import asyncio
from spade.behaviour import FSMBehaviour


class OffboardControl:
    def __init__(self, node: Node, drone_id, agent_jid, behaviour: FSMBehaviour):

        print("Using drone_id:", drone_id)
        print("Publishing to:", f'/px4_{drone_id}/fmu/in/vehicle_command')

        self.node = node
        self.agent_jid = agent_jid
        self.behaviour = behaviour

        # State
        self.image_counter = 0
        self.latest_image = None
        self.bridge = CvBridge()
        qos = QoSProfile(depth=10)
        qos.reliability = ReliabilityPolicy.BEST_EFFORT

        self.reset_variables()
        self.first_call = True


        self.current_x = 0.0
        self.current_y = 0.0
        self.current_z = 100.0

        # Publishers
        self.offboard_pub = node.create_publisher(OffboardControlMode, f'/px4_'+drone_id+'/fmu/in/offboard_control_mode', 10)
        self.setpoint_pub = node.create_publisher(TrajectorySetpoint, f'/px4_'+drone_id+'/fmu/in/trajectory_setpoint', 10)
        self.command_pub = node.create_publisher(VehicleCommand, f'/px4_'+drone_id+'/fmu/in/vehicle_command', 10)
        self.gimbal_pitch_pub = node.create_publisher(Float64, f'/model/x500_gimbal_'+drone_id+'/command/gimbal_pitch', 10)

        # Subscribers
        self.position_sub = node.create_subscription(VehicleLocalPosition, '/px4_'+drone_id+'/fmu/out/vehicle_local_position',self.position_callback, qos)
        self.image_sub = node.create_subscription(Image, f'/world/default/model/x500_gimbal_'+drone_id+'/link/camera_link/sensor/camera/image',self._image_cb, qos)

    def set_loop(self, loop):
        self.loop = loop

    def position_callback(self, msg):
        self.current_x = msg.x
        self.current_y = msg.y
        self.current_z = msg.z

    def scan(self, waypoints, waypoint_index=0):
        self.reset_variables()
        self.target_waypoints = waypoints
        self.current_waypoint_index = waypoint_index
        self.task = 'scan'
        self.nothing_to_do = False

        if(self.first_call):
            self.first_call = False
            self.scan_timer = self.node.create_timer(0.1, self.offboard_callback)

    def offboard_callback(self):
        try:
            t = self.node.get_clock().now().nanoseconds

            is_last_waypoint = self.current_waypoint_index >= len(self.target_waypoints) - 1

            if self.battery_level <= 0.0:
                print("Battery depleted")
                return

            self.manage_battery()

            if self.is_recharging == True:
                return

            if (self.nothing_to_do == True):
                self.completed_position_publishing(t)
                return
        except Exception as e:
            print(f"Error in offboard callback: {e}")
            return

        self.follow_path(t)

        self.publish_off_board_mode(t)


        if self.count == 0 and not self.armed:
            self.arm(t)
            self.armed = True
        if self.count == 15 and not self.mode_set:
            self.set_offboard_mode(t)
            self.mode_set = True

        if self.mode_set and not self.gimbal_pointed:
            self.set_gimbal_pos()

        if self.waypoint_reached == True and self.task == 'scan':
            asyncio.run_coroutine_threadsafe(self.process_image(), self.loop)

        self.count += 1

    def arm(self, t):
        msg = VehicleCommand()
        msg.timestamp = t
        msg.param1 = 1.0
        msg.command = VehicleCommand.VEHICLE_CMD_COMPONENT_ARM_DISARM
        msg.target_system = 2
        msg.target_component = 1
        msg.source_system = 1
        msg.source_component = 1
        msg.from_external = True
        self.command_pub.publish(msg)
        print('Arm command sent')

    def set_offboard_mode(self, t):

        msg = VehicleCommand()
        msg.timestamp = t
        msg.param1 = 1.0
        msg.param2 = 6.0
        msg.command = VehicleCommand.VEHICLE_CMD_DO_SET_MODE
        msg.target_system = 2
        msg.target_component = 1
        msg.source_system = 1
        msg.source_component = 1
        msg.from_external = True
        self.command_pub.publish(msg)
        print('Offboard mode command sent')

    def publish_off_board_mode(self, t):
        offboard = OffboardControlMode()
        offboard.timestamp = t
        offboard.position = True
        self.offboard_pub.publish(offboard)
    
    def _image_cb(self, msg: Image):
        try:
            frame = self.bridge.imgmsg_to_cv2(msg, 'bgr8')
            self.latest_image = frame
        except CvBridgeError as e:
            self.get_logger().error(f'CV bridge error: {e}')

    async def process_image(self):
        if self.current_waypoint_index == 0:
            return

        if self.latest_image is None:
            print('No image')
            return
        self.unlocked = True
        img = self.latest_image
        h, w = img.shape[:2]
        top    = int(0.3 * h)
        bottom = int(0.7 * h)
        left   = int(0.4 * w)
        right  = int(0.6 * w)
        cropped = img[top:bottom, left:right]

        # 2) Classify the cropped center
        label = disease_classification_service.classify_from_array(cropped)
        print(f'Predicted disease: {label}')

        try:
            if label != 'Healthy':
                print("Sending disease alert to agent:", self.agent_jid)
                print(self.behaviour)
                msg = Message(to=str(self.agent_jid))
                msg.set_metadata("performative", "inform")
                msg.set_metadata("ontology", "disease_alert")
                msg.body = f"{label}, {self.target_waypoints[self.current_waypoint_index][0]}, {self.target_waypoints[self.current_waypoint_index][1]}"
                await self.behaviour.send(msg)
        except Exception as e:
            print(f"Error sending message to agent: {e}")

    def set_gimbal_pos(self):
        print("Tried gimball")
        msg = Float64()
        msg.data = -1.5708
        self.gimbal_pitch_pub.publish(msg)
        print("Published gimbal pitch = –1.5708 rad (down)")
        self.gimbal_pointed = True
    
    def send_message_completed(self):
        self.target_waypoints = []
        self.current_waypoint_index = 0
        msg = Message(to=str(self.agent_jid))
        msg.set_metadata("performative", "inform")
        msg.set_metadata("ontology", "completed_scan")
        msg.body = "Completed"
        asyncio.run_coroutine_threadsafe(self.behaviour.send(msg), self.loop)
        return

    def completed_position_publishing(self, t):
        self.nothing_to_do = True
        offboard = OffboardControlMode()
        offboard.timestamp = t
        offboard.position = True
        self.offboard_pub.publish(offboard)
        return
    
    def follow_path(self, t):
        if self.waypoint_reached == True and self.unlocked == True:
            if self.current_waypoint_index < len(self.target_waypoints) - 1:
                self.waypoint_reached = False
                self.unlocked = False
                self.waypoint_counter = 0
                self.current_waypoint_index += 1
            else:
                print("Reached last waypoint)")
                self.nothing_to_do = True
                self.waypoint_reached = False
                self.unlocked = False
                if self.task != 'recharge':
                    self.send_message_completed()
        else:
            wp = self.target_waypoints[self.current_waypoint_index]
            x_difference = wp[0] - self.current_x
            y_difference = wp[1] - self.current_y
            z_difference = wp[2] - self.current_z

            if (self.current_waypoint_index != 0 and abs(x_difference) < 0.03 and abs(y_difference) < 0.03) or (self.current_waypoint_index == 0 and abs(z_difference) < 0.01):
                if self.waypoint_counter >= 10:
                    if self.current_waypoint_index == 0:
                        self.unlocked = True
                    self.waypoint_reached = True
                self.waypoint_counter += 1
            else:
                self.waypoint_counter = 0

        if self.nothing_to_do == False:
            sp = TrajectorySetpoint()
            sp.timestamp = t
            sp.position = self.target_waypoints[self.current_waypoint_index]
            sp.yaw = 0.0
            self.setpoint_pub.publish(sp)

    def manage_battery(self):
        is_last_waypoint = self.current_waypoint_index >= len(self.target_waypoints) - 1
        self.is_recharging = self.task == 'recharge' and is_last_waypoint and self.nothing_to_do == True

        if self.is_recharging:
            self.battery_level = self.battery_level + self.battery_recharge_rate
            if(self.count % 10 == 0):
                print(f"Recharging battery: {self.battery_level:.2f}%")
            if self.battery_level >= 100.0:
                self.battery_level = 100.0
                self.is_recharging = False
                print("Battery fully recharged")
                self.nothing_to_do = False
                # insert in first position of waypoints on hold the charging station waypoint
                self.waypoints_on_hold.insert(self.waypoint_index_on_hold, self.charging_station_waypoint)
                self.scan(self.waypoints_on_hold, self.waypoint_index_on_hold)
        else:
            self.battery_level = self.battery_level - self.battery_usage
            if self.count % 10 == 0:
                print(f"Battery level: {self.battery_level:.2f}%")
            if self.low_battery_threshold >= self.battery_level:
                print("Battery low, heading to charging station")
                if self.task != 'recharge':
                    self.waypoints_on_hold = self.target_waypoints
                    self.waypoint_index_on_hold = self.current_waypoint_index
                    self.target_waypoints = [self.charging_station_waypoint]
                    self.current_waypoint_index = 0
                    self.task = 'recharge'
                return
        
    def reset_variables(self):
        self.task = None
        self.nothing_to_do = True
        self.count = 0
        self.waypoint_counter = 0
        self.mode_set = False
        self.armed = False
        self.altitude_reached = False
        self.unlocked = False
        self.waypoint_reached = False
        self.current_waypoint_index = 0
        self.gimbal_pointed = False
        self.waypoint_index_on_hold = 0
        self.charging_station_waypoint = [0.0, 7.0, -1.3]
        self.is_recharging = False
        self.battery_recharge_rate = 1.0
        self.battery_level = 100.0
        self.battery_usage = 0.15
        self.low_battery_threshold = 30.0
        self.waypoints_on_hold = []