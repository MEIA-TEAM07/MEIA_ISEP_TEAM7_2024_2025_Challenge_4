from px4_msgs.msg import (
    OffboardControlMode,
    TrajectorySetpoint,
    VehicleCommand,
    VehicleLocalPosition,
)
from spade.behaviour import FSMBehaviour
from rclpy.node import Node
from std_msgs.msg import Float64
from sensor_msgs.msg import Image
from rclpy.qos import QoSProfile, ReliabilityPolicy
from cv_bridge import CvBridge, CvBridgeError
from config import (OFF_SET_DRONES)

class OffboardRosMessenger:
    def __init__(self, offboardControl, node: Node, drone_id):
        try:
            self.drone_id = drone_id
            qos = QoSProfile(depth=10)
            qos.reliability = ReliabilityPolicy.BEST_EFFORT
            self.bridge = CvBridge()
            self.offboardControl = offboardControl
            print(f"Drone ID messenger: {drone_id}")

            # Publishers
            self.offboard_pub = node.create_publisher(OffboardControlMode, f'/px4_{self.drone_id}/fmu/in/offboard_control_mode', 10)
            self.setpoint_pub = node.create_publisher(TrajectorySetpoint, f'/px4_{self.drone_id}/fmu/in/trajectory_setpoint', 10)
            self.command_pub = node.create_publisher(VehicleCommand, f'/px4_{self.drone_id}/fmu/in/vehicle_command', 10)
            self.gimbal_pitch_pub = node.create_publisher(Float64, f'/model/x500_gimbal_{self.drone_id}/command/gimbal_pitch', 10)
            self.x_offset, self.y_offset = self.return_offset()

            # Subscribers
            self.position_sub = node.create_subscription(VehicleLocalPosition, f'/px4_{self.drone_id}/fmu/out/vehicle_local_position', self.position_callback, qos)
            self.image_sub = node.create_subscription(Image, f'/world/default/model/x500_gimbal_{self.drone_id}/link/camera_link/sensor/camera/image', self._image_cb, qos)

        except Exception as e:
            print(f"❗ Error during setup: {e}")
    

    def _image_cb(self, msg: Image):
        try:
            frame = self.bridge.imgmsg_to_cv2(msg, 'bgr8')
            self.offboardControl.self.latest_image = frame
        except CvBridgeError as e:
            self.get_logger().error(f'CV bridge error: {e}')

    def position_callback(self, msg):
        try:
            self.offboardControl.current_x = msg.x + self.x_offset
            self.offboardControl.current_y = msg.y + self.y_offset
            self.offboardControl.current_z = msg.z
        except Exception as e:
            print(f"{e}")

    def arm(self, t):
        try:
            msg = VehicleCommand()
            msg.timestamp = t
            msg.param1 = 1.0
            msg.command = VehicleCommand.VEHICLE_CMD_COMPONENT_ARM_DISARM
            msg.target_system = int(self.drone_id) + 1
            msg.target_component = 1
            msg.source_system = 1
            msg.source_component = 1
            msg.from_external = True
            self.command_pub.publish(msg)
        except Exception as e:
            print(e)

    def set_offboard_mode(self, t):
        try:
            msg = VehicleCommand()
            msg.timestamp = t
            msg.param1 = 1.0
            msg.param2 = 6.0
            msg.command = VehicleCommand.VEHICLE_CMD_DO_SET_MODE
            msg.target_system = int(self.drone_id) + 1
            msg.target_component = 1
            msg.source_system = 1
            msg.source_component = 1
            msg.from_external = True
            self.command_pub.publish(msg)
        except Exception as e:
            print(e)

    def publish_off_board_mode(self, t):
        try:
            offboard = OffboardControlMode()
            offboard.timestamp = t
            offboard.position = True
            self.offboard_pub.publish(offboard)
        except Exception as e:
            print(e)
    
    def _image_cb(self, msg: Image):
        try:
            frame = self.bridge.imgmsg_to_cv2(msg, 'bgr8')
            self.offboardControl.latest_image = frame
        except CvBridgeError as e:
            self.get_logger().error(f'CV bridge error: {e}')
    
    def publish_setpoint(self, t, waypoint):
        
        try:
            sp = TrajectorySetpoint()
            sp.timestamp = t
            sp.position = [waypoint[0] - self.x_offset, waypoint[1] - self.y_offset, waypoint[2]]
            sp.yaw = 0.0
            self.setpoint_pub.publish(sp)
        except Exception as e:
            print(e)

    def set_gimbal_pos(self):
        try:
            print("Tried gimball")
            msg = Float64()
            msg.data = -1.5708
            self.gimbal_pitch_pub.publish(msg)
            self.offboardControl.gimbal_pointed = True
        except Exception as e:
            print(e)
    
    def return_offset(self):
        for offset in OFF_SET_DRONES:
            if offset["drone_id"] == self.drone_id:
                return offset["offset"]
        return None