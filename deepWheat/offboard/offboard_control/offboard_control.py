import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import Image
from std_msgs.msg import Float64
from px4_msgs.msg import (
    OffboardControlMode,
    TrajectorySetpoint,
    VehicleCommand,
    VehicleLocalPosition,
)
from cv_bridge import CvBridge, CvBridgeError
from .disease_classification_service import classify_from_array
from . import routing_service
from . import field_plant_location_loader

class OffboardControl(Node):
    def __init__(self, node_name: str):
        super().__init__(node_name)

    def setDrone(self, drone, drone_id, init_pos): 

        # States
        self.count = 0
        self.waypoint_counter = 0
        self.mode_set = False
        self.armed = False
        self.altitude_reached = False
        self.waypoint_reached = False
        self.current_waypoint_index = 0

        # Publishers
        self.offboard_pub = self.create_publisher(OffboardControlMode, f'/px4_{drone_id}/fmu/in/offboard_control_mode', 10)
        self.setpoint_pub = self.create_publisher(TrajectorySetpoint, f'/px4_{drone_id}/fmu/in/trajectory_setpoint', 10)
        self.command_pub = self.create_publisher(VehicleCommand, f'/px4_{drone_id}/fmu/in/vehicle_command', 10)

        # QoS Profile
        qos = QoSProfile(depth=10)
        qos.reliability = ReliabilityPolicy.BEST_EFFORT

        # Subscribers
        self.position_sub = self.create_subscription(VehicleLocalPosition, f'px4_{drone_id}/fmu/out/vehicle_local_position',self.position_callback, qos)

        # Initialize position
        self.current_x, self.current_y, self.current_z = init_pos

        if drone == "Vigilant":
            # Publisher
            self.gimbal_pitch_pub = self.create_publisher(Float64,f'/model/x500_gimbal_0/command/gimbal_pitch', 10)
            # Subscriber
            self.image_sub = self.create_subscription(Image, '/world/default/model/x500_gimbal_0/link/camera_link/sensor/camera/image',self._image_cb, qos)
            # State
            self.unlocked = False
            self.image_counter = 0
            self.bridge = CvBridge()
            self.latest_image = None
            self.gimbal_pointed = False
            # Timers
            self.timer = self.create_timer(0.1, self.timer_callback_gimbal)
            self.log_timer = self.create_timer(1.0, self.log_position_callback)
        else:
            # Timers
            self.timer = self.create_timer(0.1, self.timer_callback)
            self.log_timer = self.create_timer(1.0, self.log_position_callback)

    def setField(self, field):
        self.target_waypoints = field_plant_location_loader.return_plant_locations_by_field(field)
        self.target_waypoints.insert(0, [self.current_x, self.current_y, -1.3])
        self.target_waypoints = routing_service.find_shortest_path(self.target_waypoints)


    def position_callback(self, msg):
        self.current_x = msg.x
        self.current_y = msg.y
        self.current_z = msg.z

    def log_position_callback(self):
        self.get_logger().info(
            f"Current Position -> X: {self.current_x:.2f}, Y: {self.current_y:.2f}, Z: {self.current_z:.2f}"
        )

    def timer_callback(self):
        t = self.get_clock().now().nanoseconds
        if self.current_waypoint_index >= len(self.target_waypoints) - 1:
            self.completed_position_publishing(t)
            return
                
        self.waypoint_counter += 1

        # Send trajectory setpoint
        sp = TrajectorySetpoint()
        sp.timestamp = t
        sp.position = self.target_waypoints[self.current_waypoint_index]
        sp.yaw = 0.0
        self.setpoint_pub.publish(sp)

        self.publish_off_board_mode(t)

        # Arm and switch to offboard
        if self.count == 10 and not self.armed:
            self.arm()
            self.armed = True
        if self.count == 15 and not self.mode_set:
            self.set_offboard_mode()
            self.mode_set = True

        self.count += 1

    def timer_callback_gimbal(self):
        t = self.get_clock().now().nanoseconds
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

        # Send trajectory setpoint
        sp = TrajectorySetpoint()
        sp.timestamp = t
        sp.position = self.target_waypoints[self.current_waypoint_index]
        sp.yaw = 0.0
        self.setpoint_pub.publish(sp)

        self.publish_off_board_mode(t)

        # Arm and switch to offboard
        if self.count == 10 and not self.armed:
            self.arm()
            self.armed = True
        if self.count == 15 and not self.mode_set:
            self.set_offboard_mode()
            self.mode_set = True

        if self.mode_set and not self.gimbal_pointed:
            self.set_gimbal_pos()

        self.count += 1

        if self.count % 100 == 0:
            self.process_image()             

    def arm(self):
        msg = VehicleCommand()
        msg.timestamp = self.get_clock().now().nanoseconds
        msg.param1 = 1.0
        msg.command = VehicleCommand.VEHICLE_CMD_COMPONENT_ARM_DISARM
        msg.target_system = 1
        msg.target_component = 1
        msg.source_system = 1
        msg.source_component = 1
        msg.from_external = True
        self.command_pub.publish(msg)
        self.get_logger().info('Arm command sent')

    def set_offboard_mode(self):
        msg = VehicleCommand()
        msg.timestamp = self.get_clock().now().nanoseconds
        msg.param1 = 1.0  # custom mode
        msg.param2 = 6.0  # PX4 Offboard mode ID
        msg.command = VehicleCommand.VEHICLE_CMD_DO_SET_MODE
        msg.target_system = 1
        msg.target_component = 1
        msg.source_system = 1
        msg.source_component = 1
        msg.from_external = True
        self.command_pub.publish(msg)
        self.get_logger().info('Offboard mode command sent')

    def publish_off_board_mode(t, self):
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
    
    def process_image(self):
        if self.current_waypoint_index == 0:
            return

        if self.latest_image is None:
            self.get_logger().info('No image')
            return

        img = self.latest_image
        h, w = img.shape[:2]
        top    = int(0.3 * h)
        bottom = int(0.7 * h)
        left   = int(0.4 * w)
        right  = int(0.6 * w)
        cropped = img[top:bottom, left:right]

        # 2) Classify the cropped center
        label = classify_from_array(cropped)
        self.get_logger().info(f'Predicted disease: {label}')
        self.unlocked = True
        
    def set_gimbal_pos(self):
        self.get_logger().info("Tried gimball")
        msg = Float64()
        msg.data = -1.5708
        self.gimbal_pitch_pub.publish(msg)
        self.get_logger().info("Published gimbal pitch = –1.5708 rad (down)")
        self.gimbal_pointed = True

    def completed_position_publishing(self, t):
        offboard = OffboardControlMode()
        offboard.timestamp = t
        offboard.position = True
        self.offboard_pub.publish(offboard)
        return
