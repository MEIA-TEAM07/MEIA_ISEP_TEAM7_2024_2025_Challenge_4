import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from px4_msgs.msg import OffboardControlMode, TrajectorySetpoint, VehicleCommand
from std_msgs.msg import Float64

class OffboardControlTest(Node):
    def __init__(self):
        super().__init__('offboard_control_test_node')
        self.get_logger().info("OffboardControlTest node started!")
        self.subscription = self.create_subscription(
            String,
            '/test_takeoff',
            self.takeoff_callback,
            10
        )

        self.count = 0
        self.mode_set = False
        self.armed = False
        

        self.offboard_pub = self.create_publisher(OffboardControlMode, '/fmu/in/offboard_control_mode', 10)
        self.setpoint_pub = self.create_publisher(TrajectorySetpoint, '/fmu/in/trajectory_setpoint', 10)
        self.command_pub = self.create_publisher(VehicleCommand, '/fmu/in/vehicle_command', 10)
        self.gimbal_pitch_pub = self.create_publisher(Float64,'/model/x500_gimbal_0/command/gimbal_pitch', 10)

        self.timer = self.create_timer(0.1, self.timer_callback)



    def timer_callback(self):
        t = self.get_clock().now().nanoseconds

        sp = TrajectorySetpoint()
        sp.timestamp = t
        sp.position = [0.0, 0.0, -1.3]
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
        msg.param1 = 1.0  # custom <
        msg.param2 = 6.0  # PX4 Offboard mode ID
        msg.command = VehicleCommand.VEHICLE_CMD_DO_SET_MODE
        msg.target_system = 1
        msg.target_component = 1
        msg.source_system = 1
        msg.source_component = 1
        msg.from_external = True
        self.command_pub.publish(msg)
        self.get_logger().info('Offboard mode command sent')

    def publish_off_board_mode(self, t):
        offboard = OffboardControlMode()
        offboard.timestamp = t
        offboard.position = True
        self.offboard_pub.publish(offboard)
        
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


    def takeoff_callback(self, msg):
        self.get_logger().info(f"Received takeoff command: {msg.data}")

