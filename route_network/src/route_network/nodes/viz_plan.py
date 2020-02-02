#!/usr/bin/env python
# Software License Agreement (BSD License)
#
# Copyright (C) 2012, Jack O'Quin
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
#  * Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
#  * Redistributions in binary form must reproduce the above
#    copyright notice, this list of conditions and the following
#    disclaimer in the documentation and/or other materials provided
#    with the distribution.
#  * Neither the name of the author nor of other contributors may be
#    used to endorse or promote products derived from this software
#    without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
# COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
# Revision $Id$

"""
Visualize route plan for geographic map.
"""
import rclpy
from rclpy.node import Node

import sys
import random
import geodesy.wu_point

from geographic_msgs.msg import RouteNetwork
from geographic_msgs.msg import RouteSegment
from geographic_msgs.srv import GetRoutePlan
from geometry_msgs.msg import Point
from geometry_msgs.msg import Quaternion
from geometry_msgs.msg import Vector3
from std_msgs.msg import ColorRGBA
from visualization_msgs.msg import Marker
from visualization_msgs.msg import MarkerArray

from unique_identifier_msgs.msg import UUID


class VizPlanNode(Node):

    def __init__(self):
        """
        ROS node to visualize a route plan.
        """
        super(VizPlanNode, self).__init__("viz_plan")
        self.graph = None

        # advertise visualization marker topic
        self.pub = self.create_publisher(MarkerArray, 'visualization_marker_array', 10)

        self.get_plan  = self.create_client(GetRoutePlan, 'get_route_plan')
        while not self.get_plan .wait_for_service(timeout_sec=1.0):
            self.get_logger().info('service not available, waiting again...')

        # subscribe to route network
        self.sub = self.create_subscription(RouteNetwork, 'route_network', self.graph_callback, 10)

        self.timer_interval = 4
        self.marker_life = self.timer_interval + 1
        self.timer = self.create_timer(self.timer_interval, self.timer_callback)

    def graph_callback(self, graph):
        """Handle RouteNetwork message.

        :param graph: RouteNetwork message.

        :post: self.graph = RouteNetwork message
        :post: self.points = visualization markers message.
        """
        self.points = geodesy.wu_point.WuPointSet(graph.points)
        self.segment_ids = {}  # segments symbol table
        for sid in range(len(graph.segments)):
            self.segment_ids[graph.segments[sid].id.uuid] = sid
        self.graph = graph

    def timer_callback(self):
        """
        Called periodically.
        """
        if self.graph is None:
            print('still waiting for graph')
            return

        # select two different way points at random
        idx0, idx1 = random.sample(range(len(self.graph.points)), 2)
        start = self.graph.points[idx0].id.uuid
        goal = self.graph.points[idx1].id.uuid
        sefl.get_logger().info('plan from ' + start + ' to ' + goal)

        try:
            resp = self.get_plan(self.graph.id,
                                 UUID(uuid=start),
                                 UUID(uuid=goal))
        except rclpy.ServiceException as e:
            self.get_logger().error("Service call failed: " + str(e))
        else:  # get_map returned
            if resp.success:
                self.mark_plan(resp.plan)
            else:
                self.get_logger().error('get_route_plan failed, status: ' + str(resp.status))

    def mark_plan(self, plan):
        """
        Publish visualization markers for a RoutePath.

        :param plan: RoutePath message
        """
        marks = MarkerArray()
        hdr = self.graph.header
        hdr.stamp = self.now()
        index = 0
        for seg_msg in plan.segments:
            marker = Marker(header=hdr,
                            ns='plan_segments',
                            id=index,
                            type=Marker.LINE_STRIP,
                            action=Marker.ADD,
                            scale=Vector3(x=4.0),
                            color=ColorRGBA(r=1.0, g=1.0, b=1.0, a=0.8),
                            lifetime=self.marker_life)
            index += 1
            segment = self.graph.segments[self.segment_ids[seg_msg.uuid]]
            marker.points.append(self.points[segment.start.uuid].toPointXY())
            marker.points.append(self.points[segment.end.uuid].toPointXY())
            marks.markers.append(marker)

        self.pub.publish(marks)


def main(args=None):
    rclpy.init(args=args)
    node_class = VizPlanNode()

    try:
        rclpy.spin(node_class)  # wait for messages
    except rclpy.exceptions.ROSInterruptException:
        pass

    node_class.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    # run main function and exit
    sys.exit(main())
