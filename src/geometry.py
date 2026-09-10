# Pure geometry shared by rendering and regression tests.
def node_dimensions(cell):
    return max(7.0, cell * .78), max(5.0, cell * .56)


def wire_endpoints(source, target, cell, origin=(0, 0)):
    dx, dy = target[0] - source[0], target[1] - source[1]
    if abs(dx) + abs(dy) != 1:
        return None
    sx = origin[0] + (source[0] + 0.5) * cell
    sy = origin[1] + (source[1] + 0.5) * cell
    tx = origin[0] + (target[0] + 0.5) * cell
    ty = origin[1] + (target[1] + 0.5) * cell
    node_w, node_h = node_dimensions(cell)
    half_w, half_h = node_w / 2, node_h / 2
    return ((sx + dx * half_w, sy + dy * half_h),
            (tx - dx * half_w, ty - dy * half_h))


def panel_layout(width, height):
    margin = 12.0
    compact = width < 650
    side = 0.0 if compact else 132.0
    gutter = 12.0 if side else 0.0
    top = 150.0 if compact else 90.0
    cell = max(7.0, math.floor(min((width - 2*margin - 2*side - 2*gutter)/BOARD_W,
                                   (height - top - (180.0 if compact else 160.0))/BOARD_H)))
    bw, bh = cell*BOARD_W, cell*BOARD_H
    return dict(margin=margin, compact=compact, side=side, gutter=gutter, cell=cell,
                board=((width-bw)/2, top, bw, bh))
