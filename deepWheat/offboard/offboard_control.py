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


class OffboardControl:
    def __init__(self, node: Node, drone_id, agent: Agent):

        print("Using drone_id:", drone_id)
        print("Publishing to:", f'/px4_{drone_id}/fmu/in/vehicle_command')

        self.node = node
        self.agent = agent

        # State
        self.image_counter = 0
        self.latest_image = None
        self.bridge = CvBridge()
        qos = QoSProfile(depth=10)
        qos.reliability = ReliabilityPolicy.BEST_EFFORT

        self.count = 0
        self.waypoint_counter = 0
        self.mode_set = False
        self.armed = False
        self.altitude_reached = False
        self.unlocked = False
        self.waypoint_reached = False
        self.current_waypoint_index = 0
        self.first_scan = True
        self.gimbal_pointed = False

        self.current_x = 0.0
        self.current_y = 0.0
        self.current_z = 100.0
        

        # Publishers
        self.offboard_pub = node.create_publisher(OffboardControlMode, f'/px4_'+drone_id+'/fmu/in/offboard_control_mode', 10)
        self.setpoint_pub = node.create_publisher(TrajectorySetpoint, f'/px4_'+drone_id+'/fmu/in/trajectory_setpoint', 10)
        self.command_pub = node.create_publisher(VehicleCommand, f'/px4_'+drone_id+'/fmu/in/vehicle_command', 10)
        self.gimbal_pitch_pub = node.create_publisher(Float64, f'/model/x500_gimbal_'+drone_id+'/command/gimbal_pitch', 10)

        # self.offboard_pub = node.create_publisher(OffboardControlMode, '/fmu/in/offboard_control_mode', 10)
        # self.setpoint_pub = node.create_publisher(TrajectorySetpoint, '/fmu/in/trajectory_setpoint', 10)
        # self.command_pub = node.create_publisher(VehicleCommand, '/fmu/in/vehicle_command', 10)
        # self.gimbal_pitch_pub = node.create_publisher(Float64, f'/model/x500_gimbal_0/command/gimbal_pitch', 10)

        # Subscribers
        # self.position_sub = node.create_subscription(VehicleLocalPosition, '/fmu/out/vehicle_local_position',self.position_callback, qos)
        # self.image_sub = node.create_subscription(Image, f'/world/default/model/x500_gimbal_0/link/camera_link/sensor/camera/image',self._image_cb, qos)
        self.position_sub = node.create_subscription(VehicleLocalPosition, '/px4_'+drone_id+'/fmu/out/vehicle_local_position',self.position_callback, qos)
        self.image_sub = node.create_subscription(Image, f'/world/default/model/x500_gimbal_1/link/camera_link/sensor/camera/image',self._image_cb, qos)

    def position_callback(self, msg):
        self.current_x = msg.x
        self.current_y = msg.y
        self.current_z = msg.z

    def scan(self, waypoints):
        self.target_waypoints = waypoints
        print(waypoints)

        if(self.first_scan):
            self.scan_timer = self.node.create_timer(0.1, self.scan_callback)

    def scan_callback(self):
        t = self.node.get_clock().now().nanoseconds

        if self.current_waypoint_index >= len(self.target_waypoints) - 1:
            self.completed_position_publishing(t)
            return
            
        if self.waypoint_reached:
                if self.unlocked:
                    self.unlocked = False
                    self.waypoint_counter = 0
                    self.current_waypoint_index += 1
        else:
            wp = self.target_waypoints[self.current_waypoint_index]
            x_difference = wp[0] - self.current_x
            y_difference = wp[1] - self.current_y
            z_difference = wp[2] - self.current_z

            if (abs(x_difference) < 0.03 and abs(y_difference) < 0.03) or (self.current_waypoint_index == 0 and abs(z_difference) < 0.01):
                if self.waypoint_counter >= 10:
                    if self.current_waypoint_index == 0:
                        self.unlocked = True
                    self.waypoint_reached = True
            else:
                self.waypoint_counter = 0

        self.waypoint_counter += 1

        sp = TrajectorySetpoint()
        sp.timestamp = t
        sp.position = self.target_waypoints[self.current_waypoint_index]
        sp.yaw = 0.0
        self.setpoint_pub.publish(sp)

        self.publish_off_board_mode(t)

        if self.count == 0 and not self.armed:
            self.arm(t)
            self.armed = True
        if self.count == 15 and not self.mode_set:
            self.set_offboard_mode(t)
            self.mode_set = True

        if self.mode_set and not self.gimbal_pointed:
            self.set_gimbal_pos()

        self.count += 1

        if self.count % 100 == 0:
            self.process_image()

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

        if label != 'healthy':
            msg = Message(to=self.agent.jid)
            msg.set_metadata("performative", "inform")
            msg.set_metadata("ontology", "disease_alert")
            msg.body = f"{label}, {self.target_waypoints[self.current_waypoint_index][0]}, {self.target_waypoints[self.current_waypoint_index][1]}"
            await self.send(msg)

        self.unlocked = True


        
    def set_gimbal_pos(self):
        print("Tried gimball")
        msg = Float64()
        msg.data = -1.5708
        self.gimbal_pitch_pub.publish(msg)
        print("Published gimbal pitch = –1.5708 rad (down)")
        self.gimbal_pointed = True

    def completed_position_publishing(self, t):
        offboard = OffboardControlMode()
        offboard.timestamp = t
        offboard.position = True
        self.offboard_pub.publish(offboard)
        return
        