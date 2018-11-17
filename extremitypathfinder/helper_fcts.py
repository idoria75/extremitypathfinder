from itertools import combinations

import numpy as np

from .helper_classes import AngleRepresentation


# TODO numba precompilation of some parts possible?! do profiling first!


def inside_polygon(x, y, coords, border_value):
    # should return the border value for point equal to any polygon vertex
    # TODO overflow possible with large values when comparing slopes, change procedure
    for c in coords[:]:
        if np.all(c == [x, y]):
            return border_value

    # and if the point p lies on any polygon edge
    p = np.array([x, y])
    p1 = coords[-1, :]
    for p2 in coords[:]:
        if abs((AngleRepresentation(p1 - p).value - AngleRepresentation(p2 - p).value)) == 2.0:
            return border_value
        p1 = p2

    contained = False
    # the edge from the last to the first point is checked first
    i = -1
    y1 = coords[-1, 1]
    y_gt_y1 = y > y1
    for y2 in coords[:, 1]:
        y_gt_y2 = y > y2
        if y_gt_y1:
            if not y_gt_y2:
                x1 = coords[i, 0]
                x2 = coords[i + 1, 0]
                # only crossings "right" of the point should be counted
                x1GEx = x <= x1
                x2GEx = x <= x2
                # compare the slope of the line [p1-p2] and [p-p2]
                # depending on the position of p2 this determines whether the polygon edge is right or left of the point
                # to avoid expensive division the divisors (of the slope dy/dx) are brought to the other side
                # ( dy/dx > a  ==  dy > a * dx )
                if (x1GEx and x2GEx) or ((x1GEx or x2GEx) and (y2 - y) * (x2 - x1) <= (y2 - y1) * (x2 - x)):
                    contained = not contained

        else:
            if y_gt_y2:
                x1 = coords[i, 0]
                x2 = coords[i + 1, 0]
                # only crossings "right" of the point should be counted
                x1GEx = x <= x1
                x2GEx = x <= x2
                if (x1GEx and x2GEx) or ((x1GEx or x2GEx) and (y2 - y) * (x2 - x1) >= (y2 - y1) * (x2 - x)):
                    contained = not contained

        y1 = y2
        y_gt_y1 = y_gt_y2
        i += 1

    return contained


def no_identical_consequent_vertices(coords):
    p1 = coords[-1]
    for p2 in coords:
        # TODO adjust allowed difference epsilon
        assert not np.allclose(p1, p2)
        p1 = p2

    return True


def get_intersection_status(p1, p2, q1, q2):
    # return:
    #   0: no intersection
    #   1: intersection in ]p1;p2[
    # TODO 4 different possibilities
    #   2: intersection directly in p1 or p2
    #   3: intersection directly in q1 or q2
    # solve the set of equations
    # (p2-p1) lambda + (p1) = (q2-q1) mu + (q1)
    #  in matrix form A x = b:
    # [(p2-p1) (q1-q2)] (lambda, mu)' = (q1-p1)
    A = np.array([p2 - p1, q1 - q2]).T
    b = np.array(q1 - p1)
    try:
        x = np.linalg.solve(A, b)
        # not crossing the line segment is considered to be ok
        # so x == 0.0 or x == 1.0 is not considered an intersection
        # assert np.allclose((p2 - p1) * x[0] + p1, (q2 - q1) * x[1] + q1)
        # assert np.allclose(np.dot(A, x), b)
        if x[0] <= 0.0 or x[1] <= 0.0 or x[0] >= 1.0 or x[1] >= 1.0:
            return 0
        # if np.all(0.0 <= x) and np.all(x <= 1.0):
        #     return 2
    except np.linalg.LinAlgError:
        # line segments are parallel (matrix is singular, set of equations is not solvable)
        return 0

    return 1


# special case of has_intersection()
def lies_behind(p1, p2, v):
    # solve the set of equations
    # (p2-p1) lambda + (p1) = (v) mu
    #  in matrix form A x = b:
    # [(p1-p2) (v)] (lambda, mu)' = (p1)
    # because the vertex lies within the angle range between the two edge vertices
    #    (together with the other conditions on the polygons)
    #   this set of linear equations is always solvable (the matrix is regular)
    A = np.array([p1 - p2, v]).T
    b = np.array(p1)
    x = np.linalg.solve(A, b)

    # Debug:
    # try:
    #     x = np.linalg.solve(A, b)
    # except np.linalg.LinAlgError:
    #     raise ValueError
    # assert np.allclose((p2 - p1) * x[0] + p1, v * x[1])
    # assert np.allclose(np.dot(A, x), b)

    # vertices on the edge are possibly visible! ( < not <=)
    return x[1] < 1.0


def no_self_intersection(coords):
    polygon_length = len(coords)
    again_check = []
    for index_p1, index_q1 in combinations(range(polygon_length), 2):
        # always: index_p1 < index_q1
        if index_p1 == index_q1 - 1 or index_p1 == index_q1 + 1:
            # neighbouring edges never have an intersection
            continue
        p1, p2 = coords[index_p1], coords[(index_p1 + 1) % polygon_length]
        q1, q2 = coords[index_q1], coords[(index_q1 + 1) % polygon_length]
        intersect_status = get_intersection_status(p1, p2, q1, q2)
        if intersect_status == 1:
            return False
        # if intersect_status == 2:
        # TODO 4 different options. check which side the other edge lies on.
        # if edge changes sides this is a an intersection
        # again_check.append((p1, p2, q1, q2))
        # print(p1, p2, q1, q2)

    # TODO check for intersections across 2 edges! use computed intersection

    return True


def has_clockwise_numbering(coords):
    # approach: when numbering is clockwise:
    # at least the majority of averaged points of all consequent point triplets lie...
    #  ... inside the polygon when the second point is an extremity
    #  ... else outside

    threshold = round(len(coords) / 2)
    positive_tests = 0

    p1 = coords[-2]
    p2 = coords[-1]
    for p3 in coords:
        x, y = (p1 + p2 + p3) / 3.0
        result = inside_polygon(x, y, np.array([p1, p2, p3]), border_value=True)
        if (AngleRepresentation(p3 - p2).value - AngleRepresentation(p1 - p2).value) % 4.0 <= 2.0:
            # p2 would be considered to be an extremity if the numbering was correct
            if result:
                positive_tests += 1
                if positive_tests >= threshold:
                    return True
        elif not result:
            positive_tests += 1
            if positive_tests >= threshold:
                return True

        p1 = p2
        p2 = p3

    return False


def check_data_requirements(boundary_coords, list_hole_coords):
    # TODO test
    # todo - polygons must not intersect each other
    """
    ensure that all the following conditions on the polygons are fulfilled:
        - must at least contain 3 vertices
        - no consequent vertices with identical coordinates in the polygons! In general might have the same coordinates
        - a polygon must not have self intersections (intersections with other polygons are allowed)
        - edge numbering has to follow this convention (for easier computations):
            * outer boundary polygon: counter clockwise
            * holes: clockwise
    :param boundary_coords:
    :param list_hole_coords:
    :return:
    """

    assert boundary_coords.shape[0] >= 3
    assert boundary_coords.shape[1] == 2
    assert no_identical_consequent_vertices(boundary_coords)
    assert no_self_intersection(boundary_coords)
    assert not has_clockwise_numbering(boundary_coords)

    for hole_coords in list_hole_coords:
        assert hole_coords.shape[0] >= 3
        assert hole_coords.shape[1] == 2
        assert no_identical_consequent_vertices(hole_coords)
        assert no_self_intersection(hole_coords)
        assert has_clockwise_numbering(hole_coords)

    # TODO rectification


def find_within_range(repr1, repr2, repr_diff, vertex_set, angle_range_less_180, equal_repr_allowed):
    """
    filters out all vertices whose representation lies within the range between
      the two given angle representations
    which range ('clockwise' or 'counter-clockwise') should be checked is determined by:
      - query angle (range) is < 180deg or not (>= 180deg)
    :param repr1:
    :param repr2:
    :param repr_diff: abs(repr1-repr2)
    :param vertex_set:
    :param angle_range_less_180: whether the angle between repr1 and repr2 is < 180 deg
    :param equal_repr_allowed: whether vertices with the same representation should also be returned
    :return:
    """

    if len(vertex_set) == 0:
        return vertex_set

    if repr_diff == 0.0:
        return set()

    min_repr_val = min(repr1, repr2)
    max_repr_val = max(repr1, repr2)  # = min_angle + angle_diff

    def lies_within(vertex):
        # vertices with the same representation will not NOT be returned!
        return min_repr_val < vertex.get_angle_representation() < max_repr_val

    def lies_within_eq(vertex):
        # vertices with the same representation will be returned!
        return min_repr_val <= vertex.get_angle_representation() <= max_repr_val

    # when the range contains the 0.0 value (transition from 3.99... -> 0.0)
    # it is easier to check if a representation does NOT lie within this range
    # -> filter_fct = not_within
    def not_within(vertex):
        # vertices with the same representation will NOT be returned!
        return not (min_repr_val <= vertex.get_angle_representation() <= max_repr_val)

    def not_within_eq(vertex):
        # vertices with the same representation will be returned!
        return not (min_repr_val < vertex.get_angle_representation() < max_repr_val)

    if equal_repr_allowed:
        lies_within_fct = lies_within_eq
        not_within_fct = not_within_eq
    else:
        lies_within_fct = lies_within
        not_within_fct = not_within

    if repr_diff < 2.0:
        # angle < 180 deg
        if angle_range_less_180:
            filter_fct = lies_within_fct
        else:
            # the actual range to search is from min_val to max_val, but clockwise!
            filter_fct = not_within_fct

    elif repr_diff == 2.0:
        # angle == 180deg
        # which range to filter is determined by the order of the points
        # since the polygons follow a numbering convention,
        # the 'left' side of p1-p2 always lies inside the map
        # -> filter out everything on the right side (='outside')
        if repr1 < repr2:
            filter_fct = lies_within_fct
        else:
            filter_fct = not_within_fct

    else:
        # angle > 180deg
        if angle_range_less_180:
            filter_fct = not_within_fct
        else:
            filter_fct = lies_within_fct

    return set(filter(filter_fct, vertex_set))


def convert_gridworld(size_x: int, size_y: int, obstacle_iter: iter, simplify: bool = True) -> (list, list):
    """
    prerequisites: grid world must not have non-obstacle cells which are surrounded by obstacles
    ("single white cell in black surrounding" = useless for path planning)
    :param size_x: the horizontal grid world size
    :param size_y: the vertical grid world size
    :param obstacle_iter: an iterable of coordinate pairs (x,y) representing blocked grid cells (obstacles)
    :param simplify: whether the polygons should be simplified or not. reduces edge amount, allow diagonal edges
    :return: an boundary polygon (counter clockwise numbering) and a list of hole polygons (clockwise numbering)
    NOTE: convert grid world into polygons in a way that coordinates coincide with grid!
        -> no conversion of obtained graphs needed!
        the origin of the polygon coordinate system is (-0.5,-0.5) in the grid cell system (= corners of the grid world)
    """

    assert size_x > 0 and size_y > 0

    if len(obstacle_iter) == 0:
        # there are no obstacles. return just the simple boundary rectangle
        return [np.array(x, y) for x, y in [(0, 0), (size_x, 0), (size_x, size_y), (0, size_y)]], []

    # convert (x,y) into np.arrays
    # obstacle_iter = [np.array(o) for o in obstacle_iter]
    obstacle_iter = np.array(obstacle_iter)

    def within_grid(pos):
        return 0 <= pos[0] < size_x and 0 <= pos[1] < size_y

    def is_equal(pos1, pos2):
        return np.all(pos1 == pos2)

    def pos_in_iter(pos, iter):
        for i in iter:
            if is_equal(pos, i):
                return True
        return False

    def is_obstacle(pos):
        return pos_in_iter(pos, obstacle_iter)

    def is_blocked(pos):
        return not within_grid(pos) or is_obstacle(pos)

    def is_unblocked(pos):
        return within_grid(pos) and not is_obstacle(pos)

    def find_start(start_pos, boundary_detect_fct, **kwargs):
        # returns the lowest and leftmost unblocked grid cell from the start position
        # for which the detection function evaluates to True
        start_x, start_y = start_pos
        for y in range(start_y, size_y):
            for x in range(start_x, size_x):
                pos = np.array([x, y])
                if boundary_detect_fct(pos, **kwargs):
                    return pos

    # north, east, south, west
    directions = np.array([[0, 1], [1, 0], [0, -1], [-1, 0]], dtype=int)
    # the correct offset to determine where nodes should be added.
    offsets = np.array([[0, 1], [1, 1], [1, 0], [0, 0]], dtype=int)

    def construct_polygon(start_pos, boundary_detect_fct, cntr_clockwise_wanted: bool):
        current_pos = start_pos.copy()
        # (at least) the west and south are blocked
        #   -> there has to be a polygon node at the current position (bottom left corner of the cell)
        edge_list = [start_pos]
        forward_index = 0  # start with moving north
        forward_vect = directions[forward_index]
        left_index = (forward_index - 1) % 4
        # left_vect = directions[(forward_index - 1) % 4]
        just_turned = True

        # follow the border between obstacles and free cells ("wall") until one reaches the start position again
        while 1:
            # left has to be checked first
            # do not check if just turned left or right (-> the left is blocked for sure)
            # left_pos = current_pos + left_vect
            if not (just_turned or boundary_detect_fct(current_pos + directions[left_index])):
                # print('< turn left')
                forward_index = left_index
                left_index = (forward_index - 1) % 4
                forward_vect = directions[forward_index]
                just_turned = True

                # add a new node at the correct position
                # decrease the index first!
                edge_list.append(current_pos + offsets[forward_index])

                # move forward (previously left, there is no obstacle)
                current_pos += forward_vect
            else:
                forward_pos = current_pos + forward_vect
                if boundary_detect_fct(forward_pos):
                    node_pos = current_pos + offsets[forward_index]
                    # there is a node at the bottom left corner of the start position (offset= (0,0) )
                    if is_equal(node_pos, start_pos):
                        # check and terminate if this node does already exist
                        break

                    # add a new node at the correct position
                    edge_list.append(node_pos)
                    # print('> turn right')
                    left_index = forward_index
                    forward_index = (forward_index + 1) % 4
                    forward_vect = directions[forward_index]
                    just_turned = True
                    # print(direction_index,forward_vect,just_turned,edge_list,)
                else:
                    # print('^ move forward')
                    current_pos += forward_vect
                    just_turned = False

        if cntr_clockwise_wanted:
            # make edge numbering counter clockwise!
            edge_list.reverse()
        return np.array(edge_list)

    # build the boundary polygon
    # start at the lowest and leftmost unblocked grid cell
    start_pos = find_start(start_pos=(0, 0), boundary_detect_fct=is_unblocked)
    # print(start_pos+directions[3])
    # raise ValueError
    boundary_edges = construct_polygon(start_pos, boundary_detect_fct=is_blocked, cntr_clockwise_wanted=True)

    if simplify:
        # TODO simplify
        pass

    # detect which of the obstacles have to be converted into holes
    # just the obstacles inside the boundary polygon are part of holes
    # shift coordinates by +(0.5,0.5) for correct detection
    # the border value does not matter here
    unchecked_obstacles = [o for o in obstacle_iter if
                           inside_polygon(o[0] + 0.5, o[1] + 0.5, boundary_edges, border_value=True)]

    hole_list = []
    while len(unchecked_obstacles) > 0:
        start_pos = find_start(start_pos=(0, 0), boundary_detect_fct=pos_in_iter, iter=unchecked_obstacles)
        hole = construct_polygon(start_pos, boundary_detect_fct=is_unblocked, cntr_clockwise_wanted=False)

        # detect which of the obstacles still do not belong to any hole:
        # delete the obstacles which are included in the just constructed hole
        unchecked_obstacles = [o for o in unchecked_obstacles if
                               not inside_polygon(o[0] + 0.5, o[1] + 0.5, hole, border_value=True)]

        if simplify:
            # TODO simplify
            pass

        hole_list.append(hole)

    return boundary_edges, hole_list
