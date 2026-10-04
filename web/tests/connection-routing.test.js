import test from "node:test";
import assert from "node:assert/strict";
import {
  connectionLanes,
  routedPath,
  facingSides,
  connectionPorts,
} from "../src/connection-routing.js";

test("parallel flows use distinct stable lanes even after list reorder", () => {
  const edges = [
    { id: "lvds", source: "A", target: "B" },
    { id: "rs422", source: "A", target: "B" },
  ];
  const lanes = connectionLanes(edges),
    reversed = connectionLanes([...edges].reverse());
  assert.notEqual(lanes.get("lvds").offset, lanes.get("rs422").offset);
  assert.deepEqual(lanes, reversed);
  const geometry = { sourceX: 100, sourceY: 100, targetX: 100, targetY: 250 };
  const paths = edges.map((e) => routedPath(geometry, lanes.get(e.id)));
  assert.notEqual(paths[0].path, paths[1].path);
  assert.notEqual(paths[0].labelX, paths[1].labelX);
});
test("reverse flows are routed to opposite physical lanes", () => {
  const lanes = connectionLanes([
    { id: "forward", source: "A", target: "B" },
    { id: "reverse", source: "B", target: "A" },
  ]);
  const forward = routedPath(
    { sourceX: 100, sourceY: 100, targetX: 100, targetY: 250 },
    lanes.get("forward"),
  );
  const reverse = routedPath(
    {
      sourceX: 100,
      sourceY: 250,
      targetX: 100,
      targetY: 100,
      sourcePosition: "top",
      targetPosition: "bottom",
    },
    lanes.get("reverse"),
  );
  assert.ok((forward.labelX - 100) * (reverse.labelX - 100) < 0);
  assert.deepEqual(facingSides({ x: 0, y: 200 }, { x: 0, y: 0 }), [
    "top",
    "bottom",
  ]);
});
test("single connections are centered and unrelated pairs have independent lanes", () => {
  const lanes = connectionLanes([
    { id: "a", source: "A", target: "B" },
    { id: "b", source: "C", target: "D" },
  ]);
  assert.equal(lanes.get("a").offset, 0);
  assert.equal(lanes.get("b").count, 1);
  assert.deepEqual(facingSides({ x: 250, y: 0 }, { x: 0, y: 0 }), [
    "left",
    "right",
  ]);
});

test("parallel and reverse flows use matching distinct attachment points", () => {
  const edges = [
    { id: "a", source: "A", target: "B" },
    { id: "b", source: "A", target: "B" },
    { id: "c", source: "B", target: "A" },
  ];
  const nodes = [
    { id: "A", position: { x: 0, y: 0 } },
    { id: "B", position: { x: 500, y: 0 } },
  ];
  const ports = connectionPorts(nodes, edges, connectionLanes(edges));
  assert.equal(new Set(ports.byNode.get("A").map((p) => p.percent)).size, 3);
  for (const edge of edges) {
    const handles = ports.byEdge.get(edge.id);
    const a = ports.byNode
      .get(edge.source)
      .find((p) => p.id === handles.sourceHandle);
    const b = ports.byNode
      .get(edge.target)
      .find((p) => p.id === handles.targetHandle);
    assert.equal(a.percent, b.percent);
  }
});

test("aligned units with separate ports have straight, non-overlapping tracks", () => {
  for (const horizontal of [true, false]) {
    for (const index of [0, 1, 2, 3]) {
      const lane = {
        index,
        count: 4,
        offset: (index - 1.5) * 48,
        separatedPorts: true,
      };
      const route = routedPath(
        horizontal
          ? {
              sourceX: 0,
              sourceY: index * 32,
              targetX: 300,
              targetY: index * 32,
              sourcePosition: "right",
              targetPosition: "left",
            }
          : {
              sourceX: index * 42,
              sourceY: 0,
              targetX: index * 42,
              targetY: 200,
            },
        lane,
      );
      assert.ok(!/[CQASLT]/.test(route.path));
      assert.ok(
        horizontal ? !route.path.includes("V") : !route.path.includes("H"),
        route.path,
      );
    }
  }
});

test("all routes have only horizontal and vertical segments, with exact endpoints", () => {
  for (const positions of [
    ["right", "left", 40, 100, 400, 160],
    ["left", "right", 400, 160, 40, 100],
    ["bottom", "top", 80, 100, 120, 175],
    ["top", "bottom", 120, 175, 80, 100],
  ]) {
    const [sourcePosition, targetPosition, sourceX, sourceY, targetX, targetY] =
      positions;
    for (const index of [0, 1, 2, 3]) {
      const route = routedPath(
        { sourcePosition, targetPosition, sourceX, sourceY, targetX, targetY },
        { index, count: 4, offset: (index - 1.5) * 48 },
      );
      assert.ok(!/[CQASLT]/.test(route.path), route.path);
      assert.ok(route.path.startsWith(`M ${sourceX},${sourceY}`));
      const commands = [
        ...route.path.matchAll(/([MHV]) ([\d.-]+)(?:,([\d.-]+))?/g),
      ];
      let x = sourceX,
        y = sourceY;
      for (const [, cmd, a, b] of commands) {
        if (cmd === "M") {
          x = Number(a);
          y = Number(b);
        } else if (cmd === "H") x = Number(a);
        else y = Number(a);
      }
      assert.equal(x, targetX);
      assert.equal(y, targetY);
      assert.ok(Number.isFinite(route.labelX) && Number.isFinite(route.labelY));
    }
  }
});

test("parallel right-angle routes do not cross each other when units are offset", () => {
  const segments = (path) => {
    const parts = [...path.matchAll(/([MHV]) ([\d.-]+)(?:,([\d.-]+))?/g)];
    let x, y;
    const result = [];
    for (const [, cmd, a, b] of parts) {
      if (cmd === "M") {
        x = Number(a);
        y = Number(b);
        continue;
      }
      const nx = cmd === "H" ? Number(a) : x,
        ny = cmd === "V" ? Number(a) : y;
      if (x !== nx || y !== ny) result.push({ x, y, nx, ny });
      x = nx;
      y = ny;
    }
    return result;
  };
  const crosses = (a, b) => {
    const h = a.y === a.ny ? a : b,
      v = a.y === a.ny ? b : a;
    return (
      h.y === h.ny &&
      v.x === v.nx &&
      v.x > Math.min(h.x, h.nx) &&
      v.x < Math.max(h.x, h.nx) &&
      h.y > Math.min(v.y, v.ny) &&
      h.y < Math.max(v.y, v.ny)
    );
  };
  for (const horizontal of [true, false]) {
    const paths = Array.from({ length: 4 }, (_, i) =>
      segments(
        routedPath(
          horizontal
            ? {
                sourceX: 0,
                sourceY: i * 32,
                targetX: 300,
                targetY: 200 + i * 32,
                sourcePosition: "right",
                targetPosition: "left",
              }
            : {
                sourceX: i * 42,
                sourceY: 0,
                targetX: 200 + i * 42,
                targetY: 300,
              },
          { index: i, count: 4, separatedPorts: true },
        ).path,
      ),
    );
    for (let i = 0; i < paths.length; i++)
      for (let j = i + 1; j < paths.length; j++)
        assert.ok(!paths[i].some((a) => paths[j].some((b) => crosses(a, b))));
  }
});
