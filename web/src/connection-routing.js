// Group by unordered endpoints so both parallel and reverse flows get their own lane.
export function connectionLanes(connections) {
  const groups = new Map();
  for (const edge of connections) {
    const key = JSON.stringify([edge.source, edge.target].sort());
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(edge);
  }
  const lanes = new Map();
  for (const group of groups.values()) {
    group.sort((a, b) => a.id.localeCompare(b.id));
    group.forEach((edge, index) =>
      lanes.set(edge.id, {
        offset: (index - (group.length - 1) / 2) * 48,
        index,
        count: group.length,
        orientation: edge.source < edge.target ? 1 : -1,
      }),
    );
  }
  return lanes;
}

export function facingSides(source, target) {
  const dx = target.x - source.x,
    dy = target.y - source.y;
  return Math.abs(dx) > Math.abs(dy)
    ? dx >= 0
      ? ["right", "left"]
      : ["left", "right"]
    : dy >= 0
      ? ["bottom", "top"]
      : ["top", "bottom"];
}

const normal = { top: [0, -1], bottom: [0, 1], left: [-1, 0], right: [1, 0] };
export function connectionPorts(nodes, connections, lanes) {
  const nodeMap = new Map(nodes.map((n) => [n.id, n]));
  const byNode = new Map(nodes.map((n) => [n.id, []])),
    byEdge = new Map();
  for (const edge of connections) {
    const source = nodeMap.get(edge.source),
      target = nodeMap.get(edge.target);
    if (!source || !target) continue;
    const sides = facingSides(source.position, target.position);
    const handles = {};
    for (const [kind, node, peer, side] of [
      ["source", source, target, sides[0]],
      ["target", target, source, sides[1]],
    ]) {
      const id = kind + "-edge-" + edge.id;
      handles[kind + "Handle"] = id;
      byNode.get(node.id).push({
        id,
        kind,
        side,
        laneIndex: lanes.get(edge.id).index,
        peerCoordinate:
          side === "left" || side === "right"
            ? peer.position.y
            : peer.position.x,
      });
    }
    byEdge.set(edge.id, handles);
  }
  for (const ports of byNode.values()) {
    for (const side of ["top", "bottom", "left", "right"]) {
      const group = ports
        .filter((p) => p.side === side)
        .sort(
          (a, b) =>
            a.peerCoordinate - b.peerCoordinate ||
            a.laneIndex - b.laneIndex ||
            a.id.localeCompare(b.id),
        );
      group.forEach((p, i) => {
        p.percent = 10 + (80 * (i + 0.5)) / group.length;
      });
    }
  }
  return { byNode, byEdge };
}
export function routedPath(
  {
    sourceX: sx,
    sourceY: sy,
    targetX: tx,
    targetY: ty,
    sourcePosition = "bottom",
    targetPosition = "top",
  },
  lane,
) {
  const s = normal[sourcePosition],
    t = normal[targetPosition];
  const horizontal = s[0] !== 0;
  const gap = horizontal ? Math.abs(tx - sx) : Math.abs(ty - sy);
  // Short staggered entry/exit segments keep parallel corners apart. Clamp them
  // to the available gap so a tight layout does not fold back on itself.
  const limit = Math.max(4, gap / 5);
  const sourceStub = Math.min(limit, 18 + lane.index * 8);
  const targetStub = Math.min(limit, 18 + (lane.count - 1 - lane.index) * 8);
  let points, labelX, labelY;
  if (lane.separatedPorts) {
    // Separate attachment points allow straight parallel tracks. Only use a
    // right-angle jog when the two units are not aligned.
    const bendOrder = -Math.sign((tx - sx) * (ty - sy)) || 1;
    const axisShift =
      (lane.index - (lane.count - 1) / 2) *
      Math.min(16, gap / (lane.count + 2)) *
      bendOrder;
    if (horizontal) {
      const middle = (sx + tx) / 2 + axisShift;
      points = [
        [sx, sy],
        [middle, sy],
        [middle, ty],
        [tx, ty],
      ];
      labelX = middle;
      labelY = (sy + ty) / 2;
    } else {
      const middle = (sy + ty) / 2 + axisShift;
      points = [
        [sx, sy],
        [sx, middle],
        [tx, middle],
        [tx, ty],
      ];
      labelX = (sx + tx) / 2;
      labelY =
        sx === tx
          ? (sy + ty) / 2 + (lane.count > 1 ? (lane.index % 2 ? 18 : -18) : 0)
          : middle;
    }
  } else if (horizontal) {
    const outX = sx + s[0] * sourceStub,
      inX = tx + t[0] * targetStub;
    const channelY = (sy + ty) / 2 + lane.offset;
    points = [
      [sx, sy],
      [outX, sy],
      [outX, channelY],
      [inX, channelY],
      [inX, ty],
      [tx, ty],
    ];
    labelX = (outX + inX) / 2;
    labelY = channelY;
  } else {
    const outY = sy + s[1] * sourceStub,
      inY = ty + t[1] * targetStub;
    const channelX = (sx + tx) / 2 + lane.offset;
    points = [
      [sx, sy],
      [sx, outY],
      [channelX, outY],
      [channelX, inY],
      [tx, inY],
      [tx, ty],
    ];
    labelX = channelX;
    const stagger = Math.min(16, Math.abs(inY - outY) / 3);
    labelY =
      (outY + inY) / 2 +
      (lane.count > 1 ? (lane.index % 2 ? stagger : -stagger) : 0);
  }
  const clean = [];
  for (const p of points) {
    if (clean.length && p[0] === clean.at(-1)[0] && p[1] === clean.at(-1)[1])
      continue;
    clean.push(p);
  }
  return {
    path: clean
      .map((p, i) =>
        i === 0
          ? `M ${p[0]},${p[1]}`
          : p[1] === clean[i - 1][1]
            ? `H ${p[0]}`
            : `V ${p[1]}`,
      )
      .join(" "),
    labelX,
    labelY,
    labelAnchor:
      !horizontal && lane.count > 1
        ? lane.index % 2 === 0
          ? "left"
          : "right"
        : "center",
  };
}
